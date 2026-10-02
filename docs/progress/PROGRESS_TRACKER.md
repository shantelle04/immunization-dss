---
title: "Project Progress Report"
subtitle: "A Web-Based Decision Support System for Healthcare Workers to Address Childhood Immunization Gaps through Predictive Analytics and Smart Scheduling"
author: "Muthomi, Shantelle Nkatha (168873), BBIT 4D. Supervisor: Mr. Titus Tunduny"
date: "Status as of 2 October 2026"
---

# 1. Summary

My proposal is complete (draft 4), and I have moved into building the system. I have set up the project repository and a full execution plan that follows the four evolutionary prototyping phases in my Chapter 3, broken into eight working phases, each with a clear completion check.

The main progress this week is the data. Requesting real survey microdata would have taken longer than my timeline allows, so, in line with my limitations section (1.7), I have built a **seeded synthetic dataset** for the whole project. It is calibrated so that its vaccination coverage matches Kenya's official figures from the Kenya Demographic and Health Survey 2022. The dataset is generated, it passes all 11 automatic quality checks, and anyone can regenerate the identical dataset from the same settings in about two minutes.

Since the last update I have also frozen my requirements and drafted all the design diagrams and screen sketches from my proposal (section 5, Phase 2), so design is back on the September timeline of my Gantt chart, subject to your review.

I have also built the first prototype ahead of plan: login with the three roles, the database loaded with the synthetic data, and first versions of the inventory, scheduling and child record screens, with 194 automated tests passing. I have also built the second prototype: the system now shows a 4-week vaccine demand forecast with stock-out alerts, plans outreach sessions from the prioritised defaulter list, records attendance, and exports a child's record in the FHIR standard. The screens were redesigned to work on phones first. I trained and compared the forecasting models on Google Colab with a GPU: the GRU neural network was the most accurate (MASE 0.677), just ahead of SARIMA (0.681), and both clearly beat the two simple baselines. The trained forecasts are now used in the system. The stock-out alerts caught 84.3% of true stock-out weeks with the trained models (91.4% with the baselines), below my 95% target; I report this as it is and explain the cause below. The project is in my GitHub repository, which I have made public so that Colab can use it; it holds no real data, secrets or passwords.

# 2. Have I started cleaning the datasets?

Yes, and the data stage is largely done. I decided to use fully synthetic data instead of waiting for access to real survey records. In this project, data cleaning covers two things:

1. **Checking the generated data.** Every run is checked automatically before I use it. The first full run failed three of the checks, which exposed two errors in my generator: some children received the same dose twice, and coverage for the second measles-rubella dose was 5 points too low. I fixed both, and the current dataset passes all 11 checks (Table 2).
2. **The system cleaning incoming data.** The generator also produces import files with deliberate errors planted in about 15% of rows (duplicates, dates before birth, future dates, unknown vaccine codes, missing child IDs, badly formatted dates, negative stock quantities), with an answer key. When I build the import feature, I will measure what percentage of each error type my system catches. This matches "data ingestion errors" in my Phase 2 methodology (3.2.2).

Section 3 explains why I chose synthetic data.

**Table 1: The synthetic dataset (seed 42, run sim-seed42-368707d3)**

| Content | Size |
|---|---|
| Facilities (fictional: 5 dispensaries, 4 health centres, 3 sub-county hospitals) | 12 |
| Period | 2021 to 2025 stock records, plus two earlier years of child history |
| Registered children | 35,525 |
| Vaccination records | 499,839 |
| Immunization sessions (fixed and outreach) | 17,724 |
| Stock transactions (receipts, issues, wastage, losses) | 84,941 |
| Weekly stock series (facility x vaccine x week), with the true stock-out weeks | 21,840 |

