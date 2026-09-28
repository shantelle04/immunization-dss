# 02. Requirements and scope (v1, frozen for gate G2 on 2026-09-28)

Method (proposal 3.3, as updated by D-02): profiling of the synthetic, KDHS-calibrated dataset (`docs/04_DATA_PIPELINE.md`, EDA in `docs/evidence/EDA_sim-seed42-368707d3.md`) and a desk review of the KEPI guidelines, WHO wastage guidance and the proposal (`docs/logs/SOURCE_CHECKS.md`). Requirements are revisited after each prototype evaluation (proposal 3.2).

**Status values.** `Frozen`: ID, wording and evidence fixed for Phase 3; later changes need a logged decision. `PROVISIONAL`: depends on an open decision or unverified fact (named in the row).

**Authoritative wording.** Where the proposal is inconsistent, 2.5.2 is used for the defaulter ranking (3.8.2 is garbled, doc 09 P-06) and 3.8.3 plus D-10 for the passport (central store with a read cache, doc 09 P-04).

## 1. Actors

| Actor | Scope | Source |
|---|---|---|
| Healthcare worker (HCW) | Own facility: register children, record doses and stock transactions; read forecasts, alerts, defaulter lists and session plans; search children across facilities (FR-32) | Proposal 3.8.4 |
| Facility manager (FM) | Own facility: everything an HCW can do, plus plan outreach sessions, configure stock policy, acknowledge alerts, import CSV files, read the facility audit log | Proposal 3.8.4 |
| System administrator (SA) | Users, facilities and the vaccine schedule; no clinical data by default | Proposal 3.8.4; doc 10 section 3 |
| Scheduler (system actor) | Runs `run_forecasts` on a timetable (cron, D-13) | Proposal 3.8.4 ("scheduled background process") |

## 2. Functional requirements

