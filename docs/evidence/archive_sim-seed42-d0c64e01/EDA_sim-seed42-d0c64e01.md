# EDA evidence: sim-seed42-d0c64e01

Generated 2026-09-28 by `immdss eda`. Run seed 42, config hash `d0c64e01`, git commit `uncommitted`. Validation: PASS. Each figure is followed by its data table (table alternative and evidence).

## T-5.1 Dataset description

| folder | file | rows | columns | column_names | content | use |
|---|---|---|---|---|---|---|
| app | antigens.csv | 7 | 4 | antigen_code, name, doses_per_vial, open_vial_policy | Vaccines, vial size, open-vial policy | Loaded by the application |
| app | children.csv | 35,529 | 10 | child_id, system_id, given_name, family_name, sex, date_of_birth, caregiver_name, registration_facility_code, registered_on, is_synthetic | Registered children (synthetic names, no phone numbers) | Loaded by the application |
| app | facilities.csv | 12 | 7 | facility_code, name, keph_level, ownership, county, sub_county, is_synthetic | Fictional facilities and their KEPH level | Loaded by the application |
| app | immunization_events.csv | 500,128 | 10 | event_id, child_id, dose_code, antigen_code, dose_number, given_on, facility_code, session_id, lot_number, is_synthetic | Doses given: child, dose, date, facility, session, lot | Loaded by the application |
| app | schedule.csv | 16 | 8 | dose_code, antigen_code, dose_number, contact, recommended_age_days, min_age_days, max_age_days, min_interval_days | KEPI dose rules: recommended, minimum and maximum age, minimum interval | Loaded by the application |
| app | sessions.csv | 17,724 | 5 | session_id, facility_code, date, kind, location_name | Fixed and outreach immunization sessions | Loaded by the application |
| app | stock_transactions.csv | 102,412 | 9 | transaction_id, date, facility_code, antigen_code, lot_number, kind, quantity_doses, session_id, is_synthetic | Stock ledger: opening balances, receipts, issues, wastage, losses | Loaded by the application |
| app | vaccine_lots.csv | 5,769 | 3 | lot_number, antigen_code, first_received | Vaccine lots and first receipt date | Loaded by the application |
| imports | import_dirty_truth.csv | 120 | 3 | file, row_index, defect | Answer key: row and defect type for every planted defect | Import-cleaning test only |
| imports | import_immunizations_dirty.csv | 617 | 6 | child_system_id, date_of_birth, dose_code, given_on, facility_code, lot_number | Immunization import sample with planted defects | Import-cleaning test only |
| imports | import_stock_dirty.csv | 200 | 6 | date, facility_code, antigen_code, lot_number, kind, quantity_doses | Stock import sample with planted defects | Import-cleaning test only |
| truth | children_truth.csv | 36,431 | 16 | child_id, home_facility_code, date_of_birth, sex, education, wealth, birth_order, residence, attends_outreach, risk_log_odds, entered_care, first_contact, dropout_after_contact, moved_to_facility_code, move_from_contact, registered | Every child born (including never-registered zero-dose children), background, dropout | Evaluation only, never loaded |
| truth | stockout_turned_away.csv | 21,103 | 4 | child_id, dose_code, date, facility_code | Every dose refused because of a stock-out | Evaluation only, never loaded |
| truth | weekly_stock.csv | 21,840 | 14 | facility_code, antigen_code, week_start, opening_doses, receipts_doses, requested_doses, administered_doses, unmet_doses, vials_opened, wastage_doses, loss_doses, in_disruption, closing_doses, stockout | Facility x antigen x week: true demand, administered, unmet, wastage, stock-out flag | Evaluation only, never loaded |

## F-D1

![F-D1_calibration_vs_kdhs2022.png](F-D1_calibration_vs_kdhs2022.png)

| indicator | cohort_size | simulated_pct | kdhs_2022_pct | difference_pp |
|---|---|---|---|---|
| BCG | 5309 | 97.7 | 96.9 | 0.8 |
| OPV0 | 5309 | 87.4 | 86.1 | 1.3 |
| OPV1 | 5309 | 97.1 | 96.5 | 0.6 |
| OPV2 | 5309 | 95.1 | 94.2 | 0.9 |
| OPV3 | 5309 | 78.7 | 78.2 | 0.5 |
| Penta1 | 5309 | 97.1 | 97.1 | 0.0 |
| Penta2 | 5309 | 94.8 | 93.9 | 0.9 |
| Penta3 | 5309 | 88.1 | 89.2 | -1.1 |
| PCV1 | 5309 | 97.0 | 96.5 | 0.5 |
| PCV2 | 5309 | 95.3 | 95.4 | -0.1 |
| PCV3 | 5309 | 90.0 | 91.2 | -1.2 |
| Rota1 | 5309 | 95.7 | 96.0 | -0.3 |
| Rota2 | 5309 | 90.9 | 92.3 | -1.4 |
| IPV | 5309 | 87.9 | 87.4 | 0.5 |
| MR1 | 5309 | 87.6 | 89.0 | -1.4 |
| MR2 | 5225 | 65.9 | 66.8 | -0.9 |
| Zero-dose | 5309 | 2.1 | 2.1 | 0.0 |

