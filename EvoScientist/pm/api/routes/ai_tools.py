"""AI-powered research tools — grant writer, figure generator, impact dashboard.

Integrates EvoScientist's ``get_chat_model()`` for direct LLM access and
EvoScientist's skill guidance for specialized AI tasks.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from ..._ai import run_llm_direct_async
from ...crud.experiment_entries import create_entry, list_entries
from ...crud.experiments import get_experiment, list_linked_tasks
from ...crud.projects import get_project
from ...crud.publications import list_publications
from ...db import get_db, get_db_path
from ...models import User
from ..deps import require_lab_member, require_project_role
from ..schemas import GrantWriterRequest
from .drafting_helpers import GROUNDING_RULE, render_metrics_block

router = APIRouter()

# =============================================================================
# AI Grant Writer (uses EvoScientist's get_chat_model + ml-paper-writing skill)
# =============================================================================

_GRANT_TEMPLATES = {
    "tubitak_1001": (
        "TÜBİTAK 1001 — Bilimsel ve Teknolojik Araştırma Projelerini Destekleme Programı. "
        "Azami 36 ay süreli, 20 sayfaya kadar proje önerisi. "
        "Proje yürütücüsü + araştırmacılar + danışmanlar. "
        "Bütçe: makine-teçhizat, sarf malzemesi, seyahat, hizmet alımı, personel. "
        "Değerlendirme kriterleri: özgün değer, yöntem, proje yönetimi, yaygın etki, bütçe uygunluğu. "
        "Proje önerisi bölümleri: Proje Adı, Özet, Amaç ve Hedefler, Özgün Değer, Yöntem, "
        "Proje Yönetimi, Yaygın Etki, Bütçe Gerekçesi, Kaynakça, Ekler."
    ),
    "tubitak_1003": (
        "TÜBİTAK 1003 — Öncelikli Alanlar Ar-Ge Projelerini Destekleme Programı. "
        "Öncelikli alanlarda (sağlık, enerji, malzeme, yapay zeka vb.) uygulamalı Ar-Ge projeleri. "
        "Azami 36 ay, 20 sayfa. İki aşamalı değerlendirme. "
        "Hedef odaklı, çıktıya yönelik, takvimli projeler beklenir. "
        "Çağrı bazlı başvuru — proje çağrı metnindeki hedeflerle uyum gerekli."
    ),
    "tubitak_3501": (
        "TÜBİTAK 3501 — Kariyer Geliştirme Programı. "
        "Doktora sonrası genç araştırmacılar için (üniversitede ilk 5 yıl). "
        "Azami 24 ay, 15 sayfa. "
        "Amaç: bağımsız araştırma grubu kurma, kariyer gelişimini destekleme. "
        "Değerlendirme: araştırmanın özgünlüğü, yöntem, araştırmacının bağımsızlık potansiyeli."
    ),
    "tubitak_other": (
        "TÜBİTAK — Diğer Programlar. "
        "Standart TÜBİTAK proje önerisi formatı. "
        "Bölümler: Proje Adı, Özet (Türkçe + İngilizce), Literatür Özeti, "
        "Amaç ve Hedefler, Özgün Değer, Yöntem, İş-Zaman Çizelgesi, "
        "Risk Yönetimi, Bütçe, Yaygın Etki, Kaynakça. "
        "Maksimum 20 sayfa, 36 ay."
    ),
    "tuseb": (
        "TÜSEB — Türkiye Sağlık Enstitüleri Başkanlığı Sağlık Araştırmaları Destek Programı. "
        "Sağlık alanında uygulamalı ve temel araştırma projeleri. "
        "Bütçe kalemleri: personel, makine-teçhizat, sarf, hizmet alımı, seyahat, yayın. "
        "Proje süresi: 12-36 ay. "
        "Öncelikli alanlar: nadir hastalıklar, aşı geliştirme, biyomalzeme, "
        "dijital sağlık, geleneksel ve tamamlayıcı tıp, sağlık teknolojileri. "
        "Proje önerisi: Özet, Amaç, Gerekçe ve Önem, Yöntem, İş-Zaman Planı, Bütçe, Kaynakça."
    ),
    "nih_r01": "NIH R01 — Research Project Grant. 12-page limit, Specific Aims page, Research Strategy (Significance, Innovation, Approach).",
    "nsf": "NSF Standard Grant. 15-page project description, Intellectual Merit + Broader Impacts required.",
    "erc": "ERC Starting/Consolidator/Advanced Grant. Extended narrative with ground-breaking ambition, no page limit but concise.",
    "wellcome": "Wellcome Trust Grant. Focus on transformative research, public engagement, and researcher development.",
    "general": "General Research Grant. Standard structure: Abstract, Background, Aims, Methods, Timeline, Budget, References.",
}

_GRANT_WRITER_SYSTEM = """You are an expert grant proposal writer. Draft a complete grant proposal based on the project context.

