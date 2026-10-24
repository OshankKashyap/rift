"""Short-lived KWin scripts, with asynchronous DBus result callbacks."""

import json
import os
import uuid

from PySide6.QtCore import ClassInfo, QObject, QTimer, Slot
from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusPendingCallWatcher


@ClassInfo({"D-Bus Interface": "org.rift.Callback"})
class KWin(QObject):
    def __init__(self, runtime, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.bus = QDBusConnection.sessionBus()
        self.service = "org.rift.Application"
        self.pending = {}
        self.watchers = set()
        if not self.bus.registerService(self.service):
            raise RuntimeError("Cannot register Rift on the session bus. Is Rift already running?")
        if not self.bus.registerObject("/Rift", self, QDBusConnection.ExportAllSlots):
            self.bus.unregisterService(self.service)
            raise RuntimeError("Cannot register the KWin callback object.")

    def call(self, service, path, interface, method, arguments, callback):
        message = QDBusMessage.createMethodCall(service, path, interface, method)
        message.setArguments(arguments)
        watcher = QDBusPendingCallWatcher(self.bus.asyncCall(message, 5000), self)
        self.watchers.add(watcher)

        def finished():
            reply = watcher.reply()
            self.watchers.discard(watcher)
            watcher.deleteLater()
            if reply.type() == QDBusMessage.ErrorMessage:
                callback(None, f"{reply.errorName()}: {reply.errorMessage()}")
            else:
                callback(reply.arguments(), None)

        watcher.finished.connect(finished)

    def run(self, body, callback):
        token = uuid.uuid4().hex
        name = "rift_" + token
        path = self.runtime / (name + ".js")
        source = """
            let result;
            try { result = {value: (() => { BODY })()}; }
            catch (e) { result = {error: String(e)}; }
            callDBus('org.rift.Application', '/Rift', 'org.rift.Callback',
                     'deliver', TOKEN, JSON.stringify(result));
        """.replace("BODY", body).replace("TOKEN", json.dumps(token))
        path.write_text(source)
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self.finish(token, None,
            "KWin script timed out. Check KWin script/DBus permissions and the session log."))
        self.pending[token] = (name, path, timer, callback)
        timer.start(10000)

        def loaded(args, error):
            if token not in self.pending:
                return
            if error or not args or args[0] < 0:
                self.finish(token, None, error or "KWin refused to load the script.")
                return
            self.call("org.kde.KWin", f"/Scripting/Script{args[0]}",
                      "org.kde.kwin.Script", "run", [],
                      lambda _, err: self.finish(token, None, err) if err else None)

        self.call("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", "loadScript",
                  [str(path), name], loaded)

    @Slot(str, str)
    def deliver(self, token, payload):
        if token not in self.pending:
            return
        try:
            result = json.loads(payload)
            value, error = result.get("value"), result.get("error")
        except (ValueError, AttributeError) as exc:
            value, error = None, str(exc)
        QTimer.singleShot(0, lambda: self.finish(token, value, error))

    def finish(self, token, value, error):
        entry = self.pending.pop(token, None)
        if entry is None:
            return
        name, path, timer, callback = entry
        timer.stop()
        timer.deleteLater()
        self.call("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", "unloadScript",
                  [name], lambda *_: path.unlink(missing_ok=True))
        callback(value, error)

    def shutdown(self):
        for name, path, timer, _ in self.pending.values():
            timer.stop()
            message = QDBusMessage.createMethodCall(
                "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", "unloadScript")
            message.setArguments([name])
            self.bus.call(message, timeout=1000)
            path.unlink(missing_ok=True)
        self.pending.clear()
        self.bus.unregisterObject("/Rift")
        self.bus.unregisterService(self.service)

    def snapshot(self, callback, main_only=True):
        body = """
            return workspace.windowList()
                .filter(w => FILTER && !w.specialWindow
                             && w.pid !== PID)
                .map(w => ({window_id: String(w.internalId),
                    app_id: String(w.resourceClass || ''), title: w.caption,
                    desktop_hint: String(w.desktopFileName || ''), pid: w.pid,
                    x: Math.round(w.frameGeometry.x), y: Math.round(w.frameGeometry.y),
                    w: Math.round(w.frameGeometry.width), h: Math.round(w.frameGeometry.height)}));
        """
        window_filter = "w.normalWindow && !w.dialog && !w.skipTaskbar" if main_only else "(w.normalWindow || w.dialog)"
        self.run(body.replace("FILTER", window_filter).replace("PID", str(os.getpid())), callback)

    def close_windows(self, ids, callback):
        self.run("""
            const ids = IDS;
            let count = 0;
            for (const w of workspace.windowList()) {
                if (ids.includes(String(w.internalId))) { w.closeWindow(); count++; }
            }
            return count;
        """.replace("IDS", json.dumps(ids)), callback)

    def restore(self, placements, callback):
        self.run("""
            const placements = PLACEMENTS;
            let count = 0;
            for (const w of workspace.windowList()) {
                const p = placements.find(p => p.window_id === String(w.internalId));
                if (!p) continue;
                w.setMaximize(false, false);
                w.fullScreen = false;
                w.frameGeometry = {x: p.x, y: p.y, width: p.w, height: p.h};
                count++;
            }
            return count;
        """.replace("PLACEMENTS", json.dumps(placements)), callback)
