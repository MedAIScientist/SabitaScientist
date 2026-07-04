"""Semantic Scholar paper lookup — search by title, DOI, author, or ID."""

from __future__ import annotations

import json
import re

from .db import Paper, _row_to_paper, get_db, get_s2_db_path, is_available


def search_by_title(title: str, limit: int = 5) -> list[Paper]:
    """Search papers by title (fuzzy LIKE match)."""
    if not is_available():
        return []
    db_path = get_s2_db_path()
    results: list[Paper] = []
    with get_db(db_path) as conn:
        # Exact match first
        rows = conn.execute(
            "SELECT * FROM papers WHERE title = ? ORDER BY citation_count DESC LIMIT ?",
            (title, limit),
        ).fetchall()
        results.extend(_row_to_paper(r) for r in rows)

        if len(results) < limit:
            # Fuzzy match
            fuzzy = f"%{title}%"
            existing_ids = {r.id for r in results}
            rows = conn.execute(
                "SELECT * FROM papers WHERE title LIKE ? AND id NOT IN ({}) ORDER BY citation_count DESC LIMIT ?".format(
                    ",".join("?" for _ in existing_ids) if existing_ids else "''"
                ),
                [fuzzy] + (list(existing_ids) if existing_ids else []) + [limit - len(results)],
            ).fetchall()
            results.extend(_row_to_paper(r) for r in rows)

    return results


def search_by_doi(doi: str) -> Paper | None:
    """Find a paper by its DOI (looks in external_ids JSON)."""
    if not is_available():
        return None
    db_path = get_s2_db_path()
    # Normalize DOI
    doi = doi.lower().strip()
    doi = doi.removeprefix("doi:")
    with get_db(db_path) as conn:
        rows = conn.execute("SELECT * FROM papers").fetchall()
        for row in rows:
            ext_ids = json.loads(row["external_ids"]) if isinstance(row["external_ids"], str) else {}
            ext_doi = (ext_ids.get("DOI") or "").lower().strip()
            if ext_doi and (ext_doi == doi or ext_doi.endswith(f"/{doi}")):
                return _row_to_paper(row)
    return None


def search_by_arxiv(arxiv_id: str) -> Paper | None:
    """Find a paper by ArXiv ID."""
    if not is_available():
        return None
    db_path = get_s2_db_path()
    arxiv_id = arxiv_id.strip().lower()
    arxiv_id = arxiv_id.removeprefix("arxiv:")
    with get_db(db_path) as conn:
        rows = conn.execute("SELECT * FROM papers").fetchall()
        for row in rows:
            ext_ids = json.loads(row["external_ids"]) if isinstance(row["external_ids"], str) else {}
            ext_arxiv = (ext_ids.get("ArXiv") or "").lower().strip()
            if ext_arxiv == arxiv_id or ext_arxiv.endswith(f"/{arxiv_id}"):
                return _row_to_paper(row)
    return None


def search_by_paper_id(s2_id: str) -> Paper | None:
    """Find a paper by its Semantic Scholar ID."""
    if not is_available():
        return None
    db_path = get_s2_db_path()
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM papers WHERE id = ?", (s2_id,)
        ).fetchone()
    return _row_to_paper(row) if row else None


def get_references(paper_id: str, limit: int = 50) -> list[Paper]:
    """Get references (bibliography) of a paper."""
    if not is_available():
        return []
    db_path = get_s2_db_path()
    results: list[Paper] = []
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT p.* FROM papers p
               JOIN paper_references pr ON p.id = pr.reference_id
               WHERE pr.paper_id = ?
               ORDER BY p.citation_count DESC LIMIT ?""",
            (paper_id, limit),
        ).fetchall()
        results.extend(_row_to_paper(r) for r in rows)
    return results


def get_citations(paper_id: str, limit: int = 50) -> list[Paper]:
    """Get papers that cite this paper."""
    if not is_available():
        return []
    db_path = get_s2_db_path()
    results: list[Paper] = []
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT p.* FROM papers p
               JOIN paper_citations pc ON p.id = pc.citation_id
               WHERE pc.paper_id = ?
               ORDER BY p.citation_count DESC LIMIT ?""",
            (paper_id, limit),
        ).fetchall()
        results.extend(_row_to_paper(r) for r in rows)
    return results


