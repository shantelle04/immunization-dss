# 07. Decisions, risks, open questions

Status values: `Proposed` (recommendation, awaiting the author), `Decided`, `Supervisor` (needs supervisor sign-off), `Superseded`.

## 1. Decisions

| ID | Decision | Recommendation | Status |
|---|---|---|---|
| D-01 | Reference context | Kenya, KEPI schedule, children under 2 | Decided by author 2026-09-28 |
| D-02 | Data strategy | **Fully synthetic** seeded dataset, behaviour calibrated to KDHS 2022 Key Indicators Report Table 11 (public). No microdata requested (DHS access too slow for the timeline). Disclosed in Ch. 5.3 and limitations | Decided by author 2026-09-28; supervisor to confirm |
| D-03 | Facility sample | 12 fictional facilities in "Synthetic County" (5 dispensaries, 4 health centres, 3 sub-county hospitals); fictional names so no real facility is implied | Decided |
| D-04 | Granularity | Weekly series, 5 years of stock history (2021 to 2025) plus 2 years of earlier child history, 4-week horizon | Decided |
| D-05 | Frontend language | React with TypeScript (still React.js per proposal; catches errors earlier). TypeScript pinned to 5.x because ts-jest 29 cannot run on TypeScript 7 | Decided by author 2026-09-28 |
| D-06 | Frontend tests | Jest with React Testing Library, as named in the proposal (skeleton test passes 2026-09-28) | Decided by author 2026-09-28 |
| D-07 | Operational meaning of ">95% accuracy" | As in doc 05 section 4 | Proposed, Supervisor |
| D-08 | Defaulter definition | A due dose not received 28 days after its due date (grace days configurable). Kenya MoH 2013 guidelines (p60) require identifying defaulters from the register but give no time threshold (`docs/logs/SOURCE_CHECKS.md` section 4), so 28 days is the author's operational definition (ASSUMPTION) | Decided by author 2026-09-28 |
| D-09 | SMART Health Card export (signed JWS, QR) | Stretch goal after p2; FHIR R4 JSON export is the committed deliverable | Proposed |
| D-10 | Offline capability (proposal 3.7) | Read-only PWA cache of the last loaded dashboards; queued offline writes only if time allows | Proposed |
| D-11 | Risk score | Optional tie-breaker trained on the synthetic registry's visit history (not on hidden truth); the proposal's priority rule stays primary | Proposed |
| D-12 | UAT participants and ethics | 5 to 8 participants (healthcare workers or clinical students); confirm whether Strathmore ethics review is needed (VERIFY with supervisor) | Supervisor |
| D-13 | Scheduling of forecast runs | Django management command via cron; no Celery | Proposed |
| D-14 | GRU training location | Local CPU (small data); Google Colab only if runs exceed 30 minutes | Proposed |
| D-15 | Repository | Private repo `github.com/shantelle04/immunization-dss`, remote over SSH (`git@github.com:shantelle04/immunization-dss.git`), key `id_ed25519_168873`, assistant guides never committed; docs committed since D-28. SSH authentication confirmed by the author 2026-09-28; nothing pushed yet | Decided |
| D-16 | Real dates | Demo date, Chapter 4 to 6 deadlines, next supervisor meeting | Open (author) |
| D-17 | AI-use disclosure | What the university policy requires | Open (author) |
| D-18 | Vaccine wastage realism | Applied: BCG and MR given only at Tuesday static sessions at dispensaries and health centres (80% of deferred children return), 5% per-session discard of open-vial-policy multi-dose vials, calibration `engine_refinements` 2 to 3. Result (`docs/evidence/D-18_D-19_before_after.md`): wastage BCG 85.9 to 79.2%, MR 62.6 to 46.3%, OPV 0 to 5.5%, IPV 0 to 4.2%, PCV 0 to 1.1%; cost: Penta1 to MR1 dropout at health centres 17.1% (overall 11.3%), MR1 coverage -2.8 pp. WHO indicative wastage rates not yet checked (VERIFY). Follow-up in D-23 | Decided by author 2026-09-28 |
| D-19 | Subgroup effect strength | Applied: `effect_shrink` 0.6 to 0.8. Result: no-education Penta3 82.2 to 80.3% (KDHS 73.0), birth order 6+ 86.5 to 83.9% (82.5); remaining gap stated as a limitation (factors drawn independently) | Decided by author 2026-09-28 |
| D-20 | Local database runtime | PostgreSQL 16 in Docker Compose (`docker-compose.yml`), host port 127.0.0.1:5433 (5432 is taken on the dev machine), separate app and test roles created from `.env` on first start; one cross-platform runner `scripts/dev.py` for Linux and Windows. The machine's native PostgreSQL 16 cluster is not used | Decided by author 2026-09-28 |
| D-21 | Forecast fallback for short history | Proposal says "ARIMA fallback for facilities with no history"; ARIMA cannot fit without history. Rule: GRU when at least 104 weeks and it beats B1; else SARIMA; under 26 weeks, population-based estimate (catchment births x schedule x coverage) (doc 05 section 1) | Proposed |
| D-22 | EDA figure set | Eight figures F-D1 to F-D8 (doc 04 section 8 plus F-D8 Penta3 by subgroup vs KDHS, evidence for D-19) | Decided by author 2026-09-28 |
| D-23 | D-18 follow-up | Against WHO indicative wastage rates (WHO 2019 concept note, Table 1): BCG 79.2% vs 50% (above), MR 46.4% vs 40% (close), OPV 5.8% vs 25%, IPV 4.6% vs 10%, PCV 1.3% vs 10%, single-dose about 0.3% vs 5% (below; expected, since the simulator covers facility level only and indicative rates are planning figures). Options: (a) accept and state; (b) also batch BCG at sub-county hospitals, to bring BCG toward the 50% planning figure; (c) raise the deferred-return probability or exempt MR at health centres, to reduce the Penta1 to MR1 dropout (17.1%). Chosen: (b) only, because BCG is the one value clearly out of line with WHO; MR kept as is (within 6.4 points of 40%). Implemented as `sessions.batching.levels_by_antigen` (BCG: all three levels; MR: dispensary and health centre). Calibration method changed with it (D-26). Result (run `sim-seed42-368707d3`, `docs/evidence/D-23_D-26_before_after.md`): BCG wastage 79.2 to 65.8% (WHO 50%), BCG unmet doses 1,649 to 1,108, BCG within 28 days 72.6 to 65.0%, MR unchanged (46.1%) | Decided by author 2026-09-28 ("proceed as an expert": recommendation accepted) |
| D-24 | BCG upper age | Kenya MoH 2013 (p30): BCG "at birth and up to 59 months"; `sim.yaml` uses 365 days. Recommendation: keep 365 days in the simulator (project scope is children under 2 and catch-up after 1 year is rare), but make the app's schedule table use the KEPI value when seeded in Phase 3 | Decided by author 2026-09-28 (recommendation accepted) |
| D-25 | PCV open-vial policy | `sim.yaml` treats 4-dose PCV10 as reusable (open-vial policy); Kenya MoH 2013 (p23) says PCV10 "should be discarded after 6 hours from the time a vial is opened". The text may predate the 4-dose preserved presentation. Recommendation: ask the supervisor or a KEPI contact for current practice (VERIFY); until then keep the config and state it | Decided by author 2026-09-28 (keep and state; supervisor question added) |
| D-26 | Second-stage calibration method | Fixed refinement counts failed or passed by chance: 3 undamped rounds left OPV3 at -3.1 pp (run `sim-seed42-deca88d9`, FAIL); 6 undamped rounds oscillated 3.1, 3.3, 3.6, 2.4 pp (run `sim-seed42-cce5aedc`, passed but rejected). Method: damped re-fit steps (`engine_damping` 0.6, as stage 1 uses 0.5), stop once every dose is within `engine_target_pp` 1.5 (half the V-10 tolerance), at most `engine_refinements` 8. Result (run `sim-seed42-368707d3`): 12.4, 6.5, 5.1, 5.9, 3.9, 2.4, 2.9, 2.6, 2.5 pp; the 1.5 target was not reached. MR1 is at a ceiling set by batching (attendance logit 5.27, give probability 1.0), so the stall is structural; V-10 passes (2.5 pp). Tested in `analytics/tests/test_calibrate.py` | Decided by Claude as the technical method under the author's "proceed as an expert"; author to confirm |
| D-27 | Diagram tool | PlantUML sources in `docs/diagrams/*.puml`, rendered to SVG and PNG in `docs/evidence/` by `dev.py diagrams` through the `plantuml/plantuml` Docker image (no local Java). Mermaid kept only for markdown sketches in docs. Faculty guide suggests StarUML or Visual Paradigm "for consistency": ask the supervisor whether generated diagrams are acceptable | Decided by author 2026-09-28 |
| D-28 | Project notes in the repository | `docs/` is versioned in the main repository so the project can be set up from one clone. Excluded: assistant guides, the assistance log and copies of third-party reference documents (kept local, backed up); `pr_*.md`. Committed files contain no machine-specific paths. Engineering rules published as doc 10 and cited instead of the local rules file. Hooks moved to `scripts/hooks/` (versioned, no tool names) and enabled by `core.hooksPath` | Decided by author 2026-09-28 |

