# Data generation, validation and cleaning log

All data is synthetic (D-02). This log records every generator run used as evidence, validation results, and the system's import-cleaning scores.

## Decisions

| Date | Entry |
|---|---|
| 2026-09-28 | Real microdata (KDHS 2022 recode files) dropped: access request too slow for the timeline. Replaced by a seeded simulator calibrated to the public KDHS 2022 Key Indicators Report, Table 11 (D-02) |

## Generator runs

| Date | Run ID | Seed | Rows (children / events / stock tx) | Calibration (max error) | Validation | Notes |
|---|---|---|---|---|---|---|
| 2026-09-28 | sim-seed42-dafd92e6 | 42 | 35,493 / 498,466 / 102,378 | 1.32 pp stage 1 | Not run: params snapshot lost contact order | Fixed: config key order preserved in snapshot and hash |
| 2026-09-28 | sim-seed42-73172355 | 42 | 35,493 / 498,466 / 102,378 | 1.32 pp stage 1 | FAIL: V-06 751 interval violations, V-07 1,109 duplicate doses, V-10 MR2 -5.2 pp | Fixed: a child with two visits in one session is seen once; added stage 2 calibration against the full engine |
| 2026-09-28 | sim-seed42-d0c64e01 | 42 | 35,529 / 500,128 / 102,412 | 1.32 pp stage 1; 4.9 then 1.9 pp stage 2 | **PASS 11/11**, max coverage difference 1.4 pp (Rota2) | Superseded by sim-seed42-cf02cb90 (D-18, D-19); EDA archived in `docs/evidence/archive_sim-seed42-d0c64e01/`. Regenerated after formatting: identical run ID and results |
| 2026-09-28 | sim-seed42-080265b6 | 42 | 35,540 / 499,177 / 89,776 | 1.04 pp stage 1; 11.2 then 5.8 pp stage 2 | **FAIL** V-10: MR1 -3.2 pp (tolerance 3.0) | D-18 batching and discard, D-19 effect_shrink 0.8, engine_refinements 2. Not usable. Cause: engine refinement had not converged (budget of 2 exhausted) |
| 2026-09-28 | sim-seed42-cf02cb90 | 42 | 35,540 / 499,042 / 89,962 | 1.04 pp stage 1; 11.2, 5.8, 3.2 pp stage 2 | **PASS 11/11**, max coverage difference 2.8 pp (MR1) | **Evidence run.** Same changes, engine_refinements 3. Rerun from the same seed and config into a scratch folder: all 16 file hashes identical. Before and after: `docs/evidence/D-18_D-19_before_after.md` |
| 2026-09-28 | sim-seed42-cf02cb90 (rebuilt) | 42 | 35,540 / 499,042 / 89,962 | unchanged | **PASS 11/11**, 2.8 pp (MR1) | Rebuilt once to add `code_sha256` to the manifest and `wastage_rate_who_pct` to the validation report; every CSV hash identical to the previous build. WHO-definition wastage: BCG 79.2, MR 46.4, OPV 5.8, IPV 4.6, PCV 1.3, PENTA 0.3, ROTA 0.2 (%) |
| 2026-09-28 | sim-seed42-deca88d9 | 42 | 35,540 / 498,021 / 84,710 | stage 2: 12.4, 5.5, 4.0 pp (3 undamped rounds) | **FAIL** V-10: OPV3 -3.1 pp | D-23 (BCG batched at all levels). Not usable |
| 2026-09-28 | sim-seed42-cce5aedc | 42 | not recorded | stage 2: 12.4, 5.5, 4.0, 3.1, 3.3, 3.6, 2.4 pp (6 undamped rounds, target 1.5) | PASS 11/11, 2.4 pp (MR1), **rejected** | Errors oscillated, so the pass depended on the stopping point; replaced by the damped method (D-26) |

## Import cleaning scores (filled when the system's CSV import is built, Phase 3)

| Date | Run ID | File | Defect | Planted | Caught | Recall | Clean rows wrongly rejected |
|---|---|---|---|---|---|---|---|
