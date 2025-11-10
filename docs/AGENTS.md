# Repository Guidelines

## Project Structure & Module Organization
- `mountainstat-main/` is the production Vite + React UI targeting the Python backend (`MOUNTAINSTAT_MIGRATION_PLAN.md`); core views sit in `src/App.jsx` and `src/System.jsx`.
- `mountainstat/` is the SSE prototype—experiment there, then cherry-pick proven work into `mountainstat-main`.
- `cz2/` hosts the FastAPI + CLI backend (`src/pycz2/`) and pytest suites (`tests/`).
- Scripts `verify_implementation.sh` and `test_sse_202.py` live in `mountainstat/` for backend/API smoke testing.

## Build, Test, and Development Commands
- UI workflow: `cd mountainstat-main && npm install && npm run dev -- --host`; build with `npm run build`, preview via `npm run preview`, run tests with `npm test`. Docker image available with `docker build -t mountainstat-frontend .`.
- SSE sandbox: `cd mountainstat && npm install && npm run dev -- --host`; use this branch when iterating on `/events` behaviour.
- Backend setup: `cd cz2 && uv sync --frozen` for runtime installs or `uv pip install -e .[dev]` for tooling.
- Start the API with `cd cz2 && uv run pycz2 api`; expose via `uv run uvicorn pycz2.api:app --host 0.0.0.0 --port 8000`. Container build: `cd cz2 && docker build -t mountainstat-backend .`.
- Full-stack check: in `mountainstat/`, run `./verify_implementation.sh`, then `python3 test_sse_202.py` once the API responds.

## Coding Style & Naming Conventions
- JavaScript/JSX uses ES modules, 2-space indents, double quotes, PascalCase components, and camelCase hooks/utilities; colocate helpers and prefer React function components with hooks.
- Keep API access in `src/apiService.js` or colocated service modules.
- Python is async-first, typed, and capped at 88 columns; lint with `uv run ruff check .`, type-check via `uv run mypy src/`, run strict Pyright with `uv run pyright src/`, and surface critical issues with `uv run pylint src/ --errors-only`.
- Store configuration in ignored `.env` files and document required keys in `.env.example` or README updates.

## Testing Guidelines
- Backend: `cd cz2 && uv run pytest` (new parity tests in `tests/api/test_status_flat.py`).
- Frontend: `cd mountainstat-main && npm test -- --run` (Vitest + Testing Library). Use `npm run test:ui` for interactive runs.
- SSE Prototype: `python3 test_sse_202.py` exercises `/events` + command queue; keep logs when troubleshooting SSE jitter.

## Commit & Pull Request Guidelines
- Follow existing commit style: concise headline plus bullet-style notes on fixes and validations.
- Keep commits deployable; separate UI and backend work when possible and flag cherry-picks from `mountainstat/`.
- PRs should outline user impact, configuration changes, linked planning docs (especially the migration plan), and include screenshots or payload samples for UI/API changes.

## Configuration & Integration Tips
- UI branches read `VITE_API_BASE_URL` (default `http://localhost:8000`) and optional `VITE_MQTT_WS_URL`; adjust `.env` when proxying through Caddy or Tailscale. For Docker deploys, runtime overrides come from `/config.js`.
- Backend settings start from `cz2/.env.example`; commit only sanitized templates (includes cache, SSE, and command queue flags).
- Align schema changes by updating `apiService.js` and the corresponding FastAPI responses in the same PR to keep the migration on track.