**How it matches Kenya's figures:** for children aged 12 to 23 months, the share who received each vaccine is within 2.5 percentage points of the KDHS 2022 Key Indicators Report, Table 11, for all 16 doses (the allowed limit is 3). For example: Penta1 97.2% (KDHS 97.1%), Penta3 88.2% (89.2%), OPV3 76.2% (78.2%), MR1 86.5% (89.0%), MR2 66.3% (66.8%), children with no vaccinations 2.1% (2.1%).

**Table 2: Automatic quality checks (all passed)**

| Check | Result |
|---|---|
| Every file matches its recorded fingerprint (hash) | 16 of 16 |
| Stock adds up every week (opening + received - used - wasted = closing) | 0 errors in 21,840 weeks |
| Stock never negative | 0 |
| Stock ledger equals final balance | 0 difference |
| No vaccine given before or after the allowed age | 0 |
| Minimum 4-week gap between doses respected | 0 |
| No child given the same dose twice | 0 |
| Doses given in order | 0 |
| Every vaccination belongs to a registered child | 0 |
| Coverage within 3 points of KDHS 2022 | Largest gap 2.5 points (MR1) |
| Stock-outs present (needed to test the alerts) | 2,290 facility-vaccine-weeks |

**Two weaknesses I found and changed (decisions D-18 and D-19):** the gap in coverage between children of mothers with and without education was smaller than in the KDHS, and wastage for BCG and measles-rubella vials was very high, because a 20-dose BCG vial was opened for one to three children at small clinics. I made subgroup differences stronger, and at dispensaries and health centres BCG and measles-rubella are now given on one day per week. After checking against WHO planning figures, I also moved BCG to one day a week at sub-county hospitals. Results (full before and after tables in my evidence folder): the no-education group moved from 82.2% to 78.5% (KDHS 73.0%); measles-rubella wastage fell from 62.6% to 46.1% (WHO planning figure 40%) and BCG from 85.9% to 65.8% (WHO 50%). The costs, which I report as limitations: the largest coverage gap grew from 1.4 to 2.5 points (measles-rubella 1, which the one-day-a-week rule holds below the KDHS figure), fewer children at health centres go on from Penta1 to measles-rubella 1 (dropout 16.2%), and BCG is given later (65% within 28 days, against 79% before).

# 3. Why I chose synthetic data

I considered three options: requesting the Kenya DHS 2022 survey microdata, using open national coverage data (WHO/UNICEF estimates), or generating a synthetic dataset calibrated to published figures. I chose the third, for these reasons.

1. **The data my system needs is not public.** My forecasting module needs weekly vaccine stock and consumption for each facility, and my scheduling and passport modules need individual child vaccination records. In Kenya this data sits in the national health information systems (KHIS and the logistics system), which require official access. The DHS survey has child vaccination histories but no stock data at all, and the WHO/UNICEF estimates are one national figure per year, which cannot train a weekly forecasting model.
2. **Time.** DHS microdata requires registration and an approval that can take days to weeks, followed by substantial cleaning. My Gantt chart put data preparation in September and model training from mid October, so waiting for approval would have delayed every later phase.
3. **Privacy and ethics.** Real child health records are sensitive personal data under the Kenya Data Protection Act, 2019, and using them would need ethics approval. My proposal already commits to this in section 1.7: "only simulated patient data will be used for development and testing".
4. **Measurable accuracy.** Because I generate the data, I also know the truth: which weeks really ran out of stock, how many children were really turned away, and which children really dropped out. This lets me measure exactly how accurate my stock-out alerts and defaulter lists are, which real records could not tell me. My proposal's target of more than 95% accuracy can only be checked against a known truth.
5. **Control of scenarios.** I can include situations the system must handle, such as supply disruptions, late deliveries, children moving between facilities, and import files with planted errors, and I can regenerate the identical dataset at any time from the same seed.

**How I keep it realistic:** the dataset is not invented freely. The share of children receiving each vaccine is tuned to match the official KDHS 2022 Key Indicators Report (Table 11), which is public, within 2.5 percentage points for all 16 doses. The mix of mothers' education, wealth and birth order also comes from that table, and the vaccination schedule comes from the Kenya Expanded Programme on Immunization as described in the same report. Every other setting, such as vial sizes or delivery delays, is written down as an assumption with its reason.

