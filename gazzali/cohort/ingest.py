"""Reading an uploaded cohort file into a typed frame, with a parse report.

The report is part of the provenance: it records how the bytes became a table
(encoding, delimiter, malformed lines, columns renamed on import), so a later
reader can tell an analysis problem from a reading problem.
"""

from __future__ import annotations

import csv
import io
from dataclasses import asdict, dataclass, replace
from pathlib import PurePath

import pandas as pd

from .vendor.core.fingerprint import ensure_row_ids

__all__ = [
    "SUPPORTED_SUFFIXES",
    "IngestError",
    "ParseReport",
    "columns_payload",
    "read_upload",
]

SUPPORTED_SUFFIXES: tuple[str, ...] = (
    ".csv",
    ".tsv",
    ".txt",
    ".xlsx",
    ".xlsm",
    ".parquet",
)

_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
# Tried in order; the first delimiter that splits the header into more than one
# field wins when csv.Sniffer refuses the sample.
_DELIMITERS = (",", ";", "\t", "|")
_SNIFF_BYTES = 64 * 1024
_MAX_ROWS = 500_000


class IngestError(ValueError):
    """The uploaded file cannot be read as a table."""


@dataclass(frozen=True)
class ParseReport:
    """How the file was read. Serialised into ``cohort_versions.parse_report_json``."""

    filename: str
    suffix: str
    encoding: str | None = None
    delimiter: str | None = None
    sheet: str | None = None
    lines: int | None = None
    rows: int = 0
    columns: int = 0
    skipped_lines: int = 0
    blanks: int = 0
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {**asdict(self), "warnings": list(self.warnings)}


def _decode(content: bytes) -> tuple[str, str]:
    for encoding in _ENCODINGS:
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise IngestError(
        "the file is not valid text in any of the supported encodings "
        f"({', '.join(_ENCODINGS)}); export it as UTF-8 CSV"
    )


def _sniff_delimiter(text: str) -> str:
    sample = text[:_SNIFF_BYTES]
    try:
        return csv.Sniffer().sniff(sample, delimiters="".join(_DELIMITERS)).delimiter
    except csv.Error:
        # The sniffer refuses single-column files and some odd quoting: fall back
        # to the delimiter that splits the header into most fields.
        header = next((line for line in sample.splitlines() if line.strip()), "")
        return max(_DELIMITERS, key=header.count)


def _count_lines(text: str) -> int:
    return len([line for line in text.splitlines() if line.strip()])


def _raw_header(text: str, delimiter: str) -> list[str]:
    """The header names as written in the file.

    Read separately from the body because pandas silently renames a repeated column to
    ``age.1``, which would hide a duplicate that makes the file ambiguous to analyse.
    """
    head = pd.read_csv(
        io.StringIO(text), sep=delimiter, header=None, nrows=1, dtype=str
    )
    if head.empty:
        return []
    return [str(value).strip() for value in head.iloc[0].tolist()]


def _read_delimited(
    content: bytes, report: ParseReport
) -> tuple[pd.DataFrame, ParseReport]:
    text, encoding = _decode(content)
    delimiter = _sniff_delimiter(text)
    lines = _count_lines(text)
    header = _raw_header(text, delimiter)
    duplicated = sorted({name for name in header if header.count(name) > 1 and name})
    if duplicated:
        raise IngestError(
            "duplicate column names cannot be told apart: " + ", ".join(duplicated)
        )
    frame = pd.read_csv(
        io.StringIO(text),
        sep=delimiter,
        on_bad_lines="skip",
        skip_blank_lines=True,
        low_memory=False,
    )
    # pandas drops malformed rows silently; comparing the counts is the only
    # honest way to report how many (a multi-line quoted cell can make this an
    # upper bound, hence the wording).
    skipped = max(0, lines - 1 - len(frame))
    warnings: list[str] = []
    if skipped:
        warnings.append(
            f"{skipped} line(s) could not be parsed and were skipped; "
            "check the delimiter and the quoting of the source file"
        )
    return frame, replace(
        report,
        encoding=encoding,
        delimiter=delimiter,
        lines=lines,
        skipped_lines=skipped,
        warnings=tuple(warnings),
    )


