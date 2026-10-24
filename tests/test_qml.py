import pytest
from PySide6.QtCore import Q_ARG, QCoreApplication, QEvent, QMetaObject, QObject, QPointF, Qt, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest

from main import Controller, ROOT, SYSTEM_QT
from backend.storage import Storage


def wait_for_popup(dialog, opened=True):
    for _ in range(100):
        if (dialog.property("opened") if opened else not dialog.property("visible")):
            return
        QTest.qWait(10)
    pytest.fail("Popup did not finish opening" if opened else "Popup did not finish closing")


def click_button(window, button):
    position = button.mapToScene(QPointF(button.width() / 2, button.height() / 2)).toPoint()
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, position)


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


@pytest.mark.parametrize("name", ["captureDialog", "renameDialog", "deleteDialog", "recallDialog", "overrideDialog", "removeDialog"])
def test_dialog_renders_offscreen(ui, name):
    window, controller, gid, warnings = ui
    controller.select(gid)
    dialog = window.findChild(QObject, name)
    assert dialog is not None
    assert QMetaObject.invokeMethod(dialog, "open")
    wait_for_popup(dialog)
    assert dialog.property("visible")
    assert not warnings


@pytest.mark.parametrize("size", [(640, 460), (940, 680)])
@pytest.mark.parametrize("name", ["captureDialog", "renameDialog", "overrideDialog"])
def test_dialog_fields_stay_within_bounds(ui, size, name):
    window, controller, gid, warnings = ui
    window.resize(*size)
    controller.select(gid)
    dialog = window.findChild(QObject, name)
    QMetaObject.invokeMethod(dialog, "open")
    wait_for_popup(dialog)
    assert dialog.property("x") >= 0
    assert dialog.property("y") >= 0
    assert dialog.property("x") + dialog.property("width") <= window.width() + 1
    assert dialog.property("y") + dialog.property("height") <= window.height() + 1
    field = dialog.findChild(QObject, "desktopFile" if name == "overrideDialog" else "nameField")
    content = dialog.property("contentItem")
    position = field.mapToItem(content, QPointF(0, 0))
    assert position.x() >= -1
    assert position.x() + field.width() <= content.width() + 1
    if name != "overrideDialog":
        assert position.y() >= -1
        assert position.y() + field.height() <= content.height() + 1
    else:
        scroll = dialog.findChild(QObject, "editorScroll")
        assert scroll.property("contentHeight") > 0
        if size == (640, 460):
            assert scroll.property("contentHeight") > scroll.property("availableHeight")
    assert not warnings


@pytest.mark.parametrize("name", ["captureDialog", "renameDialog"])
@pytest.mark.parametrize("text", ["", "   "])
def test_name_dialog_blocks_empty_submission(ui, name, text):
    window, controller, gid, warnings = ui
    controller.select(gid)
    dialog = window.findChild(QObject, name)
    dialog.setProperty("text", text)
    QMetaObject.invokeMethod(dialog, "open")
    wait_for_popup(dialog)
    button = dialog.findChild(QObject, "nameAcceptButton")
    assert not button.property("enabled")
    QTest.keyClick(window, Qt.Key_Return)
    assert dialog.property("visible")
    assert controller.groupName == "Work"
    assert not controller.busy
    assert not warnings


@pytest.mark.parametrize("use_keyboard", [False, True])
def test_capture_submit_creates_and_opens_group(ui, monkeypatch, use_keyboard):
    window, controller, _, warnings = ui
    monkeypatch.setattr(controller.launcher, "snapshot", lambda callback: callback([
        dict(app_id="test", title="Test window", x=0, y=0, w=800, h=600, desktop_file="")], None))
    QMetaObject.invokeMethod(window, "startCapture")
    dialog = window.findChild(QObject, "captureDialog")
    dialog.setProperty("text", "  Study  ")
    wait_for_popup(dialog)
    if use_keyboard:
        QTest.keyClick(window, Qt.Key_Return)
    else:
        button = dialog.findChild(QObject, "nameAcceptButton")
        click_button(window, button)
    wait_for_popup(dialog, opened=False)
    assert not dialog.property("visible")
    assert controller.groupName == "Study"
    assert len(controller.groups) == 2
    assert len(controller.windows) == 1
    assert window.findChild(QObject, "groupPages").property("depth") == 2
    assert not warnings


