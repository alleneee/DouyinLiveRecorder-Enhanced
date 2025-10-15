# Repository Guidelines

## Project Structure & Module Organization
- **`app/`**: FastAPI service, modern recording runtime, and core domain modules. Key subpackages include `core/recording` for supervisors/workers, `services/` for DB-facing logic, and `runtime.py` for bootstrap.
- **`app/legacy/`**: Compatibility layer reusing the classic spider/stream stack. Only touch when extending legacy platform support.
- **`config/` & `backup_config/`**: Runtime INI sources. `URL_config.ini` remains the default room registry; keep backups in sync.
- **`downloads/` & `logs/`**: Output artifacts; never commit generated media or log files.
- **`tests/` & `tests/verify_*.py`**: Pytest suites plus higher-level flow checks (OSS, FFmpeg). Mirror new features here.
- **`openspec/`**: Architecture specs that govern contributor expectations—review before structural work.

## Build, Test, and Development Commands
- `uv venv && source .venv/bin/activate`: create/activate the project virtualenv (use `uv` for speed).
- `uv pip install -r requirements.txt`: install Python dependencies; append `--system` only in constrained environments.
- `uvicorn app.main:app --reload --port 8009`: launch the API for end-to-end testing.
- `pytest -q`: run unit and integration tests; add `tests/verify_oss_flow.py` for manual OSS checks.

## Coding Style & Naming Conventions
- Follow PEP 8 with Black configuration (`line-length = 88`). Run `black`/`isort` if large edits are made.
- Prefer descriptive snake_case for functions and variables; use UpperCamelCase for ORM models/Pydantic schemas.
- Keep changes minimal: respect existing module boundaries and avoid renaming unless required by specs.

## Testing Guidelines
- Use Pytest; test modules mirror source layout (`tests/recording/test_*`).
- Add regression tests when touching recording supervisors, workers, or repository persistence.
- For OSS/FFmpeg paths, rely on existing integration scripts (`tests/verify_oss_flow.py`) and document manual prerequisites.

## Commit & Pull Request Guidelines
- Write Conventional-style summaries (`fix:`, `feat:`, `docs:`) followed by a concise purpose, e.g., `feat: add douyin h265 stream handler`.
- Each PR should reference related issues, describe configuration changes, and include test evidence (`pytest` output or manual logs).
- Capture before/after behavior for recording workflows, especially when modifying `SegmentRecordingWorker` or OSS uploader settings.

## Security & Configuration Tips
- Never commit real OSS keys or room cookies. Store secrets in `.env` and redact when sharing logs.
- Update `config/*.ini` only through dedicated tasks; document rationale in PR descriptions to keep audit trails clear.