**Limitation I will state in my report:** the models are tested on data produced by rules I designed, not on real clinic records. To reduce this, the models only see what a real system would see (clinic records), never the hidden truth, and I compare them against simple baseline methods. Testing on real facility data is recommended as future work.

# 4. How I generated the data and where it is stored

**How it is generated.** I wrote a data generator as a Python package in my repository (`analytics/`). One command, `python3 scripts/dev.py simulate`, runs it with a fixed random seed (42), so the same settings always produce exactly the same dataset. All settings are in one file, `analytics/configs/sim.yaml`, where every value is marked either PUBLISHED (with its source, mainly the KDHS 2022 Key Indicators Report, Table 11, and the Ministry of Health immunization guidelines) or ASSUMPTION (with my reason). The generator works in these steps:

**Table 3: Steps of the data generator**

| Step | What happens |
|---|---|
| 1. Population | 12 fictional facilities (5 dispensaries, 4 health centres, 3 sub-county hospitals). Children are born every week from January 2019, each with a sex, mother's education, wealth quintile and birth order in the KDHS 2022 proportions |
| 2. Behaviour | Each child gets a chance of never starting vaccination, of dropping out after a visit, and of arriving late (more often in the rainy months) |
| 3. Calibration | A quick simulation of 40,000 children is repeated, adjusting these chances until coverage for all 16 doses matches KDHS 2022 |
| 4. Clinic and stock simulation | Session by session from 2019 to 29 December 2025: children attend, due doses are given only if vaccine is in stock, monthly deliveries arrive (sometimes late, short or missing), two supply disruptions occur, and opened vials are discarded under the open-vial rules. The full simulation is then re-checked against KDHS and corrected in small steps until every dose is within 1.5 points or 8 rounds are used |
| 5. Broken import files | Two CSV files with about 15% deliberately wrong rows, plus an answer key, to test my import checks |
| 6. Output and checks | The files are written with a manifest (row count and a SHA-256 fingerprint of every file, the seed and the settings), then the 11 checks in Table 2 run automatically. A run that fails any check cannot be loaded into the system |

It takes about two minutes on one processor core of my laptop. If nothing has changed, the command recognises the existing dataset and finishes in about a second instead of regenerating it.

**Where it is stored.** Each run gets its own folder named after its seed and settings. The dataset I use is `data/synthetic/sim-seed42-368707d3/` (53 MB). It is kept only on my laptop and is not uploaded to GitHub, because anyone can rebuild it byte for byte from the repository, and the fingerprints prove the rebuild is identical. The folder has three parts:

**Table 4: What the dataset folder contains and who may use it**

| Part | Contents | Used for |
|---|---|---|
| `app/` | Facilities, vaccine schedule, 35,525 registered children, 499,839 vaccination records, 17,724 sessions, 84,941 stock transactions, vaccine lots | The only part loaded into the system's database; also the only input for training the forecasting models |
| `truth/` | What really happened: true weekly demand and stock-out weeks, all 36,431 children born (including those never registered), doses refused because of stock-outs | Only for scoring the accuracy of my forecasts, alerts and defaulter lists. Never loaded into the system and never given to a model |
| `imports/` | The two broken CSV files and their answer key | Measuring how many planted errors my import feature catches |

The `app/` part is loaded into the system's PostgreSQL 16 database, which runs in Docker on my laptop (`python3 scripts/dev.py load`, about 60 seconds). For model training, Google Colab regenerates the same dataset from the public repository and checks every fingerprint against the reference file `analytics/configs/evidence_hashes.json`, so no data is ever uploaded. The full step-by-step description is in `docs/12_DATA_TO_TRAINING_PIPELINE.md` in my repository.

# 5. User roles and what each can access