def test_rename_keyboard_submit_and_escape_cancel(ui):
    window, controller, gid, warnings = ui
    controller.select(gid)
    dialog = window.findChild(QObject, "renameDialog")
    dialog.setProperty("text", "  New name  ")
    QMetaObject.invokeMethod(dialog, "open")
    wait_for_popup(dialog)
    QTest.keyClick(window, Qt.Key_Return)
    wait_for_popup(dialog, opened=False)
    assert controller.groupName == "New name"
    dialog.setProperty("text", "Do not save")
    QMetaObject.invokeMethod(dialog, "open")
    wait_for_popup(dialog)
    QTest.keyClick(window, Qt.Key_Escape)
    wait_for_popup(dialog, opened=False)
    assert not dialog.property("visible")
    assert controller.groupName == "New name"
    assert not warnings


def test_group_switch_reuses_detail_page(ui):
    window, controller, gid, warnings = ui
    second = controller.storage.capture("Second", [])
    controller.refresh()
    for group in (gid, second, gid):
        QMetaObject.invokeMethod(window, "openGroup", Qt.DirectConnection, Q_ARG(int, group))
        QTest.qWait(50)
        assert window.findChild(QObject, "groupPages").property("depth") == 2
        assert controller.selected == group
    assert len(window.findChildren(QObject, "groupDetail")) == 1
    QMetaObject.invokeMethod(window, "openGroup", Qt.DirectConnection, Q_ARG(int, second))
    QTest.qWait(50)
    assert window.findChild(QObject, "emptyGroupPlaceholder").property("visible")
    assert not window.findChild(QObject, "launchGroupButton").property("enabled")
    assert not warnings


def test_matching_form_validates_relative_process_path(ui):
    window, _, _, warnings = ui
    dialog = window.findChild(QObject, "overrideDialog")
    QMetaObject.invokeMethod(dialog, "open")
    field = dialog.findChild(QObject, "matchProcess")
    button = dialog.findChild(QObject, "matchingSaveButton")
    field.setProperty("text", "kate")
    assert not button.property("enabled")
    field.setProperty("text", "/usr/bin/kate")
    assert button.property("enabled")
    field.setProperty("text", "")
    assert button.property("enabled")
    assert not warnings


def test_recall_warning_explains_app_wide_scope(ui):
    window, _, _, warnings = ui
    dialog = window.findChild(QObject, "recallDialog")
    QMetaObject.invokeMethod(dialog, "open")
    warning = dialog.findChild(QObject, "recallWarning")
    assert "ALL running windows" in warning.property("text")
    assert "not captured" in warning.property("text")
    assert not warnings


def test_remove_confirmation_only_removes_saved_entry(ui):
    window, controller, gid, warnings = ui
    controller.select(gid)
    window.setProperty("removeId", controller.windows[0]["id"])
    window.setProperty("removeTitle", "A very long window title " * 40)
    dialog = window.findChild(QObject, "removeDialog")
    QMetaObject.invokeMethod(dialog, "open")
    wait_for_popup(dialog)
    QMetaObject.invokeMethod(dialog, "accept")
    wait_for_popup(dialog, opened=False)
    assert controller.windows == []
    assert len(controller.groups) == 1
    assert not warnings


def test_delete_group_returns_to_empty_group_list(ui):
    window, controller, gid, warnings = ui
    controller.select(gid)
    dialog = window.findChild(QObject, "deleteDialog")
    QMetaObject.invokeMethod(dialog, "open")
    wait_for_popup(dialog)
    QMetaObject.invokeMethod(dialog, "accept")
    wait_for_popup(dialog, opened=False)
    assert controller.groups == []
    assert controller.selected == 0
    assert window.findChild(QObject, "groupPages").property("depth") == 1
    assert window.findChild(QObject, "groupPlaceholder").property("visible")
    assert not warnings


@pytest.mark.parametrize("name", ["deleteDialog", "recallDialog", "removeDialog"])
def test_confirmation_defaults_to_cancel(ui, name):
    window, controller, gid, warnings = ui
    controller.select(gid)
    dialog = window.findChild(QObject, name)
    QMetaObject.invokeMethod(dialog, "open")
    wait_for_popup(dialog)
    assert window.activeFocusItem().property("text") == "Cancel"
    QTest.keyClick(window, Qt.Key_Space)
    wait_for_popup(dialog, opened=False)
    assert len(controller.groups) == 1
    assert len(controller.windows) == 1
    assert not controller.busy
    assert not warnings


