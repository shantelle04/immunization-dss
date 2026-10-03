# 16. Results by stage: what was done, what it achieved, what was improved

One place for the whole project: for each stage, what was built, the measured result, and every change made to improve it, in order. It points to the detailed documents rather than repeating them. Status as of 3 October 2026, commit `b63ac3b` and later. Every number comes from a test, the results ledger (`docs/logs/results_ledger.jsonl`), a training log entry or an evidence file; decisions are in doc 07.

## 1. Summary

| Stage | Result | Main evidence |
|---|---|---|
| Synthetic data | 35,525 children, 499,839 vaccination records, 84,941 stock transactions; coverage within 2.5 points of KDHS 2022 for all 16 doses; 11 of 11 quality checks pass; identical on every rebuild | doc 13, `evidence/EDA_*.md` |
| Requirements and design | 26 functional and 11 non-functional requirements, 9 business rules; 9 diagrams; wireframes | doc 02, `diagrams/`, `wireframes/` |
| Prototype 1 | Login with three roles, facility scoping, three module screens; 100% accuracy against truth; import cleaning 119 of 120 errors caught, 0 of 697 clean rows rejected | `evidence/P1_walkthrough_*.md` |
| Forecasting | GRU MASE 0.671, SARIMA 0.681, both beat seasonal naive on 96.4% of series | doc 05 section 6.1, `evidence/M1_model_comparison_*.md` |
| Stock-out alerts | Recall improved from 0.657 to 0.995 (weekly evaluation); 94.0% of stock-out weeks warned at least a week ahead; precision low (lift 1.31) | doc 15, doc 05 section 6.2 |
| Defaulter list | 10,390 of 10,390 children match an independent checking script (100%) | doc 05 section 6.3 |
| Prototype 2 | Forecasts, alerts, outreach plans, attendance, FHIR export, admin screens, mobile-first UI | doc 14, `evidence/F-UI-*.png` |
| Quality | 343 automated tests and 14 browser tests pass; slowest dashboard 261 ms (95th percentile) | `logs/TEST_LOG.md`, `evidence/P2_walkthrough_*.md` |

## 2. Stage by stage

### 2.1 Setup (Phase 0)

**Done.** Repository on the author's GitHub account with a dedicated SSH key; Django, React and the analytics package as working skeletons; PostgreSQL 16 in Docker with separate application and test accounts; one command runner for Linux and Windows (`scripts/dev.py`); every result written to a results ledger.

**Result.** All tests passed at the first upload (33 analytics, 5 runner, 17 backend, 1 frontend). The backend refuses to start with a missing, short or example secret (17 tests).

**Improved.** Commit hooks block secrets, generated data, assistant guides and machine-specific paths from ever being uploaded.

### 2.2 Synthetic data and exploration (Phase 1, pipeline stages 1 to 4)

**Done.** A seeded generator (`immdss simulate`) for 12 fictional facilities from 2019 to 2025: births with KDHS 2022 background mix, attendance and dropout behaviour, session-by-session vaccination limited by stock, monthly deliveries that are sometimes late, short or missing, two supply disruptions, open-vial rules, and import files with planted errors. Calibrated in two stages to KDHS 2022 Table 11. Eight exploration figures (F-D1 to F-D8) and a dataset table (T-5.1).

**Result.** Coverage within 2.5 percentage points for all 16 doses (largest gap MR1); 11 of 11 automatic checks pass; byte-identical rebuild from seed 42 in about two minutes; Colab rebuilt the same 14 files identically in every training run.

**Improved, in order.**

| Change | Why | Effect |
|---|---|---|
| Two generator bugs fixed (a dose given twice; MR2 coverage 5 points low) | The first full run failed three checks | All checks pass |
| D-18: BCG and MR on one weekly day at small facilities | Wastage was unrealistically high (BCG 85.9%) | BCG 65.8%, MR 46.1% (WHO planning figures 50% and 40%) |
| D-19: stronger subgroup differences | Gap between education groups smaller than KDHS | No-education Penta3 closer to KDHS |
| D-23: BCG weekly at sub-county hospitals | Checked against WHO wastage rates | BCG wastage reduced further |
| D-26: damped calibration steps with a stop rule | Fixed numbers of steps failed or passed by chance | Stable calibration within 2.5 points |

### 2.3 Requirements and design (Phase 2)

**Done.** Requirements frozen with evidence for each item; nine diagrams (use case, class, three sequence, activity, architecture, entity relationship, logical schema) generated from text sources; database diagrams and data dictionary generated from one schema file; low-fidelity wireframes.

**Result.** 26 functional and 11 non-functional requirements and 9 business rules, traced to diagrams and tests. Supervisor review pending.

### 2.4 Prototype 1 (Phase 3, pipeline stages 5 and 6)

**Done.** Django REST Framework backend with login for health worker, facility manager and administrator; every query limited to the user's facility; account lockout; refresh token in a protected cookie; React screens for stock, defaulters, children and user administration; the generated data loaded into PostgreSQL (60 seconds).

**Result (walkthrough).** Stock balances 84 of 84 correct against truth; child histories 200 of 200; registry size correct; CSV import caught 119 of 120 planted errors with 0 of 697 clean rows rejected; slowest request 326 ms (95th percentile); 188 backend tests including every endpoint against every role.

**Known gap.** One planted date error is undetectable because the swapped date is itself valid; noted for the next data regeneration.

### 2.5 Forecasting models (Phase 4, pipeline stages 7 to 11)

**Done.** Weekly series of doses issued per facility and vaccine (84 series, 260 weeks) built from the stock ledger only; rolling-origin backtest over the last 24 weeks (6 cut-offs); four models: seasonal naive, 4-week moving average, SARIMA with yearly Fourier terms, and one GRU network across all series with quantile loss. All training on Google Colab with a GPU, never on the laptop (D-14), from a notebook that rebuilds the data and checks every file hash first.

