"""Immutable cohort-data files: one Parquet file per version.

A version file is written once and never rewritten, so a number computed on it can
always be re-derived. The path is derived from server-generated ids only — a client
never supplies a path — and every read re-checks that the resolved file stays inside
the cohort root.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from .. import settings

__all__ = [
    "CohortStoreError",
    "content_sha256",
    "read_version",
    "root",
    "version_rel_path",
    "write_version",
]


class CohortStoreError(RuntimeError):
    """The stored file is missing, outside the root, or does not match its hash."""


def root() -> Path:
    """The cohort root, read at call time so tests can point it elsewhere."""
    return Path(settings.COHORT_DIR)


def _resolve(rel_path: str) -> Path:
    base = root().resolve()
    candidate = (base / rel_path).resolve()
    if candidate != base and base not in candidate.parents:
        raise CohortStoreError(f"path escapes the cohort root: {rel_path!r}")
    return candidate


def version_rel_path(table_id: str, version_no: int) -> str:
    """Where version ``version_no`` of ``table_id`` lives, relative to the root."""
    if not table_id.isalnum():
        raise CohortStoreError("table id must be alphanumeric")
    return f"{table_id}/v{int(version_no)}.parquet"


def content_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_version(
    table_id: str, version_no: int, frame: pd.DataFrame
) -> tuple[str, str]:
    """Write one version; return ``(rel_path, sha256)``.

    The row identity (``__row_id``) is persisted with the frame: it is what lets a
    population name the same rows across filters and reloads.
    """
    rel_path = version_rel_path(table_id, version_no)
    path = _resolve(rel_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise CohortStoreError(f"version file already exists: {rel_path}")
    # Write then rename, so a crash cannot leave a half-written version that a
    # later read would happily analyse.
    tmp = path.with_suffix(".parquet.tmp")
    frame.to_parquet(tmp, index=True)
    tmp.replace(path)
    return rel_path, content_sha256(path)


def read_version(rel_path: str, *, expected_sha256: str | None = None) -> pd.DataFrame:
    """Read a version, verifying its content hash before anyone analyses it."""
    path = _resolve(rel_path)
    if not path.is_file():
        raise CohortStoreError(f"version file is missing: {rel_path}")
    if expected_sha256 and content_sha256(path) != expected_sha256:
        raise CohortStoreError(
            f"version file does not match its recorded hash: {rel_path} "
            "(the file changed after it was written)"
        )
    frame = pd.read_parquet(path)
    return frame


def purge_table(table_id: str) -> None:
    """Delete every file of a table (used when the table itself is deleted)."""
    import shutil

    directory = _resolve(table_id)
    if directory.is_dir():
        shutil.rmtree(directory, ignore_errors=True)