def test_long_status_does_not_take_over_window(ui):
    window, controller, gid, warnings = ui
    window.resize(640, 460)
    controller.select(gid)
    controller.report("A long diagnostic message. " * 100)
    QTest.qWait(100)
    footer = window.property("footer")
    assert footer.height() < window.height() / 3
    assert window.findChild(QObject, "statusText").property("text") == controller.status
    assert not warnings


def test_editor_persists_overrides_and_rename(ui):
    window, controller, gid, warnings = ui
    controller.select(gid)
    row = controller.windows[0]
    dialog = window.findChild(QObject, "overrideDialog")
    dialog.setProperty("windowId", row["id"])
    dialog.findChild(QObject, "desktopFile").setProperty("text", "org.kde.kate.desktop")
    dialog.findChild(QObject, "matchApp").setProperty("text", "kate")
    dialog.findChild(QObject, "matchTitle").setProperty("text", "Notes")
    dialog.findChild(QObject, "matchProcess").setProperty("text", "  /usr/bin/kate  ")
    QMetaObject.invokeMethod(dialog, "open")
    wait_for_popup(dialog)
    click_button(window, dialog.findChild(QObject, "matchingSaveButton"))
    wait_for_popup(dialog, opened=False)
    assert controller.windows[0]["match_app_id"] == "kate"
    assert controller.windows[0]["match_process"] == "/usr/bin/kate"
    assert controller.windows[0]["desktop_file"] == "org.kde.kate.desktop"
    controller.rename("Renamed")
    assert controller.groupName == "Renamed"
    assert not warnings


def test_relative_process_override_is_rejected(ui):
    _, controller, gid, _ = ui
    controller.select(gid)
    row = controller.windows[0]
    controller.updateWindow(row["id"], "", "", "", "kate")
    assert "absolute" in controller.status
    assert controller.windows[0]["match_process"] == ""


def prepare_picker(ui, monkeypatch, count=3):
    window, controller, gid, _ = ui
    rows = [dict(app_id="org.kde.konsole", title=f"Terminal {i}",
                 x=i * 10, y=20, w=800, h=600, desktop_file="") for i in range(count)]
    monkeypatch.setattr(controller.launcher, "snapshot", lambda callback: callback(rows, None))
    controller.select(gid)
    QTest.qWait(50)
    click_button(window, window.findChild(QObject, "selectWindowsButton"))
    dialog = window.findChild(QObject, "windowPicker")
    wait_for_popup(dialog)
    return dialog


@pytest.mark.parametrize("size", [(640, 460), (940, 680)])
def test_picker_filters_keeps_selection_and_appends_only_checked(ui, monkeypatch, size):
    window, controller, gid, warnings = ui
    window.resize(*size)
    dialog = prepare_picker(ui, monkeypatch, count=40)
    assert dialog.property("x") >= 0 and dialog.property("y") >= 0
    assert dialog.property("x") + dialog.property("width") <= window.width() + 1
    assert dialog.property("y") + dialog.property("height") <= window.height() + 1
    button = dialog.findChild(QObject, "addPickedButton")
    assert not button.property("enabled")
    assert controller.pickedCount == 0
    assert len(controller.windows) == 1
    search = dialog.findChild(QObject, "windowSearch")
    search.setProperty("text", "terminal 39")
    QTest.qWait(100)
    candidates = dialog.findChild(QObject, "candidateList")
    assert candidates.property("count") == 1
    row = candidates.property("currentItem")
    assert row is not None
    assert row.objectName() == "candidate_39"
    click_button(window, row)
    QTest.qWait(50)
    assert controller.pickedCount == 1
    search.setProperty("text", "does not exist")
    QTest.qWait(50)
    assert candidates.property("count") == 0
    assert controller.pickedCount == 1
    search.setProperty("text", "ORG.KDE.KONSOLE")
    QTest.qWait(50)
    assert candidates.property("count") == 40
    search.setProperty("text", "terminal 39")
    QTest.qWait(50)
    assert candidates.property("currentItem").property("checked")
    click_button(window, button)
    wait_for_popup(dialog, opened=False)
    assert [w["title"] for w in controller.storage.windows(gid)] == ["Notes", "Terminal 39"]
    assert controller.windows[1]["x"] == 390
    assert controller.candidates == []
    assert not warnings


@pytest.mark.parametrize("cancel_key", [Qt.Key_Escape, None])
def test_picker_cancel_and_reopen_clear_selections(ui, monkeypatch, cancel_key):
    window, controller, _, warnings = ui
    dialog = prepare_picker(ui, monkeypatch)
    row = dialog.findChild(QObject, "candidateList").property("currentItem")
    click_button(window, row)
    assert controller.pickedCount == 1
    if cancel_key:
        QTest.keyClick(window, cancel_key)
    else:
        QMetaObject.invokeMethod(dialog, "reject")
    wait_for_popup(dialog, opened=False)
    assert len(controller.windows) == 1
    assert controller.candidates == []
    prepare_picker(ui, monkeypatch)
    assert controller.pickedCount == 0
    assert not warnings


