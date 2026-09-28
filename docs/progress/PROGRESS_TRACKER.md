---
title: "Project Progress Report"
subtitle: "A Web-Based Decision Support System for Healthcare Workers to Address Childhood Immunization Gaps through Predictive Analytics and Smart Scheduling"
author: "Muthomi, Shantelle Nkatha (168873), BBIT 4D. Supervisor: Mr. Titus Tunduny"
date: "Status as of 28 September 2026"
---

# 1. Summary

My proposal is complete (draft 4), and I have moved into building the system. I have set up the project repository and a full execution plan that follows the four evolutionary prototyping phases in my Chapter 3, broken into eight working phases, each with a clear completion check.

The main progress this week is the data. Requesting real survey microdata would have taken longer than my timeline allows, so, in line with my limitations section (1.7), I have built a **seeded synthetic dataset** for the whole project. It is calibrated so that its vaccination coverage matches Kenya's official figures from the Kenya Demographic and Health Survey 2022. The dataset is generated, it passes all 11 automatic quality checks, and anyone can regenerate the identical dataset from the same settings in about one minute.

Compared to my proposal Gantt chart, I am about two weeks behind on design, which was planned to finish in September. Because the data is now ready earlier than planned, I can start design and the first prototype in parallel from this week.

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

# 4. Phase status

**Table 3: Phase status**

| # | Phase | Planned dates | Status |
|---|---|---|---|
| | Proposal | April to June | Done (draft 4, Turnitin similarity 11%) |
| 0 | Setup | 28 to 30 Sep | In progress (skeletons and tests done; first upload and my `.env` pending) |
| 1 | Synthetic data and exploration | 28 Sep to 9 Oct | In progress (dataset regenerated after D-18 and D-19 and validated; figures done; supervisor sign-off pending) |
| 2 | Requirements and design | 29 Sep to 9 Oct | In progress (requirements frozen, all diagrams and wireframes drafted; supervisor review pending) |
| 3 | Prototype 1: data layer and the three module screens | 5 to 18 Oct | Not started |
| 4 | Model training and Prototype 2 | 12 to 25 Oct | Not started |
| 5 | Refinement cycles and testing | 26 Oct to 6 Nov | Not started |
| 6 | User acceptance testing and final system | 2 to 12 Nov | Not started |
| 7 | Documentation (Chapters 4 to 6) | 5 Oct to 15 Nov | Not started |
| 8 | System demonstration | 16 to 22 Nov | Not started |

# 5. Phase by phase

## Phase 0: Setup

**What this phase is:** preparing the development environment and repository so that all later work is organised, reproducible and backed up.

**Done:**

- Set up the local repository with rules that stop data files, secrets and working notes from ever being uploaded, and a check that only allows uploads to my own GitHub account.
- Created a dedicated SSH key and confirmed that it connects to my GitHub account; set my commit identity for this project only.
- Built the backend skeleton (Django). It refuses to start if any password or secret key is missing, too short, or left as the example value; 17 automated tests prove this.
- Built the frontend skeleton (React with TypeScript), with one passing automated test.
- Set up the database (PostgreSQL 16) to run in Docker, so the same setup works on Linux and Windows. The application and the tests use separate database accounts. I tested it with temporary values: it rejects example passwords and creates both accounts correctly.
- Added one command runner and a quick-start guide in the README for Linux and Windows, and pinned every library version so the project installs the same way on any machine.
- The analytics code now has 25 passing tests, and the code style checker reports no problems.

- Every test, check and data run is now recorded automatically, with its time and result, in a results log in my project notes.
- Creating my `.env` file with strong random passwords is now one command (`python3 scripts/dev.py env`). It is tested, and it never shows the passwords on screen.
- Data generation uses one processor core and about 0.7 GB of memory for about 70 seconds, at low priority, and it is skipped entirely when nothing has changed.

- Generated my `.env` and ran the one-step setup (`dev.py bootstrap`): the database started in Docker and is healthy, Django's system check passed, and all tests passed (33 analytics, 5 runner, 17 backend, 1 frontend), recorded in my results log.
- Prepared the first upload: 141 files (code plus my project notes, so the project can be set up on another machine from one download). Checked so that no assistant guides, copies of other people's documents, data, secrets or computer-specific folder paths are included; the protection blocks them even if added by mistake.

