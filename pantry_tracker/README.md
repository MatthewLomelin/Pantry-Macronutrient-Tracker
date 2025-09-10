# Macro & Pantry Tracker

A tiny Flask + SQLite app to track pantry inventory and daily macros with a clean HTML/CSS UI.

## Setup

```bash
python -m venv .venv
# Windows PowerShell
. .venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Visual Studio Code notes

- **Run in VS Code**: Use the provided *Run and Debug* config: **Flask: Macro & Pantry Tracker**.
- **Preview inside VS Code**: Press `Ctrl+Shift+P` → “Simple Browser: Show” → enter `http://127.0.0.1:5000`.
  - Do **not** open `index.html` directly in the preview (that serves from the file system and the `/api/*` calls won’t work).
- If you’re in Codespaces/remote, forward port **5000** and use the forwarded URL in Simple Browser.

## Optional: CORS

If you really want to open `index.html` as a file or with the Live Preview extension (different origin),
enable CORS by uncommenting the lines in `app.py`:

```python
# from flask_cors import CORS
# CORS(app)
```

But the recommended way is to visit `http://127.0.0.1:5000` so everything shares the same origin.