| ID | Requirement | Module | Evidence | Priority | Status |
|---|---|---|---|---|---|
| FR-01 | Users log in with username and password and log out; there is no self-registration | Core | Proposal 3.8.4; doc 10 section 3 | Must | Frozen |
| FR-02 | Access is limited by role and facility; a child record from another facility is readable only through FR-32 | Core | Proposal 3.8.4, 3.8.3 | Must | Frozen |
| FR-03 | SA manages users, facilities and the vaccine schedule (antigen, dose, recommended, minimum and maximum age, minimum interval) | Core | Proposal 3.8.4; KEPI desk review (SOURCE_CHECKS 3) | Must | Frozen |
| FR-10 | Record stock transactions per antigen and lot: opening balance, receipt, issue, wastage, loss, adjustment | M1 | Proposal 3.3 (inventory data structures); dataset `stock_transactions.csv` kinds | Must | Frozen |
| FR-11 | Show current stock per antigen, derived from transactions, with weeks of stock remaining | M1 | Proposal 2.6, 3.8.1 | Must | Frozen |
| FR-12 | Show a 4-week weekly demand forecast per antigen with an 80% interval and the model used | M1 | Proposal 2.5.1, 3.8.1; doc 05 section 1 | Must | Frozen |
| FR-13 | Raise a stock-out alert when projected stock falls below the safety minimum (BR-05) before the next replenishment; FM can acknowledge it | M1 | Proposal 2.5.1, 3.8.1; F-D4, F-D5 | Must | Frozen |
| FR-14 | Configure per facility and antigen the replenishment cycle and safety buffer used by BR-05 | M1 | Proposal 2.5.1 ("average session size and replenishment lead time") | Must | Frozen |
| FR-15 | Show forecast accuracy from the latest backtest per antigen | M1 | Objective v | Should | Frozen |
| FR-16 | Choose the forecast model per series by the D-21 rule (GRU, SARIMA, population estimate) | M1 | Proposal 2.5.1; D-21 | Must | PROVISIONAL (D-21) |
| FR-20 | Compute each child's due, overdue and closed doses from the schedule (BR-01 to BR-03) | M2 | Proposal 2.5.2 | Must | Frozen |
| FR-21 | Classify a child as a defaulter when at least one dose is overdue by more than 28 days (BR-02) | M2 | Proposal 2.5.2; D-08; KE-MOH-2013 p60 | Must | Frozen |
| FR-22 | Rank defaulters: most missed doses first, then nearest to an antigen's maximum age (BR-04) | M2 | Proposal 2.5.2 | Must | Frozen |
| FR-23 | Generate an outreach session plan: children in rank order up to capacity, doses and vaccine quantities needed, and shortfalls against current stock and forecast | M2 | Proposal 2.5.2 (three inputs), 3.8.2 | Must | Frozen |
| FR-24 | Record session attendance and the doses given, updating the child record and the stock ledger | M2 | Proposal 2.6, 3.8.2; activity diagram | Must | Frozen |
| FR-25 | Show a risk score per defaulter as a tie-breaker | M2 | Proposal 3.2.2; D-11 | Could | PROVISIONAL (D-11) |
| FR-30 | Register a child (names, sex, date of birth, caregiver, facility) with a unique system ID | M3 | Proposal 3.8.3 | Must | Frozen |
| FR-31 | Record an immunization event (dose, date, facility, lot, recorded by) with schedule validation (BR-01, BR-03, BR-06) | M3 | Proposal 3.8.3 | Must | Frozen |
| FR-32 | Search a child by system ID, or by name plus date of birth, across facilities; every cross-facility read is audited | M3 | Proposal 3.8.3 | Must | Frozen |
| FR-33 | Show the full immunization history and the next due doses | M3 | Proposal 3.8.3 | Must | Frozen |
| FR-34 | Export a child record as a FHIR R4 Bundle (Patient plus Immunization resources) | M3 | Proposal 2.5.3, 3.8.3 | Should | Frozen |
| FR-35 | Export a signed SMART Health Card | M3 | Proposal 2.5.3; D-09 | Could | PROVISIONAL (D-09) |
| FR-36 | Warn about a likely duplicate registration (same family name and date of birth at the facility) and show the existing records before creating a new one | M3 | Planted duplicate defects (F-D7); data quality for FR-32 | Should | Frozen |
| FR-40 | Bulk CSV import of immunization and stock rows with a dry run and a per-row error report | Core | Proposal 3.2.2 (ingestion errors); F-D7 | Should | Frozen |
| FR-41 | Audit log of who created, changed or read (cross-facility) clinical and stock records | Core | Kenya Data Protection Act, 2019; doc 10 section 2 | Must | Frozen |
| FR-42 | Read-only offline view of the last loaded dashboards | Core | Proposal 3.7; D-10 | Should | PROVISIONAL (D-10) |

## 3. Non-functional requirements

| ID | Requirement | Measure | Evidence | Status |
|---|---|---|---|---|
| NFR-01 | Performance | Dashboard data loads in under 3 s at the 95th percentile with 12 facilities and the full evidence dataset | Proposal 3.6 | Frozen |
| NFR-02 | Forecast run time | `run_forecasts` for all facilities finishes in under 10 minutes on the development machine | Proposal 3.6 ("acceptable processing window"); 10 minutes is an ASSUMPTION | PROVISIONAL (threshold) |
| NFR-03 | Security | Role and facility checks server-side and fail-closed, Argon2 hashing, login lockout, JWT with HttpOnly refresh cookie, security headers, startup secret validation | Proposal 3.5.2, 3.8.4; doc 10 section 3 | Frozen |
| NFR-04 | Privacy | Synthetic data only; data minimisation (no phone numbers); no identifiers in logs; `truth/` never loaded | Proposal 1.7; D-02; Kenya Data Protection Act, 2019 | Frozen |
| NFR-05 | Usability | SUS score at least 68 in UAT; core tasks completed without help | Proposal abstract, objective v; Brooke (1996) | PROVISIONAL (D-12) |
| NFR-06 | Compatibility | Current Chrome, Firefox, Edge; 360 px to desktop | Proposal 3.7 | Frozen |
| NFR-07 | Accessibility | Keyboard navigation, labelled inputs, a table alternative for every chart, colour-blind-safe palette | doc 10 section 4 | Frozen |
| NFR-08 | Data validation | Rejects impossible dates, unknown codes, negative stock, duplicate doses; measured against the import answer key | F-D7; doc 10 section 2 | Frozen |
| NFR-09 | Interoperability | FHIR R4 export validates against the base specification | Proposal 2.5.3 | Frozen |
| NFR-10 | Accuracy | Stock alerts and defaulter categorisation per D-07 | Proposal 3.2.3; D-07 | PROVISIONAL (D-07, supervisor) |
| NFR-11 | Reproducibility | Every data, training and backtest run has a manifest (seed, hashes, commit) and a results-ledger entry | doc 10 sections 2, 4 | Frozen |

