"""The per-researcher push counter.

platform-control refuses any membership document whose generation is not
strictly greater than the one it already holds — that is what makes a delayed
or replayed push unable to restore a membership that has ended. The counter
therefore has to be monotonic per person and survive restarts, so it lives in
the database rather than in a clock: two pushes in the same second get
different generations, and a clock that steps backwards changes nothing.
"""

from __future__ import annotations

from pathlib import Path

from ..db import get_db


def bump_researcher_generation(db_path: Path, email: str) -> int:
    """Increment and return this person's push generation (starts at 1)."""
    email = (email or "").strip().lower()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO researcher_pushes (email, generation) VALUES (?, 1)
               ON CONFLICT(email) DO UPDATE SET generation = generation + 1""",
            (email,),
        )
        row = conn.execute(
            "SELECT generation FROM researcher_pushes WHERE email = ?", (email,)
        ).fetchone()
    return int(row["generation"])


def researcher_generation(db_path: Path, email: str) -> int:
    """The current generation without bumping it (0 when never pushed)."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT generation FROM researcher_pushes WHERE email = ?",
            ((email or "").strip().lower(),),
        ).fetchone()
    return int(row["generation"]) if row else 0
