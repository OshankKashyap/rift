import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_CACHE_HOME"] = str(ROOT / ".runtime/cache")
os.environ["QT_QML_DISK_CACHE_PATH"] = str(ROOT / ".runtime/cache/qml")
os.environ["TMPDIR"] = str(ROOT / ".runtime/tmp")


@pytest.fixture(scope="session")
def app():
    from PySide6.QtQuickControls2 import QQuickStyle
    from PySide6.QtWidgets import QApplication

    QQuickStyle.setStyle("org.kde.desktop")
    application = QApplication.instance() or QApplication([])
    yield application
