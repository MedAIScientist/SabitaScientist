"""Semantic Scholar database — connection, schema, and paper lookup."""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

S2_DB_PATH = os.environ.get("S2_DB_PATH", "")

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id                TEXT PRIMARY KEY,                  -- S2PaperId
    title             TEXT NOT NULL,
    authors           TEXT NOT NULL DEFAULT '[]',        -- JSON array of {name, authorId}
    year              INTEGER,
    venue             TEXT,
    abstract          TEXT,
    external_ids      TEXT NOT NULL DEFAULT '{}',        -- JSON: {DOI, ArXiv, MAG, etc}
    citation_count    INTEGER DEFAULT 0,
    reference_count   INTEGER DEFAULT 0,
    influential_citation_count INTEGER DEFAULT 0,
    fields_of_study   TEXT DEFAULT '[]',                 -- JSON array
    publication_types TEXT DEFAULT '[]',                 -- JSON array
    is_open_access    INTEGER DEFAULT 0,
    url               TEXT,
    pdf_url           TEXT,
    created_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_papers_title ON papers(title COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year);
CREATE INDEX IF NOT EXISTS idx_papers_venue ON papers(venue);
CREATE INDEX IF NOT EXISTS idx_papers_fields ON papers(fields_of_study);

CREATE TABLE IF NOT EXISTS paper_references (
    paper_id      TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    reference_id  TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    PRIMARY KEY (paper_id, reference_id)
);

CREATE TABLE IF NOT EXISTS paper_citations (
    paper_id      TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    citation_id   TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    context       TEXT,
    PRIMARY KEY (paper_id, citation_id)
);

CREATE TABLE IF NOT EXISTS authors (
    id        TEXT PRIMARY KEY,                          -- authorId
    name      TEXT NOT NULL,
    aliases   TEXT DEFAULT '[]',                         -- JSON array
    papers    INTEGER DEFAULT 0,                          -- publication count
    citations INTEGER DEFAULT 0,                          -- total citations
    h_index   INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_authors_name ON authors(name COLLATE NOCASE);

PRAGMA foreign_keys = ON;
"""


@dataclass
class Paper:
    id: str
    title: str
    authors: list[dict]
    year: int | None
    venue: str | None
    abstract: str | None
    external_ids: dict
    citation_count: int
    reference_count: int
    influential_citation_count: int
    fields_of_study: list[str]
    publication_types: list[str]
    is_open_access: bool
    url: str | None
    pdf_url: str | None


@dataclass
class PaperAuthor:
    id: str
    name: str
    aliases: list[str]
    papers: int
    citations: int
    h_index: int


def get_s2_db_path() -> str:
    """Return the Semantic Scholar database path from S2_DB_PATH env var.
    Returns empty string if not configured — callers should check."""
    return S2_DB_PATH


def is_available() -> bool:
    """Check if the S2 database is configured and accessible."""
    path = get_s2_db_path()
    if not path:
        return False
    return Path(path).exists()


def create_schema(db_path: str | None = None) -> None:
    """Create the S2 schema if the DB path is set."""
    path = db_path or get_s2_db_path()
    if not path:
        return
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_db(db_path: str | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Yield a connection to the S2 database."""
    path = db_path or get_s2_db_path()
    if not path:
        raise RuntimeError("S2_DB_PATH not configured")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _row_to_paper(row: sqlite3.Row) -> Paper:
    return Paper(
        id=row["id"],
        title=row["title"],
        authors=json.loads(row["authors"]) if isinstance(row["authors"], str) else (row["authors"] or []),
        year=row["year"],
        venue=row["venue"],
        abstract=row["abstract"],
        external_ids=json.loads(row["external_ids"]) if isinstance(row["external_ids"], str) else (row["external_ids"] or {}),
        citation_count=row["citation_count"] or 0,
        reference_count=row["reference_count"] or 0,
        influential_citation_count=row["influential_citation_count"] or 0,
        fields_of_study=json.loads(row["fields_of_study"]) if isinstance(row["fields_of_study"], str) else (row["fields_of_study"] or []),
        publication_types=json.loads(row["publication_types"]) if isinstance(row["publication_types"], str) else (row["publication_types"] or []),
        is_open_access=bool(row["is_open_access"]),
        url=row["url"],
        pdf_url=row["pdf_url"],
    )
