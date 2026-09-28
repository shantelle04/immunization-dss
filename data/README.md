# Data

All data in this project is **synthetic**. It is produced by a seeded simulator (`immdss simulate`) whose behaviour is calibrated to published national immunization coverage figures (Kenya DHS 2022 Key Indicators Report, Table 11). No real patient or facility records are used.

Nothing in this folder except this file is tracked; any run can be rebuilt from the configuration and seed.

```bash
python3 -m venv .venv && .venv/bin/pip install -e "analytics[dev]"
.venv/bin/immdss simulate --out data/synthetic          # about 1 minute, validates automatically
.venv/bin/immdss validate-sim data/synthetic/<run_id>
```

Each run folder `data/synthetic/sim-seed<seed>-<confighash>/` contains:

| Path | Contents |
|---|---|
| `app/` | Tables the application loads: facilities, antigens, schedule, sessions, children, immunization events, stock transactions, vaccine lots |
| `truth/` | Ground truth used only to evaluate the system (true demand, stock-out weeks, child background and dropout); never loaded into the application |
| `imports/` | CSV import samples with planted data-quality defects, and their answer key |
| `manifest.json` | Seed, configuration hash, and SHA-256 and row count of every file |
| `validation_report.md` | Consistency and calibration checks for the run |
