# Project notes

Plans, requirements, decisions, logs, the results ledger, evidence figures, diagram sources and wireframes for the immunization DSS. They are versioned in the main repository (decision D-28) so the project can be set up on another machine from one clone.

Kept out of the repository on purpose: assistant guides, copies of third-party reference documents (`reference/`), review files (`pr_*.md`), secrets and generated data. Committed notes must not contain machine-specific paths; the pre-commit hook rejects them.

## On a new machine

```bash
git clone git@github.com:shantelle04/immunization-dss.git
cd immunization-dss
python3 scripts/dev.py setup
python3 scripts/dev.py bootstrap      # new .env with new secrets, database, tests
python3 scripts/dev.py simulate       # rebuilds the evidence run byte for byte (about 2 minutes)
python3 scripts/dev.py eda
python3 scripts/dev.py diagrams
```

Then restore the local-only files from your personal backup (reference PDFs, assistant guide) and repeat the repository-local git settings in `08_SETUP_AND_GIT.md` (SSH key, identity, owner guard).

| Folder           | Contents                                                                                                               |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `00` to `09` | Project context, plan, requirements, architecture, data, models, documentation plan, decisions, setup, proposal issues |
| `logs/`        | Implementation, data, test, training and source-check logs, defence notes, results ledger and history                  |
| `evidence/`    | Figures and tables cited in the report (EDA, diagrams, before and after tables)                                        |
| `diagrams/`    | PlantUML sources,`schema.yaml`, generated data dictionary, traceability matrix                                       |
| `wireframes/`  | Low-fidelity screen sketches                                                                                           |
| `progress/`    | Progress tracker and the Word report builder                                                                           |
