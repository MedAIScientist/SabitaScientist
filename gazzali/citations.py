"""Reference verification (paper arXiv:2605.20025 §3.4): Verified / Suspicious / Hallucinated.

Each reference is looked up by its identifier first (DOI → CrossRef, arXiv id →
arXiv, PMC id → NCBI), then by text (OpenAlex, then Semantic Scholar). The found
title must appear in the reference: an identifier that resolves to a different
paper is the classic hallucination pattern and is reported as Suspicious.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MAX_REFERENCES = 60
VERIFIED, SUSPICIOUS = 0.8, 0.5
_UA = {"User-Agent": "Gazzali/1.0 (mailto:noreply@gazzali.local)"}

_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>)\]]+)", re.IGNORECASE)
_ARXIV = re.compile(r"(?:arxiv[:./\s]*(?:abs/)?)(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
_PMC = re.compile(r"pmc/articles/(?:PMC)?(\d{5,9})", re.IGNORECASE)
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(references|bibliography|sources|kaynakça)\b", re.IGNORECASE)
_ANY_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
_BIB_TITLE = re.compile(r"title\s*=\s*[{\"](.+?)[}\"]\s*,?\s*$", re.IGNORECASE | re.MULTILINE)


def _get(url: str, params: dict | None = None) -> Any:
    """GET JSON (or text for XML); None on any failure. Tests replace this."""
    try:
        r = httpx.get(url, params=params, headers=_UA, timeout=15, follow_redirects=True)
    except httpx.HTTPError as exc:
        logger.info("lookup failed %s: %s", url, exc)
        return None
    if r.status_code == 404:
        return {"__not_found__": True}
    if r.status_code >= 400:
        return None
    return r.json() if "json" in r.headers.get("content-type", "") else r.text


def extract_references(text: str) -> list[str]:
    """Reference entries: the lines under a References heading, BibTeX titles, or DOI lines."""
    if "@" in text and _BIB_TITLE.search(text):
        return [m.group(1).strip() for m in _BIB_TITLE.finditer(text)][:MAX_REFERENCES]
    refs: list[str] = []
    inside = False
    for line in text.splitlines():
        if _HEADING.match(line):
            inside = True
            continue
        if inside and _ANY_HEADING.match(line):
            break
        if inside and line.strip():
            refs.append(re.sub(r"^\s*(?:[-*]|\[\d+\]|\d+\.)\s*", "", line).strip())
    if not refs:
        refs = [line.strip() for line in text.splitlines() if _DOI.search(line)]
    return refs[:MAX_REFERENCES]


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if len(t) > 2}


def overlap(title: str, reference: str) -> float:
    """Share of the found title's words that appear in the reference."""
    t = _tokens(title)
    return len(t & _tokens(reference)) / len(t) if t else 0.0


def _result(ref: str, status: str, title: str | None = None, url: str | None = None, source: str | None = None) -> dict:
    return {"reference": ref, "status": status, "matched_title": title, "url": url, "source": source}


def _by_doi(ref: str, doi: str) -> dict | None:
    data = _get(f"https://api.crossref.org/works/{doi}")
    if data is None:
        return None
    if data.get("__not_found__"):
        return _result(ref, "hallucinated", source="CrossRef: DOI does not exist")
    title = ((data.get("message") or {}).get("title") or [""])[0]
    return _result(ref, "verified" if overlap(title, ref) >= VERIFIED else "suspicious", title, f"https://doi.org/{doi}", "CrossRef")


def _by_arxiv(ref: str, arxiv_id: str) -> dict | None:
    xml = _get("https://export.arxiv.org/api/query", {"id_list": arxiv_id})
    if not isinstance(xml, str):
        return None
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entry = ET.fromstring(xml).find("a:entry", ns)
    title = entry.findtext("a:title", default="", namespaces=ns) if entry is not None else ""
    if not title or "error" in title.lower():
        return _result(ref, "hallucinated", source="arXiv: id does not exist")
    title = " ".join(title.split())
    return _result(ref, "verified" if overlap(title, ref) >= VERIFIED else "suspicious", title, f"https://arxiv.org/abs/{arxiv_id}", "arXiv")


def _by_pmc(ref: str, pmc: str) -> dict | None:
    data = _get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi", {"db": "pmc", "retmode": "json", "id": pmc})
    rec = ((data or {}).get("result") or {}).get(pmc) if isinstance(data, dict) else None
    if not rec:
        return None
    if rec.get("error"):
        return _result(ref, "hallucinated", source="PubMed Central: id does not exist")
    title = rec.get("title", "")
    return _result(ref, "verified" if overlap(title, ref) >= VERIFIED else "suspicious", title,
                   f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc}/", "PubMed Central")


def _by_search(ref: str) -> dict:
    query = re.sub(r"https?://\S+", "", ref)[:300]
    best: dict | None = None
    data = _get("https://api.openalex.org/works", {"search": query, "per-page": 3})
    for w in (data or {}).get("results", []) if isinstance(data, dict) else []:
        cand = _result(ref, "", w.get("display_name") or "", w.get("doi") or w.get("id"), "OpenAlex")
        cand["score"] = overlap(cand["matched_title"], ref)
        best = cand if best is None or cand["score"] > best["score"] else best
    if best is None or best["score"] < VERIFIED:
        data = _get("https://api.semanticscholar.org/graph/v1/paper/search",
                    {"query": query, "limit": 3, "fields": "title,externalIds,url"})
        for p in (data or {}).get("data", []) if isinstance(data, dict) else []:
            cand = _result(ref, "", p.get("title") or "", p.get("url"), "Semantic Scholar")
            cand["score"] = overlap(cand["matched_title"], ref)
            best = cand if best is None or cand["score"] > best["score"] else best
    if best is None or best["score"] < SUSPICIOUS:
        return _result(ref, "hallucinated", best["matched_title"] if best else None, None, "no matching paper found")
    best["status"] = "verified" if best["score"] >= VERIFIED else "suspicious"
    best.pop("score")
    return best


def verify_reference(ref: str) -> dict:
    for pattern, lookup in ((_DOI, _by_doi), (_ARXIV, _by_arxiv), (_PMC, _by_pmc)):
        m = pattern.search(ref)
        if m:
            found = lookup(ref, m.group(1).rstrip(".,;"))
            if found is not None:
                return found
    return _by_search(ref)


def verify_text(text: str) -> dict:
    refs = extract_references(text)
    results = [verify_reference(r) for r in refs]
    counts = {s: sum(1 for r in results if r["status"] == s) for s in ("verified", "suspicious", "hallucinated")}
    return {"references": results, "counts": counts}
