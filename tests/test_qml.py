import pytest
from PySide6.QtCore import Q_ARG, QCoreApplication, QEvent, QMetaObject, QObject, Qt, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest

from main import Controller, ROOT, SYSTEM_QT
from backend.storage import Storage


@pytest.fixture
def ui(app):
    storage = Storage(":memory:")
    gid = storage.capture("Work", [dict(app_id="org.kde.kate", title="Notes",
                                       x=0, y=20, w=900, h=700, desktop_file="")])
    controller = Controller(storage, None)
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    engine.addImportPath(str(SYSTEM_QT / "qml"))
    engine.rootContext().setContextProperty("rift", controller)
    engine.load(QUrl.fromLocalFile(str(ROOT / "qml/main.qml")))
    assert engine.rootObjects(), warnings
    window = engine.rootObjects()[0]
    QTest.qWait(50)
    yield window, controller, gid, warnings
    engine.deleteLater()
    QCoreApplication.sendPostedEvents(engine, QEvent.DeferredDelete)
    storage.close()


def test_group_detail_loads_without_qml_errors(ui):
    window, controller, gid, warnings = ui
    assert QMetaObject.invokeMethod(window, "openGroup", Qt.DirectConnection, Q_ARG(int, gid))
    QTest.qWait(100)
    assert controller.selected == gid
    assert window.findChild(QObject, "groupDetail") is not None
    assert not warnings


@pytest.mark.parametrize("name", ["captureDialog", "renameDialog", "deleteDialog", "recallDialog", "overrideDialog"])
def test_dialog_renders_offscreen(ui, name):
    window, controller, gid, warnings = ui
    controller.select(gid)
    dialog = window.findChild(QObject, name)
    assert dialog is not None
    assert QMetaObject.invokeMethod(dialog, "open")
    QTest.qWait(50)
    assert dialog.property("visible")
    assert not warnings


def test_editor_persists_overrides_and_rename(ui):
    _, controller, gid, _ = ui
    controller.select(gid)
    row = controller.windows[0]
    controller.updateWindow(row["id"], "org.kde.kate.desktop", "kate", "Notes", "/usr/bin/kate")
    assert controller.windows[0]["match_app_id"] == "kate"
    assert controller.windows[0]["match_process"] == "/usr/bin/kate"
    controller.rename("Renamed")
    assert controller.groupName == "Renamed"


def test_relative_process_override_is_rejected(ui):
    _, controller, gid, _ = ui
    controller.select(gid)
    row = controller.windows[0]
    controller.updateWindow(row["id"], "", "", "", "kate")
    assert "absolute" in controller.status
    assert controller.windows[0]["match_process"] == ""
