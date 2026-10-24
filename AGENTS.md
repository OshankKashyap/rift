# Rift project rules

- Work only inside `/home/oshank/Projects/rift`; keep databases, temporary scripts, caches, and the virtual environment here.
- Never run git commands, initialize a repository, push, or alter existing version-control files.
- Never install system packages. Ask the user to install missing prerequisites.
- Use the OS-default Python to create `.venv`; pip-install only dependencies in `requirements.txt` into it.
- Approved compatibility exception: `.venv` uses `--system-site-packages` to read Fedora's existing PySide6/Qt/Kirigami stack. Keep pytest local; do not replace or modify system packages. Pip Qt wheels have incompatible private ABIs here.
- Stack: PySide6, QML, Kirigami, Python backend, SQLite. Preserve the requested flat backend layout.
- No assumptions: stop and ask when requirements, permissions, or user actions are unclear.
- Use parameterized SQL and additive schema changes. Never send SIGKILL; recall uses KWin close requests.
- Capture main windows only. Skip running apps; restore geometry asynchronously. Report ambiguous identities and offer manual overrides.
- Use the Plasma theme without hardcoded colors.
- Test storage and matching/deduplication with pytest inside `.venv`. Document KDE-only checks without claiming they passed.
- Keep changes minimal; no extra libraries or unrelated features.
