# Defence notes

Per phase: what was built, why, alternatives considered, weaknesses, and likely panel questions with answers.

## Phase 4b: Prototype 2 (2026-10-02)

**What was built.** Forecasts and stock-out alerts inside the system, outreach session plans and attendance, FHIR R4 export, administrator screens, and a mobile-first interface. Until the Colab models are imported, the app forecasts with the better of the two baselines per series (D-39).

**The alert rule (D-38).** Stock minus the forecast's upper bound, week by week until the expected delivery, compared with a safety minimum that shrinks as the delivery approaches. The forecast predicts doses given, but stock also falls by discarded vial remainders (a 20-dose BCG vial opened for three children), so the forecast is scaled by the ledger's own ratio of doses leaving stock to doses given. Without that factor recall was 0.66; with it 0.914.

**Results, stated as they are.** Alert recall 0.914 against a 0.95 target, precision 0.586. The defaulter list matched an independent oracle for all 10,390 children under 2.

**Alternatives.** Alerting on weeks of stock left only (no forecast; cannot see seasonal peaks); a lower buffer for fewer alerts (recall barely changes, precision falls: sensitivity table, doc 05 section 6); storing data on the device for offline use (rejected for privacy, D-37).

**Weaknesses.** Recall below target; a late delivery is treated as "nothing arrives in the next 4 weeks", which over-alerts when the delivery comes the next day. Baselines only until Colab runs.

