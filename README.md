# Rift

A personal KDE Plasma utility for capturing groups of main application windows,
launching missing apps, restoring their frame geometry, and gracefully recalling
(closing) the group's running windows. Built with Python, PySide6, QML, Kirigami,
and the standard-library SQLite driver.

## Dependencies and environment

This checkout targets the inspected **Fedora 44 KDE / Plasma 6.7.5** environment:

- OS-default `/usr/bin/python` (Python 3.14.8 here), with venv support.
- Fedora `python3-pyside6` **6.11.2**, using the matching system Qt libraries.
- `kf6-kirigami` (the Kirigami package name on this Fedora release; not
  `kf6-kirigami2` or `kirigami2`).
- `kf6-qqc2-desktop-style` and `plasma-integration` for Plasma-themed controls.
- `kde-cli-tools` for `kstart` and `kioclient`, and KWin running on the session DBus.
- Local pytest **9.0.2**. Python requirements are pinned in `requirements.txt`.

These system dependencies were found installed. **Rift does not install or change
system packages.** If one is missing, ask the user to install the package named
above before proceeding. Package names can differ on other Fedora releases;
confirm them rather than guessing.

### Important: use the system Qt stack

With the user's approval, `.venv` uses `--system-site-packages`: PySide6 is read
from Fedora, while pytest is installed inside `.venv`. PyPI's PySide6/Qt wheels
cannot be mixed with this Fedora Kirigami build: their private Qt ABI symbols
differ even when the version numbers match. No library-preload workaround is
used, and no system packages were replaced.

This reduces Python isolation: other system Python packages are visible. Fedora
updates can change PySide6/Qt, so check the pin and rerun verification afterward.
Do not fix a version mismatch by installing pip Qt wheels over the system stack.

To recreate the environment **inside this project**, after checking the system
dependencies and pinned PySide6 version:

```sh
mkdir -p .runtime/tmp .runtime/cache
TMPDIR="$PWD/.runtime/tmp" /usr/bin/python -m venv --system-site-packages .venv
TMPDIR="$PWD/.runtime/tmp" PIP_CACHE_DIR="$PWD/.runtime/cache/pip" .venv/bin/python -m pip install -r requirements.txt
```

Run these commands from `/home/oshank/Projects/rift`. The supplied environment is
already configured. Do not run any git commands as part of setup.

## Run

From this directory, in your own KDE session:

```sh
.venv/bin/python main.py
```

For a project-local diagnostic log:

```sh
.venv/bin/python main.py > .runtime/rift.log 2>&1
```

Only one Rift instance may own `org.rift.Application` on the session bus. Closing
the window hides it when a system tray is available; use the tray's **Quit** action
to exit. Without a tray, closing the window quits.

Rift's database is `rift.sqlite3` in the project root. Temporary KWin scripts,
Qt caches, pip caches, and pytest files stay in `.runtime/`. KWin scripts are
loaded temporarily over DBus, not installed into your Plasma configuration.
No executable-script permission change is required. If the session refuses
script loading or DBus callbacks, stop and investigate the reported error with
the user; do not loosen permissions automatically.

## Features and behavior

- Group navigation uses a compact column with a highlighted current group.
  **Capture windows…** creates a named group and opens its details;
  **Add windows** appends another snapshot. Switching groups reuses the detail
  view instead of stacking duplicate pages.
- **Select windows…** opens a searchable, scrollable snapshot of open main
  windows with unchecked checkboxes. Search titles, desktop-entry app names
  (falling back to appIds), or appIds; selections persist across searches.
  **Add selected** appends only checked entries to the original group. Cancel
  or Escape saves nothing. Existing entries are not replaced or deduplicated;
  geometry is from the snapshot, not from the time you confirm. This does not
  change app-wide Launch/Recall behavior or browser-session handling.
- When creating any group, including the first one, **Capture windows…** offers
  **Select specific windows instead of capturing all** below the name field.
  Leave it unchecked to **Capture all**, or check it and continue with
  **Select windows…**. The same picker then offers **Create group**, saving only
  checked windows. Cancelling either dialog, an empty snapshot, or a capture
  failure creates no group.
- Captured windows appear in themed cards with app icons (a generic fallback
  when unavailable), titles, appIds, geometry, and a notice for missing saved
  launchers. The pencil button edits launch targets and matching; the minus
  button confirms removal without closing the running window. **More** contains
  group rename/delete actions.
- **Launch group** is the primary action. Recall's confirmation explicitly warns
  that it closes all matching app windows, including uncaptured ones. Destructive
  confirmations initially focus Cancel; Recall's app-based behavior is unchanged.
- Capture/rename dialogs constrain fields to their content area, reject empty or
  whitespace-only names, focus the name field, accept Enter, and cancel with
  Escape. The matching editor scrolls in short windows and disables Save for
  relative process paths. Status text can be selected, copied, and scrolled
  without expanding the footer indefinitely.
- Launch attempts every distinct stored app, skips apps with matching running
  main windows, and leaves skipped apps' geometry untouched. Repeated captured
  windows of the same app do not cause repeated launches by default.
