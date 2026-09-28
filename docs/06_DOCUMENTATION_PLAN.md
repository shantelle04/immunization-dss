# 06. Documentation plan (Chapters 4 to 6)

Structure follows the faculty guides in `docs/reference/faculty/` (Lec 6 Chapter 4, Lec 9 Chapters 5 and 6). The author writes all chapter text; this file maps each section to its evidence.

## 1. Chapter 4: System Analysis and Design

| Section | Evidence source | Status |
|---|---|---|
| 4.1 Introduction | n/a | [ ] |
| 4.2 Requirements gathering (data profiling, desk review) | doc 02 v1 method paragraph; EDA (F-D1 to F-D8); `docs/logs/SOURCE_CHECKS.md` (KEPI, WHO) | [ ] |
| 4.2.1 Functional requirements | doc 02 section 2 (FR-01 to FR-42, frozen or PROVISIONAL), grouped by module as the faculty guide's listing format asks | [ ] |
| 4.2.2 Non-functional requirements | doc 02 section 3 (NFR-01 to NFR-11), each with how it is achieved | [ ] |
| 4.3 Analysis diagrams: use case, sequence x3, activity | F-UC, F-SQ1, F-SQ2, F-SQ3, F-AC (`docs/evidence/`) | [ ] |
| 4.4 Design diagrams: class, ERD, logical database schema, architecture, wireframes | F-CL, F-ERD, F-LDS, F-AR, `docs/wireframes/index.html` (screenshots F-WF1 to F-WF4 to capture) | [ ] |

Page layout: F-CL (2.8:1) and F-SQ1 (1.8:1) need landscape pages; F-ERD, F-LDS and F-AC are portrait. SVG versions stay sharp at any size in Word. The logical database schema (F-LDS) is not in proposal 3.4 but is required by the faculty Chapter 4 guide.

## 2. Chapter 5: Implementation and Testing

| Section | Evidence source | Status |
|---|---|---|
| 5.2.1 Hardware | Dev machine spec (`lscpu`, RAM) logged in IMPLEMENTATION_RUN_LOG | [ ] |
| 5.2.2 Software | Pinned versions from requirements and package-lock | [ ] |
| 5.3 Description of the dataset | doc 04 sections 2, 4, 6; DATA_CLEANING_LOG; EDA figures | [ ] |
| 5.4.1 ML testing (backtests, metrics) | doc 05; TRAINING_RUN_LOG | [ ] |
| 5.4.2 Testing paradigm (unit, integration, system, security, performance, UAT) | doc 05 section 5; TEST_LOG | [ ] |
| 5.5 Testing results | TEST_LOG, EVAL tables, SUS results, screenshots | [ ] |

## 3. Chapter 6: Conclusions, Recommendations, Future Work (1 page max)

Future work candidates: KHIS/DHIS2 integration, real facility pilot, SMS reminders, native mobile, full offline sync.

## 4. Figure and screenshot capture list (capture as you go)

| ID | What | When |
|---|---|---|
| F-D1..D8, T-5.1 | EDA figures and dataset description (doc 04 section 8); `docs/evidence/EDA_sim-seed42-368707d3.md` (earlier runs archived in `docs/evidence/archive_*/`) | Phase 1 (regenerated 2026-09-28 after D-23, D-26) |
| F-UC, F-CL, F-SQ1..3, F-AC, F-AR, F-ERD, F-LDS | Diagrams (`dev.py diagrams`, PlantUML D-27) | Phase 2 (drafted 2026-09-28) |
| F-WF1..4 | Wireframe screenshots: login, inventory, scheduling, child record | Phase 2 (author to capture) |
| F-UI-INV, F-UI-SCH, F-UI-CHD, F-UI-LOGIN | Dashboard screenshots | p1, updated at p3 |
| F-M1 | Forecast vs actual chart per model | Phase 4 |
| F-M2 | Backtest comparison table | Phase 4 |
| F-T1 | Test run summaries | Phase 5 |
| F-P1 | Locust performance chart | Phase 5 |
| F-UAT | SUS score distribution | Phase 6 |

## 5. Formatting

Times New Roman 12, 1.5 spacing, justified, APA 7th, table captions above and figure captions below, chapter-based numbering, past tense for Chapters 4 to 6, no em dashes.