def parse_citation_text(text: str) -> list[dict]:
    """Parse a citation text block into structured entries.

    Handles common formats: [1] Author (Year), [2] Author et al., etc.
    Returns list of {raw_text, title_guess, author_guess, year_guess, doi_guess}
    """
    entries = []
    # Split by common delimiters
    lines = re.split(r'\n|(?=\[\d+\])|(?=\d+\.\s)', text.strip())

    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue

        entry = {"raw_text": line}

        # Try to extract DOI
        doi_match = re.search(r'(10\.\d{4,}/[^\s,;]+)', line)
        if doi_match:
            entry["doi_guess"] = doi_match.group(1).rstrip('.')

        # Try to extract year
        year_match = re.search(r'\((\d{4})\)', line)
        if year_match:
            entry["year_guess"] = int(year_match.group(1))

        # Try to extract first author
        author_match = re.match(r'[\[\(]?\d*[\]\)]?\s*([A-Z][a-zà-ü]+(?:\s(?:et\s+al\.?|and\s+[A-Z][a-z]+))?)', line)
        if author_match:
            entry["author_guess"] = author_match.group(1).strip()

        entries.append(entry)

    return entries


def verify_citations(citation_text: str) -> dict:
    """Verify citations against the Semantic Scholar database.

    Returns structured results: found papers, unmatched entries, and statistics.
    """
    if not is_available():
        return {"available": False, "message": "Semantic Scholar database not configured. Set S2_DB_PATH env var."}

    entries = parse_citation_text(citation_text)
    results = []
    found_count = 0
    suspicious_count = 0

    for entry in entries:
        result = {
            "raw_text": entry["raw_text"],
            "status": "unmatched",
            "matches": [],
            "flags": [],
        }

        # Try DOI first (most reliable)
        if entry.get("doi_guess"):
            paper = search_by_doi(entry["doi_guess"])
            if paper:
                result["status"] = "verified"
                result["matches"].append(_paper_to_verification(paper))
                found_count += 1
                continue

        # Try title search
        title_guess = entry["raw_text"]
        # Remove numbering and brackets
        title_guess = re.sub(r'^[\[\(]?\d+[\]\)]?\s*', '', title_guess)
        # Remove author prefix
        title_guess = re.sub(r'^[A-Z][a-z]+.*?\(\d{4}\)\.?\s*', '', title_guess)
        # Take first 80 chars as title candidate
        title_candidate = title_guess[:100].rstrip('.')

        if len(title_candidate) > 15:
            papers = search_by_title(title_candidate, limit=3)
            if papers:
                result["status"] = "verified"
                result["matches"] = [_paper_to_verification(p) for p in papers]
                found_count += 1

                # Flag low citation counts
                top = papers[0]
                if top.citation_count == 0 and top.year and top.year > 2018:
                    pass  # Recent papers may have 0 citations
                elif top.citation_count is not None and top.citation_count < 5 and top.year and top.year < 2020:
                    result["flags"].append(f"Low citations ({top.citation_count}) for a {top.year} paper")
                    suspicious_count += 1
                continue

        # No match found
        result["status"] = "not_found"
        suspicious_count += 1
        result["flags"].append("Could not find in Semantic Scholar database")
        results.append(result)

    return {
        "available": True,
        "total_citations": len(entries),
        "verified": found_count,
        "suspicious": suspicious_count,
        "not_found": len(entries) - found_count,
        "results": results,
    }


def _paper_to_verification(p: Paper) -> dict:
    """Convert a Paper to a verification result dict."""
    return {
        "s2_id": p.id,
        "title": p.title,
        "year": p.year,
        "venue": p.venue,
        "citation_count": p.citation_count,
        "influential_citation_count": p.influential_citation_count,
        "authors": [a.get("name", "") for a in (p.authors or [])],
        "doi": p.external_ids.get("DOI", "") if p.external_ids else "",
        "arxiv": p.external_ids.get("ArXiv", "") if p.external_ids else "",
        "fields_of_study": p.fields_of_study,
        "is_open_access": p.is_open_access,
    }