- Desktop files are resolved using exact XDG desktop IDs/paths. DBus-activatable
  entries use `org.freedesktop.Application.Activate`, falling back to
  `kstart --application <desktop-id>` for registered entries. Absolute files
  outside XDG roots use `kioclient exec <file-url> application/x-desktop`, without
  copying or registering them. Explicit paths shadowed by a different XDG entry
  also use `kioclient` so the requested file is preserved. Helper errors are
  reported; Rift never parses `Exec` into a launch command or invokes a shell.
- New windows are polled after a one-second settle delay, for about 6.5 seconds
  total plus DBus time. Geometry is restored only for uniquely matched new
  windows. All captured rows for newly launched apps are considered; exact title
  matches are reserved first. Missing or ambiguous windows produce an error
  rather than a guessed placement.
- Recall asks for confirmation and sends KWin `closeWindow()` requests to all
  matching normal windows/dialogs, not just those that were newly launched. Apps
  can ask to save or refuse closure. No process termination signals are used.
- Tray menu: open Rift, quick-launch any saved group, quit.
- Controls use Kirigami and the system desktop style; no colors are hardcoded.

### Matching and overrides

Default matching uses normalized appId (case-insensitive, optional `.desktop`
suffix), then exact resolved desktop path. If those are unreliable, exact
process executable **and** exact title can corroborate a match. The process path
comes from the desktop launch command for a stored entry and `/proc/PID/exe` for
a live window. No PID is stored as a durable identity. If an appId is absent,
an exact-title fallback is also supported. These fallbacks emit warnings in the
terminal/log; review them before using Recall.

In the pencil button's **Launch target and matching** dialog, set an exact appId,
exact title, and/or absolute process
executable path. If any overrides are supplied, they replace automatic matching:
**every nonblank override must match**. Titles and executable paths are
case-sensitive. A process-only override intentionally matches all windows using
that executable, so use a title/appId too when necessary. An invalid relative
process path is rejected. Blank fields restore automatic matching.

The desktop target can be an absolute `.desktop` path or an exact desktop ID.
If it cannot be resolved, launching that entry reports an error while the other
apps are still attempted. Nothing is inferred from a fuzzy app name.
Absolute targets must be valid UTF-8 **text desktop entries**, not executables
whose filename happens to end in `.desktop`. In particular,
`/opt/OpenCode/ai.opencode.desktop` was found to be an ELF executable, not a text
launcher; use OpenCode's actual text desktop entry instead. Rift does not create
or register launchers automatically. KDE may require trust approval for external
desktop files; Rift does not change permissions or mark files trusted.

### v1 limitations

- Captures main windows only: excludes dialogs, special/skip-taskbar helper
  windows, and Rift itself.
- Launches applications, not documents, browser tabs, command arguments, or a
  requested number of windows. If an app does not reopen all its captured main
  windows, unmatched geometry is reported; Rift does not create speculative
  extra windows.
- Captures only frame coordinates/size, not virtual desktop, activity, stacking,
  maximization, or fullscreen state. Restoring geometry clears maximization and
  fullscreen. Window rules, minimum sizes, and changed monitor layouts can affect
  final placement; verify it manually.
- Existing apps are skipped, not focused. Long-starting apps can exceed the
  settle window. Conflicting identities require manual overrides.
- Recall is app-based: matching windows outside the originally captured session
  are also closed. Test with disposable windows before relying on it.

## Verification status

Implemented backend, persistence, tray integration, and QML UI. Automated tests
exercise SQLite CRUD/rollback/foreign keys/additive migration, matching/deduping,
launch error paths and DBus/kstart/kioclient selection using test doubles,
generated KWin JavaScript in a local QJSEngine, and offscreen group-detail/dialog rendering.
UI checks cover dialog/field bounds at 640×460 and 940×680, mouse and Enter
submission, blank-name validation, Escape cancellation, group switching,
confirmation safety, matching-form saving, and bounded long status messages.
Picker checks cover filtering, selections hidden by search, separate same-app
windows, keyboard toggling, cancellation, empty/error snapshots, and target safety.
All 47 UI tests also passed offscreen with `QT_SCALE_FACTOR=1.5`; live Plasma
scaling and theme switching remain manual checks.
The final automated run passed **110 tests**, including real Qt helper-process
success/failure handling using harmless Python commands (not application launches).
`kioclient --commands` confirmed the installed helper documents desktop-file URL
launching. A separate non-window-changing session-bus check verified asynchronous
DBus replies and Rift's exported callback
interface; it did not execute any KWin scripts.

**The real KDE capture/launch/restore/recall/tray/theme workflow has not been
verified in this session.** Local JavaScript mocks and offscreen rendering do
not verify KWin permissions, actual app behavior, or live theme switching.

Run tests inside the venv, keeping generated files local and disabling unrelated
system pytest plugins:

```sh
TMPDIR="$PWD/.runtime/tmp" PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest
```

### Manual KDE checklist — user must run

Use disposable app windows and save important work first.

