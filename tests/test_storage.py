import sqlite3

import pytest

from backend.storage import Storage


@pytest.fixture
def storage(tmp_path):
    db = Storage(tmp_path / "rift.sqlite3")
    yield db
    db.close()


@pytest.fixture
def window():
    return dict(app_id="org.kde.kate", title="Notes", x=-1920, y=30, w=900, h=700,
                desktop_file="/usr/share/applications/org.kde.kate.desktop")


def test_capture_append_and_persist(tmp_path, window):
    path = tmp_path / "persist.sqlite3"
    db = Storage(path)
    gid = db.capture(" Work ", [window])
    db.capture("", [dict(window, title="Second")], gid)
    db.close()
    db = Storage(path)
    try:
        assert db.groups()[0]["name"] == "Work"
        assert db.groups()[0]["created_at"]
        rows = db.windows(gid)
        assert [r["title"] for r in rows] == ["Notes", "Second"]
        assert rows[0]["x"] == -1920
        assert rows[0]["match_app_id"] == ""
    finally:
        db.close()


def test_rename_and_sql_parameterization(storage, window):
    payload = "Robert'); DROP TABLE groups; --"
    gid = storage.capture(payload, [dict(window, title=payload)])
    assert storage.windows(gid)[0]["title"] == payload
    storage.rename(gid, "Renamed")
    assert storage.groups()[0]["name"] == "Renamed"


def test_foreign_key_cascade(storage, window):
    gid = storage.capture("Work", [window])
    storage.delete(gid)
    assert storage.windows(gid) == []
    assert storage.groups() == []
    with pytest.raises(sqlite3.IntegrityError):
        storage.connection.execute(
            "INSERT INTO group_windows(group_id, x, y, w, h) VALUES (?, ?, ?, ?, ?)",
            (gid, 0, 0, 100, 100),
        )


def test_remove_is_scoped_to_group(storage, window):
    first = storage.capture("One", [window])
    second = storage.capture("Two", [window])
    row = storage.windows(first)[0]
    storage.remove_window(second, row["id"])
    assert len(storage.windows(first)) == 1
    storage.remove_window(first, row["id"])
    assert storage.windows(first) == []


def test_update_overrides_is_scoped(storage, window):
    gid = storage.capture("Work", [window])
    row_id = storage.windows(gid)[0]["id"]
    storage.update_window(gid + 1, row_id, "wrong", "wrong", "wrong", "wrong")
    assert storage.windows(gid)[0]["match_app_id"] == ""
    storage.update_window(gid, row_id, "new.desktop", "Kate", "Exact", "/usr/bin/kate")
    row = storage.windows(gid)[0]
    assert (row["desktop_file"], row["match_app_id"], row["match_title"], row["match_process"]) == (
        "new.desktop", "Kate", "Exact", "/usr/bin/kate")


@pytest.mark.parametrize("change", [dict(w=0), dict(h=-1)])
def test_bad_geometry_rolls_back_entire_capture(storage, window, change):
    with pytest.raises(sqlite3.IntegrityError):
        storage.capture("Bad", [window, dict(window, **change)])
    assert storage.groups() == []


def test_missing_append_group_does_not_create_one(storage, window):
    with pytest.raises(ValueError):
        storage.capture("", [window], 99)
    assert storage.groups() == []


def test_blank_name_rejected(storage):
    with pytest.raises(sqlite3.IntegrityError):
        storage.capture("  ", [])


def test_additive_migration_preserves_existing_rows(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE groups(id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE group_windows(id INTEGER PRIMARY KEY,
            group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
            app_id TEXT, title TEXT, x INTEGER, y INTEGER, w INTEGER, h INTEGER, desktop_file TEXT);
        INSERT INTO groups(id, name) VALUES (1, 'Existing');
        INSERT INTO group_windows VALUES (1, 1, 'kate', 'Notes', 0, 0, 800, 600, 'kate.desktop');
    """)
    connection.close()
    for _ in range(2):
        db = Storage(path)
        assert db.windows(1)[0]["title"] == "Notes"
        assert db.windows(1)[0]["match_process"] == ""
        db.close()