## 2. Risks

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-01 | Panel questions the realism of fully synthetic data | Medium | Medium | Calibration table against KDHS 2022, published sources for every non-assumption, validation report, WHO and MoH source checks, assumptions list in defence notes |
| R-02 | Circularity: models evaluated on the simulator's own data | High | Medium | Calibrate on real data, hidden noise and shocks, baselines, optional D5 external check, state as a limitation |
| R-03 | GRU does not beat SARIMA on short weekly series | Medium | Low | Expected and reportable; selection logic handles it |
| R-04 | Schedule already behind the proposal Gantt (design due September) | High | High | Design and data in parallel in W1 to W2; weekly progress report to supervisor |
| R-05 | UAT participants or ethics clearance unavailable | Medium | High | Ask supervisor now; fallback to structured expert walkthrough plus SUS with peers, disclosed |
| R-06 | Scope creep (offline sync, SMART Health Cards, SMS) | Medium | Medium | Scope guard in doc 10; stretch items only after p2 |
| R-07 | Local-only files lost (reference PDFs, assistant files, local exclude list) | Low | Medium | Notes are versioned in the repository since D-28; the remaining local-only files are archived weekly (doc 08 section 5) |
| R-08 | Supervisor expects real secondary datasets (proposal 3.3) | Medium | Medium | Raise D-02 at the next meeting with the calibration evidence; fallback: add open WHO/UNICEF coverage series as a context chart only |

## 3. Open questions for the supervisor

1. Is the fully synthetic data approach in D-02 (seeded simulator calibrated to KDHS 2022 Table 11) acceptable in place of the secondary datasets named in proposal 3.3?
2. Is the operational definition of ">95% accuracy" in D-07 acceptable?
3. Does UAT with healthcare workers need ethics clearance, and can the supervisor suggest a facility or group (D-12)?
4. What are the exact dates for the system demonstration and the Chapter 4 to 6 submissions?
5. In current Kenyan practice, may an opened 4-dose PCV10 vial be used in later sessions (open-vial policy), or is it discarded after 6 hours as the 2013 guidelines state (D-25)?
6. Are diagrams generated with PlantUML acceptable, or should they be redrawn in StarUML or Visual Paradigm (D-27)?
