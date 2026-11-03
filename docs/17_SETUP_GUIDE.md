# 17. Setting up the system on a new computer, with or without the trained models

A step-by-step guide for anyone installing the Immunization Decision Support System from the repository, including how to train the forecasting models on Google Colab and bring them into the system. Each step says what to run and what it does. More detail: doc 14 (screens and demo), doc 12 (data pipeline), doc 15 and doc 16 (results).

On Windows, type `py scripts\dev.py <command>` wherever this guide says `python3 scripts/dev.py <command>`.

## 1. What the Forecast tab is for

The Stock screen has four tabs. **Forecast** answers one question for the facility: *how many doses of each vaccine will we use in the next four weeks?*

For the vaccine you pick, it shows:

- a line of the doses actually given in each of the last 26 weeks;
- a dashed line with the forecast for the next 4 weeks, and a shaded band for the range the true number is expected to fall in 80% of the time;
- which model made the forecast (the GRU neural network, SARIMA, or a simple method) and how accurate that model was when tested on the last 24 weeks of past data.

The same forecast drives the **stock-out alerts** on the Stock tab: the system projects stock forward using the upper end of the forecast range and warns before stock is expected to run out. So an empty Forecast tab also means no alerts.

**Why it can be empty.** Forecasts are produced by a forecast job, not by loading the data. On a new installation, the job has never run, so the tab says no forecast is stored. Step 7 fixes that.

## 2. What never comes with the repository

These are created on each computer and are never uploaded to GitHub:

| Item | Why not in the repository | How it is created |
|---|---|---|
| `.env` (passwords and secret keys) | Secrets | Step 3 |
| Synthetic dataset (53 MB) | Rebuilt identically from a seed | Step 5 |
| Database contents | Built from the dataset | Step 6 |
| Demo account passwords | Secrets, new on each computer | Step 6 |
| Trained models and forecasts | Produced on Colab | Steps 7 and section 4 |

## 3. Setup steps

| # | Run | What it does | How long |
|---|---|---|---|
| 1 | Install Python 3.12 or later, Node.js 20 or 22, Docker Desktop and Git | The tools the system needs. Start Docker Desktop before step 4 | once |
| 2 | `git clone git@github.com:shantelle04/immunization-dss.git` (or the HTTPS address), then `python3 scripts/dev.py setup` | Downloads the code, creates a Python environment, installs the exact library versions, installs the frontend packages, and turns on the checks that stop secrets and data being uploaded | about 5 minutes |
| 3 | `python3 scripts/dev.py env` | Creates `.env` with new random passwords and keys. It never shows them and never overwrites an existing `.env` | seconds |
| 4 | `python3 scripts/dev.py db-up` | Starts the PostgreSQL database in Docker on port 5433 and waits until it is ready. Its data is kept between restarts | under a minute |
| 5 | `python3 scripts/dev.py simulate` | Generates the synthetic dataset from seed 42 (12 fictional facilities, 35,525 children, 2019 to 2025), checks it with 11 quality checks, and saves fingerprints of every file. The same seed gives byte-identical files on any computer | 2 to 3 minutes |
| 6 | `python3 scripts/dev.py load`, then `python3 scripts/dev.py demo-users` | Loads the clinic records into the database (never the hidden "truth" files used for evaluation), then creates an administrator and one manager and one health worker per facility. Passwords go to `.demo_credentials.txt` on that computer only | about 1 minute |
| 7 | **Either** `python3 scripts/dev.py forecasts --results <folder>/backtest` (trained models, see section 4) **or** `python3 scripts/dev.py forecasts` (simple baseline methods) | Builds the weekly vaccine-use series from the database, stores a 4-week forecast for every vaccine at every facility, and raises or clears stock-out alerts. This is what fills the Forecast tab | seconds |
| 8 | `python3 scripts/dev.py run` | Starts the backend and the app. Open http://localhost:5173 and sign in with an account from `.demo_credentials.txt` (managers `fm-syn-...`, health workers `hcw-syn-...`, `admin`) | stays running; Ctrl+C stops |
| 9 | `python3 scripts/dev.py doctor` | Runs 17 checks, from the installed tools to the stored forecasts, and prints the command that fixes anything missing. Run it whenever something looks wrong | seconds |

Optional checks: `python3 scripts/dev.py test` runs all automated tests (343 should pass); `python3 scripts/dev.py walkthrough` measures speed and checks the system's answers against the hidden truth (all accuracy checks should be 100%).

The clinical date is fixed at 29 December 2025, the last day of the dataset, so overdue doses and alerts look as they would on that day.

## 3a. Getting updates later

The latest reviewed version is on the `main` branch; work in progress is on `phase/4-models`.