Follow the grant type's specific requirements strictly. Use professional academic language. Be specific and concrete — avoid vague promises. Do not fabricate data or citations."""


def _build_grant_prompt(grant_type: str, context: str) -> str:
    desc = _GRANT_TEMPLATES.get(grant_type, _GRANT_TEMPLATES["general"])
    return f"""Grant Type: {grant_type.upper()} ({desc})

Structure the proposal with these sections:
1. Title — Catchy, descriptive title
2. Abstract — 250-300 word summary
3. Background & Significance
4. Innovation
5. Specific Aims / Objectives — 2-4 clear, measurable aims
6. Research Strategy — Per-aim approach, methods, expected outcomes
7. Timeline
8. Budget Justification
9. Risk Management
10. Dissemination
11. References

Turkish agency rules: if grant_type starts with 'tubitak' or is 'tuseb', include a Türkçe Özet (Turkish abstract, 200-300 words), emphasize özgün değer in a separate section, specify budget in TRY.

--- Project Context ---
{context}"""


@router.post("/projects/{project_id}/grant-proposal", status_code=status.HTTP_202_ACCEPTED)
async def draft_grant_proposal(
    project_id: str,
    body: GrantWriterRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Draft a grant proposal using EvoScientist's LLM with ml-paper-writing skill guidance."""
    project = get_project(get_db_path(), project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    context = _build_project_context(project_id)
    prompt = _build_grant_prompt(body.grant_type, context)

    pub_title = f"Grant Proposal: {body.grant_type.upper()} — {project.name}"
    from ...crud.publications import create_publication
    pub = create_publication(
        get_db_path(), title=pub_title, created_by=current_user.id,
        project_id=project_id, venue_type="other",
        abstract=f"AI-generated {body.grant_type} grant proposal (in progress).",
    )

    background_tasks.add_task(_run_grant_writer, pub.id, prompt, current_user.id)
    return {"status": "drafting", "publication_id": pub.id, "grant_type": body.grant_type}


async def _run_grant_writer(pub_id: str, prompt: str, user_id: str) -> None:
    """Run grant writing through EvoScientist's get_chat_model directly, with skill guidance."""
    from ...crud.publications import update_publication as _up
    text = await run_llm_direct_async(
        system_prompt=_GRANT_WRITER_SYSTEM,
        user_prompt=prompt,
        skill_guidance=["ml-paper-writing"],
    )
    if text:
        _up(get_db_path(), pub_id, abstract=text[:800].strip(), status="draft")


# =============================================================================
# Auto Figure Generator (uses EvoScientist's get_chat_model + data analysis)
# =============================================================================

_FIGURE_GEN_SYSTEM = """You are a data analysis and visualization agent. Analyze experiment data and produce publication-quality analysis.

For each dataset or result, generate:
1. Data Summary — Key statistics (mean, std, n, effect sizes where applicable)
2. Analysis Code — Python code using matplotlib/seaborn. Write clean, self-contained code that can be executed directly.
3. Figure Description — What each figure shows and how to interpret it
4. Statistical Tests — Appropriate tests with results

Use publication-ready styling (appropriate font sizes, color schemes). Include effect sizes and confidence intervals where appropriate."""


@router.post("/projects/{project_id}/experiments/{exp_id}/generate-figures", status_code=status.HTTP_202_ACCEPTED)
async def generate_figures(
    project_id: str,
    exp_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Generate publication-quality figures using EvoScientist's LLM directly."""
    db = get_db_path()
    exp = get_experiment(db, exp_id)
    if not exp or exp.project_id != project_id:
        raise HTTPException(404, "Experiment not found")

    entries = list_entries(db, exp_id)
    linked = list_linked_tasks(db, exp_id)
    parts = [
        f"# Experiment: {exp.name}",
        f"Hypothesis: {exp.hypothesis or 'not set'}",
        f"Protocol: {exp.protocol or 'not set'}",
    ]
    if linked:
        parts.append(f"Linked tasks: {', '.join(t.title for t in linked)}")
    parts.append(render_metrics_block(exp_id))
    for e in entries:
        parts.append(f"\n## {e.title} ({e.type})")
        parts.append(e.body or "")

    prompt = "--- Experiment Data ---\n" + "\n".join(parts) + "\n" + GROUNDING_RULE
    background_tasks.add_task(_run_figure_generator, exp_id, current_user.id, prompt)
    return {"status": "generating", "experiment_id": exp_id}


async def _run_figure_generator(exp_id: str, user_id: str, prompt: str) -> None:
    text = await run_llm_direct_async(
        system_prompt=_FIGURE_GEN_SYSTEM,
        user_prompt=prompt,
        temperature=0.2,
    )
    if text:
        create_entry(
            get_db_path(),
            experiment_id=exp_id,
            entry_type="result",
            title="AI-Generated Figures & Analysis",
            body=text, author_id=user_id,
        )


# =============================================================================
# Research Impact Dashboard
# =============================================================================


@router.get("/labs/{lab_id}/research-impact")
async def research_impact(
    lab_id: str,
    current_user: User = Depends(require_lab_member()),
):
    """Generate a research impact report for a lab using S2 data and publication records."""
    from ...crud.labs import get_lab as _get_lab
    from ...crud.labs import list_members as _list_members
    db = get_db_path()
    lab = _get_lab(db, lab_id)
    if not lab:
        raise HTTPException(404, "Lab not found")

    with get_db(db) as conn:
        project_ids = [r["id"] for r in conn.execute(
            "SELECT id FROM projects WHERE lab_id = ? AND archived_at IS NULL", (lab_id,)
        ).fetchall()]

    pubs = []
    for pid in project_ids:
        pubs.extend(list_publications(db, project_id=pid))

    s2_data = []
    from ...s2.queries import is_available, search_by_doi, search_by_title
    if is_available():
        for p in pubs:
            if p.doi:
                paper = search_by_doi(p.doi)
            else:
                matches = search_by_title(p.title, limit=1)
                paper = matches[0] if matches else None
            if paper:
                s2_data.append({
                    "title": p.title,
                    "status": p.status,
                    "citations": paper.citation_count,
                    "influential_citations": paper.influential_citation_count,
                    "venue": paper.venue or p.venue,
                    "year": paper.year,
                    "fields": paper.fields_of_study,
                    "is_open_access": paper.is_open_access,
                })

    members = _list_members(db, lab_id)
    total_citations = sum(d.get("citations", 0) for d in s2_data) if s2_data else 0
    h_index = _compute_h_index([d.get("citations", 0) for d in s2_data]) if s2_data else 0

    return {
        "lab_id": lab_id,
        "lab_name": lab.name,
        "total_publications": len(pubs),
        "s2_matched": len(s2_data),
        "total_citations": total_citations,
        "h_index": h_index,
        "average_citations_per_paper": round(total_citations / max(len(s2_data), 1), 1),
        "member_count": len(members),
        "publications_by_status": {s: sum(1 for p in pubs if p.status == s) for s in {p.status for p in pubs}},
        "publications": s2_data,
        "members": [{"user_id": m.user_id, "role": m.role} for m in members],
    }


def _compute_h_index(citation_counts: list[int]) -> int:
    sorted_citations = sorted(citation_counts, reverse=True)
    h = 0
    for i, c in enumerate(sorted_citations, 1):
        if c >= i:
            h = i
        else:
            break
    return h


# =============================================================================
# Helpers
# =============================================================================

def _build_project_context(project_id: str) -> str:
    from .drafting_helpers import _build_project_context as _ctx
    return _ctx(project_id)
