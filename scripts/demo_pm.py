#!/usr/bin/env python3
"""
Gazzali — Full-Lifecycle Demo Script.

Walks through the entire research workflow:
  Setup → Login → Lab → Project (from template) → Tasks → Experiments →
  AI Tools → Publication → AI Drafting → Grant Proposal → Impact Dashboard

Usage:
  python scripts/demo_pm.py                    # localhost:7860, creates demo admin
  python scripts/demo_pm.py --url https://pm.myuni.edu --username pi --password s3cret

Requires: httpx (``pip install httpx`` or already in ``uv sync``)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from typing import Any

try:
    import httpx
except ImportError:
    print("pip install httpx"); sys.exit(1)

BASE: str = ""
TOKEN: str = ""
CLIENT: httpx.Client | None = None


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    return h


def _req(method: str, path: str, **kw) -> httpx.Response:
    url = f"{BASE}{path}"
    kw.setdefault("headers", _headers())
    kw.setdefault("timeout", 30)
    r = CLIENT.request(method, url, **kw)
    if r.status_code >= 400:
        detail = r.text[:300]
        print(f"  ✗ {method} {path} → {r.status_code}: {detail}")
    return r


def _ok(method: str, path: str, **kw) -> dict | list | None:
    r = _req(method, path, **kw)
    if r.status_code >= 400:
        return None
    if r.status_code == 204:
        return None
    ct = r.headers.get("content-type", "")
    if "json" in ct:
        return r.json()
    return {"raw": r.text[:200]}


def _step(num: int, label: str) -> None:
    print(f"\n{'='*70}")
    print(f"  Step {num}: {label}")
    print(f"{'='*70}")


def _wait(secs: float = 0.5) -> None:
    time.sleep(secs)


# ── Demo ──────────────────────────────────────────────────────────────────────

def run(base_url: str, admin_user: str, admin_pass: str) -> None:
    global BASE, TOKEN, CLIENT
    BASE = base_url.rstrip("/") + "/api/v1"
    CLIENT = httpx.Client(verify=False)

    print(f"\n  Gazzali Demo")
    print(f"  Target: {BASE}")
    print(f"  Admin:  {admin_user}\n")

    # ── Step 1: Health check ──────────────────────────────────────────────
    _step(1, "System Health")
    r = _req("GET", "/health")
    if r.status_code == 200:
        print("  ✓ API is running")
    else:
        print(f"  ✗ API not reachable at {BASE}/health"); sys.exit(1)

    # ── Step 2: Setup check & bootstrap ──────────────────────────────────
    _step(2, "Admin Setup")
    r = _req("GET", "/users/setup/status")
    if r.status_code == 200 and r.json().get("needs_setup"):
        print("  First-run detected — bootstrapping admin...")
        r2 = _req("POST", "/users/setup/admin", json={
            "username": admin_user, "password": admin_pass, "email": "demo@gazzali.local",
        })
        if r2.status_code == 201:
            print(f"  ✓ Admin '{admin_user}' created")
        else:
            print(f"  ⚠ Setup may already be done: {r2.status_code}")
    else:
        print("  ✓ Setup already complete")

    # ── Step 3: Login ────────────────────────────────────────────────────
    _step(3, "Login")
    r = _req("POST", "/auth/login", json={"username": admin_user, "password": admin_pass})
    if r.status_code != 200:
        print("  ✗ Login failed — try different credentials"); sys.exit(1)
    data: dict = r.json()
    TOKEN = data["token"]
    print(f"  ✓ Logged in as '{data['username']}' (admin={data['is_admin']})")

    # ── Step 4: List templates ────────────────────────────────────────────
    _step(4, "Project Templates")
    r = _req("GET", "/templates")
    if r.status_code == 200:
        templates = r.json()
        for t in templates:
            phases = len(t.get("phases", []))
            tasks = len(t.get("tasks", []))
            print(f"    · {t['name']} ({t.get('domain','?')}) — {phases} phases, {tasks} pre-built tasks")
    else:
        templates = []

    # ── Step 5: Create lab ────────────────────────────────────────────────
    _step(5, "Create Lab")
    lab_name = f"Demo Computational Lab {uuid.uuid4().hex[:6]}"
    r = _req("POST", "/labs", json={"name": lab_name, "department": "Demo Department", "university": "Demo University"})
    if r.status_code == 201:
        lab = r.json()
        lab_id = lab["id"]
        print(f"  ✓ Lab created: {lab['name']} (id: {lab_id[:8]}…)")
    else:
        print("  ✗ Could not create lab — using default")
        lab_id = None

    # ── Step 6: Create project from template ──────────────────────────────
    _step(6, "Create Project from Template")
    template_id = None
    if templates:
        template_id = templates[0]["id"]
        print(f"  Using template: {templates[0]['name']}")
    proj_name = f"Demo: Alzheimer's scRNA-seq Biomarkers"
    proj_payload: dict = {"name": proj_name, "description": "Single-cell transcriptomic analysis of microglial senescence in Alzheimer's disease. Identifies cell-type-specific biomarkers from post-mortem brain tissue.", "lab_id": lab_id}
    if template_id:
        r = _req("POST", "/templates/from-template", json={"template_id": template_id, **proj_payload})
    else:
        r = _req("POST", "/projects", json=proj_payload)
    if r.status_code == 201:
        project = r.json()
        pid = project["id"]
        print(f"  ✓ Project created: {project['name']}")
    else:
        print("  ✗ Could not create project"); return

    # ── Step 7: Create tasks ──────────────────────────────────────────────
    _step(7, "Create Kanban Tasks")
    tasks_data = [
        ("Download GEO datasets (GSE123456, GSE789012)", "critical",
         "Download single-cell RNA-seq datasets from GEO. Expected: 12 AD + 10 control samples."),
        ("Run QC preprocessing pipeline", "high",
         "Filter doublets, normalize with SCTransform, identify highly variable genes."),
        ("Differential expression analysis", "high",
         "MAST differential expression: AD vs control microglia. |log2FC| > 0.25, adj.p < 0.05."),
        ("Cell-type clustering and annotation", "medium",
         "UMAP clustering, marker-based cell-type annotation using canonical markers."),
        ("Pathway enrichment analysis", "medium",
         "GO and KEGG enrichment on differentially expressed genes."),
        ("Draft manuscript introduction", "medium",
         "Write first draft of introduction covering microglial senescence in AD."),
    ]
    task_ids = []
    for title, priority, desc in tasks_data:
        r = _req("POST", f"/projects/{pid}/tasks", json={"title": title, "description": desc, "priority": priority})
        if r.status_code == 201:
            t = r.json()
            task_ids.append(t["id"])
            print(f"  ✓ Task: {title[:50]}… [{priority}]")
            _wait(0.1)

    # ── Step 8: Bulk update tasks → In Progress ───────────────────────────
    _step(8, "Bulk Task Update")
    if task_ids:
        r = _req("POST", f"/projects/{pid}/tasks/bulk", json={"task_ids": task_ids[:3], "status": "in_progress"})
        if r and r.status_code == 200:
            print(f"  ✓ {r.json()['updated']} tasks moved to IN PROGRESS")

    # ── Step 9: Create experiments ────────────────────────────────────────
    _step(9, "Create Experiments")
    experiments = [
        ("Differential Expression: AD vs Control Microglia",
         "Microglial cells in AD show upregulation of inflammatory pathways (TNF-α, NF-κB) and downregulation of homeostatic markers (CX3CR1, P2RY12) compared to age-matched controls.",
         "Seurat v5 normalization with SCTransform. MAST for DE. Filter: |log2FC| > 0.25, adj.p < 0.05."),
        ("Microglial Senescence Signature Analysis",
         "Senescent microglia in AD exhibit a distinct transcriptional signature (p16INK4a, p21, SASP factors: IL-6, MMP3) identifiable by scRNA-seq.",
         "Compute senescence score using established gene sets. Compare across clusters. Validate with published AD datasets."),
        ("Spatial Transcriptomics Validation",
         "Spatially-resolved transcriptomics confirms that senescent microglia cluster near amyloid plaques in AD brain tissue.",
         "MERFISH or Visium HD on AD brain sections. Quantify microglia-plaque distance distributions."),
    ]
    exp_ids = []
    for name, hypothesis, protocol in experiments:
        r = _req("POST", f"/projects/{pid}/experiments", json={
            "name": name, "hypothesis": hypothesis, "protocol": protocol,
            "tags": ["scRNA-seq", "microglia", "alzheimers", "demo"],
            "status": "running",
        })
        if r.status_code == 201:
            e = r.json()
            exp_ids.append(e["id"])
            print(f"  ✓ Experiment: {name[:55]}…")
            _wait(0.2)

    # ── Step 10: Add experiment entries ───────────────────────────────────
    _step(10, "Experiment Entries (Notes & Results)")
    if exp_ids:
        eid = exp_ids[0]
        entries = [
            ("note", "Initial QC Observations", "After filtering: 10,234 cells remain (from 12,456). PCA shows separation by condition. UMAP clusters need parameter tuning."),
            ("result", "Differential Expression Results", "Top upregulated in AD microglia:\n- TNF-α: log2FC = 1.82, p.adj = 2.3e-15\n- IL1B: log2FC = 1.45, p.adj = 4.1e-12\n- NFKB1: log2FC = 0.92, p.adj = 1.8e-08\n\nTop downregulated:\n- CX3CR1: log2FC = -1.34, p.adj = 3.2e-10\n- P2RY12: log2FC = -1.12, p.adj = 5.6e-09"),
            ("result", "Pathway Enrichment Summary", "Upregulated pathways:\n- TNF signaling via NF-κB: p = 1.2e-10\n- Inflammatory response: p = 3.4e-8\n- Chemokine signaling: p = 2.1e-6\n\nDownregulated pathways:\n- Homeostatic microglia markers: p = 4.5e-12\n- Synaptic pruning: p = 6.7e-5"),
        ]
        for etype, title, body in entries:
            r = _req("POST", f"/projects/{pid}/experiments/{eid}/entries", json={"type": etype, "title": title, "body": body})
            if r and r.status_code == 201:
                print(f"  ✓ Entry: {title} [{etype}]")

    # ── Step 11: AI Hypothesis Generation ─────────────────────────────────
    _step(11, "AI Hypothesis Generation")
    r = _req("POST", f"/projects/{pid}/generate-hypothesis", json={
        "topic": "Microglial senescence subtypes in Alzheimer's disease identified by single-cell transcriptomics",
    })
    if r and r.status_code in (200, 202):
        print("  ✓ Hypothesis generation submitted (runs in background)")
    else:
        print("  ⚠ Hypothesis generation skipped (AI endpoint may need runner)")

    # ── Step 12: AI Methodology Validation ────────────────────────────────
    _step(12, "AI Methodology Validation")
    r = _req("POST", f"/projects/{pid}/validate-methodology", json={
        "proposed_methods": """We will use 10x Genomics scRNA-seq on post-mortem human brain tissue from 10 AD patients and 10 controls. Libraries sequenced on NovaSeq 6000. Analysis uses Seurat for clustering and MAST for differential expression. Cell-type annotation by canonical markers. Validation by RNAscope for top markers."""
    })
    if r and r.status_code in (200, 202):
        print("  ✓ Methodology validation submitted")
    else:
        print("  ⚠ Methodology validation skipped")

    # ── Step 13: AI Literature Review ─────────────────────────────────────
    _step(13, "AI Literature Review")
    r = _req("POST", f"/projects/{pid}/literature-review", json={"topic": "Microglial senescence in Alzheimer's disease single-cell transcriptomics"})
    if r and r.status_code == 202:
        print("  ✓ Literature review submitted (background task)")
    elif r and r.status_code in (200, 201):
        print("  ✓ Literature review completed")
    else:
        print("  ⚠ Literature review skipped")

    # ── Step 14: Create publication ───────────────────────────────────────
    _step(14, "Create Publication")
    r = _req("POST", "/publications", json={
        "title": "Single-cell transcriptomic profiling reveals senescent microglial subtypes in Alzheimer's disease",
        "project_id": pid,
        "venue": "Nature Neuroscience",
        "venue_type": "journal",
        "abstract": "",
    })
    if r.status_code == 201:
        pub = r.json()
        pub_id = pub["id"]
        print(f"  ✓ Publication created: {pub['title'][:60]}…")
    else:
        print("  ✗ Could not create publication"); return

    # ── Step 15: Link experiments to publication ──────────────────────────
    _step(15, "Link Experiments to Publication")
    for eid in exp_ids[:2]:
        r = _req("POST", f"/publications/{pub_id}/link-experiment", json={"experiment_id": eid, "section": "results"})
        if r and r.status_code == 200:
            print(f"  ✓ Linked experiment {eid[:8]}… → publication")

    # ── Step 16: Create version snapshot ──────────────────────────────────
    _step(16, "Create Version Snapshot")
    r = _req("POST", f"/publications/{pub_id}/versions", json={"notes": "Initial draft version for demo"})
    if r and r.status_code == 201:
        v = r.json()
        print(f"  ✓ Version {v['version']} created")

    # ── Step 17: Create grant ─────────────────────────────────────────────
    _step(17, "Create Grant Record")
    r = _req("POST", "/grants", json={
        "title": "TÜBİTAK 1001: Senescent Microglia in Alzheimer's Disease",
        "funder": "TÜBİTAK",
        "project_id": pid,
        "status": "submitted",
        "amount_requested": 1500000,
        "currency": "TRY",
    })
    if r and r.status_code == 201:
        grant = r.json()
        print(f"  ✓ Grant: {grant['title'][:55]}… [{grant['status']}]")

    # ── Step 18: Create IRB record ────────────────────────────────────────
    _step(18, "Create IRB / Ethics Approval")
    r = _req("POST", "/irb", json={
        "title": "Ethics approval for post-mortem brain tissue analysis",
        "institution": "University Ethics Committee",
        "protocol_number": "IRB-2026-0142",
        "project_id": pid,
    })
    if r and r.status_code == 201:
        irb = r.json()
        print(f"  ✓ IRB: {irb['protocol_number']} — {irb['status']}")

    # ── Step 19: Create conference entry ──────────────────────────────────
    _step(19, "Create Conference Entry")
    r = _req("POST", "/conferences", json={
        "name": "Society for Neuroscience 2026",
        "project_id": pid,
        "status": "submitted",
    })
    if r and r.status_code == 201:
        conf = r.json()
        print(f"  ✓ Conference: {conf['name']}")

    # ── Step 20: Add wiki page ────────────────────────────────────────────
    _step(20, "Lab Wiki Page")
    if lab_id:
        r = _req("POST", f"/labs/{lab_id}/wiki", json={
            "title": "scRNA-seq Analysis Protocol",
            "content": """# Standard scRNA-seq Analysis Pipeline\n\n## Preprocessing\n1. Cell Ranger count for each sample\n2. Doublet detection (Scrublet)\n3. QC filtering: 200 < genes < 6000, mito% < 20%\n\n## Normalization\n- SCTransform with regression of mitochondrial content\n\n## Clustering\n- PCA (30 components)\n- UMAP (n_neighbors=30, min_dist=0.3)\n- Leiden clustering at resolution 0.8\n\n## Differential Expression\n- MAST with cell detection rate as covariate\n- Threshold: |log2FC| > 0.25, adj.p < 0.05""",
            "tags": ["protocol", "scRNA-seq", "bioinformatics"],
        })
        if r and r.status_code in (200, 201):
            print("  ✓ Wiki page created")

    # ── Step 21: Lab impact dashboard ─────────────────────────────────────
    _step(21, "Research Impact Dashboard")
    if lab_id:
        r = _req("GET", f"/labs/{lab_id}/research-impact")
        if r.status_code == 200:
            imp = r.json()
            print(f"  ✓ Lab: {imp.get('lab_name','')}")
            print(f"    Publications: {imp.get('total_publications',0)}")
            print(f"    Citations: {imp.get('total_citations',0)} (h-index: {imp.get('h_index',0)})")

    # ── Step 22: Global search ────────────────────────────────────────────
    _step(22, "Global Search")
    r = _req("GET", "/search?q=microglial")
    if r.status_code == 200:
        s = r.json()
        total = len(s.get("projects", [])) + len(s.get("tasks", [])) + len(s.get("experiments", [])) + len(s.get("publications", []))
        print(f"  ✓ Search 'microglial' → {total} results across projects, tasks, experiments, publications")

    # ── Step 23: System health ────────────────────────────────────────────
    _step(23, "System Health")
    r = _req("GET", "/system/health")
    if r.status_code == 200:
        h = r.json()
        skills = h.get("skills_available", 0)
        print(f"  ✓ {skills} AI skills available")

    # ── Step 24: Admin stats ──────────────────────────────────────────────
    _step(24, "Admin Dashboard Stats")
    r = _req("GET", "/admin/stats")
    if r.status_code == 200:
        s = r.json()
        print(f"  ✓ Labs: {s['labs']} | Users: {s['users']} | Projects: {s['projects']} | Tasks: {s['tasks']} | Experiments: {s['experiments']}")

    # ── Step 25: AI Grant Proposal Draft ──────────────────────────────────
    _step(25, "AI Grant Proposal Draft")
    r = _req("POST", f"/projects/{pid}/grant-proposal", json={"grant_type": "tubitak_1001"})
    if r and r.status_code == 202:
        print("  ✓ Grant proposal drafting started (background task, saves as publication)")

    # ── Done ──────────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  Demo complete!")
    print(f"  Project ID: {pid}")
    print(f"  Publication ID: {pub_id}")
    print(f"  Open http://localhost:7860/projects/{pid} to view")
    print(f"{'='*70}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gazzali Demo Script")
    parser.add_argument("--url", default="http://localhost:7860", help="PM dashboard URL")
    parser.add_argument("--username", default="demo_admin", help="Admin username")
    parser.add_argument("--password", default="demo_pass_123", help="Admin password")
    args = parser.parse_args()
    run(args.url, args.username, args.password)


if __name__ == "__main__":
    main()
