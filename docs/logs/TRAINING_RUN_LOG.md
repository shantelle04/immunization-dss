# Training and backtest run log

| Run ID | Date | Git SHA | Data hash | Model | Params | Backtest window | MAE | MASE | sMAPE | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| sim-seed42-368707d3-baselines | 2026-10-02 | 855d49a | series 279617cf49ee | B1 seasonal naive | lag 52; short-history fallback mean of 4 | 6 origins x 4 weeks, 2025-07-07 to 2025-12-22 | 5.865 | 0.950 | 0.493 | Local: baselines fit nothing (D-14 allows). Coverage80 0.842 |
| sim-seed42-368707d3-baselines | 2026-10-02 | 855d49a | series 279617cf49ee | B2 moving average | window 4 | same | 4.689 | 0.766 | 0.375 | Coverage80 0.812; selected for 64 of 84 series. Alerts: recall 0.914, precision 0.586 (doc 05 section 6) |
