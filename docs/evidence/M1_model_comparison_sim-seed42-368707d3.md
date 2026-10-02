# Model comparison: sim-seed42-368707d3 (Colab run)

Generated from the results zip of the Colab notebook (`notebooks/immdss_colab_pipeline.ipynb`). Training commit `ff1ff0b`, training series SHA-256 `279617cf49eefa40473a8cb2873f4357238fd44848f791babf1459887bd9dc2b`, seed 42, 260 weeks, 6 origins x 4 weeks (24 test weeks), device `/physical_device:GPU:0` (Tesla T4), Python 3.13.15, statsmodels 0.14.6, TensorFlow 2.20.0. The regenerated data was byte-identical to the evidence run (14 of 14 files); the series hash equals the local one. Run times on Colab: SARIMA 848.9 s, GRU 158.1 s (6 fits), baselines 0.1 s each.

## T-M2 Overall (84 series)

| model | series | mean_mase | median_mase | share_beating_naive | mean_mae | mean_smape | coverage80 |
|---|---|---|---|---|---|---|---|
| gru | 84 | 0.6765 | 0.6358 | 0.9643 | 4.1078 | 0.3407 | 0.7862 |
| sarima | 84 | 0.6811 | 0.6398 | 0.9643 | 4.1713 | 0.3384 | 0.8442 |
| b2 | 84 | 0.7657 | 0.7244 | 0.9048 | 4.6885 | 0.375 | 0.8115 |
| b1 | 84 | 0.9504 | 0.9342 | 0.6429 | 5.8646 | 0.4927 | 0.8418 |

## T-M3 Mean MASE per vaccine

| antigen_code | gru | sarima | b2 | b1 |
|---|---|---|---|---|
| BCG | 0.699 | 0.687 | 0.79 | 0.923 |
| IPV | 0.772 | 0.775 | 0.924 | 1.008 |
| MR | 0.695 | 0.687 | 0.798 | 1.086 |
| OPV | 0.564 | 0.559 | 0.629 | 0.813 |
| PCV | 0.664 | 0.702 | 0.75 | 0.975 |
| PENTA | 0.697 | 0.731 | 0.802 | 0.947 |
| ROTA | 0.644 | 0.628 | 0.667 | 0.9 |

## T-M4 Selection per series (D-21)

| model | reason | series |
|---|---|---|
| gru | GRU beats seasonal naive with enough history | 80 |
| sarima | fallback: SARIMA | 4 |

## T-M5 Bias against true demand (truth/, evaluation only; doses per week)

| model | stockout_flag | weeks | mean_bias | mae_vs_true_demand |
|---|---|---|---|---|
| b1 | False | 1877 | -1.1 | 5.617 |
| b1 | True | 139 | -2.252 | 5.964 |
| b2 | False | 1877 | -0.397 | 4.322 |
| b2 | True | 139 | -0.392 | 4.813 |
| gru | False | 1877 | -1.054 | 3.682 |
| gru | True | 139 | -1.329 | 4.045 |
| sarima | False | 1877 | -0.951 | 3.767 |
| sarima | True | 139 | -1.333 | 4.193 |

## T-M6 Stock-out alerts with the selected models (D-38, buffer 0.25)

| Measure | Value |
|---|---|
| Decisions | 504 |
| Alerts | 311 |
| True stock-out weeks alerted | 167 of 198 |
| Recall | 0.8434 |
| Precision (stock-out or below minimum) | 0.6399 |
| Strict precision (stock-out only) | 0.3794 |
| F1 | 0.7277 |
| Mean lead time (weeks) | 2.04 |

Sensitivity to the buffer: | buffer | alerts | recall | precision | f1 |
|---|---|---|---|---|
| 0.0 | 304 | 0.8384 | 0.5296 | 0.6491 |
| 0.1 | 305 | 0.8384 | 0.5541 | 0.6672 |
| 0.25 | 311 | 0.8434 | 0.6399 | 0.7277 |
| 0.5 | 343 | 0.899 | 0.7784 | 0.8344 |

Recall per vaccine: | antigen | alerts | true_stockout_weeks | recall |
|---|---|---|---|
| BCG | 56.0 | 47.0 | 0.8936 |
| IPV | 47.0 | 33.0 | 0.9091 |
| MR | 50.0 | 46.0 | 0.8913 |
| OPV | 36.0 | 11.0 | 0.6364 |
| PCV | 42.0 | 22.0 | 0.8182 |
| PENTA | 42.0 | 21.0 | 0.7619 |
| ROTA | 38.0 | 18.0 | 0.7222 |

## T-M1 Series profile per vaccine

| antigen_code | series | mean_weekly_doses | share_zero_weeks | share_stockout_weeks | acf_lag1 | acf_lag4 | acf_lag52 |
|---|---|---|---|---|---|---|---|
| BCG | 12 | 8.212 | 0.057 | 0.102 | 0.03 | 0.043 | 0.08 |
| IPV | 12 | 7.349 | 0.06 | 0.069 | 0.058 | 0.062 | 0.204 |
| MR | 12 | 13.12 | 0.046 | 0.099 | 0.169 | 0.013 | 0.132 |
| OPV | 12 | 29.771 | 0.034 | 0.062 | 0.111 | 0.103 | -0.007 |
| PCV | 12 | 23.867 | 0.015 | 0.054 | 0.06 | 0.188 | 0.15 |
| PENTA | 12 | 23.616 | 0.016 | 0.066 | 0.077 | 0.3 | 0.264 |
| ROTA | 12 | 15.882 | 0.027 | 0.073 | 0.082 | 0.284 | 0.152 |

Figures: F-M1 weekly issues by vaccine, F-M2 seasonality, F-M3 MASE per series by model (`docs/evidence/`).
