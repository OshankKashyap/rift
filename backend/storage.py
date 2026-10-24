"""Project-local SQLite persistence; schema changes are additive."""

import sqlite3
from collections import Counter


def window_details(window):
    return tuple(window.get(key, "") for key in ("app_id", "title", "x", "y", "w", "h"))


class Storage:
    def __init__(self, path):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        with self.connection:
            self.connection.executescript("""
                CREATE TABLE IF NOT EXISTS groups (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL CHECK(length(trim(name)) > 0),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS group_windows (
                    id INTEGER PRIMARY KEY,
                    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
                    app_id TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    x INTEGER NOT NULL, y INTEGER NOT NULL,
                    w INTEGER NOT NULL CHECK(w > 0), h INTEGER NOT NULL CHECK(h > 0),
                    desktop_file TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS group_windows_group ON group_windows(group_id);
            """)
            columns = {r[1] for r in self.connection.execute("PRAGMA table_info(group_windows)")}
            for column in ("match_app_id", "match_title", "match_process", "window_id"):
                if column not in columns:
                    self.connection.execute(
                        f"ALTER TABLE group_windows ADD COLUMN {column} TEXT NOT NULL DEFAULT ''"
                    )

    def groups(self):
        return [dict(r) for r in self.connection.execute("SELECT * FROM groups ORDER BY id")]

    def windows(self, group_id):
        return [dict(r) for r in self.connection.execute(
            "SELECT * FROM group_windows WHERE group_id = ? ORDER BY id", (group_id,)
        )]

    def capture(self, name, windows, group_id=0):
        with self.connection:
            if not group_id:
                group_id = self.connection.execute(
                    "INSERT INTO groups(name) VALUES (?)", (name.strip(),)
                ).lastrowid
            elif not self.connection.execute("SELECT id FROM groups WHERE id = ?", (group_id,)).fetchone():
                raise ValueError("The selected group no longer exists.")
            stored = self.windows(group_id)
            known_ids = {w["window_id"] for w in stored if w["window_id"]}
            incoming_details = Counter(window_details(w) for w in windows)
            stored_details = Counter(window_details(w) for w in stored)
            added = []
            for window in windows:
                window_id = window.get("window_id", "")
                if window_id and window_id in known_ids:
                    continue
                details = window_details(window)
                # Old captures have no KWin ID. Only corroborate an exact,
                # unambiguous match; distinct known IDs are different windows.
                previous = next((w for w in stored if window_details(w) == details), None)
                if (incoming_details[details] == 1 and stored_details[details] == 1
                        and previous is not None and (not previous["window_id"] or not window_id)):
                    if window_id:
                        self.connection.execute(
                            "UPDATE group_windows SET window_id = ? WHERE id = ?",
                            (window_id, previous["id"]),
                        )
                        known_ids.add(window_id)
                    continue
                added.append(window)
                if window_id:
                    known_ids.add(window_id)
            self.connection.executemany(
                """INSERT INTO group_windows(group_id, app_id, title, x, y, w, h, desktop_file, window_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(group_id, w.get("app_id", ""), w.get("title", ""),
                  w["x"], w["y"], w["w"], w["h"], w.get("desktop_file", ""),
                  w.get("window_id", "")) for w in added],
            )
        return group_id

    def rename(self, group_id, name):
        with self.connection:
            self.connection.execute("UPDATE groups SET name = ? WHERE id = ?", (name.strip(), group_id))

    def delete(self, group_id):
        with self.connection:
            self.connection.execute("DELETE FROM groups WHERE id = ?", (group_id,))

    def remove_window(self, group_id, window_id):
        with self.connection:
            self.connection.execute(
                "DELETE FROM group_windows WHERE group_id = ? AND id = ?", (group_id, window_id)
            )

    def update_window(self, group_id, window_id, desktop_file, app_id, title, process):
        with self.connection:
            self.connection.execute(
                """UPDATE group_windows SET desktop_file = ?, match_app_id = ?,
                   match_title = ?, match_process = ? WHERE group_id = ? AND id = ?""",
                (desktop_file.strip(), app_id.strip(), title.strip(), process.strip(), group_id, window_id),
            )

    def close(self):
        self.connection.close()
