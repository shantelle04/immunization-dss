# 05. Models, metrics and testing

## 1. Demand forecasting (M1)

| Item | Definition |
|---|---|
| Series | Weekly doses administered per facility x antigen, from the app's stock issues (what a real system would see). True demand (including children turned away) exists only in `truth/weekly_stock.csv` and is used to evaluate, never to train |
| Horizon | 1 to 4 weeks ahead (rolling 4-week forecast, proposal 2.5.1) |
| Candidates | B1 seasonal naive (same week last year, or last 4-week mean when history is short); B2 moving average of the last 4 weeks (proposal's comparison point); SARIMA (statsmodels; ARIMA orders (1,0,0), (0,1,1), (1,1,1), (2,0,1), each with and without 2 Fourier harmonics of the 52.18-week year for seasonality (D-36), chosen by AIC on the training window); GRU (Keras, one global model across all 84 series, lookback 26 weeks, inputs: scaled series, ledger stock-out flag, week-of-year sine and cosine, one-hot facility and antigen) |
| Selection per series | GRU when the series has at least 104 weeks and beats B1 on its backtest; else SARIMA; if history is under 26 weeks, a population-based estimate (catchment births x schedule x coverage). Proposal says "ARIMA fallback for facilities with no history"; ARIMA cannot fit without history, so this is logged as D-21 |
| Validation | Rolling-origin backtest: 6 origins of 4 weeks covering the last 24 weeks (D-35), every model refit at each origin on the weeks before it only; scalers fit on training windows only; GRU early stopping uses the last 15% of the training weeks as a time-based hold-out |
| Intervals | 80% intervals: SARIMA native intervals; GRU from the quantile (pinball) loss at 0.1, 0.5 and 0.9, with its upper end calibrated by a one-sided conformal margin on a block of training weeks used neither for fitting nor for early stopping, so that it is exceeded about 10% of the time (D-41, option D); baselines from the 10th and 90th percentiles of in-sample residuals |

**Metrics**

| Metric | Formula | Notes |
|---|---|---|
| MAE | mean abs(y - yhat) | In doses |
| MASE | MAE over the 4 test weeks / mean abs(y_t - y_(t-52)) over that origin's training weeks; averaged over the 6 origins | Under 1 means better than the in-sample seasonal naive; undefined (reported as missing) if the training weeks repeat exactly |
| sMAPE | mean 2 abs(y - yhat) / (abs(y) + abs(yhat)) | Plain MAPE is undefined at zero weeks |
| Interval coverage | share of actuals inside the 80% interval | Calibration |

## 2. Stock-out alerts (M1)

Projected stock at week t+k = current ledger balance - cumulative (80% upper bound of the forecast x usage factor) to t+k; no receipt is assumed before the expected delivery. Usage factor = (issues + wastage + losses) / issues over the last 12 weeks, because the forecast predicts doses given while stock also falls by discarded vial remainders. Safety minimum at t+k = average weekly use x weeks still to cover until the expected delivery x (1 + buffer) (BR-05; buffer 0.25, D-33). Expected delivery = last receipt + replenishment cycle; if that date has passed (late delivery), the full 4-week horizon is covered. Alert when projected stock < safety minimum in any week before the expected delivery (D-38). Code: `analytics/src/immdss_analytics/forecast/alerts.py`, shared by the evaluation and the application.

| Metric | Definition (against simulator ground truth) |
|---|---|
| Alert recall | True stock-out weeks (`truth/weekly_stock.csv`, `stockout = true`) preceded by an alert within 4 weeks / all true stock-out weeks |
| Alert precision | Alerts followed by a true stock-out or true below-minimum week within 4 weeks / all alerts |
| F1 | Harmonic mean |
| Lead time | Weeks between alert and the event |
| Weekly evaluation (D-43) | One decision per series every week over the last 24 weeks (21 decision weeks with a full 4-week horizon, 1,764 decisions), with forecasts made at that week. Recall: true stock-out weeks with a flagged decision in that week or the 3 before / all true stock-out weeks (the first decision week is not counted). Early recall: the flagged decision is at least one week before. Onset early recall: early recall over the first week of each stock-out episode. Strict precision: flagged decisions followed by a true stock-out week within 4 weeks / flagged decisions. Base rate: decisions followed by a true stock-out / all decisions. Lift: strict precision / base rate. Code: `forecast/alert_study.py` |
| Tuning without truth | Any threshold (delivery-history gate, risk-score cut) is set on the 24 weeks before the test weeks, using the ledger's own stock-out flag (T-03) as the label; `truth/` scores the test weeks only |
| 4-weekly evaluation | One alert decision per series at each of the 6 backtest origins (504 decisions), from ledger data before the origin and that origin's forecast; scored against the 4 weeks after the origin. Precision counts a true stock-out or a true below-minimum week; strict precision counts stock-outs only |

## 3. Defaulter classification and priority (M2)

Deterministic rule (BR-01 to BR-03, D-08). Accuracy = share of children whose defaulter status and missed-dose list match the simulator ground truth exactly. Expected 100%; any mismatch is a bug. Proven by an oracle script that re-implements the rule independently from the schedule table and compares every child.

Optional risk score (D-11): logistic regression on features the registry actually holds (visit lateness so far, missed opportunities, outreach attendance), outcome Penta1 received and Penta3 not by 12 months; cross-validated AUC; tie-breaker column only. Hidden background in `truth/` is never a feature.

Vaccine wastage (data realism check, not a model metric): `wastage_rate_who_pct` = (opened-vial wastage + unopened losses) / (administered + wastage + losses) x 100 per antigen over the stock window, following WHO/V&B/03.18 Rev.1 (doses wasted / doses supplied); compared with WHO indicative rates (`docs/logs/SOURCE_CHECKS.md`). `wastage_rate_pct` (opened-vial wastage only) is kept for continuity.

Data-cleaning metric: import validation scored against `imports/import_dirty_truth.csv`: recall per defect type, and false rejection rate on clean rows.

## 4. Proposal target ">95% accuracy" (D-07, proposed operational definition)

| Target | Measure |
|---|---|
| Defaulter categorisation at least 95% | Exact-match accuracy vs ground truth (expected 100%) |
| Predictive stock alerts at least 95% | Alert recall at least 0.95 at a 4-week horizon, with precision reported alongside (so the target cannot be met by alerting everything) |
| Forecast accuracy | No fixed percentage; MASE under 1 against seasonal naive on the majority of series, reported per antigen |

## 5. Test strategy (proposal 3.6)

| Level | Tool | Examples | ID |
|---|---|---|---|
| Unit | pytest (Django TestCase), Jest + RTL | Due-date calculator, defaulter rule, conservation of stock, cleaning rules on fixture rows, components | TC-U-nn |
| Integration | pytest API client, analytics fixtures | Forecast written by `run_forecasts` appears in `/forecasts`; new immunization instantly changes `/defaulters`; FHIR export validates | TC-I-nn |
| System and E2E | Playwright | Register child, record dose, see defaulter list update; stock issue triggers alert | TC-S-nn |
| Security | pytest, manual | Endpoint x role matrix, cross-facility denial, lockout, JWT expiry, injection, headers | TC-SEC-nn |
| Performance | Locust | NFR-01 under 3 s p95; NFR-02 forecast run time | TC-P-nn |
| Data pipeline | pytest | Every C-rule has a fixture test; KDHS reproduction check; simulator validation checks | TC-D-nn |
| Model | backtest harness | Metrics above, logged per run | TC-M-nn |
| UAT and usability | Task sheet, SUS (Brooke, 1996), observer notes | 5 to 8 participants (D-12) | TC-UAT-nn |

## 6. Final results (evidence run `sim-seed42-368707d3`)

Every number is from a logged run: the final Colab run at commit `625841d` (Tesla T4; full tables in `docs/evidence/M1_model_comparison_sim-seed42-368707d3.md`, training log `colab-625841d`), the local baseline run in the results ledger (`evaluate`), and the walkthrough at commit `b63ac3b`. Training series SHA-256 `9e4e6a4edda1...` (after the T-03 fix, D-44). How the results were reached, including every failed attempt: doc 15 (alerts) and doc 16 (all stages).

### 6.1 Forecast accuracy (84 series, 6 origins, last 24 weeks)

| Model | Mean MASE | Median MASE | Series beating seasonal naive | Mean MAE (doses/week) | MAE without stock-out weeks | Mean sMAPE | 80% interval coverage |
|---|---|---|---|---|---|---|---|
| GRU (global, upper end calibrated, D-41 D) | **0.671** | 0.633 | 96.4% | 4.08 | 3.65 | 0.337 | 0.804 |
| SARIMA (Fourier seasonality, D-36) | 0.681 | 0.640 | 96.4% | 4.17 | 3.79 | 0.338 | 0.844 |
| B2 moving average (4 weeks) | 0.766 | 0.724 | 90.5% | 4.69 | 4.34 | 0.375 | 0.812 |
| B1 seasonal naive | 0.950 | 0.934 | 64.3% | 5.86 | 5.56 | 0.493 | 0.842 |

The GRU and SARIMA are close: the GRU is better on 50 of 84 series and has the lower MASE for IPV, PCV and PENTA; SARIMA for BCG, MR, OPV and ROTA. Selection by D-21: GRU for 80 series, SARIMA for 4. Bias against true demand (`truth/`, evaluation only), doses per week in normal and stock-out weeks: GRU -0.79 and -1.48, SARIMA -0.90 and -1.70, B2 -0.31 and -1.22, B1 -1.01 and -2.76. Colab run time for 6 fits: SARIMA 742 s, GRU 131 s. Forecast target "MASE under 1 on the majority of series" (section 4): **met** by both trained models (96.4%).

### 6.2 Stock-out alerts

| Evaluation | Method | Recall | Early recall | Onset early recall | Strict precision | Lift | Flagged | D-07 recall 0.95 |
|---|---|---|---|---|---|---|---|---|
| Weekly (D-43, matches the nightly check) | Rule, trained models (in the app) | 0.995 | 0.940 | 0.913 | 0.364 | 1.31 | 61.9% | **met** |
| Weekly | Risk score (D-43 stage 3) | 0.995 | 0.984 | 0.976 | 0.307 | 1.10 | 85.4% | met |
| Weekly | Rule, baselines | 1.000 | 0.973 | 0.960 | 0.348 | 1.25 | 70.0% | met |
| 4-weekly (one decision per 4 weeks) | Rule, trained models | 0.843 | - | - | 0.373 | - | 62.7% | not met |
| 4-weekly | Rule, baselines | 0.914 | - | - | 0.359 | - | 71.8% | not met |

Base rate (share of decisions followed by a true stock-out): 0.278 weekly. The risk score ranks stock-outs better than weeks of stock alone (AUC 0.712 against 0.655 on the test weeks) but, held to 95% recall, flags most vaccine-weeks. Precision stays low for every method because most stock-outs come from short deliveries, which the ledger shows only weakly in advance (doc 15 section 4). Which method the application uses is D-45.

### 6.3 Defaulter categorisation

10,390 children under 2 across 12 facilities: defaulter status and overdue dose list match the independent oracle for 10,390 of 10,390 (100%); rank order matches at 12 of 12 facilities. Target (section 4): **met**.
