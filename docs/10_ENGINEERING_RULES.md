# 10. Engineering rules

Binding rules for building and evaluating the system. Requirements (doc 02) cite these sections as evidence.

## 1. Scope

| In scope | Out of scope (needs a logged scope-change decision first) |
|---|---|
| Responsive web app (desktop, laptop, tablet browsers) | Native mobile apps |
| Three modules: inventory forecasting, scheduling and defaulters, health passport | National DHIS2 or KHIS integration, live LMIS feeds |
| Kenya KEPI schedule for children under 2 | HPV and adult vaccines, campaigns (SIAs) |
| Forecasting with seasonal naive, moving average, ARIMA/SARIMA, GRU | Other deep architectures without a logged decision |
| Rule-based defaulter priority; optional risk score (D-11) | Automated SMS to caregivers (future work) |
| FHIR R4 Immunization records; SMART Health Card export only if decided (D-09) | Blockchain, IoT cold-chain sensors |
| Read-only offline cache of dashboards; queued offline writes only if decided (D-10) | Full offline-first sync engine |
| Fully synthetic, seeded data calibrated to published KDHS 2022 figures (D-02) | Any real patient data or requested microdata |

## 2. Data

- All data is synthetic (D-02) and comes only from `immdss simulate` (seeded; configuration in `analytics/configs/sim.yaml`). Generated files are never edited by hand; the generator is fixed and the data regenerated. Every configuration value is marked PUBLISHED (with its source) or ASSUMPTION.
- Only a run's `app/` folder is loaded into the application. `truth/` (true demand, stock-out weeks, child background, dropout) is for evaluation only and never reaches the database, the API or the user interface.
- A run is usable only if `immdss validate-sim` passes all checks; its `manifest.json` (hashes, seed, configuration hash, commit) is cited for every number in the report.
- CSV import cleaning is measured against `imports/import_dirty_truth.csv` (recall per defect type, false rejections).
- No leakage: forecast evaluation uses rolling-origin backtests with the test horizon strictly after the training window; scalers and encoders are fitted on training data only; models see administered doses only, never true demand.
- Synthetic child records are treated as sensitive health data (Kenya Data Protection Act, 2019): role and facility scoping, audit logging, no identifiers in logs, no phone numbers stored.

## 3. Security

- Every API endpoint has an explicit permission class; the default is authenticated access; any public endpoint needs a logged decision. No public registration: the administrator creates users.
- Fail closed: a missing or invalid token, role or facility scope is rejected before any business logic runs. Authorization is enforced on the server, never by hiding interface elements.
- Roles: health worker (child records and stock transactions for their own facility; reads forecasts and plans), facility manager (full access to their own facility and its configuration), system administrator (users and system configuration, no clinical data by default). Every query is scoped by facility through one shared mixin; a test proves cross-facility access is denied.
- JWT: short-lived access token held in memory in the browser; refresh token in an HttpOnly, Secure, SameSite cookie with rotation and revocation on logout. Login throttling and lockout, tested.
- Passwords hashed with Argon2, minimum length 12. Secret comparisons in constant time.
- Input validation in serializers for every write and every filter parameter; ORM only, no string-built SQL.
- Startup validation: the backend refuses to start if the secret key, database credentials, the passport signing key (if D-09 is on) or the initial administrator password are missing, short or still a placeholder. No working credential appears in settings, `.env.example`, compose files or seeders; compose credentials use required-variable syntax.
- CORS allow-list; CSRF protection on cookie-authenticated endpoints; security headers (CSP, content-type options, frame options, referrer policy) with a test.
- Comments and documents state technical rationale only.

## 4. Engineering conventions

- Python 3.12, Django 5.x, Django REST Framework, PostgreSQL 16, `ruff`, type hints on public functions, `pytest` with `pytest-django`.
- Django apps: `accounts`, `facilities`, `passport`, `inventory`, `scheduling`, `analytics_api`. Business logic in `services.py`, not in views or serializers.
- Migrations are reviewed before running, reversible where possible; new NOT NULL columns on existing tables carry a default; indexes are named. Never force migration commands.
- `analytics/` is an installable package that never imports Django; the backend uses its outputs through a narrow interface.
- Forecast jobs run as a management command (`run_forecasts`) scheduled by cron (D-13).
- Frontend: React 18 with Vite and TypeScript (D-05), React Router, TanStack Query, Recharts, Jest and React Testing Library. Every chart has a table alternative and a colour-blind-safe palette; responsive from 360 px.
- Reproducibility: fixed seeds, pinned dependencies, and a manifest for every training or backtest run.

## 5. Models and evaluation

- Every metric is defined once in doc 05 (formula, unit, horizon, denominator).
- Forecasts are always reported against the seasonal naive and moving-average baselines, with MAE, MASE and sMAPE (never plain MAPE on series with zeros). Stock-out alerts: precision, recall, F1 and lead time against simulator ground truth.
- The proposal's accuracy target is evaluated exactly as defined in D-07; defaulter classification is proven by an independent oracle test with exact match.
- A result enters a document only if its run is logged; disappointing results are reported, not hidden.

## 6. Testing

- Levels: unit, integration, system and end-to-end, security, performance (dashboard under 3 s), usability and acceptance (SUS). Test IDs `TC-<level>-<nn>`.
- Every endpoint and role pair has an authorization test (allowed and denied), including cross-facility denial.
- Tests fail for the right reason first, then pass; tests are never weakened or skipped to get green.
- Results go to `logs/TEST_LOG.md` and the results ledger.
