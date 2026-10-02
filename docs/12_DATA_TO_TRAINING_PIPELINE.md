# 12. Data pipeline: from generation to trained models, in order

What each stage does, which script runs it, where its output is stored, and what is still planned. Stages 1 to 6 are done and evidenced. Stages 7 and 8 are built and tested; stages 9 to 11 are built and run only on Google Colab (D-14) through `notebooks/immdss_colab_pipeline.ipynb`; nothing has been trained yet. Stage 12 is built: the app runs the baselines until Colab results are imported (D-39). Evidence run: `sim-seed42-368707d3`.

**Basis for synthetic data (D-02).** No facility-level dataset of weekly vaccine stock and child vaccination records is publicly available for Kenya (KHIS and the logistics system need official access), and real child records would need ethics approval. Using simulated data where no dataset exists is allowed (confirmed by the author, 29 September 2026) and matches proposal 1.7 ("only simulated patient data will be used for development and testing").

## Overview

| # | Stage | Command | Output stored in | Status |
|---|---|---|---|---|
| 1 | Configure | edit `analytics/configs/sim.yaml` | the repository (versioned) | Done |
| 2 | Generate | `python3 scripts/dev.py simulate` | `data/synthetic/<run_id>/` (local, not in git) | Done |
| 3 | Validate the generated data | runs inside stage 2; `python3 scripts/dev.py validate` | `validation_report.md` in the run folder | Done: 11 of 11 checks pass |
| 4 | Explore (EDA) | `python3 scripts/dev.py eda` | `docs/evidence/` (versioned) | Done: F-D1 to F-D8, T-5.1 |
| 5 | Load into the system | `python3 scripts/dev.py load` | PostgreSQL, Docker volume `immdss_pgdata` | Done: 60 s |
| 6 | Measure import cleaning | `python3 scripts/dev.py walkthrough` | `docs/evidence/P1_walkthrough_<run_id>.md` | Done: 119 of 120 caught |
| 7 | Build training series | `immdss build-series` | `data/processed/<run_id>/` (local) or `results/series/` (Colab) | Built, tested |
| 8 | Clean the training series | inside stage 7 | same | Built, tested |
| 9 | Split for evaluation | inside stage 10 | none (rules only) | Built, tested |
| 10 | Train and backtest | `immdss backtest`, `immdss train-final` (Colab only) | `results/` on Colab, downloaded as a zip; the training log | Built; not yet run |
| 11 | Compare, select, evaluate against truth | inside stage 10 | same | Built; not yet run |
| 12 | Use in the system | `dev.py forecasts [--results DIR]` (`manage.py run_forecasts`, nightly by cron) | Forecast and StockAlert tables | Built, tested |

## Stage 1. Configure

`analytics/configs/sim.yaml` holds every setting. Each value is marked PUBLISHED with its source (the KDHS 2022 Key Indicators Report, Table 11, for coverage and the population mix; the Ministry of Health immunization guidelines for vial sizes and open-vial rules) or ASSUMPTION with its reason (for example delivery delays and session days). The seed (42) makes every run repeatable.

## Stage 2. Generate

`immdss simulate` (package `analytics/src/immdss_analytics/`) runs these steps in order:

| Step | File | What happens |
|---|---|---|
| Population | `sim/population.py` | 12 fictional facilities (5 dispensaries, 4 health centres, 3 sub-county hospitals); births each week from January 2019; each child gets sex, mother's education, wealth quintile and birth order in KDHS 2022 proportions |
| Behaviour | `sim/behaviour.py` | each child's chance of never starting, of stopping after a visit, and of being late (longer in the rainy months) |
| Calibration, stage 1 | `sim/calibrate.py` | a 40,000-child simulation without stock limits; settings are adjusted until coverage matches KDHS 2022 for all 16 doses |
| Clinic and stock engine | `sim/engine.py`, `sim/stock.py` | session by session from 2019 to 29 December 2025: children attend, due doses are given if in stock, monthly deliveries (sometimes late, short or missing), two supply disruptions, opened vials discarded, BCG and MR on one weekly day at smaller facilities |
| Calibration, stage 2 | `sim/calibrate.py`, `cli.py` | the full engine is rerun with damped corrections until every dose is within 1.5 points or 8 rounds are used (D-26); the evidence run ended at 2.5 points (MR1) |
| Dirty imports | `sim/dirty.py` | two CSV files with about 15% deliberately broken rows, plus the answer key |
| Output | `sim/outputs.py` | CSV files, `manifest.json` (row count and SHA-256 of every file, seed, settings hash, generator-code hash), parameter snapshot and calibration report |

