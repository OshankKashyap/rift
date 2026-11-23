import pytest
from PySide6.QtCore import QObject
from PySide6.QtQml import QQmlApplicationEngine

import main
from backend.storage import Storage
from backend.tray import Tray


@pytest.mark.parametrize("enabled,tray_available,visible", [
    (False, True, True), (True, True, False), (True, False, True),
])
def test_startup_visibility_and_restore(app, tmp_path, monkeypatch, enabled, tray_available, visible):
    path = tmp_path / "startup.sqlite3"
    storage = Storage(path)
    storage.set_session_option("start_in_tray", enabled)
    storage.set_session_option("enabled", True)
    storage.save_session([dict(app_id="test", title="Test", x=0, y=0, w=800, h=600)])
    storage.mark_clean()
    storage.close()

    scheduled = []
    launched = []
    visibility = []
    instances = []

    class Engine(QQmlApplicationEngine):
        def load(self, url):
            super().load(url)
            window = self.rootObjects()[0]
            visibility.append(window.isVisible())
            window.visibleChanged.connect(lambda state: visibility.append(state))

    class TestTray(Tray):
        def __init__(self, *args):
            super().__init__(*args)
            instances.append(self)

        def show(self):
            pass

        def hide(self):
            pass

    class KWin:
        def __init__(self, *_):
            pass

        def shutdown(self):
            pass

    class Signal:
        def connect(self, _):
            pass

    class Application(QObject):
        commitDataRequest = Signal()
        aboutToQuit = Signal()

        def setApplicationName(self, _): pass
        def setApplicationDisplayName(self, _): pass
        def setDesktopFileName(self, _): pass
        def setWindowIcon(self, _): pass
        def setQuitOnLastWindowClosed(self, value):
            assert value is not tray_available

        def exec(self):
            tray = instances[0]
            assert visibility == ([False, True] if visible else [False])
            assert tray.window.isVisible() is visible
            assert len(scheduled) == 1 and scheduled[0][0] == 5000
            scheduled[0][1]()
            assert [row["app_id"] for row in launched] == ["test"]
            if tray_available and enabled:
                tray.menu.actions()[0].trigger()
                assert tray.window.isVisible()
            return 0

    application = Application()
    monkeypatch.setattr(main, "QApplication", lambda _: application)
    monkeypatch.setattr(main, "QQmlApplicationEngine", Engine)
    monkeypatch.setattr(main, "Storage", lambda _: Storage(path))
    monkeypatch.setattr(main, "KWin", KWin)
    monkeypatch.setattr(main, "Tray", TestTray)
    monkeypatch.setattr(main.QSystemTrayIcon, "isSystemTrayAvailable", lambda: tray_available)
    monkeypatch.setattr(main.QTimer, "singleShot", lambda delay, callback: scheduled.append((delay, callback)))
    monkeypatch.setattr(main.Launcher, "launch", lambda _, rows, done: (launched.extend(rows), done(None)))
    assert main.main() == 0
