# 11. Project handbook

The single reference for how the Immunization Decision Support System works: status, setup, Docker, data generation, every script and command, roles and what each can access, and how everything is checked. Detailed stage-by-stage data and training plan: doc 12. Data generation, storage and role access in one place: doc 13. Decisions: doc 07. Rules: doc 10.

Status as of 29 September 2026. Evidence run: `sim-seed42-368707d3`.

---

## 1. What the system is

A web application that helps healthcare workers close childhood immunization gaps (Kenya, KEPI schedule, children under 2). Three modules share one PostgreSQL database:

| Module | What it does for the user | Status |
|---|---|---|
| M1 Predictive inventory | Stock per vaccine from the stock ledger, weeks of stock left; later a 4-week demand forecast and stock-out alerts | Stock and ledger done; forecasts and alerts in Phase 4 |
| M2 Scheduling and defaulters | Children under 2 with a dose more than 28 days overdue, ranked (most overdue doses first, then nearest to an age limit); outreach sessions | List and sessions done; session plan with vaccine quantities in Phase 4 |
| M3 Health passport | Register children, record doses with schedule checks, full history and next due doses, search across facilities | Done; FHIR export in Phase 5 |

All data is synthetic (D-02): simulated data is used because no facility-level dataset exists publicly.

## 2. Status by phase

| Phase | Name | Status | Evidence |
|---|---|---|---|
| 0 | Setup | Done | commit `a308e62`; tests in the results ledger |
| 1 | Synthetic data and EDA | Done | doc 04, `evidence/EDA_sim-seed42-368707d3.md`, `logs/DATA_CLEANING_LOG.md` |
| 2 | Requirements and design | Drafted, supervisor review pending | doc 02, `diagrams/`, `wireframes/` |
| 3 | Prototype 1 | Built and tested; gate review, screenshots, merge and `p1` tag pending | branch `phase/3-prototype-1`, `evidence/P1_walkthrough_*.md` |
| 4 | Models and Prototype 2 | In progress: training series, backtest, comparison and the Colab notebook built and tested locally; **no model has been trained yet** (training runs on Colab only, D-14) | branch `phase/4-models`, doc 12 stages 7 to 11, `notebooks/immdss_colab_pipeline.ipynb` |
| 5 to 8 | Refinement and testing, user acceptance testing, documentation, demonstration | Not started | doc 01 |

"Calibration" in Phase 1 adjusted the data generator until it matched published coverage figures. It is not model training.

## 3. Roles and what each can access

### 3.1 As defined in the proposal (section 3.8.4)

| Role | Proposal wording |
|---|---|
| Healthcare worker | read/write access to child records and stock data, read-only access to forecasts and session plans |
| Facility manager | full read/write access to all modules and facility configuration |
| System administrator | user management and system-wide configuration |

Project rules add: every role is limited to its own facility, the administrator has no clinical data by default, and there is no self-registration (doc 10 section 3).

### 3.2 As implemented (checked by the endpoint x role test matrix)

| Area and endpoint | Health worker | Facility manager | System administrator | Not signed in |
|---|---|---|---|---|
| Log in, refresh session (`auth/login`, `auth/refresh`) | yes | yes | yes | yes (public by necessity, D-31; throttled) |
| Log out, own profile (`auth/logout`, `auth/me`) | yes | yes | yes | no |
| Children of own facility: list, register (`children`) | yes | yes | no | no |
| Search children across facilities (`children/search`) | yes, read-only, logged | yes, read-only, logged | no | no |
| Child record and history (`children/<id>`, `.../immunizations` GET) | yes (other facilities read-only, logged) | yes (same) | no | no |
| Record a dose (`.../immunizations` POST) | own facility only | own facility only | no | no |
| Vaccine schedule (`schedule`) | read | read | no | no |
| Stock balance and ledger (`stock/balance`, `stock/transactions`) | read and record | read and record | no | no |
| Defaulter list (`defaulters`) | read | read | no | no |
| Sessions (`sessions`) | read | read and create | no | no |
| CSV import (`imports`) | no | yes | no | no |
| Facility audit log (`audit`) | no | yes | no | no |
| Users (`admin/users`) | no | no | list and create | no |
| Facilities (`admin/facilities`) | no | no | list | no |

Gaps against the proposal, planned: forecasts and alerts (read for the health worker, read and acknowledge for the manager) and stock policy configuration by the manager (Phase 4); schedule editing by the administrator (FR-03, later phase).

