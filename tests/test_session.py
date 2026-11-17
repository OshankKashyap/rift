import json

import pytest

from backend.storage import Storage
from main import Controller


@pytest.fixture
def session(app):
    storage = Storage(":memory:")
    controller = Controller(storage, None)
    yield storage, controller
    storage.close()


def windows(count):
    return [dict(app_id=f"app{i}", title=f"Window {i}", desktop_file="",
                 x=i, y=0, w=800, h=600, desktops=["desktop-1"]) for i in range(count)]


def test_unclean_start_discards_snapshot_and_clean_start_consumes_once(session):
    storage, _ = session
    storage.save_session(windows(1))
    assert storage.start_session()["clean"] == 0
    assert storage.consume_session() == []
    storage.save_session(windows(1))
    storage.mark_clean()
    assert json.loads(storage.start_session()["snapshot"]) == windows(1)
    assert storage.consume_session() == windows(1)
    assert storage.consume_session() == []
    assert not storage.session_settings()["clean"]


@pytest.mark.parametrize("enabled,smart,count,saved", [(True, True, 5, True),
    (True, True, 4, False), (True, False, 5, False), (False, True, 5, False)])
def test_automatic_session_threshold(session, monkeypatch, enabled, smart, count, saved):
    storage, controller = session
    controller.setSessionEnabled(enabled)
    controller.setSmartRestore(smart)
    monkeypatch.setattr(controller.launcher, "snapshot", lambda callback: callback(windows(count), None))
    assert controller.shutdownSnapshot()
    assert bool(storage.session_settings()["snapshot"]) is saved


def test_manual_save_and_exclusion_before_launch(session, monkeypatch):
    storage, controller = session
    controller.setSessionEnabled(True)
    monkeypatch.setattr(controller.launcher, "snapshot", lambda callback: callback(windows(2), None))
    controller.saveSession()
    controller.addExclusion("APP0.desktop")
    launched = []
    monkeypatch.setattr(controller.launcher, "launch", lambda rows, done: (launched.extend(rows), done(None)))
    controller.restoreSession()
    assert [w["app_id"] for w in launched] == ["app1"]
    assert storage.session_settings()["snapshot"] is None


def test_restore_disabled_preserves_saved_session(session, monkeypatch):
    storage, controller = session
    storage.save_session(windows(1))
    monkeypatch.setattr(controller.launcher, "launch", lambda *_: pytest.fail("must not launch"))
    controller.restoreSession()
    assert storage.session_settings()["snapshot"] is not None


def test_session_snapshot_preserves_maximize_mode(session):
    storage, _ = session
    saved = [dict(windows(1)[0], maximize_mode=3)]
    storage.save_session(saved)
    assert storage.consume_session() == saved
