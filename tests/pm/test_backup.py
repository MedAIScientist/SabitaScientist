"""Backups are real SQLite copies and old ones are pruned per kind."""

from __future__ import annotations

import sqlite3

from gazzali import backup


def test_backup_copies_data_and_keeps_only_the_newest(tmp_path) -> None:
    db = tmp_path / "pm.db"
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE t (x)")
        c.execute("INSERT INTO t VALUES (42)")
    old = backup.backup_dir(db)
    old.mkdir()
    for day in range(1, 5):  # four older predeploy copies and one weekly
        (old / f"predeploy-2020010{day}-000000.db").write_bytes(b"")
    (old / "weekly-20200101-000000.db").write_bytes(b"")

    made = backup.backup_db(db, "predeploy")

    left = sorted(p.name for p in old.glob("predeploy-*.db"))
    assert left == ["predeploy-20200103-000000.db", "predeploy-20200104-000000.db", made.name]
    assert (old / "weekly-20200101-000000.db").exists()
    with sqlite3.connect(made) as c:
        assert c.execute("SELECT x FROM t").fetchone() == (42,)
