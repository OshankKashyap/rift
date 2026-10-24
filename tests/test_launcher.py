import logging

import pytest

from backend.launcher import DesktopResolver, Launcher, dedupe, match_key, matches


@pytest.mark.parametrize("stored,live,expected", [
    ({"app_id": "Org.KDE.Kate.desktop"}, {"app_id": "org.kde.kate"}, True),
    ({"app_id": "kate"}, {"app_id": "org.kde.kate"}, False),
    ({"app_id": "one", "title": "Same"}, {"app_id": "two", "title": "Same"}, False),
    ({"title": "Exact"}, {"title": "Exact", "app_id": "unknown"}, True),
    ({"title": "Exact"}, {"title": "exact"}, False),
    ({}, {}, False),
    ({"desktop_file": "/a.desktop"}, {"desktop_file": "/a.desktop"}, True),
    ({"process": "/usr/bin/app", "title": "A"}, {"process": "/usr/bin/app", "title": "A"}, True),
    ({"process": "/usr/bin/app", "title": "A"}, {"process": "/usr/bin/app", "title": "B"}, False),
    ({"process": "/a/app", "title": "A", "app_id": "one"},
     {"process": "/b/app", "title": "A", "app_id": "two"}, False),
    ({"app_id": "old", "match_app_id": "new"}, {"app_id": "old"}, False),
    ({"app_id": "old", "match_app_id": "new"}, {"app_id": "NEW"}, True),
    ({"match_app_id": "app", "match_title": "Doc"}, {"app_id": "app", "title": "Other"}, False),
    ({"match_app_id": "app", "match_title": "Doc"}, {"app_id": "app", "title": "Doc"}, True),
    ({"match_process": "/usr/bin/app"}, {"process": "/usr/bin/app"}, True),
    ({"match_process": "/usr/bin/app"}, {"process": "/else/app"}, False),
])
def test_matching(stored, live, expected):
    assert bool(matches(stored, live)) is expected


def test_unreliable_identity_is_logged(caplog):
    with caplog.at_level(logging.WARNING):
        assert matches({"title": "Notes"}, {"title": "Notes"})
        assert matches({"app_id": "bad", "process": "/bin/app", "title": "Notes"},
                       {"app_id": "different", "process": "/bin/app", "title": "Notes"})
    assert "override" in caplog.text
    assert "AppId unreliable" in caplog.text


def test_desktop_fallback_logs_changed_app_id(caplog):
    with caplog.at_level(logging.WARNING):
        assert matches({"app_id": "old", "desktop_file": "/app.desktop"},
                       {"app_id": "new", "desktop_file": "/app.desktop"})
    assert "matched exact desktop file" in caplog.text


def test_dedupe_launches_app_once_and_retains_first_geometry():
    first = {"app_id": "kate", "title": "One", "x": 1}
    second = {"app_id": "KATE.desktop", "title": "Two", "x": 2}
    other = {"app_id": "konsole"}
    assert dedupe([first, second, other]) == [first, other]


def test_override_is_an_explicit_distinct_identity():
    assert match_key({"app_id": "app", "match_title": "One"}) != match_key(
        {"app_id": "app", "match_title": "Two"})


def test_key_fallbacks_and_missing_identity():
    assert match_key({"desktop_file": "/app.desktop"}) == ("desktop", "/app.desktop")
    assert match_key({"title": "Notes"}) == ("title", "Notes")
    with pytest.raises(ValueError):
        match_key({})


def test_desktop_resolution_exact_precedence_and_nested_id(tmp_path):
    local, system = tmp_path / "local", tmp_path / "system"
    local.mkdir()
    (system / "nested").mkdir(parents=True)
    (local / "app.desktop").write_text("[Desktop Entry]\nType=Application\nExec=/usr/bin/true\n")
    (system / "app.desktop").write_text("[Desktop Entry]\n")
    (system / "nested/other.desktop").write_text("[Desktop Entry]\n")
    resolver = DesktopResolver()
    resolver.roots = [local, system]
    assert resolver.resolve("app") == str(local / "app.desktop")
    assert resolver.resolve("nested-other") == str(system / "nested/other.desktop")
    assert resolver.resolve("APP") == ""
    assert resolver.resolve("../app") == ""
    assert resolver.resolve(str(local / "app.desktop")) == str(local / "app.desktop")
    assert resolver.resolve(str(local / "missing.desktop")) == ""


def test_no_execution_of_desktop_exec(tmp_path):
    desktop = tmp_path / "app.desktop"
    marker = tmp_path / "MUST_NOT_EXIST"
    desktop.write_text(f"[Desktop Entry]\nType=Application\nExec=/usr/bin/touch {marker}\n")
    resolver = DesktopResolver()
    assert resolver.executable(str(desktop))
    assert not marker.exists()


