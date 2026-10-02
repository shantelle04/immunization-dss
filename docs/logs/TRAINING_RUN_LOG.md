# Training and backtest run log

| Run ID | Date | Git SHA | Data hash | Model | Params | Backtest window | MAE | MASE | sMAPE | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| sim-seed42-368707d3-baselines | 2026-10-02 | 855d49a | series 279617cf49ee | B1 seasonal naive | lag 52; short-history fallback mean of 4 | 6 origins x 4 weeks, 2025-07-07 to 2025-12-22 | 5.865 | 0.950 | 0.493 | Local: baselines fit nothing (D-14 allows). Coverage80 0.842 |
| sim-seed42-368707d3-baselines | 2026-10-02 | 855d49a | series 279617cf49ee | B2 moving average | window 4 | same | 4.689 | 0.766 | 0.375 | Coverage80 0.812; selected for 64 of 84 series. Alerts: recall 0.914, precision 0.586 (doc 05 section 6) |
| colab-ff1ff0b | 2026-10-02 | ff1ff0b | series 279617cf49ee | GRU (global) | lookback 26, 64 units, pinball loss q 0.1/0.5/0.9, early stopping (24 to 31 epochs), seed 42 | 6 origins x 4 weeks, 2025-07-07 to 2025-12-22 | 4.108 | 0.677 | 0.341 | Colab Tesla T4, TensorFlow 2.20.0; 158 s; coverage80 0.786; selected for 80 series; `gru.keras` in the results zip |
| colab-ff1ff0b | 2026-10-02 | ff1ff0b | series 279617cf49ee | SARIMA | ARIMA orders by AIC with 0 or 2 Fourier harmonics (D-36); chosen most often (1,1,1) and (0,1,1) | same | 4.171 | 0.681 | 0.338 | Colab CPU, statsmodels 0.14.6; 849 s; coverage80 0.844; selected for 4 series |
| colab-ff1ff0b | 2026-10-02 | ff1ff0b | series 279617cf49ee | B1, B2 (rerun) | as above | same | 5.865, 4.689 | 0.950, 0.766 | 0.493, 0.375 | Identical to the local baseline run. Alerts with the D-21 selection: recall 0.843, precision 0.640 (doc 05 section 6). Imported into the app: 336 forecasts, 66 active alerts |
| colab-03d112c | 2026-10-02 | 03d112c | series 279617cf49ee | GRU (global) + conformal margin (D-41) | as colab-ff1ff0b; margins -0.0073 to 0.0275 (scaled) | same | 4.108 | 0.677 | 0.341 | Colab T4; point forecasts identical to colab-ff1ff0b; coverage80 0.787; alerts recall 0.843, precision 0.639; imported into the app |