**Pending:** the first upload to GitHub (nothing has been uploaded yet); supervisor confirmation of D-02 (synthetic data) and D-07 (what 95% accuracy means) (section 7).

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

- Froze my requirements: 26 functional and 11 non-functional requirements and 8 business rules, each linked to its evidence (my proposal, the Kenyan guidelines, WHO guidance or my data figures). Items that depend on an open decision are marked provisional.
- Confirmed decisions D-01 (Kenya, children under 2), D-06 (Jest tests) and D-08 (a dose is overdue 28 days after its due date), and chose PlantUML for diagrams (D-27).
- Drew nine diagrams: use case, class, three sequence diagrams, activity, architecture, entity relationship diagram and logical database schema (the last one is asked for by the faculty Chapter 4 guide). The database diagrams and a data dictionary are generated from one file, so they always agree.
- Made a table that links every requirement to its diagrams and planned tests.
- Made low-fidelity wireframes of the login, inventory, scheduling and child record screens.

**Pending:** your review of the wireframes and diagrams; your answer on whether diagrams generated with PlantUML are acceptable, or whether you want StarUML or Visual Paradigm.

## Phase 3: Prototype 1

**What this phase is:** the first working version (proposal 3.2.1): login with roles, the database loaded with the synthetic data, and basic versions of the three dashboards.

**Pending:** all. Starts 5 October.

## Phase 4: Model training and Prototype 2

**What this phase is:** training and comparing the forecasting models, then adding them to the system (proposal 3.2.2). I will compare the GRU model and ARIMA against two simple baselines, because a model is only useful if it beats the simple method a clinic could use without software. I will also build the stock-out alerts and the defaulter priority ranking (most missed doses first, then children closest to the upper age limit for a vaccine).

**Pending:** all. Starts 12 October.

## Phase 5: Refinement cycles and testing

**What this phase is:** repeated evaluate, fix, re-evaluate cycles (proposal 3.2.3), plus unit, integration, security and performance testing (dashboards loading in under 3 seconds).

**Pending:** all.

## Phase 6: User acceptance testing and final system

**What this phase is:** testing with real users using set tasks and the System Usability Scale, then final integration testing (proposal 3.2.4).

**Pending:** all. I need your guidance on participants and ethics (section 6).

## Phase 7: Documentation

**What this phase is:** writing Chapters 4 to 6 from the results as they come in. I keep logs of every data run, model run and test so that every number in the report can be traced.

**Pending:** writing starts once the Phase 2 diagrams are ready.

## Phase 8: Demonstration

**What this phase is:** a rehearsed demonstration that shows a stock-out alert, planning an outreach session for the top defaulters, recording doses, and retrieving a child's record at another facility.

**Pending:** all.

# 6. Corrections I found in my proposal

While planning, I re-read my proposal and listed items to correct, including four in-text citations missing from the reference list, four references that are never cited, a missing description of user acceptance testing in section 3.6, and an inconsistency about whether the health passport needs a live database connection. Sections 3.3 and 3.2.1 will also need to describe the synthetic, calibrated data in place of secondary datasets. I will correct these in my own words for the final report.

# 7. Where I need your input

1. Is the fully synthetic dataset, calibrated to the KDHS 2022 coverage figures, acceptable in place of the secondary datasets described in section 3.3 of my proposal?
2. My proposal targets "more than 95% accuracy" for stock alerts and defaulter categorisation. I propose to measure it as (a) at least 95% of true stock-outs alerted up to 4 weeks ahead, with the false alarm rate also reported, and (b) defaulter status matching the true status for at least 95% of children. Is this acceptable?
3. For user acceptance testing, do I need ethics clearance, and could you suggest healthcare workers or a group I could approach?
4. Could you confirm the dates for the system demonstration and the Chapter 4 to 6 submissions?

# 8. Next seven days (28 September to 4 October)

| Task | Output I will show you |
|---|---|
| Exploration charts from the synthetic data (done 28 Sep) | Figures F-D1 to F-D8 and the dataset description table |
| Fix the two dataset weaknesses (done 28 Sep, partly improved) | Before and after tables |
| Design diagrams started | Use case and ERD drafts |
| Project skeleton (Django, React, database) (done 28 Sep, database pending my `.env`) | Test run output |
| First upload to GitHub | Repository link |
