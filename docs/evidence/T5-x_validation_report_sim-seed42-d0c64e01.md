# Validation report: sim-seed42-d0c64e01

Overall: PASS

| Check | Description | Result | Detail |
|---|---|---|---|
| V-01 | Every file matches its manifest hash | PASS | 16 files verified |
| V-02 | Stock conservation: opening + receipts - administered - wastage - losses = closing | PASS | 0 of 21840 facility-antigen-weeks violate it |
| V-03 | Stock never negative | PASS | 0 negative balances |
| V-04 | Transaction ledger sums to the final closing balance | PASS | max difference 0 doses |
| V-05 | No dose before its minimum age or after its maximum age | PASS | 0 too young, 0 too old |
| V-06 | Minimum interval between doses of the same antigen respected | PASS | 0 violations |
| V-07 | No child receives the same dose twice | PASS | 0 duplicates |
| V-08 | Doses of a series are given in order | PASS | 0 out-of-order series |
| V-09 | Every event belongs to a registered child | PASS | 0 orphan events |
| V-10 | Coverage within 3.0 points of KDHS 2022 Table 11 for every antigen | PASS | largest difference 1.4 points (rota2) |
| V-11 | Stock-outs occur (the alert evaluation needs positive cases) | PASS | 2367 stock-out facility-antigen-weeks |

## coverage_vs_kdhs2022

| indicator | cohort_size | simulated_pct | kdhs_2022_pct | difference_pp |
|---|---|---|---|---|
| bcg | 5309 | 97.7 | 96.9 | 0.8 |
| opv0 | 5309 | 87.4 | 86.1 | 1.3 |
| opv1 | 5309 | 97.1 | 96.5 | 0.6 |
| opv2 | 5309 | 95.1 | 94.2 | 0.9 |
| opv3 | 5309 | 78.7 | 78.2 | 0.5 |
| penta1 | 5309 | 97.1 | 97.1 | 0.0 |
| penta2 | 5309 | 94.8 | 93.9 | 0.9 |
| penta3 | 5309 | 88.1 | 89.2 | -1.1 |
| pcv1 | 5309 | 97.0 | 96.5 | 0.5 |
| pcv2 | 5309 | 95.3 | 95.4 | -0.1 |
| pcv3 | 5309 | 90.0 | 91.2 | -1.2 |
| rota1 | 5309 | 95.7 | 96.0 | -0.3 |
| rota2 | 5309 | 90.9 | 92.3 | -1.4 |
| ipv | 5309 | 87.9 | 87.4 | 0.5 |
| mr1 | 5309 | 87.6 | 89.0 | -1.4 |
| mr2 | 5225 | 65.9 | 66.8 | -0.9 |
| zero_dose | 5309 | 2.1 | 2.1 | 0.0 |

## penta3_by_group

| group | category | n | simulated_penta3_pct | kdhs_2022_pct |
|---|---|---|---|---|
| education | none | 534 | 82.2 | 73.0 |
| education | primary | 1987 | 89.0 | 90.6 |
| education | secondary | 1866 | 88.3 | 90.6 |
| education | higher | 922 | 89.5 | 92.6 |
| wealth | lowest | 1235 | 87.0 | 85.1 |
| wealth | second | 989 | 91.0 | 92.3 |
| wealth | middle | 876 | 85.8 | 88.8 |
| wealth | fourth | 1010 | 88.1 | 90.0 |
| wealth | highest | 1199 | 88.6 | 90.4 |
| birth_order | 1 | 1648 | 89.3 | 92.0 |
| birth_order | 2-3 | 2038 | 87.5 | 89.0 |
| birth_order | 4-5 | 1058 | 88.5 | 88.9 |
| birth_order | 6+ | 565 | 86.5 | 82.5 |

## timeliness

| dose | median_days_after_recommended_age | share_within_28_days_pct |
|---|---|---|
| BCG-1 | 3.0 | 79.0 |
| PENTA-1 | 9.0 | 91.9 |
| PENTA-3 | 28.0 | 51.7 |
| MR-1 | 25.0 | 56.9 |

## stock_summary

| antigen_code | stockout_weeks | unmet_doses | administered | wasted | wastage_rate_pct |
|---|---|---|---|---|---|
| BCG | 490 | 2056 | 25777 | 157283 | 85.9 |
| IPV | 322 | 1328 | 23121 | 1 | 0.0 |
| MR | 490 | 3361 | 40466 | 67854 | 62.6 |
| OPV | 209 | 4037 | 93063 | 0 | 0.0 |
| PCV | 303 | 3763 | 74329 | 0 | 0.0 |
| PENTA | 272 | 3862 | 73577 | 0 | 0.0 |
| ROTA | 281 | 2696 | 49495 | 0 | 0.0 |