**Likely questions**
1. Why is your alert accuracy below 95%? (It is measured against simulator truth with the baseline forecasts. Recall is lowest for OPV (0.818) and PCV (0.864) and highest for MR (0.978); why those series are missed is VERIFY (inspect `alert_decisions.csv`). The trained models may change it; both results will be reported.)
2. How do you know the defaulter list is right? (An independent script re-implements the rule with whole-column operations from the raw files and agrees on every child.)
3. Can a facility manager see another facility's alerts or sessions? (No: every query is filtered by the user's facility; tests show a 404 for another facility's alert and session.)
4. Does the app store patient data on the phone? (No: only the app's code is cached; data on screen is kept in memory and cleared when the tab closes.)

## Phase 4a: forecasting pipeline, built but not yet trained (2026-09-29)

**What was built.** The code that turns the stock ledger into weekly series and compares four ways of forecasting them, plus one Colab notebook that runs every stage from data generation to the final models. Nothing has been trained: training runs only on Colab (D-14) and the commands refuse to fit a model anywhere else.

**The series.** One per facility and vaccine (84), weekly doses issued from 4 January 2021 (260 weeks). Only the issues a clinic records are used; `truth/` is never read to build them. A week without issues is 0, and a week in which the ledger balance hit zero is flagged, because issues in that week understate demand (a child turned away is not an issue).

**The comparison.** Seasonal naive (same week last year) and a 4-week moving average are the baselines any model must beat; SARIMA and a GRU are the candidates. Each is refitted at 6 cut-offs and forecasts the 4 weeks after each, so 24 weeks are scored and no test week is ever seen in training. MASE compares a model's error with the seasonal naive error on the training weeks: below 1 means the model is better than the simple rule.

**Selection (D-21).** Per series: the GRU if it has at least 104 training weeks and beats seasonal naive; otherwise SARIMA; otherwise the better baseline.

**Alternatives.** A single train and test split (one lucky or unlucky test period decides everything); training on the laptop (too little memory for TensorFlow, and the author ruled it out); SARIMA with a seasonal term at lag 52 (correct but slow for 84 series at 6 cut-offs, so seasonality is modelled with Fourier terms, D-36).

**Weaknesses.** The data is simulated, so a model can learn the simulator's rules (R-02). Stock-out weeks censor demand; the bias against true demand is reported separately rather than hidden.

**Likely questions**
1. How do you know there is no leakage? (Every cut-off asserts that the last training week is before the first test week; scaling uses training weeks only; a test checks the cut-offs.)
2. Why a global GRU instead of 84 small ones? (84 series of 260 weeks are short; one model shared across facilities and vaccines sees about 19,000 training windows instead of about 230.)
3. Can someone reproduce your result? (Open the notebook in Colab at the tagged commit; it regenerates the identical data, checks every hash against `analytics/configs/evidence_hashes.json`, and records the git commit, seed, library versions and GPU in the manifest.)

## Phase 0: project skeleton and safe setup (2026-09-28)

**What was built.** Three empty but working parts, each with a test: the analytics package (already had the data generator; now also the `immdss eda` command), a Django backend, and a React app. The database runs in Docker so the same setup works on Linux and Windows. One helper, `scripts/dev.py`, runs every common task with the same command on any operating system.

**The startup check (`backend/config/preflight.py`).** Before Django does anything, it checks that every secret it needs is set, long enough, and not the placeholder copied from `.env.example`. If any check fails, it stops with a list of what to fix and never prints the secret itself. Why: a system that starts with a weak or default password is insecure without anyone noticing. Refusing to start makes the mistake visible straight away (fail closed).

**Two database roles.** The application connects as one PostgreSQL user and the tests as another. The test user can create and drop its own test database; the application user cannot. Why: separate credentials limit the damage if one leaks, and a test run can never touch the real data.

**Docker instead of installing PostgreSQL.** A single file (`docker-compose.yml`) gives the same PostgreSQL 16 on every machine. Port 5433 is used because 5432 was already taken on the development laptop. The container also refuses to set itself up with placeholder passwords.

**Alternatives.** A native PostgreSQL install (different on each operating system, harder for a panel or examiner to reproduce); SQLite for development (differs from production PostgreSQL, so bugs can hide).

**Likely questions**
1. What happens if someone forgets to set the secret key? (Django refuses to start and names the missing setting; test TC-SEC-01 proves it, 17 tests in `backend/tests/test_preflight.py`.)
2. Why not ship a default password for convenience? (A default that works is a real password that everyone knows. The example file only contains values that are rejected.)
3. How would an examiner run your system? (Install Python, Node and Docker, then follow the README quick start: setup, copy `.env.example`, db-up, test.)

## Phase 2: requirements and design (2026-09-28)

**What was produced.** A frozen requirements list (doc 02 v1: 26 functional and 11 non-functional requirements, 8 business rules), nine diagrams drawn from text sources with PlantUML (F-UC, F-CL, F-SQ1 to F-SQ3, F-AC, F-AR, F-ERD, F-LDS), a data dictionary, a traceability matrix from every requirement to its diagrams and planned tests, and low-fidelity wireframes of the four main screens.

**How each diagram answers a question.**

| Diagram | The question it answers | One-sentence explanation |
|---|---|---|
| F-UC use case | Who can do what? | Three human roles plus a nightly scheduler; a facility manager can do everything a health worker can, plus planning, configuration and imports; the administrator has no clinical access. |
| F-SQ1 | How does a stock-out alert appear? | Each night the forecast command reads what was issued, forecasts four weeks, and raises an alert where projected stock falls below the safety minimum; the dashboard only reads the results, after the login and facility checks. |
| F-SQ2 | How is the outreach list built? | Each child's doses are classified (given, due, overdue after 28 days, closed at the age limit), defaulters are ranked by the proposal's rule, and the plan compares doses needed with stock. |
| F-SQ3 | How does a record follow a child? | Facility A registers the child; facility B finds it by system ID, reads it without changing it, and the read is logged. |
| F-AC | What does a session day look like? | One flow that crosses all three modules: plan, check stock, find or register, vaccinate if due and in stock, record, discard opened vials, close. |
| F-AR | How is the system built? | Three tiers: React in the browser, Django REST API with a security layer, PostgreSQL; forecasts run in a separate package through a narrow interface; evaluation data never enters the database. |
| F-CL | What are the building blocks? | Entities grouped by Django app plus services that hold the rules, so views stay thin and rules are testable. |
| F-ERD, F-LDS | How is data stored? | 18 tables; the stock balance is calculated from the ledger, never typed in; one child cannot receive the same dose twice (database constraint). |

**Why text-based diagrams (D-27).** They are version-controlled, regenerated with one command, and the ERD, schema and data dictionary are generated from one file, so they cannot contradict each other or the database built in Phase 3.

**Likely questions**
1. Why is the defaulter list not stored in a table? (It changes every day and after every dose; computing it from the records avoids stale data. Stored results would need their own update logic and could disagree with the records.)
2. Why can a health worker see a child from another facility? (The passport's purpose is cross-facility retrieval (proposal 3.8.3); it is limited to exact search, read-only, and every such read is logged.)
3. Why is there no stock balance column? (A balance that is only ever the sum of recorded transactions cannot drift from the ledger; this is also what the data generator's check V-04 proves.)
4. How do you know the design covers the requirements? (The traceability matrix maps each FR to a use case, diagrams and planned tests.)
5. What did you add beyond the proposal? (A logical database schema, required by the faculty guide; a duplicate-registration warning (FR-36); an audit log for data protection.)

## Phase 1b: what each EDA figure shows (2026-09-28, evidence run after D-23 and D-26)

Source: evidence run `sim-seed42-368707d3` (validation 11/11, reproduces byte for byte); tables in `docs/evidence/EDA_sim-seed42-368707d3.md`. Before and after: `docs/evidence/D-18_D-19_before_after.md`, `docs/evidence/D-23_D-26_before_after.md`.

| Figure | In plain language | What to say if asked |
|---|---|---|
| F-D1 calibration | For each of the 16 doses, a diamond (simulated) sits next to a circle (KDHS 2022). All are within the 3-point limit; the largest gaps are MR1 (-2.5) and OPV3 (-2.0). | Proves the simulated population vaccinates at Kenya's published rates. Coverage counts all children born, including those who never came, as the survey does. MR1 is lowest because MR is given on one day a week at smaller facilities and some children sent to that day never come back. |
| F-D2 dropout | Of registered children aged 12 to 23 months who got Penta1, 9.2% never got Penta3 and 11.0% never got MR1. Health centres lose the most between Penta1 and MR1 (16.2%). | KDHS national totals give (97.1 - 89.2) / 97.1 = 8.1% and (97.1 - 89.0) / 97.1 = 8.3%. Penta1 to Penta3 is close; Penta1 to MR1 is higher, which is the cost of the MR vaccine day. It is exactly the problem the defaulter list in Module 2 targets. |
| F-D3 timeliness | Each line shows how many doses had been given by a given number of days after the recommended age. Penta1 is prompt (median 9 days late, 92.6% within 28 days). Penta3 and MR1 are slower (medians 27 and 26 days; about half within 28 days). BCG climbs to about 65% within ten days, stays flat, and jumps again at about day 45: babies who missed the weekly BCG day get it at their 6-week visit. | Delays add up across visits, so later doses are later. Penta3 has a long tail (10% given more than 192 days late): VERIFY against a published Kenyan timeliness figure before calling it realistic. The 28-day line is the defaulter grace period (D-08). |
| F-D4 weekly demand | Blue is what the clinic records as given; orange is how many children actually needed the vaccine. In shaded weeks the vaccine had run out, so blue drops while orange stays up. Example: sub-county hospital SYN-S03, MR, last 104 weeks: 3,295 doses needed, 2,792 given, 503 turned away (15%). | This is "censored demand": a model trained only on what was given underestimates need after stock-outs. The system only sees blue; orange exists only in the evaluation data, which is how forecast bias after stock-outs can be measured. |
| F-D5 stock vs minimum | Stock rises when the monthly delivery arrives and falls as it is used (a sawtooth). Grey bands are the two planned supply disruptions (OPV 2022, MR 2024); red bands are stock-out weeks. At health centre SYN-H01, closing stock was below two weeks of use in 119 (OPV) and 109 (MR) of 260 weeks, with 27 and 35 stock-out weeks. | The situation the stock-out alert must detect in advance. |
| F-D6 registry | Children registered per facility: sub-county hospitals 18,209, health centres 11,652, dispensaries 5,664 (total 35,525). | Workload differs a lot by level, so forecasts and plans are per facility. |
| F-D7 import defects | The import files contain 120 deliberately broken rows: 90 of 617 immunization rows and 30 of 200 stock rows (about 15%), across 11 defect types. | The answer key used to score the system's CSV import in Phase 3. |
| F-D8 subgroups | Penta3 coverage by mother's education, wealth and birth order, simulated vs KDHS. Most groups are within 3 points; the no-education group is 5.5 points too high (78.5% vs 73.0%; it was 9.2 before D-19). | The three factors are drawn independently, so group gaps stay weaker than in real data. National totals are unaffected. Stated as a limitation. |

**D-18, D-19, D-23 and D-26 in one paragraph for the panel.** Two things looked unrealistic, so I changed the generator (never the data) and regenerated with the same seed. Vaccines whose opened vial must be thrown away after the session (BCG, measles-rubella) are given on one day a week, as clinics do to save doses: MR at dispensaries and health centres, BCG at every level after comparing with WHO's planning figures. Reusable vials are occasionally discarded too. Subgroup effects were made stronger. Matching the KDHS again needed a better tuning method: fixed tuning rounds either missed (OPV3 3.1 points off) or passed by chance (the error swung up and down), so the tuning now takes smaller steps and stops once close enough. The accepted run passes all 11 checks and reproduces byte for byte. Its honest costs: MR1 stays 2.5 points below KDHS because some children sent to the MR day never return, BCG is given later, and BCG wastage (66%) is still above WHO's 50% planning figure.

**Likely questions**
1. Why did your tuning not reach its 1.5-point target? (MR1 has a ceiling: its visit attendance is already about 99.5% and every attending child is offered MR, so the only loss left comes from children who do not return on the MR day and from stock-outs. No tuning knob can remove that; the last four tuning rounds stayed between 2.4 and 2.9 points, inside the 3-point check.)
2. Is it cheating to keep tuning until it passes? (The first undamped attempt that passed was rejected because it passed by chance. The method, not a count, was changed, it is tested, and both failed runs are logged.)

## Checking the data against WHO and Kenyan guidance (2026-09-28)

**What was checked.** Vaccine wastage in the simulated data was compared with WHO's indicative wastage rates, using WHO's own formula (doses wasted, including unopened losses, divided by doses supplied). Vial sizes, open-vial rules and age limits were compared with the Kenya MoH National Policy Guidelines on Immunization (2013). Details and page numbers: `docs/logs/SOURCE_CHECKS.md`.

**Result in plain language.** Measles-rubella wastage (46%) is close to WHO's planning figure (40%). BCG (79%) is well above WHO's figure (50%), because a 20-dose vial is opened for a handful of babies. Vaccines in single-dose or reusable vials waste less than WHO's planning figures, which is expected: those figures are deliberately generous planning allowances covering the whole supply chain, while the simulator covers only the facility. The Kenyan guidelines confirm the BCG vial size and which vaccines may be reused. They give no fixed number of days for calling a child a defaulter, so 28 days is my own operational choice.

**Likely questions**
1. Is your wastage realistic? (MR matches WHO's planning figure; BCG is higher, which I state; D-23 decides whether to reduce it.)
2. Why is wastage for Penta almost zero? (Single-dose vials cannot waste unused doses; only losses of unopened stock count, and WHO's 5% is a planning allowance, not a measurement.)
3. Where does 28 days for a defaulter come from? (Kenyan guidelines require tracing defaulters but set no threshold; 28 days is my configurable choice, D-08.)

## Assumptions list (every ASSUMPTION in `analytics/configs/sim.yaml`, for panel preparation)

| Setting | Value | Why | If it were wrong |
|---|---|---|---|
| `start_date` | 2021-01-04 | First Monday, gives a clean weekly calendar | None for results; dates only shift |
| `weeks` | 260 (5 years) | Every series has well over the 104 weeks the GRU rule needs (D-21) | Fewer weeks: GRU could not be selected for most series |
| `warmup_weeks` | 104 | Children of every age already exist on day one of the stock window | Too short: early weeks would have too few older children and too little demand |
| facilities and `births_per_week` | 12 facilities, 2.0 to 18.0 births per week | Plausible spread across KEPH levels | Different volumes change forecast difficulty (small series are noisier), not the method |
| `sessions.fixed_days` | Dispensary Tue and Thu; health centres and hospitals Mon to Fri | Smaller facilities run fewer static days | Affects wastage of multi-dose vials (D-18) and waiting time |
| `sessions.outreach_per_month` | 1, 2, 1 by level | One or two outreach sessions a month is a typical pattern | Changes how far-away children are reached; dropout shifts |
| `far_share` | rural 0.30, urban 0.05 | Rural children live further from the facility | Changes outreach demand and dropout by residence |
| `outreach_window_days` | 10 | A far child uses an outreach session within this window | Timeliness for far children shifts |
| `sessions.batching` (D-18) | BCG and MR only on Tuesday static sessions at dispensaries and health centres; 80% of deferred children return that day | A 20-dose BCG or 10-dose MR vial is discarded after the session, so grouping children on one day cuts wastage | Too strict: more missed opportunities and lower coverage (calibration compensates); too loose: wastage stays high |
| `birth_growth_per_year` | 0.02 | Slow population growth | Trend in demand; the forecasts must follow it |
| `birth_seasonal_amplitude` | 0.05 | Mild seasonality in births | Seasonal models gain or lose value |
| `mobility_share` | 0.05 | Some children move to another facility once | Tests cross-facility record retrieval (Module 3); too low would hide that need |
| `effect_shrink` | 0.8 (was 0.6, D-19) | Subgroup effects are shrunk because the factors are drawn independently | Subgroup gaps too weak (0.6) or too strong: D-19 |
| `first_contact_at_birth` | 0.90 | Most vaccinated children start at birth (BCG, OPV0) | Changes BCG and OPV0 timing and coverage; calibration compensates |
| `timeliness` delays | Median 1 to 30 days by contact, lognormal sigma 0.8, risk factor 0.5, rainy months x1.3 | Later contacts slip more; rains make travel harder | F-D3 shapes change; the defaulter list size changes |
| `stock.cycle_weeks` | 4 | Monthly replenishment from the sub-county store | Stock-out frequency changes |
| `stock.lead_time_weeks` | 0, 1 or 2 | Delivery delay varies | Longer delays mean more stock-outs |
| `stock.max_stock_weeks` | 6 | Order up to six weeks of use | Higher: fewer stock-outs, more wastage from expiry |
| `stock.min_stock_weeks` | 2 | Emergency order trigger | Also used as the minimum line in F-D5 |
| `stock.monthly_loss_rate` | 0.003 | Breakage, expiry and cold-chain loss of unopened stock | Small effect on stock levels |
| `stock.open_vial_discard_probability` (D-18) | 0.05 per session, multi-dose open-vial-policy vaccines (OPV, PCV, IPV) | Even reusable vials are sometimes discarded (contamination, vaccine vial monitor, cold chain) | Zero would keep their wastage unrealistically at 0% |
| `stock.return_after_stockout` | 0.6 | A child turned away by a stock-out usually returns within 1 to 3 weeks | Higher dropout if lower |
| `stock.disruptions` | OPV weeks 70 to 77 at 30% fill; MR weeks 180 to 185 at 20% fill | Positive cases for the alert evaluation | Without them, alerts would have too few serious events to measure |

Values in the config without an explicit label (they are modelling choices and should be treated as ASSUMPTION): `emergency_fill_probability` 0.5, `delivery_skip_probability` 0.04, `delivery_partial_probability` 0.08, `partial_fill_rate` 0.5, the calibration settings (`cohort_size`, `iterations`, `damping`, `engine_refinements`), and `dirty_import.rows` 600 and `defect_share` 0.15. Vial sizes, open-vial policy and age limits are marked VERIFY against current KEPI guidance.

## Phase 1: synthetic data generator (2026-09-28)

**What was built.** A program that creates five years of realistic immunization clinic records for 12 fictional facilities: children, visits, vaccines given, sessions, and every stock movement. The same seed always produces the same files.

**How realism is achieved.** The program is tuned so that, for children aged 12 to 23 months, the share who received each vaccine matches the Kenya DHS 2022 Key Indicators Report, Table 11. It gets within 1.4 percentage points for all 16 doses. Differences between children of mothers with different education, wealth and birth order also come from that table.

**How it works, simply.** Each child is born at a facility. Each child has a chance of never coming (2% in Kenya), of stopping after a visit, and of coming late (later in the rainy months). At each visit the nurse gives every vaccine that is due, if it is in stock. Stock arrives monthly, sometimes late, short, or not at all, and there are two supply disruptions (OPV and MR). If a vaccine runs out, the child comes back later or waits for the next visit.

**Why it helps the evaluation.** The program knows the truth: which weeks really ran out of stock and how many children were really turned away. So the stock-out alerts and the defaulter list can be scored exactly. The truth is kept in a separate folder that the system never reads.

**Checks.** Eleven automatic checks: stock always adds up, never negative, no vaccine given too early, too late, twice or out of order, every file matches its fingerprint (hash), coverage matches the KDHS. The first full run failed three checks, which found two real bugs that were then fixed. That is the checks doing their job.

**Likely questions**
1. Why not real data? (Facility stock and child records are in national systems that are not public; the DHS microdata request takes too long; real child records need ethics approval. Proposal 1.7 already states simulated data.)
2. How do you know it is realistic? (Calibration table against KDHS 2022, and the validation report.)
3. Is it circular to test your models on data you generated? (Partly. The models only see what a real system would see, never the hidden rules or truth. Results are compared with simple baselines, and the limitation is stated.)
4. Which numbers did you choose yourself? (Every one marked ASSUMPTION in the config, for example vial sizes, delivery delays, disruptions. Each is listed with its reason.)
5. What are the weaknesses? (Differences between groups are weaker than in the KDHS, and BCG and MR wastage are very high. Both are logged as D-18 and D-19.)

## Planning (2026-09-28)

**Why simulated operations data?** Facility-level weekly vaccine stock and consumption for Kenya sit in the national LMIS and KHIS, which are not public. The project uses real public data (WUENIC, KMHFL, KDHS 2022) to calibrate a simulator, which also provides known ground truth for measuring alert and defaulter accuracy.

**Likely questions**
1. How do you know the simulator is realistic? (Calibration targets and validation checks in doc 04 section 5; KDHS reproduction check.)
2. Is it circular to test models on simulated data? (Yes, partly; mitigations and the limitation statement in doc 07 R-02.)
3. What does 95% accuracy mean in your system? (D-07.)
