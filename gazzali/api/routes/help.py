import re
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

_HERE = Path(__file__).parent
_CANDIDATES = [
    _HERE.parent.parent.parent / "docs" / "PM-USER-GUIDE.md",
    Path("/src/docs/PM-USER-GUIDE.md"),
    _HERE.parent.parent / "docs" / "PM-USER-GUIDE.md",
    _HERE.parent / "help" / "PM-USER-GUIDE.md",
]
_HELP_FILE = next((p for p in _CANDIDATES if p.exists()), None)


def _slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return s.strip("-")


def _parse_sections(md: str):
    import markdown

    _md = markdown.Markdown(extensions=["fenced_code", "tables"])
    sections: list[dict] = []
    heading_re = re.compile(r"^## (.+)$", re.MULTILINE)

    parts = heading_re.split(md)
    # parts[0] = content before first ## (H1 + intro + TOC)
    intro_html = _md.convert(parts[0])
    _md.reset()

    # Even indices (1, 3, 5...) are headings, odd (2, 4, 6...) are body text
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        slug = _slugify(heading)
        html = _md.convert(body)
        _md.reset()
        sections.append({"slug": slug, "title": heading, "html": html})

    return intro_html, sections


@router.get("/help")
def get_help():
    if _HELP_FILE is None:
        return {
            "intro": "<p>Help document not found.</p>",
            "sections": [],
            "title": "Help — Not Available",
        }
    md = _HELP_FILE.read_text(encoding="utf-8")
    intro_html, sections = _parse_sections(md)
    return {"intro": intro_html, "sections": sections, "title": "PM User Guide — Gazzali"}
