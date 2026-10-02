# 14. User guide, running the system and demo script

How to start the system, what each screen does for each role, how forecasts and alerts are produced, how trained models from Colab are brought in, and a demonstration script. Setup of a new machine: doc 11. Data: doc 13. Decisions: doc 07.

## 1. Start the system

| Step | Command | What it does |
|---|---|---|
| 1 | `python3 scripts/dev.py db-up` | Starts PostgreSQL 16 in Docker (port 5433) |
| 2 | `python3 scripts/dev.py load` | Loads the evidence run's `app/` folder (first time only, about 60 s) |
| 3 | `python3 scripts/dev.py demo-users` | Creates the administrator and one manager and one health worker per facility; passwords go to `.demo_credentials.txt` (never committed) |
| 4 | `python3 scripts/dev.py forecasts` | Stores the 4-week forecasts and refreshes stock-out alerts (about 2 s; see section 4) |
| 5 | `python3 scripts/dev.py run` | Backend on 127.0.0.1:8000 and the app on http://localhost:5173; Ctrl+C stops both |

On Windows use `py scripts\dev.py <command>`. The clinical date is pinned to the dataset's as-of date, 29 December 2025 (D-32), so overdue doses and alerts look as they would on that day.

**On a phone or tablet.** The app is mobile first: under 900 px wide the side menu becomes a bottom bar, and under 600 px every table becomes a list of labelled cards, so nothing scrolls sideways. To open it from a phone on the same network, the backend's allowed hosts and trusted origins must include the laptop's address (`DJANGO_ALLOWED_HOSTS`, `DJANGO_CORS_ORIGINS` in `.env`; set them yourself) and Vite must listen on the network (`npm run dev -- --host` in `frontend/`). Browsers can install the app to the home screen (manifest and app-shell service worker, built app only).

**Offline (D-37).** If the connection drops, a banner appears, data already on screen stays readable, and every save button is disabled until the connection returns. No clinical data is stored on the device.

## 2. Screens by role

### Health worker

| Screen | What it is for |
|---|---|
| Overview | Counts for the facility: open stock-out alerts, vaccines low or out, defaulters, doses due in 7 days, the next session; quick actions (register, find, record stock). Each count opens its screen |
| Stock > Stock | Stock-out alerts, then one card per vaccine: doses in stock, use per week, weeks left, and a status in words (OK, under 4 weeks, low, out) |
| Stock > Forecast | Choose a vaccine: the last 26 weeks of doses issued, the forecast for the next 4 weeks with its 80% interval, the model used and its backtest accuracy (MASE, MAE, sMAPE, interval coverage). Chart or table |
| Stock > Ledger | Record a receipt, issue, wastage, loss or adjustment (stock can never go negative); the latest 25 entries |
| Stock > Settings | Delivery cycle and safety buffer per vaccine (read only) |
| Outreach > Defaulters | Children under 2 with a dose more than 28 days overdue, most missed doses first, then nearest to an age limit; filter by name or ID |
| Outreach > Sessions | Sessions of the facility; open one to see its plan and record attendance |
| Session | Vaccines needed against stock and the forecast (shortfalls flagged), the planned children in priority order; tick the doses given and save, or mark "did not attend". Saving records the doses on the child's passport and issues them from stock |
| Children > Find | Exact system ID, or family name with date of birth, across all facilities; other facilities' records open read-only and each look-up is logged |
| Children > Register | Register a child; a likely duplicate (same family name and date of birth here) is shown before a new record is created |
| Child record | Details, record a due dose, every scheduled dose with its state, the history at any facility, and "Export FHIR record" (a FHIR R4 Bundle file) |
| Vaccine schedule | The schedule the system uses |

### Facility manager

Everything the health worker has, plus: acknowledge an alert (Stock > Stock), change the delivery cycle and safety buffer (Stock > Settings), create a session and generate its plan from the defaulter list (Outreach > Sessions), Import data (CSV with a dry run and a per-row error report) and the Audit log.

### System administrator

| Screen | What it is for |
|---|---|
| System | Accounts by role, locked accounts, sign-ins and failed sign-ins in the last 7 days, the last forecast run. No clinical data |
| Users | Create accounts (no self-registration), deactivate or reactivate, set a new password (also clears a lockout); an administrator cannot deactivate their own account |
| Facilities | List and add facilities |
| Schedule | Edit each dose's recommended, minimum and maximum age and minimum interval; the order minimum <= recommended <= maximum is enforced |

