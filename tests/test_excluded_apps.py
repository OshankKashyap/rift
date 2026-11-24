import pytest
from PySide6.QtCore import QCoreApplication, QMetaObject, QObject
from PySide6.QtTest import QTest
from test_qml import ui
from test_session import session

from backend.launcher import DesktopResolver, normalized


def test_discovery_honors_precedence_and_visibility(tmp_path):
    user, system = tmp_path / "user", tmp_path / "system"
    user.mkdir()
    system.mkdir()
    (user / "hidden.desktop").write_text("[Desktop Entry]\nHidden=true\n")
    (user / "nodisplay.desktop").write_text(
        "[Desktop Entry]\nName=Hidden\nNoDisplay=true\n"
    )
    for name in ("hidden", "nodisplay"):
        (system / f"{name}.desktop").write_text("[Desktop Entry]\nName=Shadowed\n")
    (user / "org.example.App.desktop").write_text(
        "[Desktop Entry]\nName=User App\nIcon=example\n"
    )
    (system / "org.example.App.desktop").write_text(
        "[Desktop Entry]\nName=System App\n"
    )
    (system / "broken.desktop").write_text("not a desktop entry")
    resolver = DesktopResolver()
    resolver.roots = [user, system]
    assert resolver.installed_apps() == [
        {
            "id": "org.example.App.desktop",
            "path": str(user / "org.example.App.desktop"),
            "name": "User App",
            "icon": "example",
        }
    ]


def test_discovery_uses_localized_name(tmp_path, monkeypatch):
    from backend import launcher

    class Locale:
        @staticmethod
        def system():
            return Locale()

        def uiLanguages(self):
            return ["fr-FR", "fr"]

    monkeypatch.setattr(launcher, "QLocale", Locale)
    (tmp_path / "app.desktop").write_text(
        "[Desktop Entry]\nName=Default\nName[fr]=Français\n"
    )
    resolver = DesktopResolver()
    resolver.roots = [tmp_path]
    assert resolver.installed_apps()[0]["name"] == "Français"


def test_matching_and_unchecking_all_existing_exclusions(session):
    storage, controller = session
    app = {
        "id": "org.example.App.desktop",
        "path": "/some/App.desktop",
        "name": "App",
        "icon": "",
    }
    controller._installed_apps = [app]
    controller.addExclusion(app["id"])
    controller.addExclusion(app["path"])
    controller.addExclusion("unmatched")
    assert controller.installedApps[0]["checked"]
    controller.setAppExcluded(app["id"], app["path"], False)
    assert storage.exclusions() == ["unmatched"]
    controller.setAppExcluded(app["id"], app["path"], True)
    assert normalized(app["path"]) in storage.exclusions()


def test_picker_path_excludes_window_with_different_app_id(session, monkeypatch):
    storage, controller = session
    controller.setSessionEnabled(True)
    desktop_path = "/applications/Example.desktop"
    storage.save_session(
        [
            dict(
                app_id="different-id",
                desktop_file=desktop_path,
                title="Example",
                x=0,
                y=0,
                w=10,
                h=10,
            )
        ]
    )
    controller.setAppExcluded("org.example.App.desktop", desktop_path, True)
    monkeypatch.setattr(
        controller.launcher, "launch", lambda *_: pytest.fail("excluded app launched")
    )
    controller.restoreSession()


def test_search_uses_display_name_only(ui):
    window, controller, _, warnings = ui
    controller._installed_apps = [
        {
            "id": "secret.desktop",
            "path": "/secret.desktop",
            "name": "Visible Name",
            "icon": "",
        }
    ]
    controller.appsChanged.emit()
    dialog = window.findChild(QObject, "excludedAppsDialog")
    QMetaObject.invokeMethod(dialog, "open")
    QTest.qWait(100)
    search = dialog.findChild(QObject, "excludedAppSearch")
    app_list = dialog.findChild(QObject, "excludedAppList")
    assert app_list.property("count") == 1
    search.setProperty("text", "secret")
    QCoreApplication.processEvents()
    assert app_list.property("count") == 0
    search.setProperty("text", "visible")
    QCoreApplication.processEvents()
    assert app_list.property("count") == 1
    assert not warnings


def test_discovery_runs_and_publishes_results(session, monkeypatch):
    _, controller = session
    apps = [
        {
            "id": "example.desktop",
            "path": "/example.desktop",
            "name": "Example",
            "icon": "",
        }
    ]
    monkeypatch.setattr(DesktopResolver, "installed_apps", lambda self: apps)
    controller.discoverApps()
    for _ in range(100):
        QTest.qWait(10)
        if not controller.appsLoading and controller.installedApps:
            break
    assert controller.installedApps[0]["name"] == "Example"