| Situation | Run |
|---|---|
| First time (clone) | `git clone git@github.com:shantelle04/immunization-dss.git`, then `cd immunization-dss` |
| Already cloned, get the latest | `git checkout main`, then `git pull` |
| After pulling | `python3 scripts/dev.py setup` (installs any new library versions), then `python3 scripts/dev.py doctor` |
| If `doctor` reports pending migrations | `cd backend`, then `python manage.py migrate` (run it yourself; it is never forced) |
| If the data or training series changed | `python3 scripts/dev.py simulate`, `python3 scripts/dev.py load --replace`, `python3 scripts/dev.py forecasts` (or with `--results`) |

`git pull` never touches `.env`, the generated data, the database or `.demo_credentials.txt`, because they are not in the repository.

## 4. Training the models on Google Colab and bringing them in

Model training never runs on a personal computer; it runs on Colab with a free GPU. There are two ways to get trained forecasts.

**A. Use an existing results file.** If you have a results zip from a finished Colab run (the final one is `results_sim-seed42-368707d3_625841d.zip`), copy it to the computer, unzip it, and run step 7 with `--results <unzipped folder>/backtest`.

**B. Train them yourself (about 40 minutes).**

1. Open the notebook in Colab: `https://colab.research.google.com/github/shantelle04/immunization-dss/blob/main/notebooks/immdss_colab_pipeline.ipynb` (or `phase/4-models` in place of `main` for work in progress). In its first cell, set `REF` to the same branch
2. Runtime > Change runtime type > **T4 GPU** > Save.
3. Runtime > **Run all**. Do not use "Save a copy in GitHub" afterwards.
4. When it finishes, the browser downloads `results_<run>_<commit>.zip`. Copy it to the computer running the system, unzip it, and run step 7 with `--results <unzipped folder>/backtest`.

**What the notebook does, cell by cell:**

| Cell | What it does |
|---|---|
| Settings, GPU check | Confirms Python version and that a GPU is attached |
| Clone and install | Downloads the code at the chosen branch and installs the analytics package; stops if the download is not the expected version |
| Tests | Runs the analytics tests (about 57) |
| Generate and validate | Rebuilds the same synthetic dataset from seed 42 and stops if any file differs from the reference fingerprints, so Colab and your computer use identical data |
| Exploration | Draws the data exploration figures |
| Training series | Builds 84 weekly series (12 facilities x 7 vaccines, 260 weeks) from the clinic records only |
| Backtest | Tests four methods on the last 24 weeks, pretending each time that later weeks are unknown: seasonal naive, 4-week moving average, SARIMA and the GRU neural network |
| Compare and select | Picks the model for each series (the GRU where it beats the simple method, otherwise SARIMA) and measures accuracy against the hidden truth |
| Alert evaluation and study | Measures how many true stock-outs the alerts would have caught, and tests a risk score |
| Final models | Retrains the chosen model on all 260 weeks and forecasts the next 4 weeks |
| Package | Zips everything and downloads it |

**What the import checks.** Step 7 compares the training data's fingerprint inside the zip with the series rebuilt from your database. If they differ, for example because the data was generated with a different version of the code, it refuses and says so. `doctor` checks that your data is identical to the evidence run before you try.

## 5. What a correct installation looks like

`python3 scripts/dev.py doctor` ends with `17 of 17 checks pass`. If you used the baseline methods instead of the trained models, 16 pass and "Trained models imported" fails; the system works, but the forecasts come from the simple methods.

In the app, signed in as a manager or health worker: the Overview shows counts of alerts and defaulters; Stock > Forecast shows a chart for each vaccine with "Model: GRU neural network" for most series; Outreach shows the ranked defaulter list.

## 6. Common problems

| Symptom | Cause | Fix |
|---|---|---|
| Forecast tab says no forecast is stored | Step 7 not done on this computer | `python3 scripts/dev.py forecasts` (or with `--results`) |
| "Not Found" at 127.0.0.1:8000 | That is the backend, which only answers under `/api/v1/` | Open http://localhost:5173 instead |
| Database connection refused | Docker or the database container is not running | Start Docker Desktop, then `python3 scripts/dev.py db-up` |
| Import refused: trained on a different series | The dataset differs from the one the models were trained on | Run `doctor`; regenerate with `simulate`, reload with `load --replace`, or retrain on Colab |
| Sign-in fails with demo passwords from another computer | Passwords are created per computer | Use `.demo_credentials.txt` on this computer, or `python3 scripts/dev.py demo-users --reset` |
| Every child looks months overdue | Clinical date is today's real date | Start with `python3 scripts/dev.py run`, or set `IMMDSS_TODAY=2025-12-29` in `.env` |
