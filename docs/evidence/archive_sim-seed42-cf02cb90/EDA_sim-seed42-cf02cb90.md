# EDA evidence: sim-seed42-cf02cb90

Generated 2026-09-28 by `immdss eda`. Run seed 42, config hash `cf02cb90`, git commit `uncommitted`. Validation: PASS. Each figure is followed by its data table (table alternative and evidence).

## T-5.1 Dataset description

| folder | file | rows | columns | column_names | content | use |
|---|---|---|---|---|---|---|
| app | antigens.csv | 7 | 4 | antigen_code, name, doses_per_vial, open_vial_policy | Vaccines, vial size, open-vial policy | Loaded by the application |
| app | children.csv | 35,540 | 10 | child_id, system_id, given_name, family_name, sex, date_of_birth, caregiver_name, registration_facility_code, registered_on, is_synthetic | Registered children (synthetic names, no phone numbers) | Loaded by the application |
| app | facilities.csv | 12 | 7 | facility_code, name, keph_level, ownership, county, sub_county, is_synthetic | Fictional facilities and their KEPH level | Loaded by the application |
| app | immunization_events.csv | 499,042 | 10 | event_id, child_id, dose_code, antigen_code, dose_number, given_on, facility_code, session_id, lot_number, is_synthetic | Doses given: child, dose, date, facility, session, lot | Loaded by the application |
| app | schedule.csv | 16 | 8 | dose_code, antigen_code, dose_number, contact, recommended_age_days, min_age_days, max_age_days, min_interval_days | KEPI dose rules: recommended, minimum and maximum age, minimum interval | Loaded by the application |
| app | sessions.csv | 17,724 | 5 | session_id, facility_code, date, kind, location_name | Fixed and outreach immunization sessions | Loaded by the application |
| app | stock_transactions.csv | 89,962 | 9 | transaction_id, date, facility_code, antigen_code, lot_number, kind, quantity_doses, session_id, is_synthetic | Stock ledger: opening balances, receipts, issues, wastage, losses | Loaded by the application |
| app | vaccine_lots.csv | 5,769 | 3 | lot_number, antigen_code, first_received | Vaccine lots and first receipt date | Loaded by the application |
| imports | import_dirty_truth.csv | 120 | 3 | file, row_index, defect | Answer key: row and defect type for every planted defect | Import-cleaning test only |
| imports | import_immunizations_dirty.csv | 617 | 6 | child_system_id, date_of_birth, dose_code, given_on, facility_code, lot_number | Immunization import sample with planted defects | Import-cleaning test only |
| imports | import_stock_dirty.csv | 200 | 6 | date, facility_code, antigen_code, lot_number, kind, quantity_doses | Stock import sample with planted defects | Import-cleaning test only |
| truth | children_truth.csv | 36,431 | 16 | child_id, home_facility_code, date_of_birth, sex, education, wealth, birth_order, residence, attends_outreach, risk_log_odds, entered_care, first_contact, dropout_after_contact, moved_to_facility_code, move_from_contact, registered | Every child born (including never-registered zero-dose children), background, dropout | Evaluation only, never loaded |
| truth | stockout_turned_away.csv | 22,277 | 4 | child_id, dose_code, date, facility_code | Every dose refused because of a stock-out | Evaluation only, never loaded |
| truth | weekly_stock.csv | 21,840 | 14 | facility_code, antigen_code, week_start, opening_doses, receipts_doses, requested_doses, administered_doses, unmet_doses, vials_opened, wastage_doses, loss_doses, in_disruption, closing_doses, stockout | Facility x antigen x week: true demand, administered, unmet, wastage, stock-out flag | Evaluation only, never loaded |

## F-D1

![F-D1_calibration_vs_kdhs2022.png](F-D1_calibration_vs_kdhs2022.png)

| indicator | cohort_size | simulated_pct | kdhs_2022_pct | difference_pp |
|---|---|---|---|---|
| BCG | 5309 | 97.6 | 96.9 | 0.7 |
| OPV0 | 5309 | 86.7 | 86.1 | 0.6 |
| OPV1 | 5309 | 97.1 | 96.5 | 0.6 |
| OPV2 | 5309 | 95.0 | 94.2 | 0.8 |
| OPV3 | 5309 | 79.4 | 78.2 | 1.2 |
| Penta1 | 5309 | 97.2 | 97.1 | 0.1 |
| Penta2 | 5309 | 95.0 | 93.9 | 1.1 |
| Penta3 | 5309 | 88.7 | 89.2 | -0.5 |
| PCV1 | 5309 | 97.1 | 96.5 | 0.6 |
| PCV2 | 5309 | 95.3 | 95.4 | -0.1 |
| PCV3 | 5309 | 90.4 | 91.2 | -0.8 |
| Rota1 | 5309 | 96.2 | 96.0 | 0.2 |
| Rota2 | 5309 | 92.7 | 92.3 | 0.4 |
| IPV | 5309 | 87.9 | 87.4 | 0.5 |
| MR1 | 5309 | 86.2 | 89.0 | -2.8 |
| MR2 | 5225 | 64.4 | 66.8 | -2.4 |
| Zero-dose | 5309 | 2.1 | 2.1 | 0.0 |

## F-D2

![F-D2_dropout_by_level.png](F-D2_dropout_by_level.png)

