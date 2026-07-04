"""Tests for Semantic Scholar query module (works without a database)."""
from EvoScientist.pm.s2.queries import is_available, parse_citation_text, verify_citations


def test_is_available_returns_false_without_db():
    assert is_available() is False


def test_verify_citations_graceful_without_db():
    result = verify_citations("Some citation text here (2020)")
    assert result.get("available") is False
    assert "not configured" in result.get("message", "").lower()


def test_parse_citation_text_simple():
    text = "[1] Smith et al. (2020) A study of something. Journal of Science."
    entries = parse_citation_text(text)
    assert len(entries) >= 1
    assert entries[0]["raw_text"] == text
    assert entries[0]["year_guess"] == 2020
    assert "Smith" in entries[0].get("author_guess", "")


def test_parse_citation_text_with_doi():
    text = "Zhang et al. (2021) Deep learning methods. Nature. doi:10.1038/s41586-021-12345-6"
    entries = parse_citation_text(text)
    assert len(entries) >= 1
    assert entries[0]["doi_guess"] is not None
    assert "10.1038" in entries[0]["doi_guess"]


def test_parse_citation_text_multiple_entries():
    text = """[1] First Author (2020) First paper title.
[2] Second Author (2021) Second paper title."""
    entries = parse_citation_text(text)
    assert len(entries) >= 2


def test_parse_citation_text_empty():
    assert parse_citation_text("") == []
    assert parse_citation_text("   ") == []
