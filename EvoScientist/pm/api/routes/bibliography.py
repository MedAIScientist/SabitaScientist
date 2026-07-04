"""Bibliography import — parse citations from text, RIS, BibTeX, or Zotero export."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException

from ...crud.publications import (
    create_publication,
    get_publication,
    list_publications,
)
from ...db import get_db_path
from ...models import User
from ...s2.queries import parse_citation_text, search_by_doi, search_by_title
from ..deps import get_current_user
from ..schemas import BibliographyImportRequest

router = APIRouter()


def _parse_bibtex(text: str) -> list[dict]:
    """Parse BibTeX entries into structured citation dicts."""
    entries = []
    for match in re.finditer(r"@(\w+)\{([^,]+),\s*([^@]+)", text):
        entry_type = match.group(1).lower()
        cite_key = match.group(2).strip()
        body = match.group(3)
        entry = {"cite_key": cite_key, "type": entry_type, "title": "", "authors": [], "year": None,
                 "journal": "", "doi": "", "url": "", "abstract": ""}
        fields = re.findall(r"(\w+)\s*=\s*\{(.*?)\}", body, re.DOTALL)
        for key, val in fields:
            val = val.strip()
            if key == "title":
                entry["title"] = val
            elif key == "author":
                entry["authors"] = [a.strip() for a in val.replace("\n", " ").split(" and ")]
            elif key == "year":
                entry["year"] = int(val) if val.isdigit() else None
            elif key == "journal":
                entry["journal"] = val
            elif key == "doi":
                entry["doi"] = val
            elif key == "url":
                entry["url"] = val
            elif key == "abstract":
                entry["abstract"] = val
        if entry["title"]:
            entries.append(entry)
    return entries


def _parse_ris(text: str) -> list[dict]:
    """Parse RIS format into structured citation dicts."""
    entries = []
    current = {}
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("TY  - "):
            if current.get("title"):
                entries.append(current)
            current = {"type": line[6:].strip().lower(), "title": "", "authors": [],
                       "year": None, "journal": "", "doi": "", "url": "", "abstract": ""}
        elif line.startswith("T1  - ") or line.startswith("TI  - "):
            current["title"] = line[6:].strip()
        elif line.startswith("AU  - "):
            current.setdefault("authors", []).append(line[6:].strip())
        elif line.startswith("PY  - "):
            yr = line[6:].strip()
            current["year"] = int(yr) if yr.isdigit() else None
        elif line.startswith("JO  - ") or line.startswith("JF  - "):
            current["journal"] = line[6:].strip()
        elif line.startswith("DO  - "):
            current["doi"] = line[6:].strip()
        elif line.startswith("UR  - "):
            current["url"] = line[6:].strip()
        elif line.startswith("N2  - ") or line.startswith("AB  - "):
            current["abstract"] = (current.get("abstract", "") + " " + line[6:].strip()).strip()
    if current.get("title"):
        entries.append(current)
    return entries


def _import_citations(
    citations: list[dict],
    project_id: str | None,
    user_id: str,
    db_path: str,
) -> dict:
    """Import a list of citation dicts into publications."""
    imported = 0
    skipped = 0
    results = []
    for cit in citations:
        title = cit.get("title", "").strip()
        if not title or len(title) < 5:
            skipped += 1
            continue

        existing = list_publications(db_path)
        if any(p.title.lower() == title.lower() for p in existing):
            skipped += 1
            results.append({"title": title, "status": "skipped", "reason": "already exists"})
            continue

        doi = cit.get("doi", "")
        pub = create_publication(
            db_path,
            title=title,
            created_by=user_id,
            project_id=project_id,
            venue=cit.get("journal", ""),
            doi=doi or None,
            abstract=cit.get("abstract", "") or None,
        )
        imported += 1
        results.append({"title": title, "status": "imported", "id": pub.id})
    return {"imported": imported, "skipped": skipped, "results": results}


@router.post("/bibliography/import-text")
def import_bibliography_text(
    body: BibliographyImportRequest,
    current_user: User = Depends(get_current_user),
):
    """Import bibliography from plain text, BibTeX, or RIS format."""
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "No text provided")

    citations = []
    if text.startswith("@") and "{" in text:
        citations = _parse_bibtex(text)
    elif text.startswith("TY  - "):
        citations = _parse_ris(text)
    else:
        parsed = parse_citation_text(text)
        for p in parsed:
            doi = p.get("doi_guess")
            paper = search_by_doi(doi) if doi else None
            if not paper and p.get("title_guess"):
                matches = search_by_title(p["title_guess"], limit=1)
                paper = matches[0] if matches else None
            citations.append({
                "title": paper.title if paper else p.get("raw_text", "")[:200],
                "doi": paper.external_ids.get("DOI", "") if paper and paper.external_ids else "",
                "journal": paper.venue if paper else "",
                "authors": [a.get("name", "") for a in (paper.authors or [])] if paper else [],
                "year": paper.year if paper else None,
                "abstract": (paper.abstract or "")[:500] if paper else "",
            })

    result = _import_citations(
        citations,
        project_id=body.project_id,
        user_id=current_user.id,
        db_path=get_db_path(),
    )
    return result


@router.get("/bibliography/export/{pub_id}/bibtex")
def export_bibtex(pub_id: str, current_user: User = Depends(get_current_user)):
    """Export a single publication as BibTeX."""
    db = get_db_path()
    pub = get_publication(db, pub_id)
    if not pub:
        raise HTTPException(404, "Publication not found")
    cite_key = re.sub(r"[^a-zA-Z0-9]", "", pub.title[:40].replace(" ", ""))
    authors = "; ".join(a.get("name", "") for a in pub.authors) if pub.authors else ""
    bib = f"@article{{{cite_key},\n"
    bib += f"  title = {{{pub.title}}},\n"
    if authors:
        bib += f"  author = {{{authors}}},\n"
    if pub.venue:
        bib += f"  journal = {{{pub.venue}}},\n"
    if pub.doi:
        bib += f"  doi = {{{pub.doi}}},\n"
    if pub.abstract:
        bib += f"  abstract = {{{pub.abstract[:300]}}},\n"
    bib += "}"
    return {"bibtex": bib, "filename": f"{cite_key}.bib"}