def test_picker_empty_snapshot(ui, monkeypatch):
    dialog = prepare_picker(ui, monkeypatch, count=0)
    _, controller, _, warnings = ui
    assert controller.candidates == []
    assert not dialog.findChild(QObject, "addPickedButton").property("enabled")
    assert not controller.addPicked()
    assert len(controller.windows) == 1
    assert not warnings


def test_picker_snapshot_error_and_busy_guard(ui, monkeypatch):
    window, controller, gid, warnings = ui
    callbacks = []
    monkeypatch.setattr(controller.launcher, "snapshot", callbacks.append)
    controller.preparePicker(gid)
    assert controller.busy
    controller.preparePicker(gid)
    assert len(callbacks) == 1
    callbacks[0](None, "Snapshot failed")
    assert not controller.busy
    assert controller.status == "Snapshot failed"
    assert not window.findChild(QObject, "windowPicker").property("visible")
    assert len(controller.storage.windows(gid)) == 1
    assert not warnings


def test_picker_retains_original_target_and_handles_deleted_group(ui, monkeypatch):
    _, controller, gid, warnings = ui
    dialog = prepare_picker(ui, monkeypatch)
    other = controller.storage.capture("Other", [])
    controller.setPicked(1, True)
    controller.select(other)
    assert controller.addPicked()
    QMetaObject.invokeMethod(dialog, "close")
    wait_for_popup(dialog, opened=False)
    assert len(controller.storage.windows(gid)) == 2
    assert controller.storage.windows(other) == []
    prepare_picker(ui, monkeypatch)
    controller.setPicked(0, True)
    controller.storage.delete(gid)
    assert not controller.addPicked()
    assert "no longer exists" in controller.status
    assert not controller.busy
    assert controller.pickedCount == 1
    assert controller.storage.windows(other) == []
    assert not warnings


def test_picker_keyboard_toggle_preserves_focus(ui, monkeypatch):
    window, controller, _, warnings = ui
    dialog = prepare_picker(ui, monkeypatch)
    row = dialog.findChild(QObject, "candidateList").property("currentItem")
    row.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Space)
    QTest.qWait(50)
    assert controller.pickedCount == 1
    assert row.property("checked")
    assert window.activeFocusItem() == row
    QTest.keyClick(window, Qt.Key_Space)
    assert controller.pickedCount == 0
    assert not row.property("checked")
    assert not warnings


def test_picker_searches_desktop_app_name_and_keeps_same_app_windows_separate(ui, monkeypatch):
    _, controller, gid, warnings = ui
    monkeypatch.setattr(controller.launcher.resolver, "entry", lambda path: {"Name": "Friendly App"})
    rows = [dict(app_id="same.app", title="Same title", x=i * 10, y=0,
                 w=800, h=600, desktop_file="test.desktop") for i in range(2)]
    monkeypatch.setattr(controller.launcher, "snapshot", lambda callback: callback(rows, None))
    controller.preparePicker(gid)
    dialog = ui[0].findChild(QObject, "windowPicker")
    wait_for_popup(dialog)
    dialog.findChild(QObject, "windowSearch").setProperty("text", "friendly")
    QTest.qWait(50)
    assert dialog.findChild(QObject, "candidateList").property("count") == 2
    controller.setPicked(1, True)
    controller.setPicked(1, True)
    controller.setPicked(-1, True)
    controller.setPicked(20, True)
    assert controller.pickedCount == 1
    assert controller.addPicked()
    assert [w["x"] for w in controller.storage.windows(gid)] == [0, 10]
    assert not warnings


