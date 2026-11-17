from PySide6.QtQml import QJSEngine
import pytest

from backend.kwin import KWin


class ScriptCapture:
    def run(self, body, callback):
        self.body = body


def test_snapshot_script_filters_helpers_and_exports_geometry(app):
    script = ScriptCapture()
    KWin.snapshot(script, None)
    engine = QJSEngine()
    result = engine.evaluate("""
        const normal = {normalWindow: true, dialog: false, specialWindow: false,
            skipTaskbar: false, pid: 42, internalId: 'main', resourceClass: 'kate',
            caption: 'Notes', desktopFileName: 'org.kde.kate', maximizeMode: 3,
            frameGeometry: {x: -900, y: 10, width: 800, height: 600}};
        const dialog = Object.assign({}, normal, {internalId: 'dialog', normalWindow: false, dialog: true});
        const helper = Object.assign({}, normal, {internalId: 'helper', skipTaskbar: true});
        const workspace = {windowList: () => [normal, dialog, helper]};
        (() => { BODY })();
    """.replace("BODY", script.body))
    assert not result.isError(), result.toString()
    windows = result.toVariant()
    assert windows == [dict(window_id="main", app_id="kate", title="Notes",
                            desktop_hint="org.kde.kate", pid=42, x=-900, y=10, w=800, h=600, desktops=[], maximize_mode=3)]


def test_close_script_uses_close_request_only_on_selected_ids(app):
    script = ScriptCapture()
    KWin.close_windows(script, ["one"], None)
    engine = QJSEngine()
    result = engine.evaluate("""
        let closed = [];
        const workspace = {windowList: () => ['one', 'two'].map(id => ({
            internalId: id, closeWindow: () => closed.push(id)}))};
        const count = (() => { BODY })();
        ({count, closed});
    """.replace("BODY", script.body))
    assert not result.isError(), result.toString()
    assert result.toVariant() == {"count": 1, "closed": ["one"]}


def test_restore_script_applies_frame_geometry_only_to_selected_id(app):
    script = ScriptCapture()
    KWin.restore(script, [dict(window_id="one", x=-900, y=10, w=800, h=600)], None)
    engine = QJSEngine()
    result = engine.evaluate("""
        const one = {internalId: 'one', fullScreen: true,
                     setMaximize: (horizontal, vertical) => one.maximized = [horizontal, vertical]};
        const two = {internalId: 'two'};
        const workspace = {windowList: () => [one, two]};
        const count = (() => { BODY })();
        ({count, geometry: one.frameGeometry, fullscreen: one.fullScreen,
          maximized: one.maximized, unrelatedUnchanged: two.frameGeometry === undefined});
    """.replace("BODY", script.body))
    assert not result.isError(), result.toString()
    assert result.toVariant() == dict(count=1, geometry=dict(x=-900, y=10, width=800, height=600),
                                     fullscreen=False, maximized=[False, False], unrelatedUnchanged=True)


def test_restore_script_assigns_saved_virtual_desktop(app):
    script = ScriptCapture()
    KWin.restore(script, [dict(window_id="one", x=0, y=0, w=800, h=600, desktops=["desk-2"])], None)
    engine = QJSEngine()
    result = engine.evaluate("""
        const one = {internalId: 'one', setMaximize: () => {}};
        const workspace = {windowList: () => [one], desktops: [{id: 'desk-1'}, {id: 'desk-2'}]};
        (() => { BODY })();
        one.desktops[0].id;
    """.replace("BODY", script.body))
    assert not result.isError(), result.toString()
    assert result.toString() == "desk-2"


@pytest.mark.parametrize("mode, expected", [(0, [False, False]), (1, [True, False]),
                                            (2, [False, True]), (3, [True, True])])
def test_restore_script_reapplies_maximize_mode(app, mode, expected):
    script = ScriptCapture()
    KWin.restore(script, [dict(window_id="one", x=0, y=0, w=800, h=600, maximize_mode=mode)], None)
    engine = QJSEngine()
    result = engine.evaluate("""
        const one = {internalId: 'one', setMaximize: (v, h) => one.maximized = [v, h]};
        const workspace = {windowList: () => [one]};
        (() => { BODY })();
        one.maximized;
    """.replace("BODY", script.body))
    assert not result.isError(), result.toString()
    assert result.toVariant() == expected