Every refusal happens on the server before any data is read: a request without a valid token gets 401, a signed-in user without the right role or facility gets 403. The screens only hide what a role cannot use.

### 3.3 Demo accounts

Created by `python3 scripts/dev.py demo-users`:

| Account | Role | Facility |
|---|---|---|
| `admin` | System administrator | none; password is `DJANGO_INITIAL_ADMIN_PASSWORD` in `.env` |
| `fm-syn-<code>`, for example `fm-syn-h01` | Facility manager | one per facility (12) |
| `hcw-syn-<code>`, for example `hcw-syn-d01` | Health worker | one per facility (12) |

Passwords are random and written only to `.demo_credentials.txt` in the repository folder (owner-only, never committed). Logging in as `admin` shows only Administration by design; use a manager or health worker account to see the dashboards.

## 4. Setting up a machine

### 4.1 Tools

| Tool | Version | Why |
|---|---|---|
| Python | 3.12 | analytics package and backend |
| Node.js | 20 or 22 | frontend |
| Docker with Compose v2 | recent | PostgreSQL 16 (and PlantUML for diagrams) |
| Git | recent | version control |

### 4.2 First run

```bash
git clone git@github.com:shantelle04/immunization-dss.git
cd immunization-dss
python3 scripts/dev.py setup        # .venv, pinned Python and npm packages, git hooks
python3 scripts/dev.py bootstrap    # .env with random secrets, database up, Django check, all tests
python3 scripts/dev.py simulate     # generate and validate the synthetic data (about 2 minutes)
python3 scripts/dev.py eda          # exploration figures
cd backend && ../.venv/bin/python manage.py migrate && cd ..    # create the database tables
python3 scripts/dev.py load         # load the data into the database (about 1 minute)
python3 scripts/dev.py demo-users   # demo accounts
python3 scripts/dev.py run          # open http://localhost:5173
```

Windows (PowerShell): use `py scripts\dev.py ...` and `..\.venv\Scripts\python manage.py migrate`. Repository-local git settings (SSH key, identity, push guard): doc 08.

### 4.3 Environment file

`.env` holds every secret and is never committed or printed. `python3 scripts/dev.py env` creates it from `.env.example` with random values and refuses to overwrite an existing one.

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | signs sessions and tokens (at least 50 characters) |
| `DJANGO_INITIAL_ADMIN_PASSWORD` | password of the `admin` demo account (at least 12) |
| `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` | development switches (debug off by default) |
| `POSTGRES_SUPERUSER_PASSWORD` | database superuser inside the container |
| `DB_HOST`, `DB_PORT`, `DB_NAME` | database address (127.0.0.1, 5433, immdss) |
| `DB_USER`, `DB_PASSWORD` | the application's database account |
| `DB_TEST_USER`, `DB_TEST_PASSWORD` | a separate account used only by tests |
| `IMMDSS_TODAY` | clinical "today" for the synthetic demo (2025-12-29); empty means the real date (D-32) |

Django refuses to start if a secret is missing, too short, or still the example value.

## 5. Docker

Docker is used for the database so every machine gets the same PostgreSQL. It is required.

| Item | Setting |
|---|---|
| File | `docker-compose.yml` |
| Service | `db`, image `postgres:16` |
| Address | `127.0.0.1:5433` on the host (5432 was already in use on the development laptop; change `DB_PORT` if needed) |
| Data | Docker volume `immdss_pgdata` (survives restarts; `dev.py db-reset` deletes it after asking) |
| First start | `backend/docker/initdb/01-roles.sh` creates the application and test accounts from `.env`, refusing short or example passwords and a shared account |
| Credentials | required variables (`${VAR:?}`): the container will not start without them |

| Command | What it does |
|---|---|
| `dev.py db-up` | start the database and wait until healthy |
| `dev.py db-down` | stop it (data kept) |
| `dev.py db-shell` | open `psql` inside the container as the application account |
| `dev.py db-reset` | delete the volume (asks first); the next `db-up` recreates the accounts |

If Docker is not running after a restart: `sudo systemctl start docker` (Linux) or start Docker Desktop (Windows, macOS).

A second image, `plantuml/plantuml` (pinned by digest), is used only by `dev.py diagrams`, in a container limited to 768 MB.

## 6. Every command and script

### 6.1 The runner: `scripts/dev.py`

