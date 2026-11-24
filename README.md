<p align="center">
  <img src="logos/rift-banner.png" alt="Rift" width="260">
</p>

<h1 align="center">Rift</h1>

<p align="center"><strong>Save your workspace. Bring it back when you need it.</strong><br>
A window-group and session restore app for KDE Plasma.</p>

---

## What Rift can do

- **Capture a workspace** — save all your main windows or pick just the ones you need.
- **Launch a group** — start missing apps and restore the positions of uniquely matched windows.
- **Recall a group** — gracefully ask matching app windows to close.
- **Restore a session** — bring back eligible windows after a clean exit, with optional automatic saving and app exclusions.

Built with Python, PySide6, QML, Kirigami and SQLite. Target: **Fedora 44 / KDE Plasma 6.7.5**.

## Get started

From the project directory in your KDE session:

```sh
.venv/bin/python main.py
```

1. Select **Capture windows…** to name a group and capture all main windows or choose specific ones.
2. Select the group and choose **Launch group** to bring back missing apps.
3. Use **Recall…** when you want to close the group's matching app windows.

> **Save your work before Recall.** It requests that **all matching app windows** close, including windows not captured in the group. Apps may show save prompts or refuse; Rift never forces them to quit.

Run only one instance at a time. Closing Rift hides it in the system tray; use **Quit** in the tray to exit or restart. If no tray is available, closing the window quits.

## Work with groups

| Action              | What it does                                                                                              |
| ------------------- | --------------------------------------------------------------------------------------------------------- |
| **Add windows**     | Append current main windows, skipping those already saved.                                                |
| **Select windows…** | Search by title or app and select windows to add. Cancel saves nothing.                                   |
| **Launch group**    | Start missing apps and restore uniquely matched new windows. Already-running apps are skipped, not moved. |
| **Recall…**         | Ask all matching app windows to close gracefully.                                                         |
| **Pencil / minus**  | Edit launch targets and matching / remove an entry without closing its window.                            |
| **More**            | Rename or delete a group. Running apps stay open.                                                         |

## Preferences

Open **Preferences** in the top-right corner to configure:

- **Start in system tray** — start without showing the main window, then use **Open Rift** in the tray. The setting takes effect on the next launch, including automatic startup; if no tray is available, the window opens normally. It does not configure automatic startup.
- **Session restore** — restore a saved session five seconds after the next eligible launch. Save a session from Preferences or the tray.
- **Smart restore** — capture main windows on a clean exit when at least five are open.
- **Excluded apps** — choose installed apps from the list or search by display name. You can also add or remove app IDs and exact desktop-file paths manually, including entries absent from the list. Changes take effect immediately.

A saved session is consumed when restore begins; an unclean exit discards it. Exclusions are stored separately and do not prevent capture. Apps with an already-running main window are skipped; the window tracker does not detect background-only processes.

## Things to know

- Rift captures main windows, not helper dialogs or Rift itself.
- Groups store titles and frame geometry. Session snapshots also store virtual desktop assignments. Neither stores documents, browser tabs or sessions, or activities.
- Each distinct app is launched once; Rift cannot guarantee a particular number of windows.
- Session restore preserves maximized state; group launches clear it. Both clear fullscreen state. Monitor changes and window rules can affect placement.
- Missing launchers and ambiguous matches are reported; use manual overrides when needed.
- Both add actions skip saved windows using KWin window IDs while keeping separate windows of the same app. The picker uses snapshot geometry.
- Older entries without window IDs use exact app, title and geometry matching only when unambiguous. Changed details may require manual duplicate removal; existing duplicates are not removed automatically.

<details>
<summary><strong>Launch targets and matching overrides</strong></summary>

Use the pencil button to set an exact desktop ID or an absolute path to a valid **text `.desktop` file**, not an executable. Registered entries use DBus/KDE launching; external or shadowed paths use `kioclient`. Rift does not register launchers or bypass KDE trust checks.

Blank matching overrides use the captured identity. Otherwise, **every nonblank override must match**. App IDs are case-insensitive; titles and absolute executable paths are case-sensitive. A process-only override can match multiple windows, so review warnings before Recall.

</details>

## Setup

The supplied `.venv` is already configured. System prerequisites:

- OS-default Python with venv support and Fedora `python3-pyside6` **6.11.2**.
- `kf6-kirigami`, `kf6-qqc2-desktop-style`, `plasma-integration` and `kde-cli-tools`.
- A running KWin session with session DBus access.

> **Use Fedora's Qt/PySide6 stack.** Pip Qt wheels conflict with the system Kirigami ABI. Install any missing system prerequisites yourself; Rift does not install them or change permissions.

<details>
<summary><strong>Recreate the virtual environment</strong></summary>

After checking the prerequisites, run from the project directory:

```sh
mkdir -p .runtime/tmp .runtime/cache
TMPDIR="$PWD/.runtime/tmp" /usr/bin/python -m venv --system-site-packages .venv
TMPDIR="$PWD/.runtime/tmp" PIP_CACHE_DIR="$PWD/.runtime/cache/pip" .venv/bin/python -m pip install -r requirements.txt
```

</details>

## Data and diagnostics

| Item                                          | Location or command                                 |
| --------------------------------------------- | --------------------------------------------------- |
| Saved groups                                  | `rift.sqlite3` in the project root                  |
| Temporary KWin scripts, caches and test files | `.runtime/`                                         |
| Optional log                                  | `.venv/bin/python main.py > .runtime/rift.log 2>&1` |

KWin scripts are temporary, not installed into Plasma. Investigate access errors; do not loosen permissions automatically.

## Tests

```sh
TMPDIR="$PWD/.runtime/tmp" PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest
```

Offscreen and mocked tests do not establish live KDE behavior.

<details>
<summary><strong>Manual KDE checklist</strong></summary>

Use disposable windows and save important work first:

- [ ] Create the first and subsequent groups using both capture-all and selection; verify cancellation saves nothing.
- [ ] Add/remove entries, rename/delete groups, restart, and check persistence.
- [ ] Launch with some apps already open; verify skipping, launcher errors, and new-window geometry.
- [ ] Recall disposable apps; check uncaptured matching windows, save prompts, and no forced closure.
- [ ] Check tray actions, keyboard navigation, minimum window size, display scaling, and Plasma light/dark themes.
- [ ] Check normal startup with **Start in system tray** disabled, hidden startup with it enabled, opening from the tray, and the no-tray fallback. Confirm there is no window flash.
- [ ] With hidden startup enabled, verify an eligible session still restores after five seconds.
- [ ] Save a session and quit Rift cleanly; restart and check the five-second delay, desktop assignments, geometry, exclusions, and running-app skips.
- [ ] In Preferences, check installed distro, user-local, and user/system Flatpak apps, their icons and name search. Check and uncheck apps, restart, and verify selected apps are skipped during session restore. Check manual IDs and paths, including an unmatched entry.
- [ ] Save and restore a maximized window and a normal-sized window; check their size and maximize state in Plasma.
- [ ] Repeat after a Plasma logout/restart and after an unclean Rift termination; verify only the clean session restores.
- [ ] Check Smart restore with four and five main windows and test manual save from Preferences and the tray.

</details>

---

`main.py` — controller · `backend/` — KWin, launching, storage and tray · `qml/` — UI · `tests/` — verification