def test_launch_skips_running_and_dedupes_without_kwin_writes():
    class Resolver:
        def enrich(self, windows):
            return windows

    class KWin:
        def snapshot(self, callback, main_only=True):
            callback([{"app_id": "kate", "window_id": "existing"}], None)

    messages, results = [], []
    launcher = Launcher(KWin(), Resolver(), messages.append)
    launcher.launch([{"app_id": "kate"}, {"app_id": "KATE"}], results.append)
    assert results == [None]
    assert "Launching 0 apps; skipping 1" in messages[0]


def test_recall_only_requests_matching_windows_including_dialogs():
    class Resolver:
        def enrich(self, windows):
            return windows

    class KWin:
        def snapshot(self, callback, main_only=True):
            assert not main_only
            callback([{"app_id": "kate", "window_id": "main"},
                      {"app_id": "kate", "window_id": "dialog"},
                      {"app_id": "other", "window_id": "unrelated"}], None)

        def close_windows(self, ids, callback):
            assert ids == ["main", "dialog"]
            callback(len(ids), None)

    results = []
    launcher = Launcher(KWin(), Resolver(), lambda _: None)
    launcher.recall([{"app_id": "kate"}], results.append)
    assert results == [None]


@pytest.mark.parametrize("ambiguous", [False, True])
def test_geometry_only_targets_unique_new_windows(monkeypatch, ambiguous):
    class Timer:
        @staticmethod
        def singleShot(delay, callback):
            callback()

    class Resolver:
        def enrich(self, windows):
            return windows

    class KWin:
        def __init__(self):
            self.calls = 0
            self.placements = None

        def snapshot(self, callback, main_only=True):
            self.calls += 1
            windows = [{"app_id": "other", "title": "Unrelated", "window_id": "old"}]
            if self.calls > 1:
                windows.append({"app_id": "kate", "title": "New document", "window_id": "new"})
                if ambiguous:
                    windows.append({"app_id": "kate", "title": "Another document", "window_id": "other-new"})
            callback(windows, None)

        def restore(self, placements, callback):
            self.placements = placements
            callback(len(placements), None)

    monkeypatch.setattr("backend.launcher.QTimer", Timer)
    kwin = KWin()
    launcher = Launcher(kwin, Resolver(), lambda _: None)
    activations = []

    def activate(window, callback):
        activations.append(window["app_id"])
        callback(None)

    monkeypatch.setattr(launcher, "activate", activate)
    results = []
    launcher.launch([dict(app_id="kate", title="Captured", x=-900, y=10, w=800, h=600)], results.append)
    assert activations == ["kate"]
    if ambiguous:
        assert kwin.placements == []
        assert "No unique new window" in results[0]
    else:
        assert results == [None]
        assert kwin.placements == [dict(window_id="new", x=-900, y=10, w=800, h=600)]


def test_live_unknown_pid_does_not_infer_process_from_desktop(tmp_path):
    desktop = tmp_path / "app.desktop"
    desktop.write_text("[Desktop Entry]\nType=Application\nExec=/usr/bin/true\n")
    row = {"app_id": "app", "pid": 0, "desktop_file": str(desktop)}
    DesktopResolver().enrich([row])
    assert row["process"] == ""


@pytest.mark.parametrize("activatable,bus_error", [(True, None), (True, "activation failed"), (False, None)])
def test_desktop_activation_and_kstart_fallback(tmp_path, monkeypatch, activatable, bus_error):
    desktop = tmp_path / "org.example.App.desktop"
    desktop.write_text("[Desktop Entry]\nType=Application\nExec=/usr/bin/true\n"
                       + f"DBusActivatable={str(activatable).lower()}\n")
    calls, processes, results = [], [], []

    class KWin:
        def call(self, service, path, interface, method, arguments, callback):
            calls.append((service, path, interface, method, arguments))
            callback([], bus_error)

    class Process:
        @staticmethod
        def startDetached(command, arguments):
            processes.append((command, arguments))
            return True, 123

    monkeypatch.setattr("backend.launcher.QProcess", Process)
    monkeypatch.setattr("backend.launcher.shutil.which", lambda _: "/usr/bin/kstart")
    launcher = Launcher(KWin(), DesktopResolver(), lambda _: None)
    launcher.activate({"desktop_file": str(desktop)}, results.append)
    assert results == [None]
    if activatable:
        assert calls == [("org.example.App", "/org/example/App", "org.freedesktop.Application", "Activate", [{}])]
    else:
        assert calls == []
    assert processes == ([] if activatable and not bus_error else [
        ("/usr/bin/kstart", ["--application", str(desktop)])])


def test_launch_attempts_every_app_even_after_failure(monkeypatch):
    class Resolver:
        def enrich(self, windows):
            return windows

    class KWin:
        def snapshot(self, callback, main_only=True):
            callback([], None)

    launcher = Launcher(KWin(), Resolver(), lambda _: None)
    calls, results = [], []

    def activate(window, callback):
        calls.append(window["app_id"])
        callback("Cannot launch " + window["app_id"])

    monkeypatch.setattr(launcher, "activate", activate)
    launcher.launch([{"app_id": "one"}, {"app_id": "two"}, {"app_id": "ONE"}], results.append)
    assert calls == ["one", "two"]
    assert results == ["Cannot launch one; Cannot launch two"]
