# 05. Models, metrics and testing

## 1. Demand forecasting (M1)

| Item | Definition |
|---|---|
| Series | Weekly doses administered per facility x antigen, from the app's stock issues (what a real system would see). True demand (including children turned away) exists only in `truth/weekly_stock.csv` and is used to evaluate, never to train |
| Horizon | 1 to 4 weeks ahead (rolling 4-week forecast, proposal 2.5.1) |
| Candidates | B1 seasonal naive (same week last year, or last 4-week mean when history is short); B2 moving average of the last 4 weeks (proposal's comparison point); SARIMA (statsmodels; ARIMA orders (1,0,0), (0,1,1), (1,1,1), (2,0,1), each with and without 2 Fourier harmonics of the 52.18-week year for seasonality (D-36), chosen by AIC on the training window); GRU (Keras, one global model across all 84 series, lookback 26 weeks, inputs: scaled series, ledger stock-out flag, week-of-year sine and cosine, one-hot facility and antigen) |
| Selection per series | GRU when the series has at least 104 weeks and beats B1 on its backtest; else SARIMA; if history is under 26 weeks, a population-based estimate (catchment births x schedule x coverage). Proposal says "ARIMA fallback for facilities with no history"; ARIMA cannot fit without history, so this is logged as D-21 |
| Validation | Rolling-origin backtest: 6 origins of 4 weeks covering the last 24 weeks (D-35), every model refit at each origin on the weeks before it only; scalers fit on training windows only; GRU early stopping uses the last 15% of the training weeks as a time-based hold-out |
| Intervals | 80% intervals: SARIMA native intervals; GRU from the quantile (pinball) loss at 0.1, 0.5 and 0.9; baselines from the 10th and 90th percentiles of in-sample residuals |

**Metrics**

| Metric | Formula | Notes |
|---|---|---|
| MAE | mean abs(y - yhat) | In doses |
| MASE | MAE over the 4 test weeks / mean abs(y_t - y_(t-52)) over that origin's training weeks; averaged over the 6 origins | Under 1 means better than the in-sample seasonal naive; undefined (reported as missing) if the training weeks repeat exactly |
| sMAPE | mean 2 abs(y - yhat) / (abs(y) + abs(yhat)) | Plain MAPE is undefined at zero weeks |
| Interval coverage | share of actuals inside the 80% interval | Calibration |

## 2. Stock-out alerts (M1)

Projected stock at week t+k = current stock + scheduled receipts up to t+k - cumulative upper-quantile demand to t+k. Alert when projected stock < safety minimum (BR-05) before the next replenishment.

| Metric | Definition (against simulator ground truth) |
|---|---|
| Alert recall | True stock-out weeks (`truth/weekly_stock.csv`, `stockout = true`) preceded by an alert within 4 weeks / all true stock-out weeks |
| Alert precision | Alerts followed by a true stock-out or true below-minimum week within 4 weeks / all alerts |
| F1 | Harmonic mean |
| Lead time | Weeks between alert and the event |

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