def _read_excel(
    content: bytes, report: ParseReport
) -> tuple[pd.DataFrame, ParseReport]:
    with pd.ExcelFile(io.BytesIO(content)) as book:
        sheet = str(book.sheet_names[0]) if book.sheet_names else None
        if sheet is None:
            raise IngestError("the workbook has no sheets")
        frame = book.parse(sheet)
    return frame, replace(report, sheet=sheet)


def _read_parquet(
    content: bytes, report: ParseReport
) -> tuple[pd.DataFrame, ParseReport]:
    return pd.read_parquet(io.BytesIO(content)), report


def _normalise_columns(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Trim column names, name the unnamed, and refuse names we cannot address."""
    warnings: list[str] = []
    columns: list[str] = []
    renamed = 0
    for i, raw in enumerate(frame.columns):
        name = str(raw).strip() or f"column_{i + 1}"
        if name != str(raw):
            renamed += 1
        columns.append(name)
    if renamed:
        warnings.append(
            f"{renamed} column name(s) had surrounding whitespace and were trimmed"
        )
    frame = frame.set_axis(columns, axis=1)
    duplicated = sorted({c for c in frame.columns if list(frame.columns).count(c) > 1})
    if duplicated:
        raise IngestError(
            "duplicate column names cannot be told apart: " + ", ".join(duplicated)
        )
    if frame.shape[1] == 0:
        raise IngestError("the file has no columns")
    return frame, warnings


def _drop_empty_rows(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """A row that is entirely blank is not a record; dropping it is reported."""
    if frame.empty:
        return frame, 0
    keep = ~frame.isna().all(axis=1)
    dropped = int((~keep).sum())
    return (frame.loc[keep] if dropped else frame), dropped


def read_upload(filename: str, content: bytes) -> tuple[pd.DataFrame, ParseReport]:
    """Read ``content`` as a cohort table: the frame (with row ids) and the report."""
    suffix = PurePath(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise IngestError(
            f"unsupported file type {suffix or '(none)'}; supported: "
            + ", ".join(SUPPORTED_SUFFIXES)
        )
    if not content:
        raise IngestError("the uploaded file is empty")
    if suffix == ".xls":
        raise IngestError(
            "legacy .xls is not supported; save the sheet as .xlsx or CSV"
        )

    report = ParseReport(filename=filename, suffix=suffix)
    if suffix == ".parquet":
        frame, report = _read_parquet(content, report)
    elif suffix in (".xlsx", ".xlsm"):
        frame, report = _read_excel(content, report)
    else:
        frame, report = _read_delimited(content, report)

    frame, warnings = _normalise_columns(frame)
    frame, blanks = _drop_empty_rows(frame)
    if frame.empty:
        raise IngestError("the file has no data rows")
    if len(frame) > _MAX_ROWS:
        raise IngestError(
            f"{len(frame):,} rows exceeds the {_MAX_ROWS:,}-row limit of the in-process "
            "engine; aggregate or subset the cohort first"
        )

    frame = ensure_row_ids(frame.reset_index(drop=True))
    if not frame.index.is_unique:
        raise IngestError("row identifiers are not unique after import")

    return frame, replace(
        report,
        rows=len(frame),
        columns=int(frame.shape[1]),
        blanks=blanks,
        warnings=(*report.warnings, *warnings),
    )


def columns_payload(frame: pd.DataFrame) -> list[dict]:
    """Column metadata as stored in ``cohort_versions.columns_json``."""
    out: list[dict] = []
    for name in frame.columns:
        series = frame[name]
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(
            series
        ):
            kind = "numeric"
        elif pd.api.types.is_datetime64_any_dtype(series):
            kind = "datetime"
        elif pd.api.types.is_bool_dtype(series):
            kind = "boolean"
        else:
            kind = "categorical"
        out.append(
            {
                "name": str(name),
                "dtype": str(series.dtype),
                "kind": kind,
                "missing": int(series.isna().sum()),
                "levels": int(series.nunique(dropna=True))
                if kind != "numeric"
                else None,
            }
        )
    return out
