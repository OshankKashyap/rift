![Rift banner](logos/rift-banner.png)

# Rift

Save groups of KDE Plasma windows, launch missing apps, and restore their positions.
Built with Python, PySide6, QML, Kirigami, and SQLite.

## Run

From the project directory, in your KDE session:

```sh
.venv/bin/python main.py
```

Closing the window hides Rift in the tray. Use **Quit** in the tray to exit or restart.
Without a tray, closing the window quits. Run only one instance at a time.

## Use

| Action | What it does |
| --- | --- |
| **Capture windows…** | Name a new group; capture all main windows or select specific ones—even for your first group. |
| **Add windows** | Append current main windows, skipping those already saved. |
| **Select windows…** | Search by title/app, check windows, then add only those selected. Cancel saves nothing. |
| **Launch group** | Start missing apps and restore uniquely matched new windows. Already-running apps are skipped, not moved. |
| **Recall…** | Gracefully close **all matching app windows**, including windows never captured in the group. |
| **Pencil / minus** | Edit launch targets and matching / remove a saved entry without closing its window. |
| **More** | Rename or delete a group. Running apps stay open. |

**Save your work before Recall.** Apps may show save prompts or refuse to close; Rift never forces them to quit.

## Know the limits

- Captures main windows, not helper dialogs or Rift itself.
- Stores titles and frame geometry—not documents, browser tabs/sessions, activities, or virtual desktops.
- Launches each distinct app once; it does not recreate a specific number of windows.
- Geometry restoration clears maximized/fullscreen state. Monitor changes and window rules can affect placement.
- Missing or ambiguous matches need manual overrides; Rift does not guess placement.
- Both add actions skip already-saved windows using KWin window IDs; separate windows of the same app are kept. Picker geometry comes from the snapshot.
- Older entries without window IDs use exact app/title/geometry matching only when unambiguous. If those details changed, a duplicate may need manual removal. Existing duplicates are not removed automatically.

### Launch targets and matching

Use the pencil button to set an exact desktop ID or absolute path to a valid **text `.desktop` file**, not an executable.
Registered entries use DBus/KDE launching; external or shadowed paths use `kioclient`.
Rift does not register launchers or bypass KDE trust checks.

Blank matching overrides use captured identity. Otherwise, **every nonblank override must match**.
AppIds are case-insensitive; titles and absolute executable paths are case-sensitive.
A process-only override can match multiple windows—review warnings before Recall.

## Setup

Current target: **Fedora 44 / KDE Plasma 6.7.5**. The supplied `.venv` is already configured.

System prerequisites:
- OS-default Python with venv support; Fedora `python3-pyside6` **6.11.2**.
- `kf6-kirigami`, `kf6-qqc2-desktop-style`, `plasma-integration`, and `kde-cli-tools`.
- A running KWin session with session DBus access.

**Use Fedora's Qt/PySide6 stack.** Pip Qt wheels conflict with the system Kirigami ABI here.
Install missing system prerequisites yourself; Rift does not install them or change permissions.

To recreate the venv from the project directory after checking prerequisites:

```sh
mkdir -p .runtime/tmp .runtime/cache
TMPDIR="$PWD/.runtime/tmp" /usr/bin/python -m venv --system-site-packages .venv
TMPDIR="$PWD/.runtime/tmp" PIP_CACHE_DIR="$PWD/.runtime/cache/pip" .venv/bin/python -m pip install -r requirements.txt
```

## Data and diagnostics

- Saved groups: `rift.sqlite3` in the project root.
- Temporary KWin scripts, caches, and test files: `.runtime/`.
- Optional log: `.venv/bin/python main.py > .runtime/rift.log 2>&1`.
- KWin scripts are temporary, not installed into Plasma. Investigate access errors; do not loosen permissions automatically.

## Tests

```sh
TMPDIR="$PWD/.runtime/tmp" PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest
```

Latest checks: **127 tests passed**; all **49 UI tests also passed offscreen at 150% scaling**.
Offscreen/mocked tests do not establish live KDE behavior.

### Quick manual KDE checks

Use disposable windows and save important work first:
- [ ] Create the first and subsequent groups using both capture-all and selection; verify cancellation saves nothing.
- [ ] Add/remove entries, rename/delete groups, restart, and check persistence.
- [ ] Launch with some apps already open; verify skipping, launcher errors, and new-window geometry.
- [ ] Recall disposable apps; check uncaptured matching windows, save prompts, and no forced closure.
- [ ] Check tray actions, keyboard navigation, minimum window size, display scaling, and Plasma light/dark themes.

Code: `main.py` (controller), `backend/` (KWin, launching, storage, tray), `qml/` (UI), `tests/` (verification).
