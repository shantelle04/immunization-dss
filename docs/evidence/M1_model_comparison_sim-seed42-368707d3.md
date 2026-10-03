# Model comparison: sim-seed42-368707d3 (final Colab run)

From the results zip of the Colab notebook at commit `625841d` (Tesla T4; Python 3.13.15, statsmodels 0.14.6, TensorFlow 2.20.0). Training series SHA-256 `9e4e6a4edda1d6e4d6ab86cd70c324d4bdb746519f3c20947821773613f6d4cf` (after the T-03 fix, D-44), seed 42, 260 weeks, 6 origins x 4 weeks. The regenerated data was byte-identical to the evidence run (14 of 14 files). Earlier runs and why each was repeated: doc 15.

## T-M2 Overall (84 series)

| model | series | mean_mase | median_mase | share_beating_naive | mean_mae | mean_smape | coverage80 |
|---|---|---|---|---|---|---|---|
| gru | 84 | 0.6709 | 0.6327 | 0.9643 | 4.0788 | 0.3368 | 0.8041 |
| sarima | 84 | 0.6811 | 0.6398 | 0.9643 | 4.1713 | 0.3384 | 0.8442 |
| b2 | 84 | 0.7657 | 0.7244 | 0.9048 | 4.6885 | 0.375 | 0.8115 |
| b1 | 84 | 0.9504 | 0.9342 | 0.6429 | 5.8646 | 0.4927 | 0.8418 |

## T-M3 Mean MASE per vaccine

| antigen_code | gru | sarima | b2 | b1 |
|---|---|---|---|---|
| BCG | 0.689 | 0.687 | 0.79 | 0.923 |
| IPV | 0.765 | 0.775 | 0.924 | 1.008 |
| MR | 0.69 | 0.687 | 0.798 | 1.086 |
| OPV | 0.561 | 0.559 | 0.629 | 0.813 |
| PCV | 0.665 | 0.702 | 0.75 | 0.975 |
| PENTA | 0.687 | 0.731 | 0.802 | 0.947 |
| ROTA | 0.64 | 0.628 | 0.667 | 0.9 |

## T-M4 Selection per series (D-21)

| model | reason | series |
|---|---|---|
| gru | GRU beats seasonal naive with enough history | 80 |
| sarima | fallback: SARIMA | 4 |

## T-M5 Bias against true demand (truth/, evaluation only; doses per week)

| model | stockout_flag | weeks | mean_bias | mae_vs_true_demand |
|---|---|---|---|---|
| b1 | False | 1818 | -1.008 | 5.568 |
| b1 | True | 198 | -2.758 | 6.313 |
| b2 | False | 1818 | -0.307 | 4.265 |
| b2 | True | 198 | -1.221 | 5.193 |
| gru | False | 1818 | -0.787 | 3.613 |
| gru | True | 198 | -1.475 | 4.153 |
| sarima | False | 1818 | -0.899 | 3.736 |
| sarima | True | 198 | -1.695 | 4.348 |

## T-M6 MAE on test weeks without a ledger stock-out

| model | mae_no_stockout |
|---|---|
| b1 | 5.556 |
| b2 | 4.337 |
| gru | 3.649 |
| sarima | 3.785 |

## T-M7 Stock-out alerts, 4-weekly evaluation (504 decisions, buffer 0.25)

| Measure | Value |
|---|---|
| Recall | 0.8434 (167 of 198) |
| Precision (stock-out or below minimum) | 0.6297 |
| Strict precision | 0.3734 |
| F1 | 0.7211 |
| Mean lead time (weeks) | 2.04 |

## T-M8 Stock-out alerts, weekly evaluation (D-43; 1,764 decisions over 21 test weeks)

| method | decisions | flagged | flagged_share | true_stockout_weeks | recall | early_recall | onsets | onset_early_recall | precision_stockout_only | base_rate | lift | f1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rule, weekly decisions | 1764 | 1091 | 0.6185 | 183 | 0.9945 | 0.9399 | 126 | 0.9127 | 0.3639 | 0.2783 | 1.31 | 0.5328 |
| rule + late-delivery warning (all facilities) | 1764 | 1651 | 0.9359 | 183 | 1.0 | 1.0 | 126 | 1.0 | 0.2938 | 0.2783 | 1.06 | 0.4541 |
| rule + late-delivery warning gated by delivery history | 1764 | 1651 | 0.9359 | 183 | 1.0 | 1.0 | 126 | 1.0 | 0.2938 | 0.2783 | 1.06 | 0.4541 |
| risk score | 1764 | 1506 | 0.8537 | 183 | 0.9945 | 0.9836 | 126 | 0.9762 | 0.3068 | 0.2783 | 1.1 | 0.4689 |
| risk score or rule | 1764 | 1552 | 0.8798 | 183 | 1.0 | 0.9945 | 126 | 0.9921 | 0.3048 | 0.2783 | 1.09 | 0.4672 |

Risk score: logistic regression, 12180 training decisions, threshold 0.1655 chosen on 1764 tuning decisions (ledger recall 0.9506). Delivery-history gate chosen on the tuning weeks: 0.0.

## T-M1 Series profile per vaccine

| antigen_code | series | mean_weekly_doses | share_zero_weeks | share_stockout_weeks | acf_lag1 | acf_lag4 | acf_lag52 |
|---|---|---|---|---|---|---|---|
| BCG | 12 | 8.212 | 0.057 | 0.143 | 0.03 | 0.043 | 0.08 |
| IPV | 12 | 7.349 | 0.06 | 0.105 | 0.058 | 0.062 | 0.204 |
| MR | 12 | 13.12 | 0.046 | 0.142 | 0.169 | 0.013 | 0.132 |
| OPV | 12 | 29.771 | 0.034 | 0.096 | 0.111 | 0.103 | -0.007 |
| PCV | 12 | 23.867 | 0.015 | 0.069 | 0.06 | 0.188 | 0.15 |
| PENTA | 12 | 23.616 | 0.016 | 0.081 | 0.077 | 0.3 | 0.264 |
| ROTA | 12 | 15.882 | 0.027 | 0.098 | 0.082 | 0.284 | 0.152 |

Figures: F-M1 weekly issues by vaccine, F-M2 seasonality, F-M3 MASE per series by model (`docs/evidence/`).