## F-D2

![F-D2_dropout_by_level.png](F-D2_dropout_by_level.png)

| facility_level | registered_12_23m | penta1 | penta3 | mr1 | dropout_penta1_penta3_pct | dropout_penta1_mr1_pct |
|---|---|---|---|---|---|---|
| Dispensary | 815 | 804 | 720 | 734 | 10.4 | 8.7 |
| Health centre | 1761 | 1749 | 1580 | 1572 | 9.7 | 10.1 |
| Sub-county hospital | 2620 | 2602 | 2379 | 2347 | 8.6 | 9.8 |
| All facilities | 5196 | 5155 | 4679 | 4653 | 9.2 | 9.7 |

## F-D3

![F-D3_timeliness.png](F-D3_timeliness.png)

| dose | doses_given | median_days_late | p75_days_late | p90_days_late | within_28_days_pct |
|---|---|---|---|---|---|
| BCG | 35349 | 3.0 | 8.0 | 53.0 | 79.0 |
| Penta1 | 34572 | 9.0 | 16.0 | 26.0 | 91.9 |
| Penta3 | 30069 | 28.0 | 51.0 | 192.0 | 51.7 |
| MR1 | 28250 | 25.0 | 43.0 | 73.0 | 56.9 |

## F-D4

![F-D4_weekly_demand_stockouts.png](F-D4_weekly_demand_stockouts.png)

| facility | antigen | weeks | stockout_weeks | requested_doses | administered_doses | unmet_doses |
|---|---|---|---|---|---|---|
| SYN-D02 | PENTA | 104 | 24 | 964 | 809 | 155 |
| SYN-D02 | MR | 104 | 22 | 552 | 500 | 52 |
| SYN-S01 | PENTA | 104 | 15 | 6331 | 5739 | 592 |
| SYN-S01 | MR | 104 | 21 | 3466 | 3134 | 332 |

## F-D5

![F-D5_stock_vs_minimum.png](F-D5_stock_vs_minimum.png)

| facility | antigen | weeks_below_minimum | stockout_weeks | disruption_weeks | median_closing_doses |
|---|---|---|---|---|---|
| SYN-H03 | OPV | 113 | 23 | 8 | 61.0 |
| SYN-H03 | MR | 125 | 38 | 6 | 80.0 |

## F-D6

![F-D6_registry_by_facility.png](F-D6_registry_by_facility.png)

| facility_code | name | keph_level | registered_children |
|---|---|---|---|
| SYN-D04 | Kasanga Dispensary | Dispensary | 1545 |
| SYN-D03 | Mugathi Dispensary | Dispensary | 1332 |
| SYN-D01 | Olomani Dispensary | Dispensary | 1131 |
| SYN-D02 | Chimani Dispensary | Dispensary | 924 |
| SYN-D05 | Gamani Dispensary | Dispensary | 737 |
| SYN-H02 | Semani Health Centre | Health centre | 3700 |
| SYN-H01 | Ndotamu Health Centre | Health centre | 2999 |
| SYN-H03 | Chinyeri Health Centre | Health centre | 2687 |
| SYN-H04 | Watamu Health Centre | Health centre | 2262 |
| SYN-S01 | Kirura Sub-County Hospital | Sub-county hospital | 6874 |
| SYN-S03 | Nyatamu Sub-County Hospital | Sub-county hospital | 6035 |
| SYN-S02 | Nyabiru Sub-County Hospital | Sub-county hospital | 5303 |

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
| education | none | 534 | 82.2 | 73.0 | 9.2 |
| education | primary | 1987 | 89.0 | 90.6 | -1.6 |
| education | secondary | 1866 | 88.3 | 90.6 | -2.3 |
| education | higher | 922 | 89.5 | 92.6 | -3.1 |
| wealth | lowest | 1235 | 87.0 | 85.1 | 1.9 |
| wealth | second | 989 | 91.0 | 92.3 | -1.3 |
| wealth | middle | 876 | 85.8 | 88.8 | -3.0 |
| wealth | fourth | 1010 | 88.1 | 90.0 | -1.9 |
| wealth | highest | 1199 | 88.6 | 90.4 | -1.8 |
| birth_order | 1 | 1648 | 89.3 | 92.0 | -2.7 |
| birth_order | 2-3 | 2038 | 87.5 | 89.0 | -1.5 |
| birth_order | 4-5 | 1058 | 88.5 | 88.9 | -0.4 |
| birth_order | 6+ | 565 | 86.5 | 82.5 | 4.0 |