## 3. How a stock-out alert is decided (D-38)

For each vaccine at a facility, after every forecast run:

1. Current stock is the sum of the stock ledger.
2. The forecast's upper bound (80% interval) for each of the next 4 weeks is multiplied by the usage factor (doses leaving stock per dose given, from the last 12 weeks), because opened multi-dose vials are partly discarded.
3. The expected delivery is the last receipt plus the delivery cycle; if that date has passed, no delivery is assumed within the 4 weeks.
4. For each week before the expected delivery, projected stock is compared with the safety minimum: average weekly use x weeks still to cover x (1 + safety buffer).
5. The first week where projected stock falls below the minimum raises an alert. An existing alert keeps its acknowledgement; it is resolved automatically when a later run finds no breach.

Measured accuracy on the evidence run is in doc 05 section 6 (recall 0.914, below the 0.95 target).

## 4. Forecasts: baselines now, Colab models later (D-14, D-39)

| Situation | Command | Result |
|---|---|---|
| No trained models yet | `python3 scripts/dev.py forecasts` | For each series the better of seasonal naive and moving average in a 24-week backtest; nothing is fitted |
| After a Colab run | unzip `results_<run_id>_<commit>.zip`, then `python3 scripts/dev.py forecasts --results <unzipped folder>/backtest` | Imports the Colab forecasts and accuracy; refused if the Colab series hash differs from the series rebuilt from the database, or if the forecasts do not start at the current week |
| Scheduled | cron on the server: `cd <repo>/backend && ../.venv/bin/python manage.py run_forecasts` nightly (D-13) | Same as the first row |

Evaluation without the app: `python3 scripts/dev.py evaluate` (baseline backtest and alert precision and recall against truth; writes `data/results/<run_id>-baselines/` and a results-ledger entry). On Colab the notebook also runs `immdss evaluate-alerts` for all four models.

## 5. Checks

| Command | What it checks | Latest result (commit `855d49a`) |
|---|---|---|
| `dev.py test all` | Unit, integration and security tests | 333 passed |
| `dev.py e2e --screenshots` | Browser tests TC-S-01 to TC-S-07 on desktop and phone widths, on a separate database; saves F-UI screenshots | 14 passed |
| `dev.py walkthrough` | Latency of 8 endpoints, accuracy against truth and the defaulter oracle, import cleaning | 8 of 8 checks 100%; max p95 373 ms |
| `dev.py evaluate` | Baseline backtest and alert accuracy | doc 05 section 6 |

## 6. Demonstration script (about 10 minutes)

Before: `db-up`, `forecasts`, `run`; open http://localhost:5173 on the laptop and on a phone (or the browser's phone view at 360 px). Have `.demo_credentials.txt` open privately.

| # | Who | Show | Point to make |
|---|---|---|---|
| 1 | - | Sign in with a wrong password | Generic refusal; lockout after 5 failures |
| 2 | Health worker (`hcw-syn-d01`) | Overview | One screen answers "what needs attention today" |
| 3 | Health worker | Stock > Forecast, BCG; switch to Table | Forecast with interval, model and its measured accuracy; table alternative for every chart |
| 4 | Health worker | Stock > Stock alerts | Alert in words with the projected week; colour is never the only signal |
| 5 | Health worker | Children > Register a child, then record BCG-1 | Validation by the schedule; stock is issued automatically |
| 6 | Health worker at another facility (`hcw-syn-h01`) | Find the same child by system ID | Health passport across facilities, read-only, logged |
| 7 | Health worker | Export FHIR record | Interoperable record (FHIR R4) |
| 8 | Facility manager (`fm-syn-d01`) | Outreach > Defaulters, then Sessions > New session > Generate plan | Ranked by the proposal's rule; vaccines needed against stock and forecast |
| 9 | Facility manager | Record attendance for one child | The child leaves the defaulter list; stock falls |
| 10 | Facility manager | Acknowledge an alert; Audit log | Accountability: every change and cross-facility read is logged |
| 11 | Administrator (`admin`) | System, Users | Accounts managed centrally; no clinical data visible |
| 12 | - | Turn off Wi-Fi on the phone | Offline banner; data stays readable, saving is blocked |

Backup: the screenshots F-UI-01 to F-UI-11 (desktop and phone) in `docs/evidence/`.
