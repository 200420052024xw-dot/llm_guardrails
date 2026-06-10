# Repository Guidelines

## Project Structure & Module Organization

This repository is a Python FastAPI MVP for an LLM guardrails gateway. The entry point is `app.py`. Core request/response schemas, orchestration, and shared exceptions belong in `core/`. Runtime configuration lives in `config/`, including `config/model.yaml` and settings loaders. Logging helpers belong in `logs/`. Project notes and architecture references are in `project_infor/`. Tests are not present yet; add them under `tests/` using the same module names, for example `tests/test_orchestrator.py`.

## Build, Test, and Development Commands

Create and activate a virtual environment before installing dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the local API with:

```powershell
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Run tests with `pytest` once test files exist. Use `python -m pytest` if the active environment has multiple Python installations.

## Coding Style & Naming Conventions

Use Python 3.11+ syntax and 4-space indentation. Name modules and functions with `snake_case`, classes with `PascalCase`, and constants with `UPPER_SNAKE_CASE`. Keep FastAPI route handlers in `app.py`; move business logic into `core/` so routes remain thin. Prefer Pydantic models for API contracts and structured dictionaries only at external integration boundaries. Keep imports grouped as standard library, third-party, then local modules.

## Testing Guidelines

Use `pytest` and `pytest-asyncio` for async flows. Mirror source modules in test names: `core/orchestrator.py` should have `tests/test_orchestrator.py`. Test the main gateway paths: `allow`, `redact`, `block`, detector failures, policy failures, and LLM call failures. Mock external LLM calls with `unittest.mock` or pytest fixtures; tests must not require real API keys or network access.

## Commit & Pull Request Guidelines

Git history was not available during guide generation, so use simple imperative commit messages such as `Add guardrail schemas` or `Handle LLM timeout`. Keep commits focused on one behavior or module. Pull requests should include a short summary, commands run, related issue or task, and sample request/response output for API behavior changes. Include screenshots only when a UI or rendered documentation changes.

## Security & Configuration Tips

Do not commit `.env`, API keys, customer data, or real secrets. Keep provider URLs, model names, timeouts, and key environment variable names in `config/`. Audit logs should store request IDs, action, risk score, and short sanitized previews rather than full sensitive prompts.
