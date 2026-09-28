# Traceability matrix (requirements to design to tests)

Frozen with doc 02 v1 on 2026-09-28. Test IDs are planned (created in Phases 3 to 5, logged in `docs/logs/TEST_LOG.md`); a requirement is "verified" only when its tests pass. Diagram IDs: F-UC use case, F-CL class, F-SQ1 to F-SQ3 sequence, F-AC activity, F-AR architecture, F-ERD, F-LDS (rendered in `docs/evidence/`).

| FR | Use case | Diagrams | Django app (tables) | Planned tests | Phase |
|---|---|---|---|---|---|
| FR-01 | UC-01 | F-UC, F-AR | accounts (user) | TC-SEC-03 login, logout, refresh rotation; TC-SEC-04 lockout | 3 |
| FR-02 | all | F-AR, F-SQ1 to F-SQ3 | all (FacilityScopedQuerysetMixin) | TC-SEC-05 endpoint x role matrix; TC-SEC-06 cross-facility denial | 3 |
| FR-03 | UC-02, UC-03 | F-UC, F-CL | accounts, facilities, passport (scheduledose) | TC-I admin CRUD; TC-SEC SA has no clinical access | 3 |
| FR-10 | UC-04 | F-UC, F-AC, F-ERD | inventory (stocktransaction) | TC-U ledger sign by kind; TC-U no negative balance (BR-06) | 3 |
| FR-11 | UC-05 | F-SQ1 | inventory (stock_balance view) | TC-U balance equals ledger sum; TC-P dashboard p95 < 3 s | 3, 5 |
| FR-12 | UC-05, UC-08 | F-SQ1, F-AR | inventory (forecastrun, forecast) | TC-I run_forecasts writes forecasts visible via API; TC-M backtests | 4 |
| FR-13 | UC-06, UC-08 | F-SQ1 | inventory (stockalert) | TC-U projection and BR-05; TC-M alert precision, recall, lead time (D-07) | 4 |
| FR-14 | UC-07 | F-CL | inventory (stockpolicy) | TC-I FM only; TC-SEC HCW denied | 3 |
| FR-15 | UC-05 | F-SQ1 | inventory (forecastrun.metrics) | TC-I latest metrics shown per antigen | 4 |
| FR-16 | UC-08 | F-SQ1 | analytics package | TC-M selection rule per series (D-21) | 4 |
| FR-20 | UC-09 | F-SQ2, F-CL (DoseStatus) | passport (service) | TC-U due-date calculator on fixture children | 3 |
| FR-21 | UC-09 | F-SQ2 | scheduling (service) | Oracle test: independent script, exact match on the evidence run (D-07) | 4 |
| FR-22 | UC-09 | F-SQ2 | scheduling (service) | TC-U BR-04 ordering, ties by system ID | 4 |
| FR-23 | UC-10 | F-SQ2 | scheduling (outreachsession, sessionplanitem) | TC-I plan respects capacity; shortfall against balance and forecast | 4 |
| FR-24 | UC-11 | F-AC | scheduling (sessionattendance), passport, inventory | TC-S Playwright: record dose, defaulter list and stock update | 3, 5 |
| FR-25 | UC-09 | F-SQ2 | scheduling | TC-M cross-validated AUC (only if D-11 is on) | 4 |
| FR-30 | UC-12 | F-SQ3, F-AC | passport (child) | TC-U validation; TC-I system ID unique | 3 |
| FR-31 | UC-14 | F-AC, F-CL | passport (immunizationevent) | TC-U BR-01, BR-03, BR-06 on fixture rows | 3 |
| FR-32 | UC-13 | F-SQ3 | passport (child) | TC-SEC read-only cross-facility, audited (BR-08) | 3 |
| FR-33 | UC-15 | F-SQ3 | passport | TC-I history and next due doses | 3 |
| FR-34 | UC-16 | F-SQ3 | passport (service) | TC-I FHIR R4 Bundle validates (NFR-09) | 5 |
| FR-35 | UC-16 | F-SQ3 | passport | Only if D-09 is on | after p2 |
| FR-36 | UC-12 | F-SQ3 | passport (child index) | TC-U duplicate warning on family name + date of birth | 3 |
| FR-40 | UC-17 | F-CL, F-ERD | analytics_api (importbatch, importrowerror) | TC-D recall per defect type and false rejections against `import_dirty_truth.csv` | 3 |
| FR-41 | UC-18 | F-SQ1 to F-SQ3 | accounts (auditlog) | TC-SEC every write and cross-facility read audited, no field contents | 3 |
| FR-42 | UC-05 | F-AR | frontend service worker | TC-S offline read of last dashboards (D-10) | 5 |

| NFR | Design element | Planned tests | Phase |
|---|---|---|---|
| NFR-01 | Indexes in F-LDS; stock_balance view | TC-P Locust, dashboard p95 < 3 s | 5 |
| NFR-02 | run_forecasts via cron (F-AR) | TC-P timed full run | 4 |
| NFR-03 | Security layer (F-AR); preflight (done) | TC-SEC-01 (passing), TC-SEC-02 (passing), TC-SEC-03 onwards | 0, 3, 5 |
| NFR-04 | No phone column (F-LDS); truth/ never loaded (F-AR) | TC-D loader refuses truth/; log scan for identifiers | 3 |
| NFR-05 | Wireframes (docs/wireframes) | TC-UAT SUS (D-12) | 6 |
| NFR-06, NFR-07 | Responsive layout, table alternatives | TC-S Playwright at 360 px; accessibility checks | 5 |
| NFR-08 | CHECK constraints (F-LDS); import validation | TC-D import scoring | 3 |
| NFR-09 | FHIR export (F-SQ3) | TC-I base-spec validation | 5 |
| NFR-10 | Alert and defaulter logic (F-SQ1, F-SQ2) | D-07 measures | 4 |
| NFR-11 | ForecastRun manifest (F-ERD); results ledger | TC-D manifest fields present | 4 |