My proposal (section 3.8.4) defines three roles. I have added two rules: every user is limited to their own facility, and the system administrator does not see clinical data. There is no self-registration; the administrator creates every account.

**Table 5: Roles and access in Prototype 1 (every row is checked by an automated test for every role)**

| What | Health worker | Facility manager | System administrator |
|---|---|---|---|
| Proposal definition | Read and write child records and stock data; read forecasts and session plans | Full access to all modules and facility configuration | User management and system configuration |
| Log in, log out, own profile | Yes | Yes | Yes |
| List and register children | Own facility | Own facility | No |
| Search children and view a child's record from another facility (health passport) | Read only, and each view is logged | Read only, and each view is logged | No |
| Record a vaccination | Own facility | Own facility | No |
| View the vaccine schedule | Yes | Yes | No |
| View stock balances and record stock transactions | Own facility | Own facility | No |
| View the defaulter list | Own facility | Own facility | No |
| Immunization sessions | View | View and create | No |
| Import CSV files | No | Yes | No |
| View the facility audit log | No | Yes | No |
| Manage user accounts | No | No | List and create |
| View facilities | No | No | Yes |

Every check happens on the server before any data is read: a request without a valid login is refused (401), and a user without the right role or facility is refused (403). The screens only hide what a role cannot use. Still to add, as the proposal requires: viewing forecasts and stock-out alerts (health worker read, manager read and acknowledge) and stock settings for the manager in Phase 4, and schedule editing by the administrator in a later phase.

# 6. Phase status

**Table 6: Phase status**

| # | Phase | Planned dates | Status |
|---|---|---|---|
| | Proposal | April to June | Done (draft 4, Turnitin similarity 11%) |
| 0 | Setup | 28 to 30 Sep | Done (all tests pass; first upload pushed, commit a308e62) |
| 1 | Synthetic data and exploration | 28 Sep to 9 Oct | In progress (dataset regenerated after D-18 and D-19 and validated; figures done; supervisor sign-off pending) |
| 2 | Requirements and design | 29 Sep to 9 Oct | In progress (requirements frozen, all diagrams and wireframes drafted; supervisor review pending) |
| 3 | Prototype 1: data layer and the three module screens | 5 to 18 Oct | Built and tested ahead of plan (screenshots, gate review and `p1` tag pending) |
| 4 | Model training and Prototype 2 | 12 to 25 Oct | In progress (models trained and compared, Prototype 2 built and tested; alert decision D-41 and `p2` tag pending) |
| 5 | Refinement cycles and testing | 26 Oct to 6 Nov | Not started |
| 6 | User acceptance testing and final system | 2 to 12 Nov | Not started |
| 7 | Documentation (Chapters 4 to 6) | 5 Oct to 15 Nov | Not started |
| 8 | System demonstration | 16 to 22 Nov | Not started |

# 7. Phase by phase

## Phase 0: Setup

**What this phase is:** preparing the development environment and repository so that all later work is organised, reproducible and backed up.

**Done:**

- Created a dedicated SSH key for this project and set my commit identity for this project only; uploads are allowed only to my own GitHub account.
- Built the backend skeleton (Django). It refuses to start if any password or secret key is missing, too short, or left as the example value; 17 automated tests prove this.
- Built the frontend skeleton (React with TypeScript), with one passing automated test.
- Set up the database (PostgreSQL 16) to run in Docker, so the same setup works on Linux and Windows. The application and the tests use separate database accounts, and the database refuses example passwords.
- Added one command runner and a quick-start guide for Linux and Windows, pinned every library version, and made creating my `.env` file with strong random passwords one command that never shows them on screen.
- Every test, check and data run is recorded automatically, with its time and result, in a results log in my project notes. Data generation runs on one processor core at low priority and is skipped when nothing has changed.
- Ran the one-step setup: the database is healthy, Django's system check passes, and all tests pass (33 analytics, 5 runner, 17 backend, 1 frontend).
- First upload done: commit `a308e62` (141 files: code plus my project notes, so the project can be set up on another machine from one download) pushed to my private GitHub repository. Checks block secrets, generated data, copies of other people's documents, assistant guides and computer-specific folder paths, even if added by mistake.

