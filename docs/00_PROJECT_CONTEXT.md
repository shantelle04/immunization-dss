# 00. Project context

| Item | Value |
|---|---|
| Title | A Web-Based Decision Support System for Healthcare Workers to Address Childhood Immunization Gaps through Predictive Analytics and Smart Scheduling |
| Author | Muthomi, Shantelle Nkatha, adm. 168873, BBIT 4D |
| Supervisor | Mr. Titus Tunduny |
| Institution | School of Computing and Engineering Sciences, Strathmore University |
| Proposal | Draft 4, June 2026 (`docs/reference/proposal_draft_4.docx`, text in `proposal.md`). Turnitin overall similarity 11% (embedded report page) |
| Proposal Gantt | Design Aug to Sep; data collection and preparation Sep; model training Sep to Oct; testing Oct to early Nov; demonstration Nov 2026 |
| Work in this repo starts | 2026-09-28 |

## 1. Objectives to deliverables (traceability)

| Obj | Specific objective (proposal 1.3.2) | Research question | Deliverable that answers it | Thesis location |
|---|---|---|---|---|
| i | Examine operational challenges (inventory, scheduling, records) | RQ i | Literature (done in proposal ch. 2) plus data profiling findings (dropout, timeliness, stock patterns) | Ch. 2, Ch. 4.2 |
| ii | Review forecasting, scheduling, and record standards | RQ ii | Literature (ch. 2.5) plus model comparison (baselines, ARIMA, GRU) and FHIR mapping | Ch. 2, Ch. 5 |
| iii | Design a user-friendly interface | RQ iii | Requirements (FR/NFR), UML set, ERD, wireframes | Ch. 4 |
| iv | Develop the DSS with the three modules | RQ iv | Working system, tagged prototypes p1, p2, p3, v1.0 | Ch. 5.2 |
| v | Test against usability, accuracy, functionality | RQ v | Test log, backtest metrics, oracle tests, performance runs, SUS/UAT results | Ch. 5.4, 5.5 |

## 2. The three modules

| Module | Inputs | Processing | Output (dashboard) |
|---|---|---|---|
| M1 Predictive inventory | Stock ledger, doses administered history, scheduled receipts | Weekly demand forecast per antigen, 4-week horizon (GRU, ARIMA fallback, baselines); projected stock vs safety minimum | Inventory dashboard: stock, forecast chart with interval, reorder and stock-out alerts |
| M2 Scheduling and defaulters | Child registry, immunization history (M3), KEPI schedule, stock forecast (M1) | Due dates, defaulter rule, priority ranking, session plan with vaccine quantities | Scheduling dashboard: prioritised defaulter list, outreach plan, vaccines needed vs stock |
| M3 Health passport | Registration, immunization events | FHIR R4 Patient and Immunization resources from relational tables; cross-facility lookup | Child record interface: register, record dose, search, view history, export |

## 3. Data position (short)

Fully synthetic (D-02). A seeded simulator generates 5 years of operations for 12 fictional facilities: children, visits, doses, sessions, stock ledger. Its behaviour is calibrated so that simulated coverage matches the Kenya DHS 2022 Key Indicators Report, Table 11, within 3 points for every dose (achieved 2.5 in evidence run sim-seed42-368707d3). The simulator also produces ground truth (true demand, stock-out weeks, dropout) for measuring accuracy, and import files with planted defects for measuring data cleaning. Details: `docs/04_DATA_PIPELINE.md`.

## 4. Stack (from proposal 3.5)

React.js, Django REST Framework, PostgreSQL, Python (pandas, scikit-learn, statsmodels, Keras on TensorFlow), JWT with three roles, Git and GitHub with tagged prototypes, Trello for the backlog, VS Code. Testing: Python unit tests, Jest, integration, performance (dashboard under 3 s), UAT.

## 5. Document map

| Doc | Purpose |
|---|---|
| `01_MASTER_PLAN.md` | Phases, gates, dates |
| `02_REQUIREMENTS_AND_SCOPE.md` | FR and NFR IDs, business rules |
| `03_ARCHITECTURE_AND_DATA.md` | Architecture, data model, API, roles |
| `04_DATA_PIPELINE.md` | Datasets, acquisition, cleaning rules, simulator |
| `05_MODELS_AND_EVALUATION.md` | Models, metrics, test strategy |
| `06_DOCUMENTATION_PLAN.md` | Chapters 4 to 6 evidence map, diagram list |
| `07_DECISIONS_RISKS.md` | Decisions D-xx, risks R-xx, open questions |
| `08_SETUP_AND_GIT.md` | Machine setup, SSH key, GitHub, hooks |
| `09_PROPOSAL_ISSUES.md` | Defects found in draft 4 for the author to fix |
| `10_ENGINEERING_RULES.md` | Scope, data, security, conventions, model and testing rules |
| `progress/PROGRESS_TRACKER.md` | Living status by phase, first person, for the supervisor |
| `logs/` | As-executed logs |