**Where it is stored.** `data/synthetic/sim-seed42-368707d3/` (53 MB), on the development machine only. Generated data is never committed to git: it can be rebuilt byte for byte in about 2 minutes, and the manifest's hashes prove a rebuild is identical. Runs that failed or were rejected (for example `sim-seed42-deca88d9`) stay in the folder for traceability and are logged in `logs/DATA_CLEANING_LOG.md`.

| Sub-folder | Contents | Who may use it |
|---|---|---|
| `app/` | facilities, antigens, schedule, sessions, children, immunization events, stock transactions, vaccine lots | the application (stage 5) and model training (stage 7) |
| `truth/` | true weekly demand and stock-outs, every child born (including never-registered children), doses refused because of stock-outs | evaluation only (stages 6 and 11); never loaded into the system or given to a model |
| `imports/` | the two broken CSV files and their answer key | import-cleaning measurement (stage 6) |

## Stage 3. Validate the generated data (cleaning of generated data)

`sim/validate.py` runs 11 checks on every run: file hashes; stock adds up every week; stock never negative; the ledger matches the final balance; no dose too early, too late, twice or out of order; every dose belongs to a registered child; coverage within 3 points of KDHS 2022; stock-outs exist. A run that fails any check cannot be loaded (stage 5 refuses it). Errors are fixed in the generator and the data regenerated, never by editing files. Example: the first full run failed three checks and exposed two generator bugs, both fixed.

## Stage 4. Explore (EDA)

`eda.py` produces figures F-D1 to F-D8 (coverage against KDHS, dropout, timeliness, weekly demand with stock-outs, stock against its minimum, registry, import defects, subgroup coverage) and table T-5.1 (every file, rows, columns, purpose), in `docs/evidence/EDA_<run_id>.md`. It refuses a run that failed validation. Plain-language explanations: `logs/DEFENCE_NOTES.md`.

## Stage 5. Load into the system

`backend/apps/analytics_api/loader.py` loads `app/` only, after checking that the run passed validation and every file matches its hash; it refuses any path inside `truth/`. Rows are marked synthetic. The database is PostgreSQL 16 in Docker; its data lives in the Docker volume `immdss_pgdata` on the development machine.

## Stage 6. Measure import cleaning

The system's CSV import rules (`backend/apps/analytics_api/services.py`) were written from the file format and the schedule, then scored against the answer key: 119 of 120 planted errors caught, 0 of 697 clean rows rejected. The one miss is a planted date that is itself valid (a day-month swap with a day of 12 or less); the generator will be corrected at the next regeneration.

## Stage 7. Build the training series

A forecast model learns weekly vaccine use. The series is built only from what a real clinic system records: the **issue** transactions in `app/stock_transactions.csv` (identical to the stock ledger in the database).

- One series per facility and vaccine: 12 facilities x 7 vaccines = 84 series.
- Weekly totals of doses issued, weeks starting Monday, 4 January 2021 to 29 December 2025 (260 weeks).
- Saved as `weekly_issues.csv` (columns facility_code, antigen_code, week_start, issued, stockout_flag) with `series_manifest.json` (its SHA-256, counts of zero and stock-out weeks), so every training run can say exactly which data it used. For the evidence run: 84 series, 260 weeks, 1,635 stock-out-flagged weeks, 799 zero weeks; built in 2 seconds.
- Code: `analytics/src/immdss_analytics/forecast/series.py`. It refuses a run that failed validation.
- Planned for stage 12: the same function builds the series from the database for the nightly job, with a test that the two paths give identical series.

## Stage 8. Clean the training series

| Rule | What it does | Why |
|---|---|---|
| T-01 | Weeks with no issues are 0, not missing | a week without vaccination is real information |
| T-02 | Only weeks from 4 January 2021 (the stock window) | earlier history has no stock ledger |
| T-03 | Flag stock-out weeks from the ledger itself (balance reached zero during the week) | during a stock-out, issues understate demand ("censored demand"); the flag is visible to a real system, unlike `truth/` |
| T-04 | Accuracy is also reported without stock-out-flagged test weeks (`mae_no_stockout`) | shows how much censored weeks affect the score |
| T-05 | No outlier removal without a logged rule | the synthetic data has no data-entry errors in `app/`; spikes are real catch-up demand |

