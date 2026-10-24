"""Exact app identities, desktop activation, and group lifecycle orchestration."""

import configparser
import logging
import os
from pathlib import Path
import shlex
import shutil

from PySide6.QtCore import QProcess, QTimer

LOG = logging.getLogger(__name__)


def normalized(value):
    value = str(value or "").strip().casefold()
    return value.removesuffix(".desktop")


def match_key(window):
    overrides = tuple(window.get(k, "").strip() for k in
                      ("match_app_id", "match_title", "match_process"))
    if any(overrides):
        return ("override", normalized(overrides[0]), overrides[1], overrides[2])
    if window.get("app_id"):
        return ("app", normalized(window["app_id"]))
    if window.get("desktop_file"):
        return ("desktop", str(Path(window["desktop_file"])))
    if window.get("title"):
        return ("title", window["title"])
    raise ValueError("Window has no usable identity; set a manual match override.")


def dedupe(windows):
    unique = {}
    for window in windows:
        unique.setdefault(match_key(window), window)
    return list(unique.values())


def matches(stored, live):
    app, title, process = (stored.get(k, "").strip() for k in
                           ("match_app_id", "match_title", "match_process"))
    if app or title or process:
        return ((not app or normalized(app) == normalized(live.get("app_id")))
                and (not title or title == live.get("title"))
                and (not process or process == live.get("process")))
    if stored.get("app_id") and normalized(stored["app_id"]) == normalized(live.get("app_id")):
        return True
    if stored.get("desktop_file") and stored["desktop_file"] == live.get("desktop_file"):
        if normalized(stored.get("app_id")) != normalized(live.get("app_id")):
            LOG.warning("AppId unreliable for %r; matched exact desktop file. Review overrides.", stored.get("title"))
        return True
    # /proc/<KWin PID>/exe supplies an exact executable, not a guessed process name.
    if (stored.get("process") and stored["process"] == live.get("process")
            and stored.get("title") and stored["title"] == live.get("title")):
        LOG.warning("AppId unreliable for %r; matched exact process executable. Review overrides.", stored.get("title"))
        return True
    if (not stored.get("app_id") or not live.get("app_id")) and stored.get("title") == live.get("title") and stored.get("title"):
        LOG.warning("AppId unavailable for %r; using exact title. Set a manual override.", stored["title"])
        return True
    return False


