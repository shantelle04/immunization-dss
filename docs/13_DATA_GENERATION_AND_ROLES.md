# 13. Data generation, storage and role access

How the synthetic data is generated, where every copy of it lives, how it is used, and what each user role can access. Stage-by-stage training detail: doc 12. Commands and setup: doc 11. Decisions cited: doc 07.

## 1. Why the data is synthetic (D-02)

| Reason | Detail |
|---|---|
| The needed data is not public | Weekly facility stock and child-level vaccination records sit in KHIS and the national logistics system, which need official access. KDHS has child histories but no stock data; WHO/UNICEF estimates are one national figure per year |
| Privacy | Real child records are sensitive under the Kenya Data Protection Act, 2019, and would need ethics approval. Proposal 1.7: "only simulated patient data will be used for development and testing" |
| Measurable accuracy | The generator also records the truth (true demand, true stock-outs, true dropouts), so alerts, forecasts and defaulter lists can be scored exactly |
| Control | Supply disruptions, late deliveries and broken import files are included on purpose, and the identical dataset can be rebuilt from the seed |

Realism comes from calibration: coverage for all 16 doses is within 2.5 percentage points of the KDHS 2022 Key Indicators Report, Table 11 (limit 3 points).

## 2. How the data is generated

```
analytics/configs/sim.yaml  ->  immdss simulate (seed 42)  ->  data/synthetic/<run_id>/
    ->  11 validation checks  ->  EDA  ->  load app/ into PostgreSQL (Docker)
                                       ->  Colab: rebuild, hash check, series, backtest, models
```

**Command:** `python3 scripts/dev.py simulate` (wraps `immdss simulate`). About two minutes on one CPU core; about one second when an identical validated run already exists (same seed, settings and generator code).

**Settings:** `analytics/configs/sim.yaml`. Every value is marked PUBLISHED (with its source: KDHS 2022 Table 11, Ministry of Health immunization guidelines) or ASSUMPTION (with its reason).

| Step | Code | What happens |
|---|---|---|
| 1. Population | `sim/population.py` | 12 fictional facilities (5 dispensaries, 4 health centres, 3 sub-county hospitals); births every week from January 2019; each child gets sex, mother's education, wealth quintile and birth order in KDHS 2022 proportions |
| 2. Behaviour | `sim/behaviour.py` | Each child's chance of never starting, of dropping out after a visit, and of arriving late (more in rainy months) |
| 3. Calibration, stage 1 | `sim/calibrate.py` | A 40,000-child simulation without stock limits; chances are adjusted until coverage matches KDHS 2022 for all 16 doses |
| 4. Clinic and stock engine | `sim/engine.py`, `sim/stock.py` | Session by session to 29 December 2025: children attend, due doses are given only if in stock, monthly deliveries (sometimes late, short or missing), two supply disruptions, open-vial discard rules, BCG and MR on one weekly day at smaller facilities |
| 5. Calibration, stage 2 | `sim/calibrate.py`, `cli.py` | The full engine is rerun with damped corrections until every dose is within 1.5 points or 8 rounds are used (D-26); the evidence run ended at 2.5 points (MR1) |
| 6. Broken imports | `sim/dirty.py` | Two CSV files with about 15% deliberately wrong rows, plus the answer key |
| 7. Output | `sim/outputs.py` | CSV files and `manifest.json`: row count and SHA-256 of every file, seed, settings hash, generator-code hash |
| 8. Validation | `sim/validate.py` | 11 checks (hashes, stock balances, no negative stock, ledger equals final balance, dose ages, intervals, no duplicates, order, registered children, coverage within 3 points, stock-outs present). A failed run cannot be loaded |

Errors are fixed in the generator and the data regenerated, never by editing files.

## 3. Where the data is stored

| Copy | Location | In git? | How it is made |
|---|---|---|---|
| Settings | `analytics/configs/sim.yaml` | Yes | Edited by hand, versioned |
| Evidence run name | `analytics/configs/evidence_run.txt` (`sim-seed42-368707d3`) | Yes | Set when a run is accepted |
| Reference fingerprints | `analytics/configs/evidence_hashes.json` | Yes | Written from the run's manifest |
| Generated dataset | `data/synthetic/sim-seed42-368707d3/` (53 MB), development laptop | No | `dev.py simulate` |
| Rejected or earlier runs | `data/synthetic/<other run_id>/` | No | Kept for traceability, logged in `logs/DATA_CLEANING_LOG.md` |
| Application database | PostgreSQL 16 in Docker, volume `immdss_pgdata` | No | `dev.py load` (about 60 s), `app/` only |
| Training series | `data/processed/<run_id>/weekly_issues.csv` (laptop) or `results/series/` (Colab) | No | `immdss build-series` |
| EDA figures and reports | `docs/evidence/` | Yes | `dev.py eda` |
| Training results | `results_<run_id>_<commit>.zip`, downloaded from Colab | No | The Colab notebook |

