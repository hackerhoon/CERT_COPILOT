# src

Python source for the D4D shared intelligence core.

## Layout

```text
src/d4d/
  config.py                     # env / .env credential loading
  stealthmole/
    auth.py                     # HS256 JWT, fresh token per request
    client.py                   # StealthMoleClient (sync / async / monitoring)
    redaction.py                # mask emails, passwords, IPs, users, hosts
    sanitize.py                 # raw response -> masked, demo-safe view models
    loader.py                   # load sanitized runs from disk
    errors.py                   # typed exceptions (QuotaExceeded, AuthError, ...)
  collect_stealthmole.py        # live-data collector entrypoint
  scenario.py                   # build defensive training scenarios from intel
  report.py                     # render intel + scenarios to HTML / Markdown
  api/
    main.py                     # FastAPI app entrypoint
    routers/                    # health, adapters, home/scenario routes
    envelope.py                 # response/error envelope helpers
  fixtures/readiness.py         # synthetic T5 demo fixtures
  services/scenario_catalog.py  # home/scenario/adapter status services
  repositories/mission.py       # storage port + SQLite/PostgreSQL adapters
```

This maps to the "OSINT / StealthMole Enrichment" adapter in
`architecture/SYSTEM_ARCHITECTURE.md`. The client keeps **raw** responses
separate from **sanitized** view models so the UI, logs, and pitch only ever
touch masked data.

## Requirements

The collector remains standard-library only. The API server uses FastAPI and
uvicorn through `uv`.
Credentials come from the repo-root `.env` (see `.env.tmpl`) only for live
StealthMole collection, not for the fixture API.

Install dependencies:

```bash
uv sync --frozen
```

## Run the readiness API

```bash
uv run uvicorn d4d.api.main:app --reload
```

By default the API uses SQLite at `data/runtime/readiness.sqlite3` through the
`MissionSessionRepository` port. Override storage with:

```bash
# isolated local/dev database
D4D_STORAGE_BACKEND=sqlite D4D_SQLITE_PATH=/tmp/d4d-readiness.sqlite3 \
  uv run uvicorn d4d.api.main:app --reload

# deployment-style PostgreSQL adapter
D4D_STORAGE_BACKEND=postgres D4D_DATABASE_URL=postgresql://user:pass@host:5432/d4d \
  uv run uvicorn d4d.api.main:app
```

Application services do not call SQLite/PostgreSQL directly; they use
`src/d4d/repositories/mission.py`.

Smoke test:

```bash
uv run python -m unittest discover -s tests
```

Real-server E2E:

```bash
uv run python -m unittest tests.test_api_real_server_e2e
```

The E2E test starts uvicorn on a random localhost port and calls the API over
HTTP. It covers `훈련 시작 -> 이벤트 피드 -> 장비 조회 -> 근거 pin -> 판단 저장
-> 대응 제출 -> AAR -> 운영 보조 재사용`, and restarts the server to confirm
SQLite-backed session state survives process restart.

## Run as a backend container

```bash
docker build -t d4d-readiness-backend .
docker run --rm -p 8000:8000 d4d-readiness-backend
```

The container uses SQLite by default at `/app/data/runtime/readiness.sqlite3`.
Mount `/app/data/runtime` if you want container restarts to keep local state, or
set `D4D_STORAGE_BACKEND=postgres` and `D4D_DATABASE_URL` to attach PostgreSQL.

Implemented B-ticket endpoints:

- `GET /api/health`
- `GET /api/adapters/status`
- `GET /api/training/home`
- `GET /api/scenarios`
- `GET /api/scenarios/{scenario_id}`
- `POST /api/training/sessions`
- `GET /api/training/sessions/{session_id}`
- `GET /api/training/sessions/{session_id}/events`
- `POST /api/training/sessions/{session_id}/equipment/query`
- `POST /api/training/sessions/{session_id}/evidence/pins`
- `PUT /api/training/sessions/{session_id}/assessment`
- `POST /api/training/sessions/{session_id}/evaluation/preview`
- `POST /api/training/sessions/{session_id}/actions`
- `POST /api/training/sessions/{session_id}/aar`
- `GET /api/training/sessions/{session_id}/aar`
- `POST /api/ops/cases/from-training-session`

## Run the collector

```bash
# from the repo root
python -m d4d.collect_stealthmole --profile safe
# or, without setting PYTHONPATH:
python src/d4d/collect_stealthmole.py --profile safe
```

`--profile safe` (default) pulls quotas, the rm/gm/lm monitoring feeds, and
the tt/cdf target lists — low quota cost, no leaked-credential payloads.

`--profile full` adds one `cl`/`cds` credential search and one `tt` async
search. These charge quota and can return sensitive data (masked on output).
Override the query with `--sync-query "domain:yourdomain.com"`.

Output goes to `data/stealthmole/` (git-ignored). See that folder's README.

## Build the human report + scenarios

```bash
python -m d4d.report                 # uses the latest run
python -m d4d.report --run 20260704T041030Z
```

This reads a sanitized run and writes a browser-openable HTML dashboard and a
Markdown report to `data/stealthmole/reports/`, plus one JSON per **defensive**
training scenario to `data/stealthmole/scenarios/`. Scenarios are built by
`scenario.py`: the first scenario, `SCEN-MAIN-STEALTH-000`, attaches
StealthMole enrichment to the T5 main demo flow (request + TrusGuard-like log +
Genian NAC-like attribution + directive/blacklist gap). Other
scenarios remain standalone defensive drills. Injects present observable clues
from the real intel, and the expected trainee actions are detection / triage /
containment-request / reporting — never offensive steps. Unit context is
synthetic and all external indicators stay masked.

## Use the client from code

```python
from d4d.stealthmole import StealthMoleClient, load_stealthmole_config, sanitize

client = StealthMoleClient(load_stealthmole_config())
quotas = sanitize.sanitize_quotas(client.get_quotas())
```