class DesktopResolver:
    def __init__(self):
        data_home = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))
        self.roots = [Path(p) / "applications" for p in
                      [data_home, *os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")]]

    def resolve(self, hint):
        if not hint:
            return ""
        path = Path(hint)
        if path.is_absolute():
            return str(path) if path.is_file() and path.suffix == ".desktop" else ""
        if "/" in hint or hint in (".", ".."):
            return ""
        name = hint if hint.endswith(".desktop") else hint + ".desktop"
        for root in self.roots:
            direct = root / name
            if direct.is_file():
                return str(direct)
            # Desktop IDs flatten subdirectories using '-', as specified by XDG.
            if root.is_dir():
                for candidate in root.rglob("*.desktop"):
                    if str(candidate.relative_to(root)).replace("/", "-") == name:
                        return str(candidate)
        return ""

    def entry(self, path):
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        parser.read(path, encoding="utf-8")
        if not parser.has_section("Desktop Entry"):
            raise ValueError(f"Invalid desktop file: {path}")
        entry = parser["Desktop Entry"]
        if entry.get("Type", "Application") != "Application" or entry.getboolean("Hidden", False):
            raise ValueError(f"Desktop file is not a launchable application: {path}")
        return entry

    def executable(self, path):
        if not path:
            return ""
        command = shlex.split(self.entry(path).get("Exec", ""))
        if not command or command[0] == "env":
            return ""
        executable = shutil.which(command[0])
        return str(Path(executable).resolve()) if executable else ""

    def enrich(self, windows):
        for window in windows:
            window["desktop_file"] = self.resolve(window.get("desktop_file") or
                window.get("desktop_hint") or window.get("app_id"))
            if "pid" in window:
                try:
                    pid = int(window["pid"])
                    window["process"] = str(Path(f"/proc/{pid}/exe").resolve(strict=True)) if pid > 0 else ""
                except (OSError, ValueError):
                    window["process"] = ""
            else:
                try:
                    window["process"] = self.executable(window["desktop_file"])
                except (ValueError, configparser.Error):
                    window["process"] = ""
            if not window.get("app_id"):
                LOG.warning("Missing appId for %r; review manual matching overrides.", window.get("title"))
        return windows


class Launcher:
    def __init__(self, kwin, resolver, report):
        self.kwin = kwin
        self.resolver = resolver
        self.report = report

    def snapshot(self, callback, main_only=True):
        def received(windows, error):
            if error:
                callback(None, error)
                return
            try:
                windows = self.resolver.enrich(windows)
            except (OSError, ValueError, configparser.Error) as exc:
                callback(None, str(exc))
                return
            callback(windows, None)
        self.kwin.snapshot(received, main_only=main_only)

    def activate(self, window, callback):
        path = window.get("desktop_file")
        if not path:
            callback("No desktop file for " + window.get("title", "app") + "; set it in the editor.")
            return
        try:
            entry = self.resolver.entry(path)
            activatable = entry.getboolean("DBusActivatable", False)
        except (ValueError, configparser.Error, OSError) as exc:
            callback(str(exc))
            return

        def fallback(*_):
            kstart = shutil.which("kstart") or shutil.which("kstart6")
            if not kstart:
                callback("kstart is missing. Ask the user to install Fedora's plasma-workspace package.")
                return
            ok, _pid = QProcess.startDetached(kstart, ["--application", path])
            callback(None if ok else f"kstart could not launch {path}")

        if not activatable:
            fallback()
            return
        desktop_id = Path(path).stem
        for root in self.resolver.roots:
            if Path(path).is_relative_to(root):
                desktop_id = str(Path(path).relative_to(root)).removesuffix(".desktop").replace("/", "-")
                break
        object_path = "/" + desktop_id.replace(".", "/").replace("-", "_")
        self.kwin.call(desktop_id, object_path, "org.freedesktop.Application", "Activate", [{}],
                       lambda _, error: fallback() if error else callback(None))

    def launch(self, stored, done):
        stored = self.resolver.enrich(stored)
        apps = dedupe(stored)

        def captured(live, error):
            if error:
                done(error)
                return
            todo = [w for w in apps if not any(matches(w, v) for v in live)]
            skipped = len(apps) - len(todo)
            self.report(f"Launching {len(todo)} apps; skipping {skipped} already running.")
            original_ids = {w["window_id"] for w in live}
            launched = []
            errors = []

            def next_app(index=0):
                if index == len(todo):
                    if not launched:
                        done("; ".join(errors) or None)
                        return
                    QTimer.singleShot(1000, lambda: settle(0))
                    return

                def activated(err):
                    if err:
                        errors.append(err)
                        self.report(err)
                    else:
                        launched.append(todo[index])
                    next_app(index + 1)
                self.activate(todo[index], activated)

            def settle(attempt):
                def received(current, err):
                    if err:
                        done(err)
                        return
                    fresh = [v for v in current if v["window_id"] not in original_ids]
                    placements = []
                    missing = []
                    used = set()
                    launched_keys = {match_key(app) for app in launched}
                    rows = [row for row in stored if match_key(row) in launched_keys]
                    # Reserve exact-title matches before considering a single remaining window.
                    rows.sort(key=lambda row: not any(matches(row, v) and v["title"] == row["title"] for v in fresh))
                    for app in rows:
                        candidates = [v for v in fresh if matches(app, v) and v["window_id"] not in used]
                        exact = [v for v in candidates if v["title"] == app["title"]]
                        if len(exact) == 1:
                            candidates = exact
                        if len(candidates) != 1:
                            missing.append(app["title"])
                            continue
                        target = candidates[0]
                        used.add(target["window_id"])
                        placements.append({"window_id": target["window_id"],
                                           **{k: app[k] for k in ("x", "y", "w", "h")}})
                    if missing and attempt < 11:
                        QTimer.singleShot(500, lambda: settle(attempt + 1))
                        return
                    if missing:
                        errors.append("No unique new window for: " + ", ".join(missing)
                                      + ". Review matching overrides; geometry was not guessed.")
                    self.kwin.restore(placements, lambda _, restore_error:
                        done("; ".join(errors + ([restore_error] if restore_error else [])) or None))
                self.snapshot(received)
            next_app()
        self.snapshot(captured)

    def recall(self, stored, done):
        stored = self.resolver.enrich(stored)

        def captured(live, error):
            if error:
                done(error)
                return
            ids = [v["window_id"] for v in live if any(matches(w, v) for w in stored)]
            def closed(count, err):
                done(err)
                if not err:
                    self.report(f"Sent {count} graceful close requests. Save prompts may remain open.")
            self.kwin.close_windows(ids, closed)
        self.snapshot(captured, main_only=False)
