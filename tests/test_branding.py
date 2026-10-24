from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QIcon, QImage

from backend.tray import Tray
from main import ROOT


def test_branding_assets_load(app):
    icon = QIcon(str(ROOT / "logos/rift.png"))
    assert not icon.isNull()
    for size in (16, 22, 32, 48, 64, 128):
        assert not icon.pixmap(size, size).isNull()
    assert not QImage(str(ROOT / "logos/rift-banner.png")).isNull()


def test_tray_reuses_application_icon(app):
    previous = app.windowIcon()
    tray = None
    try:
        app.setWindowIcon(QIcon(str(ROOT / "logos/rift.png")))
        tray = Tray(None, lambda group_id: None)
        assert tray.icon().cacheKey() == app.windowIcon().cacheKey()
    finally:
        if tray is not None:
            tray.menu.deleteLater()
            tray.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.setWindowIcon(previous)