- [ ] Start Rift on KDE; confirm the UI loads, colors/fonts match Plasma, and
  the terminal has no Qt/Kirigami import errors.
- [ ] Resize Rift to its minimum size and test your normal/fractional display
  scale. In Capture and Rename, confirm the field stays inside the dialog;
  blank/space-only names cannot submit, Enter saves a valid name, and Escape
  cancels. Confirm capture opens the newly created group.
- [ ] Switch between several groups repeatedly. Confirm the selected highlight
  follows the group, the group column stays compact beside the detail view, and
  navigation does not accumulate duplicate detail pages. Check long titles,
  icon tooltips, keyboard focus order, and the empty-group guidance.
- [ ] Use More → Rename/Delete and the entry-removal confirmation. Confirm
  Cancel is initially focused, cancellation changes nothing, and removing an
  entry/deleting a group never closes running windows. Check the explicit
  app-wide Recall warning without closing important browser windows.
- [ ] At minimum height, scroll the matching editor to every field; verify Save
  remains reachable, relative process paths disable it, and saved values persist.
  For a long diagnostic, verify the status area scrolls and permits copying
  without covering the main view.
- [ ] Open Select windows with many main windows running. Check title/app search,
  checkbox keyboard navigation, scrolling, and selections retained across searches.
  Verify Add selected appends only checked entries and Cancel/Escape saves nothing;
  Add windows must still append all main windows. Check on your normal display scale.
- [ ] From Capture windows, test both Capture all and Select specific windows
  when creating the first group and subsequent groups. Confirm Create group
  stores only checked windows; cancelling selection creates no group.
- [ ] Open two different apps, a second main window of one app, and a helper
  dialog. Capture a named group. Verify every main window's title/appId, desktop
  target, and geometry; confirm the helper dialog and Rift are excluded.
- [ ] Append a capture to that group, remove a row, rename it, restart Rift, and
  confirm changes persist. Delete a disposable group and confirm only its saved
  entries disappear; running apps must remain open.
- [ ] Test an app with unreliable/missing appId. Check logged warnings, set
  exact overrides in the editor, restart, and verify the overrides persist and
  distinguish it from an unrelated app. Test an unresolved desktop target.
- [ ] With one app already open and another closed, launch the group. Confirm
  the closed app starts and the existing app is neither duplicated nor moved.
  Repeat launch; all now-running apps must be skipped.
- [ ] Test a DBus-activatable desktop entry and one needing `kstart`. Confirm all
  apps are attempted even when another entry has an invalid launch target.
- [ ] Restart Rift and launch a captured Konsole entry. Confirm `kstart` receives
  `org.kde.konsole`, not its absolute file path, and the new window appears without
  `No such service ""`. Existing Konsole windows must still be skipped.
- [ ] In **Launch target and matching**, choose a valid text `.desktop` file outside XDG
  directories, save its absolute path, and restart Rift to confirm it persists.
  With that app closed, launch the group and confirm the `kioclient` fallback
  opens it without copying/registering the file. Test a path containing spaces
  and `#`, and an external DBus-activatable entry whose activation falls back.
  If KDE requests trust approval or denies execution, stop and ask before
  granting permissions; confirm cancellation/failure is reported by Rift.
- [ ] Set a known invalid text/binary desktop target and verify a useful launch
  error appears rather than only a geometry timeout. Confirm other valid apps
  in the group are still attempted.
- [ ] Close the captured apps yourself, then launch. Verify new windows return
  to captured coordinates/sizes after settling, including negative coordinates
  on a second monitor. Check multi-window/title ambiguity and ensure an error
  is shown rather than an arbitrary placement.
- [ ] Recall a disposable group containing an unsaved document. Confirm save
  prompts appear, unrelated apps stay open, and all matching group-app windows
  receive graceful close requests. Cancel a save prompt to verify no forced exit.
- [ ] Close Rift's main window: confirm it stays in the tray. Reopen it from the
  tray, quick-launch each saved group, verify renamed/deleted menu entries update,
  then use Quit and confirm Rift exits.
- [ ] Switch Plasma light/dark color schemes while Rift is running. Confirm the
  main view, details, dialogs, and controls update without hardcoded colors.
- [ ] Check the terminal/log for KWin script/DBus errors. If access is denied or
  scripts time out, stop and ask before changing any permissions.

## Layout

```text
main.py              Qt application and QML-facing controller
backend/kwin.py      Temporary KWin scripts and asynchronous DBus callbacks
backend/launcher.py  Desktop resolution, matching, launching, restore, recall
backend/storage.py   Parameterized SQLite persistence and additive schema
backend/tray.py      QSystemTrayIcon menu
qml/main.qml         Kirigami group navigation, window cards, actions
qml/AppDialog.qml    Shared bounded modal layout and confirmation labels
qml/NameDialog.qml   Capture/rename field layout and name validation
qml/WindowPicker.qml Searchable, scrollable selective window capture
tests/               Unit and offscreen QML tests
AGENTS.md            Project constraints and approved environment exception
```