Nothing generated is uploaded anywhere: Colab regenerates the same dataset from the public repository and stops if any file differs from `evidence_hashes.json` (R-09).

## 4. What the dataset contains and who may use it

| Part | Contents (evidence run) | Allowed use |
|---|---|---|
| `app/` | 12 facilities, 7 antigens, 16-dose schedule, 35,525 registered children, 499,839 vaccination records, 17,724 sessions, 84,941 stock transactions, 5,806 vaccine lots | Loaded into the system; the only input for model training |
| `truth/` | Weekly true demand and stock-outs (21,840 facility-antigen-weeks), all 36,431 children born (including never registered), 20,005 doses refused for lack of stock | Scoring only. Never loaded into the database, API or UI; never given to a model |
| `imports/` | 617-row immunization file and 200-row stock file with planted errors, 120-row answer key | Measuring the import checks (119 of 120 caught, 0 of 697 clean rows rejected) |

## 5. How the data is used

| Use | Input | Command | Output |
|---|---|---|---|
| Run the system | `app/` | `dev.py load` | PostgreSQL tables, rows marked synthetic |
| Explore | whole run | `dev.py eda` | F-D1 to F-D8, T-5.1 in `docs/evidence/` |
| Test the import checks | `imports/` | `dev.py walkthrough` | `docs/evidence/P1_walkthrough_<run_id>.md` |
| Train forecasting models | `app/stock_transactions.csv` (issues only) | Colab notebook `notebooks/immdss_colab_pipeline.ipynb` | Backtest comparison, selection, final forecasts |
| Score forecasts and alerts | `truth/weekly_stock.csv` | inside the backtest, after forecasting | Bias against true demand; alert precision and recall |

Training never runs on the development laptop (D-14); the training commands refuse outside Colab.

## 6. Roles and what each can access

### 6.1 Proposal definition (section 3.8.4)

| Role | Proposal wording |
|---|---|
| Healthcare worker | Read/write access to child records and stock data, read-only access to forecasts and session plans |
| Facility manager | Full read/write access to all modules and facility configuration |
| System administrator | User management and system-wide configuration |

Added rules (doc 10 section 3): every user is limited to their own facility; the administrator sees no clinical data by default; no self-registration, the administrator creates every account.

### 6.2 As implemented in Prototype 1

Every row is checked for every role by the endpoint x role test matrix (`backend/tests`).

| Area (endpoint under `/api/v1/`) | Health worker | Facility manager | System administrator | Not signed in |
|---|---|---|---|---|
| Log in, refresh session (`auth/login`, `auth/refresh`) | Yes | Yes | Yes | Yes (D-31; throttled) |
| Log out, own profile (`auth/logout`, `auth/me`) | Yes | Yes | Yes | No |
| List and register children (`children`) | Own facility | Own facility | No | No |
| Search children across facilities (`children/search`) | Read only, logged | Read only, logged | No | No |
| Child record and history (`children/<id>`, `.../immunizations` GET) | Yes; other facilities read only, logged | Same | No | No |
| Record a dose (`.../immunizations` POST) | Own facility | Own facility | No | No |
| Vaccine schedule (`schedule`) | Read | Read | No | No |
| Stock balance and ledger (`stock/balance`, `stock/transactions`) | Read and record, own facility | Read and record, own facility | No | No |
| Defaulter list (`defaulters`) | Read, own facility | Read, own facility | No | No |
| Sessions (`sessions`) | Read | Read and create | No | No |
| CSV import (`imports`) | No | Yes | No | No |
| Facility audit log (`audit`) | No | Yes | No | No |
| Users (`admin/users`) | No | No | List and create | No |
| Facilities (`admin/facilities`) | No | No | List | No |

**Enforcement.** Every refusal happens on the server before any data is read: no valid token gives 401; a signed-in user without the right role or facility gives 403. The screens only hide what a role cannot use.

**Still to build against the proposal.** Forecasts and stock-out alerts (health worker read; manager read and acknowledge) and stock policy settings for the manager (Phase 4); schedule editing by the administrator (FR-03, later phase).

### 6.3 Demo accounts

Created by `python3 scripts/dev.py demo-users`.

| Account | Role | Facility | What it shows |
|---|---|---|---|
| `admin` | System administrator | None | Administration only (users, facilities), by design |
| `fm-syn-<code>`, for example `fm-syn-h01` | Facility manager | One per facility (12) | All dashboards, imports, audit log, session creation |
| `hcw-syn-<code>`, for example `hcw-syn-d01` | Health worker | One per facility (12) | Children, doses, stock, defaulters, schedule |

The administrator password is `DJANGO_INITIAL_ADMIN_PASSWORD` in `.env`. Demo passwords are random and written only to `.demo_credentials.txt` (owner-only, never committed).
