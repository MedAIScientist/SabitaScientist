"""Data → annotation → results: CSV numbers, live CVAT progress, CVAT counts as numbers."""

from __future__ import annotations

import httpx

from gazzali import cvat_client

JOBS = {"count": 3, "next": None, "results": [
    {"id": 1, "task_id": 7, "state": "completed", "stage": "annotation", "start_frame": 0, "stop_frame": 9, "assignee": {"username": "ayse"}},
    {"id": 2, "task_id": 7, "state": "in progress", "stage": "annotation", "start_frame": 10, "stop_frame": 19, "assignee": {"username": "mert"}},
    {"id": 3, "task_id": 7, "state": "new", "type": "ground_truth", "start_frame": 0, "stop_frame": 4},
]}
LABELS = {"count": 2, "next": None, "results": [{"id": 11, "name": "fracture"}, {"id": 12, "name": "implant"}]}
ANN = {
    1: {"shapes": [{"label_id": 11, "frame": 0}, {"label_id": 11, "frame": 0}, {"label_id": 12, "frame": 3}], "tags": [], "tracks": []},
    2: {"shapes": [], "tags": [{"label_id": 12, "frame": 12}],
        "tracks": [{"label_id": 11, "shapes": [{"frame": 14, "outside": False}, {"frame": 15, "outside": True}]}]},
}


def _fake_cvat(monkeypatch):
    async def fake_request(method, path, json_body=None):
        if path.startswith("/api/jobs?"):
            return httpx.Response(200, json=JOBS)
        if path.startswith("/api/labels?"):
            return httpx.Response(200, json=LABELS)
        if path.startswith("/api/jobs/"):
            return httpx.Response(200, json=ANN[int(path.split("/")[3])])
        return httpx.Response(404, json={})

    monkeypatch.setattr(cvat_client, "_request", fake_request)


def _setup(client, h):
    pid = client.post("/api/v1/projects", json={"name": "Ankle"}, headers=h).json()["id"]
    exp = client.post(f"/api/v1/projects/{pid}/experiments", json={"name": "E1"}, headers=h).json()["id"]
    cid = client.post(f"/api/v1/projects/{pid}/cvat", json={"cvat_id": 29, "name": "ankle-labels"}, headers=h).json()["id"]
    return pid, exp, cid


def test_csv_preview_saves_nothing_until_asked(client, admin_token) -> None:
    h = {"Authorization": f"Bearer {admin_token}"}
    pid, exp, _ = _setup(client, h)
    url = f"/api/v1/projects/{pid}/experiments/{exp}/metrics"
    csv = "metric,value,unit\nAUC,0.91,\nsensitivity,88,%\n"
    preview = client.post(f"{url}/csv", json={"text": csv}, headers=h).json()
    assert [m["name"] for m in preview["metrics"]] == ["AUC", "sensitivity"]
    assert preview["saved"] == 0
    assert client.get(url, headers=h).json() == []
    assert client.post(f"{url}/csv", json={"text": csv, "save": True}, headers=h).json()["saved"] == 2
    assert {m["source"] for m in client.get(url, headers=h).json()} == {"csv"}


def test_cvat_progress_counts_finished_frames_per_annotator(client, admin_token, monkeypatch) -> None:
    h = {"Authorization": f"Bearer {admin_token}"}
    pid, _, cid = _setup(client, h)
    _fake_cvat(monkeypatch)
    p = client.get(f"/api/v1/projects/{pid}/cvat/{cid}/progress", headers=h).json()
    assert (p["frames_total"], p["frames_done"], p["jobs"], p["jobs_done"]) == (20, 10, 2, 1)
    assert [(a["name"], a["frames_done"]) for a in p["by_assignee"]] == [("ayse", 10), ("mert", 0)]
    assert client.get(f"/api/v1/projects/{pid}/cvat", headers=h).json()[0]["num_images"] == 20


def test_cvat_annotations_become_measured_numbers_and_reimport_replaces(client, admin_token, monkeypatch) -> None:
    h = {"Authorization": f"Bearer {admin_token}"}
    pid, exp, cid = _setup(client, h)
    _fake_cvat(monkeypatch)
    url = f"/api/v1/projects/{pid}/experiments/{exp}/cvat/{cid}/import-metrics"
    r = client.post(url, headers=h).json()
    assert r["summary"]["labels"] == {"fracture": 3, "implant": 2}
    assert r["summary"]["frames_annotated"] == 4  # frames 0, 3, 12, 14
    client.post(url, headers=h)
    got = {m["name"]: (m["value"], m["source"]) for m in client.get(f"/api/v1/projects/{pid}/experiments/{exp}/metrics", headers=h).json()}
    assert got == {
        "images annotated": (4, "cvat"), "images in annotation project": (20, "cvat"),
        "annotations: fracture": (3, "cvat"), "annotations: implant": (2, "cvat"),
    }


def test_paper_context_carries_annotation_lineage_for_methods(client, admin_token, tmp_db, monkeypatch) -> None:
    from gazzali.paper_context import build_paper_context

    h = {"Authorization": f"Bearer {admin_token}"}
    pid, exp, cid = _setup(client, h)
    _fake_cvat(monkeypatch)
    client.post(f"/api/v1/projects/{pid}/experiments/{exp}/assets", json={"asset_type": "cvat_project", "asset_id": cid, "role": "output"}, headers=h)
    client.post(f"/api/v1/projects/{pid}/experiments/{exp}/cvat/{cid}/import-metrics", headers=h)

    data = build_paper_context(tmp_db, pid)["sources"]["data"]
    rec = next(r for r in data if r["id"] == f"cvat_project:{cid}")
    assert "Manual annotation in CVAT" in rec["text"]
    assert "annotated objects: 5" in rec["text"]
    assert "Used by: E1" in rec["text"]