@pytest.mark.parametrize("first_group", [False, True])
@pytest.mark.parametrize("confirm", [False, True])
def test_new_group_selective_capture_from_group_navigation(ui, monkeypatch, first_group, confirm):
    window, controller, gid, warnings = ui
    if first_group:
        window.resize(640, 460)
        controller.storage.delete(gid)
        controller.refresh()
        QTest.qWait(50)
    original_groups = controller.groups
    rows = [dict(app_id="test.app", title=f"Window {i}", x=i * 10, y=0,
                 w=800, h=600, desktop_file="") for i in range(3)]
    monkeypatch.setattr(controller.launcher, "snapshot", lambda callback: callback(rows, None))
    click_button(window, window.findChild(QObject, "captureWindowsButton"))
    naming = window.findChild(QObject, "captureDialog")
    wait_for_popup(naming)
    naming.setProperty("text", "  Selected workspace  ")
    choice = naming.findChild(QObject, "selectSpecificWindows")
    assert choice.property("visible")
    content = naming.property("contentItem")
    position = choice.mapToItem(content, QPointF(0, 0))
    assert position.x() >= -1
    assert position.x() + choice.width() <= content.width() + 1
    assert position.y() + choice.height() <= content.height() + 1
    click_button(window, choice)
    assert naming.property("selectWindows")
    click_button(window, naming.findChild(QObject, "nameAcceptButton"))
    wait_for_popup(naming, opened=False)
    picker = window.findChild(QObject, "windowPicker")
    wait_for_popup(picker)
    assert controller.pickerName == "Selected workspace"
    assert controller.groups == original_groups
    assert not picker.findChild(QObject, "addPickedButton").property("enabled")
    row = picker.findChild(QObject, "candidateList").property("currentItem")
    click_button(window, row)
    if confirm:
        click_button(window, picker.findChild(QObject, "addPickedButton"))
        wait_for_popup(picker, opened=False)
        assert len(controller.groups) == len(original_groups) + 1
        assert controller.groupName == "Selected workspace"
        assert [w["title"] for w in controller.windows] == ["Window 0"]
        assert window.findChild(QObject, "groupPages").property("depth") == 2
        if not first_group:
            assert [w["title"] for w in controller.storage.windows(gid)] == ["Notes"]
    else:
        QTest.keyClick(window, Qt.Key_Escape)
        wait_for_popup(picker, opened=False)
        assert controller.groups == original_groups
    assert controller.pickerName == ""
    assert not warnings


@pytest.mark.parametrize("snapshot_error", [None, "Snapshot failed"])
def test_new_group_picker_does_not_create_group_for_empty_or_failed_snapshot(ui, monkeypatch, snapshot_error):
    window, controller, _, warnings = ui
    before = controller.groups
    monkeypatch.setattr(controller.launcher, "snapshot", lambda callback: callback([], snapshot_error))
    controller.preparePicker(0, "New group")
    assert controller.groups == before
    assert not controller.busy
    assert not controller.addPicked()
    if snapshot_error:
        assert controller.status == snapshot_error
        assert not window.findChild(QObject, "windowPicker").property("visible")
    else:
        picker = window.findChild(QObject, "windowPicker")
        wait_for_popup(picker)
        assert not picker.findChild(QObject, "addPickedButton").property("enabled")
    assert not warnings


def test_new_group_picker_rejects_blank_name(ui, monkeypatch):
    _, controller, _, warnings = ui
    monkeypatch.setattr(controller.launcher, "snapshot", lambda callback: pytest.fail("Must not capture"))
    controller.preparePicker(0, "   ")
    assert "group name" in controller.status
    assert not controller.busy
    assert not warnings


@pytest.mark.parametrize("selective", [False, True])
def test_both_add_paths_skip_saved_window_and_keep_other_same_app_window(ui, monkeypatch, selective):
    window, controller, gid, warnings = ui
    controller.select(gid)
    saved = controller.storage.windows(gid)[0]
    # Associate the pre-feature saved row with its live KWin ID first.
    controller.storage.capture("", [dict(saved, window_id="saved-window")], gid)
    rows = [dict(saved, window_id="saved-window", title="Title changed", x=200),
            dict(saved, window_id="other-window")]
    monkeypatch.setattr(controller.launcher, "snapshot", lambda callback: callback(rows, None))
    if selective:
        controller.preparePicker(gid)
        picker = window.findChild(QObject, "windowPicker")
        wait_for_popup(picker)
        controller.setPicked(0, True)
        controller.setPicked(1, True)
        click_button(window, picker.findChild(QObject, "addPickedButton"))
        wait_for_popup(picker, opened=False)
    else:
        controller.capture("", gid)
    assert [w["window_id"] for w in controller.windows] == ["saved-window", "other-window"]
    assert controller.windows[0]["title"] == "Notes"
    assert "Added 1" in controller.status
    assert "Skipped 1" in controller.status
    controller.capture("", gid)
    assert len(controller.windows) == 2
    assert "Added 0" in controller.status
    assert "Skipped 2" in controller.status
    assert not warnings
