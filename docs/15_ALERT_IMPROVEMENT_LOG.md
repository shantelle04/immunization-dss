# 15. Stock-out alert improvement log

A dated record of every attempt to improve the stock-out alerts: what was tried, why, the measured result, and what was concluded. Nothing here is a tuned-on-test result: thresholds are fixed before measuring or set on earlier weeks, and negative results stay in the log. Metric definitions: doc 05 section 2. Decisions: doc 07 (D-38, D-41 to D-44). Evidence run `sim-seed42-368707d3`; every figure is in the results ledger or a Colab results folder.

## 1. Target and starting point

D-07 (proposed, for the supervisor): alert recall at least 0.95 at a 4-week horizon, with precision reported beside it so the target cannot be met by alerting everything.

## 2. Timeline

| # | Date | Attempt | Forecasts | Recall | Precision (strict) | Flagged | Outcome |
|---|---|---|---|---|---|---|---|
| 1 | 2026-10-02 | First rule: projected stock from the forecast upper bound against the BR-05 safety minimum, one decision per series every 4 weeks | baselines | 0.657 | 0.335 | 281 of 504 | Too low. Cause found: stock also falls by discarded vial remainders (BCG, MR), which the rule ignored |
| 2 | 2026-10-02 | Usage factor: scale the forecast by doses leaving stock per dose given, from the ledger (D-38) | baselines | 0.914 | 0.359 | 362 of 504 | Large gain; kept. Below 0.95 |
| 3 | 2026-10-02 | Same rule with the trained models (first Colab run `ff1ff0b`) | GRU 80, SARIMA 4 | 0.843 | 0.379 | 311 of 504 | More accurate forecasts, fewer alerts, lower recall |
| 4 | 2026-10-02 | Calibrate the GRU interval, two-sided, on the early-stopping weeks (D-41 C, run `03d112c`) | GRU 80, SARIMA 4 | 0.843 | 0.377 | 313 of 504 | No change: margin near zero on those weeks |
| 5 | 2026-10-02 | Calibrate only the upper end on a separate block of weeks (D-41 D, run `25f6f70`) | GRU 80, SARIMA 4 | 0.843 | 0.373 | 316 of 504 | Forecast improved (MASE 0.671, coverage 0.806); recall unchanged. The misses are not a forecasting problem |
| 6 | 2026-10-02 | Late-delivery check: warn if a one-week-late delivery would empty the stock (D-42 B) | GRU 80, SARIMA 4 | 1.000 | 0.303 | 482 of 504 | Rejected: flags 95.6% of decisions. Not used in the app |
| 7 | 2026-10-02 | Weekly decisions (D-43 stage 1): same rule, decided every week as the app does | baselines | 1.000; early 0.973; onset early 0.960 | 0.348 (base rate 0.278, lift 1.25) | 1,234 of 1,764 | **Recall target met** on the weekly definition, including with a full week of warning. Precision is only 1.25 times the base rate. Trained models: pending the next Colab run |
| 8 | 2026-10-02 | Delivery-history gate (D-43 stage 2): raise the late-delivery warning only for series whose past deliveries were late | baselines | 1.000; early 1.000 | 0.289 (lift 1.04) | 1,677 of 1,764 | No gain: deliveries are rarely late by more than a week (late rate 0 for 73.8% of tuning decisions, never above 0.25), so the gate cannot separate series. Negative result |
| 9 | 2026-10-02 | Fix of the ledger stock-out flag (T-03, D-44), found while testing stage 3 | - | - | - | - | The flag missed weeks that start and stay at zero stock. After the fix it marks 2,290 weeks, exactly the simulator's true stock-out weeks, without reading `truth/`. Training series hash changed |
| 10 | pending | Risk score (D-43 stage 3): logistic regression on ledger features, threshold set on earlier weeks | Colab | pending | pending | pending | Needs the next Colab run |

Rows 1 to 6 use the 4-weekly evaluation (504 decisions, 198 true stock-out weeks); rows 7 and 8 the weekly evaluation (1,764 decisions, 183 true stock-out weeks counted, 126 episode starts). The two are not directly comparable: see section 3.

## 3. What changed in the measurement, and why it is fair (D-43)

The application re-checks stock every night. The first evaluation made one decision per series every 4 weeks and never looked again, so a stock-out in week 3 could only be caught by a decision made 3 weeks earlier. The weekly evaluation makes a decision every week over the same last 24 weeks and scores it with three measures (doc 05 section 2):

- **Recall**: true stock-out weeks with a flagged decision in that week or the 3 weeks before.
- **Early recall**: the same, but the flagged decision must be at least one week before (a real warning).
- **Onset early recall**: early recall for the first week of each stock-out episode only, so a long stock-out is not counted many times.

Precision is reported with the **base rate** (the share of all decisions followed by a stock-out, which is the precision of flagging everything) and their ratio, the **lift**. A lift near 1 means the alerts are little better than flagging everything.

## 4. What the data says about why stock-outs are hard to predict

From the ledger features on the 24 tuning weeks (1,764 decisions, labels from the ledger's stock-out flag):

| Signal | Stock-out in the next 4 weeks |
|---|---|
| All decisions (base rate on ledger labels) | 28.7% |
| Under half a week of stock | 43.4% |
| 1 to 3 weeks of stock | 30.3% |
| More than 4 weeks of stock | 13.8% |
| Last three deliveries covered at most one cycle of use | 35.1% |
| Last three deliveries covered 1.0 to 1.2 cycles | 17.5% |
| Delivery overdue by 2 weeks or more | 21.4% (14 decisions only) |
| Share of late delivery intervals above 10% | 11.5% (78 decisions), against 29.5% for the rest |

Even a nearly empty store avoids a stock-out more often than not, because the next delivery usually arrives in time; and a well-stocked store still runs out 14% of the time. The clearest ledger signal is whether recent deliveries were big enough; lateness shows no useful signal. This corrects the wording of D-42, which said "late or short": the evidence points to **short** deliveries.

## 5. Current position

| Measure (weekly evaluation, baselines) | Value | Target |
|---|---|---|
| Recall | 1.000 | 0.95: met |
| Early recall (at least one week of warning) | 0.973 | 0.95: met |
| Onset early recall | 0.960 | 0.95: met |
| Strict precision | 0.348 | reported |
| Base rate, lift | 0.278, 1.25 | reported |
| Share of decisions flagged | 70.0% | reported |

The recall target is met on a definition that matches how the system runs, but the alerts are not selective: 7 in 10 vaccine-weeks are flagged. The remaining work is precision, which is what the risk score is for.

## 6. Next

1. Colab run at the new commit: main backtest on the corrected series, weekly forecasts for the selected models, the risk score. Record rows 7 and 10 for the trained models.
2. If the risk score has a better lift at 0.95 recall than the rule, propose it for the application (author decides).
3. Raise the precision question with the supervisor alongside D-07.