The cleaning rules are applied to the training window only, and any scaling for the GRU is fitted on training weeks only (no leakage).

## Stage 9. Split for evaluation

Rolling-origin backtest (doc 05 section 1, D-35): train on all weeks before a cut-off, forecast the next 4 weeks, move the cut-off forward 4 weeks; 6 cut-offs cover the last 24 weeks (7 July to 22 December 2025). Test weeks are always after the training weeks, and the code asserts it at every cut-off. Code: `forecast/backtest.py`.

## Stage 10. Train and backtest (Google Colab only, D-14)

| Model | Code | Library |
|---|---|---|
| B1 seasonal naive (same week last year) | `forecast/models.py` | numpy |
| B2 moving average (last 4 weeks) | `forecast/models.py` | numpy |
| SARIMA (ARIMA orders by AIC, Fourier yearly seasonality, D-36) | `forecast/models.py` | statsmodels |
| GRU, one model across all 84 series, quantile loss | `forecast/gru.py` | Keras with TensorFlow |

All fitting runs on Colab with a GPU. `immdss backtest` and `immdss train-final` refuse to fit SARIMA or the GRU anywhere else (exit code 3; `forecast/guard.py`). Only the pure functions are tested on the laptop (`analytics/tests/test_forecast.py`: series building and flags, metrics, baselines, cut-offs, scoring and selection, the refusal itself).

**The notebook.** `notebooks/immdss_colab_pipeline.ipynb`, opened in Colab from GitHub (File > Open notebook > GitHub, `shantelle04/immunization-dss`), runtime set to GPU, then Run all. One cell per stage:

1. Settings (repository, branch or tag, seed 42, models), Python and GPU check.
2. Clone at the chosen branch, tag or commit (it stops if the checkout fails), install `analytics[dev,train]`, save `pip freeze`, run the unit tests.
3. `immdss simulate --seed 42` and validation, then a check that every file is byte-identical to the evidence run (`analytics/configs/evidence_hashes.json`); it stops on any difference (R-09).
4. `immdss eda`: figures F-D1 to F-D8 and table T-5.1, displayed.
5. `immdss build-series`, with a hash check, then a series EDA: level, zero and stock-out shares, autocorrelation at lags 1, 4 and 52 per vaccine (T-M1), weekly totals (F-M1) and seasonality (F-M2).
6. `immdss backtest` with B1 and B2 as a quick check, then with all four models (the run that counts).
7. Comparison overall and per vaccine, selection per series (D-21), bias against true demand, and the MASE box plot (F-M3).
8. `immdss train-final`: the selected model per series fitted on all 260 weeks, forecasting the next 4; the GRU is saved as `gru.keras`.
9. Everything under `results/` is zipped as `results_<run_id>_<commit>.zip` and downloaded.

No data or secret is uploaded: Colab regenerates the data from the seed. The zip's `backtest/manifest.json` (git commit, series hash, seed, library versions, GPU) is what the training log entry cites.

## Stage 11. Compare, select and evaluate against truth

| Question | Compared with | Metric (doc 05) |
|---|---|---|
| How accurate are the forecasts? | the doses actually issued in the test weeks | MAE, MASE, sMAPE; always against B1 and B2 |
| Do forecasts under-predict after stock-outs? | true demand in `truth/weekly_stock.csv` | bias in stock-out-affected weeks |
| Do alerts catch real stock-outs early enough? | true stock-out weeks in `truth/` | precision, recall, F1, lead time (D-07 target: recall at least 0.95) |
| Is the defaulter list right? | an independent checking script | exact match (expected 100%) |

`truth/` is read only here, for scoring; no model ever receives it as input.

## Stage 12. Use in the system

`manage.py run_forecasts` (cron, D-13; `dev.py forecasts`) rebuilds the series from the database with the same function as stage 7 (its SHA-256 equals the training series for the evidence run, checked by the walkthrough), takes forecasts from the baselines or from an imported Colab results folder (refused if the series hash differs, D-39), stores them, and raises, keeps or resolves stock-out alerts (D-38). The Stock screen shows the forecast, its interval, the model and its backtest accuracy (doc 14).

## Where training runs (D-14, decided)

Option C, everything on Google Colab, decided by the author on 29 September 2026: all model fitting runs on Colab, never on the development laptop, and the commands enforce it.
