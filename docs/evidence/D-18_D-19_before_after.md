# D-18 and D-19: before and after

Before: `sim-seed42-d0c64e01` (effect_shrink 0.6, no batching, no open-vial discard). After: `sim-seed42-cf02cb90` (effect_shrink 0.8, BCG and MR batched to Tuesday static sessions at dispensaries and health centres with 80% return, open-vial-policy discard 0.05 per session, engine_refinements 3). Same seed 42. Both runs pass validate-sim 11/11. An intermediate run `sim-seed42-080265b6` (engine_refinements 2) FAILED V-10 (MR1 -3.2 pp) and is not usable.

## Coverage vs KDHS 2022 Table 11 (V-10, tolerance 3.0 pp)

| indicator | kdhs_2022_pct | before_pct | before_diff_pp | after_pct | after_diff_pp |
|---|---|---|---|---|---|
| bcg | 96.9 | 97.7 | 0.8 | 97.6 | 0.7 |
| opv0 | 86.1 | 87.4 | 1.3 | 86.7 | 0.6 |
| opv1 | 96.5 | 97.1 | 0.6 | 97.1 | 0.6 |
| opv2 | 94.2 | 95.1 | 0.9 | 95.0 | 0.8 |
| opv3 | 78.2 | 78.7 | 0.5 | 79.4 | 1.2 |
| penta1 | 97.1 | 97.1 | 0.0 | 97.2 | 0.1 |
| penta2 | 93.9 | 94.8 | 0.9 | 95.0 | 1.1 |
| penta3 | 89.2 | 88.1 | -1.1 | 88.7 | -0.5 |
| pcv1 | 96.5 | 97.0 | 0.5 | 97.1 | 0.6 |
| pcv2 | 95.4 | 95.3 | -0.1 | 95.3 | -0.1 |
| pcv3 | 91.2 | 90.0 | -1.2 | 90.4 | -0.8 |
| rota1 | 96.0 | 95.7 | -0.3 | 96.2 | 0.2 |
| rota2 | 92.3 | 90.9 | -1.4 | 92.7 | 0.4 |
| ipv | 87.4 | 87.9 | 0.5 | 87.9 | 0.5 |
| mr1 | 89.0 | 87.6 | -1.4 | 86.2 | -2.8 |
| mr2 | 66.8 | 65.9 | -0.9 | 64.4 | -2.4 |
| zero_dose | 2.1 | 2.1 | 0.0 | 2.1 | 0.0 |

## Penta3 by subgroup (D-19)

| group | category | kdhs_2022_pct | before_pct | before_diff_pp | after_pct | after_diff_pp |
|---|---|---|---|---|---|---|
| education | none | 73.0 | 82.2 | 9.2 | 80.3 | 7.3 |
| education | primary | 90.6 | 89.0 | -1.6 | 89.8 | -0.8 |
| education | secondary | 90.6 | 88.3 | -2.3 | 89.4 | -1.2 |
| education | higher | 92.6 | 89.5 | -3.1 | 89.8 | -2.8 |
| wealth | lowest | 85.1 | 87.0 | 1.9 | 86.0 | 0.9 |
| wealth | second | 92.3 | 91.0 | -1.3 | 92.1 | -0.2 |
| wealth | middle | 88.8 | 85.8 | -3.0 | 86.1 | -2.7 |
| wealth | fourth | 90.0 | 88.1 | -1.9 | 88.6 | -1.4 |
| wealth | highest | 90.4 | 88.6 | -1.8 | 90.7 | 0.3 |
| birth_order | 1 | 92.0 | 89.3 | -2.7 | 90.0 | -2.0 |
| birth_order | 2-3 | 89.0 | 87.5 | -1.5 | 89.1 | 0.1 |
| birth_order | 4-5 | 88.9 | 88.5 | -0.4 | 88.6 | -0.3 |
| birth_order | 6+ | 82.5 | 86.5 | 4.0 | 83.9 | 1.4 |

## Wastage and stock-outs by antigen, 2021 to 2025 (D-18)

| antigen | wastage_before_pct | wastage_after_pct | stockout_weeks_before | stockout_weeks_after | unmet_doses_before | unmet_doses_after |
|---|---|---|---|---|---|---|
| BCG | 85.9 | 79.2 | 490 | 473 | 2056 | 1649 |
| IPV | 0.0 | 4.2 | 322 | 323 | 1328 | 1483 |
| MR | 62.6 | 46.3 | 490 | 458 | 3361 | 2783 |
| OPV | 0.0 | 5.5 | 209 | 277 | 4037 | 5210 |
| PCV | 0.0 | 1.1 | 303 | 259 | 3763 | 3485 |
| PENTA | 0.0 | 0.0 | 272 | 274 | 3862 | 3987 |
| ROTA | 0.0 | 0.0 | 281 | 307 | 2696 | 3680 |

## Timeliness

| dose | median_days_before | median_days_after | within_28d_before_pct | within_28d_after_pct |
|---|---|---|---|---|
| BCG-1 | 3.0 | 4.0 | 79.0 | 72.6 |
| PENTA-1 | 9.0 | 9.0 | 91.9 | 91.8 |
| PENTA-3 | 28.0 | 28.0 | 51.7 | 51.0 |
| MR-1 | 25.0 | 26.0 | 56.9 | 54.6 |