One command runner for Linux, macOS and Windows (standard library only). Result-producing commands append a line to `docs/logs/results_ledger.jsonl`.

| Command | What it does | Recorded |
|---|---|---|
| `setup` | create `.venv`, install `requirements.txt` and `frontend/package-lock.json`, enable `scripts/hooks` | |
| `env` | create `.env` with random secrets (never overwrites, prints no values) | |
| `bootstrap` | `env` if needed, `db-up`, `check`, `test` | yes |
| `db-up`, `db-down`, `db-shell`, `db-reset` | database control (section 5) | |
| `check` | Django system check, including the startup secret checks | yes |
| `test [all\|analytics\|scripts\|backend\|frontend]` | run the test suites | yes |
| `lint` | ruff lint and format check | yes |
| `simulate [--force]` | generate the synthetic data; skipped in about 1 s if an identical validated run exists | yes |
| `validate [run]` | rerun the 11 data checks | yes |
| `eda [run]` | exploration figures and dataset table | yes |
| `load [run] [--replace]` | load a validated run's `app/` folder into the database | yes |
| `demo-users [--reset]` | create demo accounts, passwords to `.demo_credentials.txt` | yes |
| `walkthrough [run]` | prototype evaluation: latency, accuracy against truth, import cleaning | yes |
| `run` | start the backend (127.0.0.1:8000) and frontend (http://localhost:5173); Ctrl+C stops both | |
| `diagrams` | regenerate the schema diagrams and data dictionary, render all PlantUML to `docs/evidence/` | yes |
| `history` | turn the ledger into `docs/logs/RESULTS_HISTORY.md` | |

Heavy commands run at low CPU priority with numeric libraries limited to one thread.

### 6.2 Analytics package: `analytics/src/immdss_analytics/` (never imports Django)

| File | Job |
|---|---|
| `cli.py` | the `immdss` command: `simulate`, `validate-sim`, `eda`, `build-series`, `backtest`, `train-final` |
| `sim/config.py` | reads and checks `sim.yaml`, listing every problem at once |
| `sim/population.py` | facilities, births, child backgrounds in KDHS proportions |
| `sim/behaviour.py` | attendance, dropout and lateness per child |
| `sim/calibrate.py` | fits the generator to KDHS 2022 coverage (cohort stage, then damped engine stage) |
| `sim/engine.py` | session-by-session clinic simulation: doses, stock, deliveries, disruptions, batching |
| `sim/stock.py` | vials, lots, open-vial rules, stock at one facility for one vaccine |
| `sim/dirty.py` | the deliberately broken import files and their answer key |
| `sim/outputs.py` | writes the run folder and `manifest.json`; decides whether an identical run can be reused |
| `sim/validate.py` | the 11 checks and the validation report |
| `eda.py` | figures F-D1 to F-D8 and table T-5.1 |
| `forecast/series.py` | weekly issues per facility and vaccine from the stock ledger, cleaning rules T-01 to T-03 (`build-series`) |
| `forecast/metrics.py` | MAE, MASE, sMAPE, 80% interval coverage (doc 05) |
| `forecast/models.py` | B1 seasonal naive, B2 moving average, SARIMA with Fourier seasonality (D-36) |
| `forecast/gru.py` | the global GRU with quantile loss |
| `forecast/backtest.py` | rolling-origin backtest, scoring, comparison, selection (D-21), bias against truth, final fit |
| `forecast/guard.py` | refuses SARIMA and GRU fitting outside Google Colab (D-14; exit code 3) |
| `forecast/commands.py` | the files each forecasting command writes |
| `configs/evidence_hashes.json` | SHA-256 of every file of the evidence run and of its training series; Colab checks its regenerated data against it |
| `../notebooks/immdss_colab_pipeline.ipynb` | the Colab notebook: generation to final models, one cell per stage (doc 12 stage 10) |
| `configs/sim.yaml` | every generator setting (PUBLISHED or ASSUMPTION) |
| `configs/evidence_run.txt` | which run the thesis cites |

### 6.3 Backend: `backend/` (Django REST Framework)

| Path | Job |
|---|---|
| `config/settings.py` | settings; refuses to start on missing or weak secrets (`config/preflight.py`) |
| `config/urls.py` | the API routes under `/api/v1/` |
| `apps/accounts/` | users, roles, login with lockout, token refresh and logout, audit log, permissions, `seed_demo_users` command |
| `apps/facilities/` | facilities |
| `apps/passport/` | children, schedule, dose status, registration, dose recording, search |
| `apps/inventory/` | stock ledger, balances, weeks of stock left; forecast and alert tables for Phase 4 |
| `apps/scheduling/` | defaulter list and ranking, sessions |
| `apps/analytics_api/` | CSV import validation, `loader.py`, `load_synthetic` command |
| `apps/*/migrations/` | database changes (reviewed before running, all reversible) |
| `evaluation/walkthrough.py` | the only code that reads `truth/`, for scoring; not part of the running application |
| `tests/` | 188 tests: security, permissions matrix, clinical rules, stock, imports, loader, schema conformance, truth isolation |
| `docker/initdb/01-roles.sh` | creates the database accounts on first start |

### 6.4 Frontend: `frontend/` (React, TypeScript, MUI)

| Path | Job |
|---|---|
| `src/api.ts` | talks to the API; access token kept in memory only, one silent refresh on expiry |
| `src/auth.tsx` | sign-in state |
| `src/routes.tsx` | sends each role to its home screen |
| `src/components.tsx` | layout, navigation, the "synthetic data" notice |
| `src/pages/` | Login, Inventory, Scheduling, Children, Child record, Administration |
| `src/App.test.tsx` | 6 tests (login, role routing, token refresh, duplicate warning) |
| `vite.config.ts` | development server on port 5173, forwarding `/api` to the backend |

### 6.5 Documentation tools

| Script | Job |
|---|---|
| `docs/diagrams/gen_schema.py` | builds F-ERD, F-LDS and `data_dictionary.md` from `schema.yaml` |
| `docs/progress/build_report.py` | builds the Word progress report from the progress tracker (needs pandoc) |
| `scripts/hooks/pre-commit`, `pre-push` | refuse local-only files, machine paths, and pushes to anyone but the owner |

## 7. How the data is generated and stored

```
sim.yaml -> immdss simulate -> data/synthetic/<run_id>/ -> 11 checks -> EDA -> load app/ -> PostgreSQL
```

| Folder in the run | Contents | Used for |
|---|---|---|
| `app/` | facilities, schedule, children, doses given, stock ledger, sessions, lots | running the system; training the forecast models (Phase 4) |
| `truth/` | true demand and stock-out weeks, every child born, doses refused for lack of stock | scoring only; never loaded, never given to a model |
| `imports/` | broken CSV files and their answer key | measuring the import checks |

The run folder (53 MB) stays on the machine and is never committed; `simulate` rebuilds it byte for byte, which the manifest's hashes prove. Full stage-by-stage description, cleaning rules and the training plan: doc 12.

## 8. How it is checked

| Check | How | Latest result |
|---|---|---|
| Data quality | 11 checks per generated run | 11 of 11 pass |
| Automated tests | `dev.py test` | backend 188, analytics 33, runner 5, frontend 6: all pass |
| Security | endpoint x role matrix, cross-facility denial, lockout, token rotation, CSRF, headers | all pass |
| Database design | schema conformance test against `schema.yaml` | 18 of 18 tables match |
| Prototype walkthrough | `dev.py walkthrough` | 100% accuracy on 3 truth checks; slowest p95 326 ms; 119 of 120 planted import errors caught, 0 of 697 clean rows rejected |
| History of every result | `logs/results_ledger.jsonl`, `dev.py history` | continuous |

## 9. Tracking checklist

| Item | Done |
|---|---|
| Repository, hooks, identity, first push | yes |
| `.env`, Docker database, all tests on this machine | yes |
| Synthetic data generated, validated, explored | yes |
| WHO and Ministry of Health source checks | yes |
| Requirements frozen, diagrams, wireframes | yes (supervisor review pending) |
| Database migrated and loaded | yes |
| Prototype 1 screens and APIs | yes |
| Prototype 1 walkthrough | yes |
| Screenshots F-WF1 to F-WF4 and F-UI-* | author to capture |
| Gate G3 review, merge, `p1` tag | pending author sign-off |
| Training series, backtest and selection code, Colab notebook | built and tested locally |
| Colab run: backtest of B1, B2, SARIMA, GRU; comparison; final models | author to run on Colab after the push |
| Stock-out alerts, nightly forecast job, Prototype 2 screens | Phase 4, next |
| Supervisor: D-02, D-07, D-12, D-25, D-27 | pending |