**Result (final run `625841d`).**

| Model | Mean MASE | Series beating seasonal naive | MAE (doses/week) | Interval coverage (target 0.80) |
|---|---|---|---|---|
| GRU | **0.671** | 96.4% | 4.08 | 0.804 |
| SARIMA | 0.681 | 96.4% | 4.17 | 0.844 |
| Moving average | 0.766 | 90.5% | 4.69 | 0.812 |
| Seasonal naive | 0.950 | 64.3% | 5.86 | 0.842 |

The GRU is used for 80 series and SARIMA for 4 (selection rule D-21). The training is repeatable: the GRU gave identical forecasts in two separate Colab runs.

**Improved, in order.**

| Change | Why | Effect |
|---|---|---|
| SARIMA with Fourier terms instead of a seasonal lag-52 term (D-36) | Run time | 14 minutes on Colab for all fits |
| Time-based validation split for the GRU | The first split took the last items in a list, not the last weeks | No leakage into early stopping |
| Two-sided interval calibration (D-41 C) | GRU interval too narrow (coverage 0.786) | No effect (margin near zero) |
| Upper-end calibration on a separate block of weeks (D-41 D) | Target the end the alerts use | MASE 0.677 to 0.671, coverage 0.786 to 0.804 |
| Stock-out flag fixed (D-44) | It missed weeks that stayed at zero stock | Flag now equals the true stock-out weeks (2,290 of 2,290) without reading the truth; models retrained |

### 2.6 Stock-out alerts (Phase 4)

**Done.** An alert rule that projects stock forward from the forecast's upper bound and compares it with a safety minimum before the next delivery (BR-05); measured against the simulator's true stock-outs. Full history: doc 15.

**Result.** With the trained models and a decision every week (as the app does nightly): 99.5% of true stock-out weeks flagged, 94.0% at least one week ahead, 91.3% of stock-out episodes warned before they start. Strict precision 0.364, lift 1.31 over flagging everything; 61.9% of vaccine-weeks flagged.

**Improved, in order.**

| # | Change | Recall | Note |
|---|---|---|---|
| 1 | First rule, checked every 4 weeks | 0.657 | Ignored discarded vial doses |
| 2 | Usage factor for wastage (D-38) | 0.914 | Baselines |
| 3 | Trained models instead of baselines | 0.843 | More accurate forecasts, fewer alerts |
| 4, 5 | Two interval calibrations (D-41) | 0.843 | Forecasts improved; alerts did not: misses come from short deliveries |
| 6 | Late-delivery warning (D-42) | 1.000 | Rejected: flags 95.6% of cases |
| 7 | Weekly decisions, as the app runs (D-43) | 0.995 | Target met; early recall 0.940 |
| 8 | Delivery-history gate (D-43) | 1.000 | No gain: deliveries are rarely late |
| 9 | Risk score, logistic regression (D-43) | 0.995 | Early recall 0.984 but flags 85.4%; not recommended |

**Conclusion.** The recall target is met. Selectivity is the limit: in this data most stock-outs follow deliveries that are too small, which a demand forecast cannot see. The method to use in the app is the author's decision (D-45); recommendation: keep the rule.

### 2.7 Defaulter tracking (Phase 4)

**Done.** Each child's due, overdue and closed doses from the schedule; defaulters ranked by most missed doses, then nearest to an age limit (BR-04); outreach session plans from the ranked list with vaccines needed against stock and forecast; attendance recording that updates the child record and the stock ledger.

**Result.** An independently written checking script agrees with the system for all 10,390 children under 2 at all 12 facilities (status, missed doses and order).

### 2.8 Prototype 2 and the interface (Phase 4, pipeline stage 12)

**Done.** Nightly forecast job that rebuilds the series from the database and refuses a Colab result trained on different data; forecasts with interval, model and accuracy on the Stock screen; alerts the facility manager acknowledges; delivery and buffer settings; FHIR R4 export of a child record; administrator screens for accounts, facilities and the schedule; interface redesigned mobile first (bottom navigation on phones, tables as cards under 600 px, light and dark themes, offline notice, installable app shell).

**Result.** The database series matches the training series byte for byte; walkthrough 8 of 8 accuracy checks at 100%; slowest dashboard 261 ms (95th percentile, in-process); 14 browser tests pass at desktop and phone width; screenshots F-UI-01 to F-UI-11.

**Improved.** Two defects found by the browser tests and fixed: the session was lost on page reload when two refreshes raced, and the test port's origin was not trusted for the CSRF check.

## 3. Quality and testing

| Level | Count | Latest result |
|---|---|---|
| Analytics unit tests | 57 | pass |
| Backend unit, integration and security tests (including every endpoint against every role) | 269 | pass |
| Runner tests | 5 | pass |
| Frontend tests | 12 | pass |
| Browser tests (desktop and phone) | 14 | pass |
| Walkthrough accuracy checks | 8 | 100% |

## 4. What remains

| Item | Who |
|---|---|
| Decision D-45 (alert method) and confirmation of D-31, D-32, D-35 to D-44 | Author |
| Supervisor sign-offs: D-02, D-07, D-12, D-25, D-27 | Supervisor |
| Gate reviews, merge to `main`, tags `p1` and `p2` | Claude, on the author's go-ahead |
| Load test (Locust) | Claude |
| User acceptance testing with real participants and the SUS questionnaire | Author (needs ethics answer) |
| Chapters 4 to 6 | Author |
| Demo rehearsal and backup recording (script in doc 14) | Author |
| Future work: forecast delivery size and reliability per facility | Thesis recommendation |
