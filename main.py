"""Rift entry point. Run using .venv/bin/python main.py."""

import configparser
import logging
import os
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".runtime"
RUNTIME.mkdir(exist_ok=True)
os.environ["XDG_CACHE_HOME"] = str(RUNTIME / "cache")
os.environ["QT_QML_DISK_CACHE_PATH"] = str(RUNTIME / "cache/qml")
os.environ["TMPDIR"] = str(RUNTIME / "tmp")
(RUNTIME / "tmp").mkdir(exist_ok=True)
# Kirigami and the Plasma platform theme are supplied by Fedora, not pip.
SYSTEM_QT = Path("/usr/lib64/qt6")
os.environ["QT_PLUGIN_PATH"] = os.pathsep.join(filter(None, [
    str(SYSTEM_QT / "plugins"), os.environ.get("QT_PLUGIN_PATH", "")]))

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Property, Signal, Slot, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from backend.kwin import KWin
from backend.launcher import DesktopResolver, Launcher
from backend.storage import Storage
from backend.tray import Tray

LOG = logging.getLogger(__name__)


class Controller(QObject):
    changed = Signal()
    statusChanged = Signal()
    busyChanged = Signal()
    pickerChanged = Signal()
    pickerReady = Signal()
    picksChanged = Signal()

    def __init__(self, storage, kwin, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.launcher = Launcher(kwin, DesktopResolver(), self.report)
        self._selected = 0
        self._busy = False
        self._status = "Ready. Capture main windows to create a group."
        self.tray = None
        self._candidates = []
        self._picker_group = 0
        self._picker_name = ""
        self._picked = set()

    @Property("QVariantList", notify=pickerChanged)
    def candidates(self):
        return self._candidates

    @Property(str, notify=pickerChanged)
    def pickerName(self):
        return self._picker_name

    @Property("QVariantList", notify=picksChanged)
    def pickedIndices(self):
        return sorted(self._picked)

    @Property(int, notify=picksChanged)
    def pickedCount(self):
        return len(self._picked)

    @Property("QVariantList", notify=changed)
    def groups(self):
        return self.storage.groups()

    @Property("QVariantList", notify=changed)
    def windows(self):
        return self.storage.windows(self._selected)

    @Property(str, notify=changed)
    def groupName(self):
        return next((g["name"] for g in self.groups if g["id"] == self._selected), "")

    @Property(int, notify=changed)
    def selected(self):
        return self._selected

    @Property(str, notify=statusChanged)
    def status(self):
        return self._status

    @Property(bool, notify=busyChanged)
    def busy(self):
        return self._busy

    def report(self, text):
        self._status = text
        LOG.info(text)
        self.statusChanged.emit()

    def refresh(self):
        self.changed.emit()
        if self.tray:
            self.tray.refresh(self.groups)

    @Slot(int)
    def select(self, group_id):
        self._selected = group_id
        self.changed.emit()

    def edit(self, action):
        if self.busy:
            return
        try:
            action()
            self.refresh()
        except (ValueError, OSError, sqlite3.Error) as exc:
            self.report(str(exc))

    @Slot(str)
    def rename(self, name):
        self.edit(lambda: self.storage.rename(self._selected, name))

    @Slot()
    def deleteGroup(self):
        def remove():
            self.storage.delete(self._selected)
            self._selected = 0
        self.edit(remove)

    @Slot(int)
    def removeWindow(self, window_id):
        self.edit(lambda: self.storage.remove_window(self._selected, window_id))

    @Slot(int, str, str, str, str)
    def updateWindow(self, window_id, desktop_file, app_id, title, process):
        if process and not Path(process).is_absolute():
            self.report("Process override must be an absolute executable path.")
            return
        self.edit(lambda: self.storage.update_window(self._selected, window_id,
                                                     desktop_file, app_id, title, process))

    def begin(self):
        if self.busy:
            return False
        self._busy = True
        self.busyChanged.emit()
        return True

    def done(self, error=None):
        self._busy = False
        self.busyChanged.emit()
        if error:
            LOG.error(error)
            self.report(error)
        else:
            self.report("Operation complete. Review the session log for matching warnings.")

    @Slot(str, int)
    def capture(self, name, group_id):
        if not group_id and not name.strip():
            self.report("Enter a group name first.")
            return
        if not self.begin():
            return

        def captured(windows, error):
            if error:
                self.done(error)
                return
            if not windows:
                self.done("No main windows found; no group was changed.")
                return
            self.save_capture(name, windows, group_id)
        self.launcher.snapshot(captured)

    def save_capture(self, name, windows, group_id):
        try:
            before = len(self.storage.windows(group_id)) if group_id else 0
            self._selected = self.storage.capture(name, windows, group_id)
            added = len(self.storage.windows(self._selected)) - before
            skipped = len(windows) - added
            self.refresh()
            self.done()
            unresolved = [w["title"] for w in windows if not w.get("app_id") or not w.get("desktop_file")]
            self.report(f"Added {added} main windows."
                + (f" Skipped {skipped} already-saved windows." if skipped else "")
                + (" Review app identity/desktop-file overrides for: " + ", ".join(unresolved) if unresolved else ""))
            return True
        except (ValueError, OSError, sqlite3.Error) as exc:
            self.done(str(exc))
            return False

    @Slot(int)
    @Slot(int, str)
    def preparePicker(self, group_id, name=""):
        if not group_id and not name.strip():
            self.report("Enter a group name first.")
            return
        if not self.begin():
            return
        self.cancelPicker()

        def captured(windows, error):
            if error:
                self.done(error)
                return
            self._picker_group = group_id
            self._picker_name = name.strip() if not group_id else ""
            for index, window in enumerate(windows):
                app_name = window.get("app_id") or "Unknown app"
                if window.get("desktop_file"):
                    try:
                        app_name = self.launcher.resolver.entry(window["desktop_file"]).get("Name", app_name)
                    except (ValueError, OSError, configparser.Error):
                        pass  # Unresolved launchers must not prevent selecting a window.
                self._candidates.append(dict(window, candidate_index=index, app_name=app_name))
            self.pickerChanged.emit()
            self.done()
            self.report("Choose windows to save. Nothing is saved until you confirm the selection.")
            self.pickerReady.emit()

        self.launcher.snapshot(captured)

    @Slot(int, bool)
    def setPicked(self, index, picked):
        if 0 <= index < len(self._candidates):
            if picked:
                self._picked.add(index)
            else:
                self._picked.discard(index)
            self.picksChanged.emit()

    @Slot()
    def cancelPicker(self):
        self._candidates = []
        self._picker_group = 0
        self._picker_name = ""
        self._picked.clear()
        self.pickerChanged.emit()
        self.picksChanged.emit()

    @Slot(result=bool)
    def addPicked(self):
        windows = [w for index, w in enumerate(self._candidates) if index in self._picked]
        if not windows or not (self._picker_group or self._picker_name) or not self.begin():
            return False
        if not self.save_capture(self._picker_name, windows, self._picker_group):
            return False
        self.cancelPicker()
        return True

    def group_action(self, group_id, action):
        if not self.begin():
            return
        try:
            action(self.storage.windows(group_id), self.done)
        except (ValueError, OSError, sqlite3.Error, configparser.Error) as exc:
            self.done(str(exc))

    @Slot(int)
    def launch(self, group_id):
        self.group_action(group_id, self.launcher.launch)

    @Slot(int)
    def recall(self, group_id):
        self.group_action(group_id, self.launcher.recall)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not (SYSTEM_QT / "qml/org/kde/kirigami/qmldir").is_file():
        LOG.error("Kirigami is missing. On Fedora 44, install kf6-kirigami yourself; Rift installs no system packages.")
        return 1
    QQuickStyle.setStyle("org.kde.desktop")
    app = QApplication(sys.argv)
    app.setApplicationName("rift")
    app.setApplicationDisplayName("Rift")
    app.setDesktopFileName("org.rift.Application")
    app.setWindowIcon(QIcon(str(ROOT / "logos/rift.png")))
    storage = Storage(ROOT / "rift.sqlite3")
    try:
        kwin = KWin(RUNTIME, app)
    except RuntimeError as exc:
        LOG.error("%s", exc)
        storage.close()
        return 1
    controller = Controller(storage, kwin, app)
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(SYSTEM_QT / "qml"))
    engine.rootContext().setContextProperty("rift", controller)
    engine.load(QUrl.fromLocalFile(str(ROOT / "qml/main.qml")))
    if not engine.rootObjects():
        kwin.shutdown()
        storage.close()
        return 1
    window = engine.rootObjects()[0]
    tray = Tray(window, controller.launch, app)
    controller.tray = tray
    tray.refresh(controller.groups)
    tray_available = QSystemTrayIcon.isSystemTrayAvailable()
    window.setProperty("trayAvailable", tray_available)
    app.setQuitOnLastWindowClosed(not tray_available)
    if tray_available:
        tray.show()
    else:
        controller.report("System tray unavailable; closing the window will quit Rift.")
    result = app.exec()
    tray.hide()
    kwin.shutdown()
    engine.deleteLater()
    QCoreApplication.sendPostedEvents(engine, QEvent.DeferredDelete)
    storage.close()
    return result


if __name__ == "__main__":
    sys.exit(main())
