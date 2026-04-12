"""Tests for ExperimentEntry CRUD operations."""
from __future__ import annotations
from pathlib import Path
import pytest
from EvoScientist.pm.crud.users import create_user
from EvoScientist.pm.crud.projects import create_project
from EvoScientist.pm.crud.experiments import create_experiment
from EvoScientist.pm.crud.experiment_entries import (
    create_entry, get_entry, list_entries, update_entry, delete_entry,
)
from EvoScientist.pm.db import create_schema


@pytest.fixture
def setup(tmp_path: Path):
    db = tmp_path / "test.db"
    create_schema(db)
    user = create_user(db, username="u1", password_hash="h")
    project = create_project(db, name="P1", created_by=user.id)
    exp = create_experiment(db, project_id=project.id, name="Exp", created_by=user.id)
    return db, user, exp


def test_create_and_get_entry(setup):
    db, user, exp = setup
    entry = create_entry(
        db, experiment_id=exp.id, entry_type="note",
        title="Day 1 Observations", body="Cells looked healthy.",
        author_id=user.id,
    )
    assert entry.id is not None
    assert entry.type == "note"
    fetched = get_entry(db, entry.id)
    assert fetched is not None
    assert fetched.title == "Day 1 Observations"
    assert fetched.body == "Cells looked healthy."


def test_list_entries_all(setup):
    db, user, exp = setup
    create_entry(db, exp.id, "note", "N1", "", user.id)
    create_entry(db, exp.id, "result", "R1", "", user.id)
    entries = list_entries(db, exp.id)
    assert len(entries) == 2


def test_list_entries_by_type(setup):
    db, user, exp = setup
    create_entry(db, exp.id, "note", "N1", "", user.id)
    create_entry(db, exp.id, "result", "R1", "", user.id)
    notes = list_entries(db, exp.id, entry_type="note")
    assert len(notes) == 1
    assert notes[0].type == "note"
    results = list_entries(db, exp.id, entry_type="result")
    assert len(results) == 1
    assert results[0].type == "result"


def test_update_entry(setup):
    db, user, exp = setup
    entry = create_entry(db, exp.id, "note", "Old Title", "old", user.id)
    updated = update_entry(db, entry.id, title="New Title", body="new body")
    assert updated.title == "New Title"
    assert updated.body == "new body"


def test_delete_entry(setup):
    db, user, exp = setup
    entry = create_entry(db, exp.id, "note", "T", "", user.id)
    assert delete_entry(db, entry.id) is True
    assert get_entry(db, entry.id) is None


def test_get_entry_missing(setup):
    db, *_ = setup
    assert get_entry(db, "nonexistent") is None
