# Repository Guidelines

## Project Structure & Module Organization
- `config/` centralizes environment handling; call `get_settings()` from `config/settings.py` for paths and secrets (DB, static assets, app secret).
- `data/` owns SQLite persistence in `database.py`. Keep SQL in this layer—routes or services should import helpers like `list_bots()` and `upsert_flow()` instead of opening connections directly.
- `core/` bundles runtime logic: `runtime.py` hosts the bot process manager, `flows.py` executes Blockly flows, `pseudo.py` parses/prints Chinese pseudocode, and `ai.py` integrates DeepSeek with local fallbacks.
- `interact/` provides the Flask surface. `interact/__init__.py` exposes `create_app()`, while `interact/routes/` splits auth, bot CRUD, flow editing, AI endpoints, and runtime controls into focused modules. Static assets stay in `static/`.
- Legacy shims (`app.py`, `db.py`, `flow_engine.py`, etc.) re-export the new packages so older scripts remain functional; prefer the structured modules for new work.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` — create/activate a virtualenv.
- `pip install -r requirements.txt` — install backend dependencies; add `openai` when using DeepSeek.
- `python main.py` — launch the Flask API + SPA at `http://0.0.0.0:8000` (runs `create_app()`).
- `python -m py_compile $(git ls-files '*.py')` — fast syntax gate before sending patches.

## Coding Style & Naming Conventions
- Python files use 4-space indentation, snake_case modules, CamelCase classes, UPPER_SNAKE constants.
- Annotate function signatures; prefer `Dict[str, Any]`/`list[str]` hints where practical.
- JSON responses stick to snake_case unless matching front-end expectations; document non-trivial helpers with short docstrings (see `core/ai.py`).

## Testing Guidelines
- Place tests under `tests/` mirroring package layout (e.g., `tests/core/test_runtime.py`). Use pytest fixtures for temporary SQLite files.
- Cover happy paths and failure branches (permission denials, JSON validation). Add regression tests when fixing bugs reported in the UI.
- Run `pytest -q` locally; record command + result in PR discussions or release notes.

## Commit & Pull Request Guidelines
- Write imperative commit subjects (`Add runtime blueprint router`). Squash noisy WIP commits before review.
- Describe scope, configuration impacts (`DEEPSEEK_API_KEY`, `BOT_ADMIN_DB`), and manual/automated test evidence.
- Attach screenshots or screencasts when altering `static/` UX so reviewers can assess UI changes quickly.