## 4. Business rules

| ID | Rule | Source | Status |
|---|---|---|---|
| BR-01 | A dose is due from its recommended age; it may be given from its minimum age and not before the minimum interval after the previous dose of the same antigen | KEPI schedule (section 5) | Frozen |
| BR-02 | A due dose is overdue once today is more than 28 days after its recommended date (configurable grace days) | D-08; KE-MOH-2013 p60 (no threshold given) | Frozen |
| BR-03 | A dose past its antigen's maximum age is closed ("missed, not recoverable"): never scheduled, counted as missed, not as overdue | KEPI; D-24 (BCG up to 59 months, KE-MOH-2013 p30); rotavirus limit VERIFY | Frozen (rotavirus value PROVISIONAL) |
| BR-04 | Defaulter rank: number of overdue doses (descending), then days until the nearest maximum age among overdue doses (ascending), then system ID | Proposal 2.5.2 | Frozen |
| BR-05 | Safety minimum = average doses per session x sessions until the next replenishment x (1 + buffer), per facility and antigen | Proposal 2.5.1 | Frozen |
| BR-06 | A child can receive each scheduled dose at most once; stock can never go negative (issues beyond stock are rejected) | Validation checks V-03, V-07 | Frozen |
| BR-07 | Opened vials of vaccines without an open-vial policy are wasted at the end of the session; policy vaccines may be reused for up to 4 weeks | KE-MOH-2013 p28; PCV open question D-25 | Frozen (PCV PROVISIONAL) |
| BR-08 | A child record from another facility is readable only through FR-32 (exact system ID, or name plus date of birth), read-only, and audited; writes stay limited to the user's own facility | Proposal 3.8.3; doc 10 section 3 | Frozen |

## 5. KEPI schedule used by the system

| Age | Doses | Source status |
|---|---|---|
| Birth | BCG, OPV0 | BCG: KE-MOH-2013 p30. OPV0 timing: KDHS 2022 KIR 3.10 (doc 04) |
| 6 weeks | OPV1, Penta1, PCV1, Rota1 | Penta: KE-MOH-2013 Hib section ("6, 10 & 14 weeks"); others KDHS 2022 KIR 3.10 |
| 10 weeks | OPV2, Penta2, PCV2, Rota2 | As above |
| 14 weeks | OPV3, Penta3, PCV3, IPV | As above |
| 9 months | MR1 | KE-MOH-2013 measles section ("9 months of age") |
| 18 months | MR2 | KDHS 2022 KIR 3.10 (doc 04) |

Out of scope: vitamin A (not a vaccine), yellow fever (designated counties only), HPV and campaigns (doc 10 section 1). Maximum ages other than BCG and vial sizes other than BCG: VERIFY (SOURCE_CHECKS 2 and 3).

## 6. Traceability

`docs/diagrams/traceability.md` maps every FR to its use case, diagrams, owning Django app and planned test IDs.