**Pending:** nothing.

## Phase 1: Synthetic data and exploration

**What this phase is:** producing the dataset the whole system runs on and describing it. This replaces "Data Collection and Preparation" and "Exploratory Data Analysis" in my Gantt chart.

**Done:**

- Built the data generator. It creates births at each facility, gives each child a background (mother's education, wealth, birth order) in the same proportions as the KDHS, decides whether and how late each child comes for each vaccination visit, and gives every due vaccine if it is in stock. Stock arrives monthly and is sometimes late, short or missing, and I included two supply disruptions (OPV and measles-rubella).
- Tuned it in two stages to match the KDHS 2022 coverage figures: first without stock limits, then with stock-outs included.
- Added the 11 automatic checks and 23 tests, including a test that the same seed always gives identical files.
- Separated what the system is allowed to see (clinic records) from the ground truth that is used only to evaluate it.
- Produced the eight exploration figures (F-D1 to F-D8) and a dataset description table (T-5.1) with a repeatable command (`immdss eda`), which only works on a dataset that passed the quality checks. Figures and their data tables are in `docs/evidence/`.
- Applied my decisions D-18 and D-19 in the generator, not by editing data, with 3 new tests (28 tests passing). The first regenerated dataset failed the coverage check (measles-rubella 1 was 3.2 points off), so I gave the calibration one more round. The final dataset passes all 11 checks and reproduces byte for byte from the same seed. I archived the previous figures and regenerated all eight.
- Compared vaccine wastage with WHO planning figures, and vial sizes and open-vial rules with the Kenya Ministry of Health immunization guidelines (sources saved, with page numbers). Measles-rubella wastage (46%) was close to WHO's figure (40%); BCG (79%) was above WHO's 50%.
- Because of that, I decided (D-23) to give BCG on one day a week at sub-county hospitals as well. BCG wastage fell to 66%. The first dataset after this change failed the coverage check (OPV3 3.1 points off), and a second one passed but only by chance (its tuning swung up and down). I changed the tuning method so that each step is smaller and it stops once close enough (D-26). The accepted dataset (`sim-seed42-368707d3`) passes all 11 checks (largest gap 2.5 points, measles-rubella 1) and reproduces byte for byte. Measles-rubella 1 cannot get closer to the KDHS figure because some children sent away to the vaccine day do not come back; I report this as a limitation. I regenerated all eight figures; 33 analytics tests pass.
- Decided (D-24) to keep the BCG age limit at one year in the generator but use the Kenyan limit (59 months) in the system, and (D-25) to keep reusable pneumococcal vials for now and ask you about current practice.

**Pending:** your confirmation of the synthetic approach and of the pneumococcal vial question (D-25).

## Phase 2: Requirements and design

**What this phase is:** turning the Kenyan immunization schedule, the published guidance and the data profile into requirements, then producing the design diagrams in my proposal (3.4) and screen sketches.

**Done:**

- Froze my requirements: 26 functional and 11 non-functional requirements and 9 business rules, each linked to its evidence (my proposal, the Kenyan guidelines, WHO guidance or my data figures). Items that depend on an open decision are marked provisional.
- Confirmed decisions D-01 (Kenya, children under 2), D-06 (Jest tests) and D-08 (a dose is overdue 28 days after its due date), and chose PlantUML for diagrams (D-27).
- Drew nine diagrams: use case, class, three sequence diagrams, activity, architecture, entity relationship diagram and logical database schema (the last one is asked for by the faculty Chapter 4 guide). The database diagrams and a data dictionary are generated from one file, so they always agree.
- Made a table that links every requirement to its diagrams and planned tests.
- Made low-fidelity wireframes of the login, inventory, scheduling and child record screens.

**Pending:** your review of the wireframes and diagrams; your answer on whether diagrams generated with PlantUML are acceptable, or whether you want StarUML or Visual Paradigm.

## Phase 3: Prototype 1

**What this phase is:** the first working version (proposal 3.2.1): login with roles, the database loaded with the synthetic data, and basic versions of the three dashboards.

**Done:**

- Built the backend (Django REST Framework) with login for the three roles, facility-restricted access, account lockout after 5 failed logins, and the database model generated from my single schema file. 188 backend tests pass, including a test of every endpoint against every role.
- Built the first screens (React): login, inventory, scheduling, child records and user administration. 6 frontend tests pass.
- Loaded the synthetic data into the database (60 seconds) and ran a scripted walkthrough: stock balances matched for 84 of 84 facility and vaccine pairs, child histories for 200 of 200 sampled children, and the CSV import caught 119 of 120 planted errors while rejecting 0 of 697 clean rows. The slowest page request took 326 ms (95th percentile).

**Pending:** screenshots of every screen for Chapter 4, the gate review, and tagging the version as `p1`.

## Phase 4: Model training and Prototype 2

**What this phase is:** training and comparing the forecasting models, then adding them to the system (proposal 3.2.2). I will compare the GRU model and ARIMA against two simple baselines, because a model is only useful if it beats the simple method a clinic could use without software. I will also build the stock-out alerts and the defaulter priority ranking (most missed doses first, then children closest to the upper age limit for a vaccine).

**Done:**

- Decided that all model training runs on Google Colab with a GPU, never on my laptop (D-14), and made the repository public so Colab can use it (D-34). The training commands refuse to run anywhere else.
- Built the weekly training series from the stock ledger: 84 series (12 facilities x 7 vaccines) of 260 weeks, with stock-out weeks flagged from the ledger itself.
- Wrote the backtest (6 rolling cut-offs over the last 24 weeks), the four models (seasonal naive, moving average, SARIMA and GRU), the accuracy measures and the rule that picks the best model per series. 11 new tests pass.
- Wrote one Colab notebook that runs everything in order: data generation and a check that it is identical to my evidence dataset, validation, data exploration, training series, the model comparison, selection and the final models.

- Built the stock-out alerts and measured them against the true stock-outs in the synthetic data: with the baseline forecasts they caught 181 of 198 true stock-out weeks (recall 0.914), on average 2.15 weeks ahead, and 58.6% of alerts were followed by a stock-out or a week below the safety minimum. My target is a recall of at least 0.95, so it is **not met yet**. A first version of the rule caught only 66%, because it ignored the doses lost when opened vials are discarded; I corrected the rule before reporting (D-38).
- Trained and compared all four models on Google Colab (Tesla T4 GPU), after checking that Colab rebuilt exactly the same dataset (14 of 14 files identical). Average MASE (below 1 beats the seasonal naive method): GRU 0.677, SARIMA 0.681, moving average 0.766, seasonal naive 0.950. The GRU and SARIMA are close: each is better on about half of the series. Following my selection rule (D-21), the GRU is used for 80 series and SARIMA for 4, and these forecasts are now in the system.
- With the trained forecasts the alerts caught 167 of 198 true stock-out weeks (recall 0.843) and 64.0% of alerts were useful; with the baselines recall was 0.914. The cause: the GRU's uncertainty range is too narrow (it contained the true value 78.6% of the time instead of 80%), so the alert rule sees less risk. I have listed options to fix this (D-41).
- Checked my defaulter list against an independently written checking script for all 10,390 children under 2: status and missed doses matched for every child (100%), and the order matched at all 12 facilities.
- Added to the system: the forecast job, forecasts with their accuracy on the Stock screen, alerts the facility manager can acknowledge, the delivery cycle and safety buffer settings, outreach session plans with the vaccines needed against stock, attendance recording, FHIR export of a child's record, and administrator screens for accounts, facilities and the schedule.
- Redesigned the screens for phones first, with light and dark themes and an offline notice. 333 automated tests and 14 browser tests (desktop and phone) pass; the slowest page took 373 ms (95th percentile, without network time).

- I tried to fix the alert recall by calibrating the GRU's uncertainty range on its validation weeks (D-41). It made no difference (recall still 0.843): the range was already right on those weeks, but on the test weeks actual demand went above the GRU's upper bound 13.1% of the time instead of 10%. The GRU gave exactly the same forecasts in both Colab runs, which shows the training is repeatable.

**Pending:** I have now built a calibration of only the upper end of the GRU's range, on weeks the model never sees during training (D-41, option D); one more Colab run will measure it; tagging the version as `p2`. Choices for your review: a 24-week test period instead of 26 (D-35), yearly seasonality in SARIMA with Fourier terms (D-36), and the alert rule details (D-38).

## Phase 5: Refinement cycles and testing

**What this phase is:** repeated evaluate, fix, re-evaluate cycles (proposal 3.2.3), plus unit, integration, security and performance testing (dashboards loading in under 3 seconds).

**Pending:** all.

## Phase 6: User acceptance testing and final system

**What this phase is:** testing with real users using set tasks and the System Usability Scale, then final integration testing (proposal 3.2.4).

**Pending:** all. I need your guidance on participants and ethics (section 7, question 3).

## Phase 7: Documentation

**What this phase is:** writing Chapters 4 to 6 from the results as they come in. I keep logs of every data run, model run and test so that every number in the report can be traced.

**Pending:** the diagrams and requirements for Chapter 4 are ready, so I can start writing Chapter 4 once you have reviewed them.

## Phase 8: Demonstration

**What this phase is:** a rehearsed demonstration that shows a stock-out alert, planning an outreach session for the top defaulters, recording doses, and retrieving a child's record at another facility.

**Pending:** all.

# 8. Corrections I found in my proposal

While planning, I re-read my proposal and listed items to correct, including four in-text citations missing from the reference list, four references that are never cited, a missing description of user acceptance testing in section 3.6, and an inconsistency about whether the health passport needs a live database connection. Sections 3.3 and 3.2.1 will also need to describe the synthetic, calibrated data in place of secondary datasets. I will correct these in my own words for the final report.

# 9. Where I need your input

1. Is the fully synthetic dataset, calibrated to the KDHS 2022 coverage figures, acceptable in place of the secondary datasets described in section 3.3 of my proposal?
2. My proposal targets "more than 95% accuracy" for stock alerts and defaulter categorisation. I propose to measure it as (a) at least 95% of true stock-outs alerted up to 4 weeks ahead, with the false alarm rate also reported, and (b) defaulter status matching the true status for at least 95% of children. Is this acceptable?
3. For user acceptance testing, do I need ethics clearance, and could you suggest healthcare workers or a group I could approach?
4. Could you confirm the dates for the system demonstration and the Chapter 4 to 6 submissions?
5. In current Kenyan practice, may an opened 4-dose pneumococcal (PCV10) vial be used in later sessions, or is it discarded after 6 hours as the 2013 national guidelines state?
6. My design diagrams are drawn with PlantUML (a text-based tool, so they stay consistent with the database design). Are these acceptable, or should I redraw them in StarUML or Visual Paradigm?
7. Could you review my wireframes and design diagrams (attached)?
8. For the model comparison, I propose testing on the last 24 weeks (6 periods of 4 weeks) instead of 26, and modelling yearly seasonality in SARIMA with Fourier terms because the standard 52-week seasonal term is too slow for 84 series. Are these acceptable?

# 10. Next seven days (3 to 9 October)

| Task | Output I will show you |
|---|---|
| Colab run with the upper-end calibration (D-41, option D) | Updated alert recall and precision |
| Gate reviews of Prototypes 1 and 2; tag `p1` and `p2` | Review notes and the tagged versions |
| Prepare the user acceptance test task sheet and SUS questionnaire | Draft for your approval (needs your answer on ethics, question 3) |
