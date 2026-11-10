import logging
from pathlib import Path
import sys
import time

import pytest

from backend.launcher import DesktopResolver, Launcher, dedupe, match_key, matches


class Resolver:
    def enrich(self, windows):
        return windows


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


@pytest.mark.parametrize("content", [b"\x7fELF\x02\x01\xdd", b"[Desktop Entry]\nName=\xdd\n"])
def test_invalid_desktop_encoding_reports_expected_format(tmp_path, content):
    desktop = tmp_path / "invalid.desktop"
    desktop.write_bytes(content)
    results = []
    Launcher(None, DesktopResolver(), lambda _: None).activate({"desktop_file": str(desktop)}, results.append)
    assert len(results) == 1
    assert "Expected UTF-8 desktop-entry text" in results[0]


def test_launch_skips_running_and_dedupes_without_kwin_writes():
    class KWin:
        def snapshot(self, callback, main_only=True):
            callback([{"app_id": "kate", "window_id": "existing"}], None)

    messages, results = [], []
    launcher = Launcher(KWin(), Resolver(), messages.append)
    launcher.launch([{"app_id": "kate"}, {"app_id": "KATE"}], results.append)
    assert results == [None]
    assert "Launching 0 apps; skipping 1" in messages[0]


def test_recall_only_requests_matching_windows_including_dialogs():
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
@pytest.mark.parametrize("outside_roots", [False, True])
@pytest.mark.parametrize("relative_name", ["org.kde.konsole.desktop", "nested/ai.opencode.desktop"])
def test_desktop_activation_and_file_fallbacks(tmp_path, monkeypatch, activatable, bus_error, outside_roots, relative_name):
    resolver = DesktopResolver()
    resolver.roots = [tmp_path / "applications"]
    directory = tmp_path / "opt/Open Code #1" if outside_roots else resolver.roots[0]
    desktop = directory / relative_name
    desktop.parent.mkdir(parents=True)
    desktop.write_text("[Desktop Entry]\nType=Application\nExec=/usr/bin/true\n"
                       + f"DBusActivatable={str(activatable).lower()}\n")
    assert desktop.is_absolute()
    assert desktop.is_relative_to(resolver.roots[0]) == (not outside_roots)
    resolved = resolver.resolve(str(desktop))
    assert resolved == str(desktop)
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
    monkeypatch.setattr("backend.launcher.shutil.which", lambda name: {
        "kstart": "/usr/bin/kstart", "kioclient": "/usr/bin/kioclient"}.get(name))
    launcher = Launcher(KWin(), resolver, lambda _: None)

    def run_helper(program, arguments, callback):
        processes.append((program, arguments))
        callback(None)

    monkeypatch.setattr(launcher, "run_helper", run_helper)
    launcher.activate({"desktop_file": resolved}, results.append)
    assert results == [None]
    desktop_id = Path(relative_name).stem if outside_roots else relative_name.removesuffix(".desktop").replace("/", "-")
    if activatable:
        object_path = "/" + desktop_id.replace(".", "/").replace("-", "_")
        assert calls == [(desktop_id, object_path, "org.freedesktop.Application", "Activate", [{}])]
    else:
        assert calls == []
    if activatable and not bus_error:
        assert processes == []
    elif outside_roots:
        assert processes == [("/usr/bin/kioclient", ["exec", desktop.as_uri(), "application/x-desktop"])]
    else:
        assert processes == [("/usr/bin/kstart", ["--application", desktop_id])]


def test_absolute_path_does_not_launch_shadowing_xdg_entry(tmp_path, monkeypatch):
    resolver = DesktopResolver()
    resolver.roots = [tmp_path / "local", tmp_path / "system"]
    for root in resolver.roots:
        root.mkdir()
        (root / "org.kde.konsole.desktop").write_text("[Desktop Entry]\nType=Application\nExec=konsole\n")
    desktop = resolver.roots[1] / "org.kde.konsole.desktop"
    assert resolver.resolve("org.kde.konsole") != str(desktop)
    monkeypatch.setattr("backend.launcher.shutil.which", lambda name: "/usr/bin/kioclient" if name == "kioclient" else None)
    launcher = Launcher(None, resolver, lambda _: None)
    calls, results = [], []

    def run_helper(program, arguments, callback):
        calls.append((program, arguments))
        callback(None)

    monkeypatch.setattr(launcher, "run_helper", run_helper)
    launcher.activate({"desktop_file": str(desktop)}, results.append)
    assert results == [None]
    assert calls == [("/usr/bin/kioclient", ["exec", desktop.as_uri(), "application/x-desktop"])]


@pytest.mark.parametrize("outside_roots", [False, True])
def test_missing_launch_helper_is_reported(tmp_path, monkeypatch, outside_roots):
    resolver = DesktopResolver()
    resolver.roots = [tmp_path / "applications"]
    directory = tmp_path / "external" if outside_roots else resolver.roots[0]
    directory.mkdir()
    desktop = directory / "app.desktop"
    desktop.write_text("[Desktop Entry]\nType=Application\nExec=app\n")
    monkeypatch.setattr("backend.launcher.shutil.which", lambda _: None)
    results = []
    Launcher(None, resolver, lambda _: None).activate({"desktop_file": str(desktop)}, results.append)
    assert len(results) == 1
    assert ("kioclient" if outside_roots else "kstart") + " is missing" in results[0]


@pytest.mark.parametrize("case", ["success", "nonzero", "invalid_stderr", "start_failure"])
def test_real_helper_process_reports_result_without_launching_apps(app, tmp_path, case):
    from PySide6.QtTest import QTest

    launcher = Launcher(None, None, lambda _: None)
    results = []
    program = str(tmp_path / "missing-helper") if case == "start_failure" else sys.executable
    script = {
        "success": "pass",
        "nonzero": "import sys; sys.stderr.write('Desktop launch refused'); sys.exit(1)",
        "invalid_stderr": "import sys; sys.stderr.buffer.write(bytes([221])); sys.exit(1)",
        "start_failure": "pass",
    }[case]
    launcher.run_helper(program, ["-c", script], results.append)
    deadline = time.monotonic() + 5
    while not results and time.monotonic() < deadline:
        QTest.qWait(10)
    assert len(results) == 1
    assert not launcher.processes
    if case == "success":
        assert results == [None]
    elif case == "start_failure":
        assert "Cannot start" in results[0]
    elif case == "nonzero":
        assert "Desktop launch refused" in results[0]
    else:
        assert "failed:" in results[0]


def test_launch_attempts_every_app_even_after_failure(monkeypatch):
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
