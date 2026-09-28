# D-23 and D-26: before and after

Before: `sim-seed42-cf02cb90` (BCG and MR batched at dispensaries and health centres; 3 undamped refinement rounds). After: `sim-seed42-368707d3` (BCG also batched at sub-county hospitals, D-23; damped refinement, D-26: `engine_damping` 0.6, target 1.5 pp, at most 8 rounds). Same seed 42; both pass validate-sim 11/11. Rejected or failed runs in between: `sim-seed42-deca88d9` (FAIL, OPV3 -3.1), `sim-seed42-cce5aedc` (passed at 2.4 but oscillating).

Second-stage refinement, largest error per round (pp): 12.4, 6.5, 5.1, 5.9, 3.9, 2.4, 2.9, 2.6, 2.5. The 1.5 target was not reached; the last four rounds stayed between 2.4 and 2.9. MR1 is the limiting dose: its contact attendance is already about 99.5% (logit 5.27) and its give probability is 1.0, so the shortfall comes from children who are deferred to the MR day and do not return (20%) and from MR stock-outs. This is a ceiling set by the batching assumption, not a calibration failure.

## Coverage vs KDHS 2022 Table 11 (tolerance 3.0 pp)

| indicator | kdhs_2022_pct | before_pct | before_diff_pp | after_pct | after_diff_pp |
|---|---|---|---|---|---|
| bcg | 96.9 | 97.6 | 0.7 | 97.1 | 0.2 |
| opv0 | 86.1 | 86.7 | 0.6 | 85.0 | -1.1 |
| opv1 | 96.5 | 97.1 | 0.6 | 97.0 | 0.5 |
| opv2 | 94.2 | 95.0 | 0.8 | 94.7 | 0.5 |
| opv3 | 78.2 | 79.4 | 1.2 | 76.2 | -2.0 |
| penta1 | 97.1 | 97.2 | 0.1 | 97.2 | 0.1 |
| penta2 | 93.9 | 95.0 | 1.1 | 94.8 | 0.9 |
| penta3 | 89.2 | 88.7 | -0.5 | 88.2 | -1.0 |
| pcv1 | 96.5 | 97.1 | 0.6 | 97.1 | 0.6 |
| pcv2 | 95.4 | 95.3 | -0.1 | 95.5 | 0.1 |
| pcv3 | 91.2 | 90.4 | -0.8 | 91.4 | 0.2 |
| rota1 | 96.0 | 96.2 | 0.2 | 95.9 | -0.1 |
| rota2 | 92.3 | 92.7 | 0.4 | 91.7 | -0.6 |
| ipv | 87.4 | 87.9 | 0.5 | 87.6 | 0.2 |
| mr1 | 89.0 | 86.2 | -2.8 | 86.5 | -2.5 |
| mr2 | 66.8 | 64.4 | -2.4 | 66.3 | -0.5 |
| zero_dose | 2.1 | 2.1 | 0.0 | 2.1 | 0.0 |

## Wastage (WHO definition) and stock-outs, 2021 to 2025

WHO indicative rates: WHO (2019) concept note, Table 1 (`docs/logs/SOURCE_CHECKS.md`).

| antigen | who_indicative_pct | wastage_who_before_pct | wastage_who_after_pct | stockout_weeks_before | stockout_weeks_after | unmet_before | unmet_after |
|---|---|---|---|---|---|---|---|
| BCG | 50 | 79.2 | 65.8 | 473 | 446 | 1649 | 1108 |
| IPV | 10 | 4.6 | 4.2 | 323 | 327 | 1483 | 1439 |
| MR | 40 | 46.4 | 46.1 | 458 | 444 | 2783 | 2589 |
| OPV | 25 | 5.8 | 6.1 | 277 | 300 | 5210 | 5952 |
| PCV | 10 | 1.3 | 1.4 | 259 | 214 | 3485 | 2976 |
| PENTA | 5 | 0.3 | 0.2 | 274 | 254 | 3987 | 3006 |
| ROTA | 5 | 0.2 | 0.3 | 307 | 305 | 3680 | 2935 |

## Timeliness

| dose | median_days_before | median_days_after | within_28d_before_pct | within_28d_after_pct |
|---|---|---|---|---|
| BCG-1 | 4.0 | 7.0 | 72.6 | 65.0 |
| PENTA-1 | 9.0 | 9.0 | 91.8 | 92.6 |
| PENTA-3 | 28.0 | 27.0 | 51.0 | 52.5 |
| MR-1 | 26.0 | 26.0 | 54.6 | 54.6 |
