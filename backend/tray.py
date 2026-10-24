from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


class Tray(QSystemTrayIcon):
    def __init__(self, window, launch, parent=None):
        super().__init__(QApplication.windowIcon(), parent)
        self.window = window
        self.launch = launch
        self.menu = QMenu()
        self.setToolTip("Rift")
        self.setContextMenu(self.menu)
        self.activated.connect(self.activated_icon)

    def open_window(self):
        self.window.show()
        self.window.raise_()
        self.window.requestActivate()

    def activated_icon(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.open_window()

    def refresh(self, groups):
        self.menu.clear()
        self.menu.addAction("Open Rift", self.open_window)
        self.menu.addSeparator()
        for group in groups:
            self.menu.addAction(group["name"], lambda checked=False, gid=group["id"]: self.launch(gid))
        self.menu.addSeparator()
        self.menu.addAction("Quit", QApplication.quit)