| facility_level | registered_12_23m | penta1 | penta3 | mr1 | dropout_penta1_penta3_pct | dropout_penta1_mr1_pct |
|---|---|---|---|---|---|---|
| Dispensary | 814 | 803 | 733 | 707 | 8.7 | 12.0 |
| Health centre | 1763 | 1751 | 1604 | 1452 | 8.4 | 17.1 |
| Sub-county hospital | 2622 | 2604 | 2373 | 2418 | 8.9 | 7.1 |
| All facilities | 5199 | 5158 | 4710 | 4577 | 8.7 | 11.3 |

## F-D3

![F-D3_timeliness.png](F-D3_timeliness.png)

| dose | doses_given | median_days_late | p75_days_late | p90_days_late | within_28_days_pct |
|---|---|---|---|---|---|
| BCG | 35153 | 4.0 | 46.0 | 61.0 | 72.6 |
| Penta1 | 34575 | 9.0 | 15.0 | 26.0 | 91.8 |
| Penta3 | 29980 | 28.0 | 55.0 | 194.0 | 51.0 |
| MR1 | 28084 | 26.0 | 47.0 | 89.0 | 54.6 |

## F-D4

![F-D4_weekly_demand_stockouts.png](F-D4_weekly_demand_stockouts.png)

| facility | antigen | weeks | stockout_weeks | requested_doses | administered_doses | unmet_doses |
|---|---|---|---|---|---|---|
| SYN-D02 | PENTA | 104 | 10 | 901 | 858 | 43 |
| SYN-D02 | MR | 104 | 21 | 545 | 488 | 57 |
| SYN-S02 | PENTA | 104 | 8 | 4730 | 4553 | 177 |
| SYN-S02 | MR | 104 | 21 | 2851 | 2482 | 369 |

## F-D5

![F-D5_stock_vs_minimum.png](F-D5_stock_vs_minimum.png)

| facility | antigen | weeks_below_minimum | stockout_weeks | disruption_weeks | median_closing_doses |
|---|---|---|---|---|---|
| SYN-H02 | OPV | 114 | 22 | 8 | 90.5 |
| SYN-H02 | MR | 126 | 52 | 6 | 40.0 |

## F-D6

![F-D6_registry_by_facility.png](F-D6_registry_by_facility.png)

| facility_code | name | keph_level | registered_children |
|---|---|---|---|
| SYN-D04 | Kasanga Dispensary | Dispensary | 1543 |
| SYN-D03 | Mugathi Dispensary | Dispensary | 1332 |
| SYN-D01 | Olomani Dispensary | Dispensary | 1132 |
| SYN-D02 | Chimani Dispensary | Dispensary | 924 |
| SYN-D05 | Gamani Dispensary | Dispensary | 736 |
| SYN-H02 | Semani Health Centre | Health centre | 3700 |
| SYN-H01 | Ndotamu Health Centre | Health centre | 3002 |
| SYN-H03 | Chinyeri Health Centre | Health centre | 2693 |
| SYN-H04 | Watamu Health Centre | Health centre | 2264 |
| SYN-S01 | Kirura Sub-County Hospital | Sub-county hospital | 6873 |
| SYN-S03 | Nyatamu Sub-County Hospital | Sub-county hospital | 6035 |
| SYN-S02 | Nyabiru Sub-County Hospital | Sub-county hospital | 5306 |

## F-D7

![F-D7_import_defects.png](F-D7_import_defects.png)

| file | defect | rows | share_of_file_pct |
|---|---|---|---|
| immunizations | DUPLICATE_ROW | 17 | 2.8 |
| immunizations | MALFORMED_DATE | 14 | 2.3 |
| immunizations | MISSING_CHILD_ID | 14 | 2.3 |
| immunizations | DATE_BEFORE_BIRTH | 13 | 2.1 |
| immunizations | UNKNOWN_DOSE | 13 | 2.1 |
| immunizations | UNKNOWN_FACILITY | 11 | 1.8 |
| immunizations | FUTURE_DATE | 8 | 1.3 |
| stock | NON_NUMERIC_QUANTITY | 11 | 5.5 |
| stock | UNKNOWN_ANTIGEN | 9 | 4.5 |
| stock | NEGATIVE_RECEIPT | 6 | 3.0 |
| stock | MALFORMED_DATE | 4 | 2.0 |

## F-D8

![F-D8_penta3_by_subgroup.png](F-D8_penta3_by_subgroup.png)

| group | category | n | simulated_penta3_pct | kdhs_2022_pct | difference_pp |
|---|---|---|---|---|---|
| education | none | 534 | 80.3 | 73.0 | 7.3 |
| education | primary | 1987 | 89.8 | 90.6 | -0.8 |
| education | secondary | 1866 | 89.4 | 90.6 | -1.2 |
| education | higher | 922 | 89.8 | 92.6 | -2.8 |
| wealth | lowest | 1235 | 86.0 | 85.1 | 0.9 |
| wealth | second | 989 | 92.1 | 92.3 | -0.2 |
| wealth | middle | 876 | 86.1 | 88.8 | -2.7 |
| wealth | fourth | 1010 | 88.6 | 90.0 | -1.4 |
| wealth | highest | 1199 | 90.7 | 90.4 | 0.3 |
| birth_order | 1 | 1648 | 90.0 | 92.0 | -2.0 |
| birth_order | 2-3 | 2038 | 89.1 | 89.0 | 0.1 |
| birth_order | 4-5 | 1058 | 88.6 | 88.9 | -0.3 |
| birth_order | 6+ | 565 | 83.9 | 82.5 | 1.4 |
