"""Reference verification with canned lookups (no network)."""

from __future__ import annotations

import pytest

from gazzali import citations

ARXIV_OK = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Attention Is All You Need</title></entry></feed>"""


@pytest.fixture
def lookups(monkeypatch):
    def fake_get(url, params=None):
        if "crossref" in url:
            if url.endswith("10.1000/real"):
                return {"message": {"title": ["Deep learning for diabetic retinopathy screening"]}}
            if url.endswith("10.1000/other"):
                return {"message": {"title": ["A completely different paper about soil chemistry"]}}
            return {"__not_found__": True}
        if "arxiv" in url:
            return ARXIV_OK
        if "openalex" in url:
            q = params["search"].lower()
            if "glaucoma" in q:
                return {"results": [{"display_name": "Glaucoma detection from fundus images with CNNs", "doi": "https://doi.org/10.1/g"}]}
            return {"results": [{"display_name": "Unrelated work on graph theory", "doi": None}]}
        if "semanticscholar" in url:
            return {"data": []}
        return None

    monkeypatch.setattr(citations, "_get", fake_get)


def test_extracts_the_reference_list_under_its_heading() -> None:
    text = "# Intro\nSee [1].\n\n## References\n1. A paper. doi:10.1000/real\n- Another one\n\n## Appendix\nx"
    assert citations.extract_references(text) == ["A paper. doi:10.1000/real", "Another one"]


def test_classifies_verified_suspicious_hallucinated(lookups) -> None:
    text = """## References
1. Smith (2023). Deep learning for diabetic retinopathy screening. Ophthalmology. https://doi.org/10.1000/real
2. Doe (2022). Retinal vessel segmentation revisited. https://doi.org/10.1000/other
3. Roe (2021). Imaginary results. doi:10.1000/fake
4. Vaswani et al. Attention is all you need. arXiv:1706.03762
5. Lee (2020). Glaucoma detection from fundus images with CNNs. Eye.
6. Nobody (2019). A paper that does not exist anywhere at all.
"""
    r = citations.verify_text(text)
    assert [x["status"] for x in r["references"]] == [
        "verified", "suspicious", "hallucinated", "verified", "verified", "hallucinated"]
    assert r["counts"] == {"verified": 3, "suspicious": 1, "hallucinated": 2}
    assert r["references"][1]["matched_title"].startswith("A completely different")


def test_route_uses_the_latest_draft(tmp_db, client, admin_token, admin_user, lookups) -> None:
    from gazzali.crud.publications import create_publication, create_version

    pub = create_publication(tmp_db, "P", admin_user.id)
    h = {"Authorization": f"Bearer {admin_token}"}
    assert client.post(f"/api/v1/publications/{pub.id}/references/verify", json={}, headers=h).status_code == 400
    create_version(tmp_db, pub.id, admin_user.id, content="## References\n1. x doi:10.1000/fake\n")
    r = client.post(f"/api/v1/publications/{pub.id}/references/verify", json={}, headers=h)
    assert r.json()["counts"]["hallucinated"] == 1
