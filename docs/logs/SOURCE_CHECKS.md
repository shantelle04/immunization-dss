# Source checks (VERIFY items resolved against primary sources)

Local copies in `docs/reference/sources/` (not committed). Page numbers are PDF page numbers. Retrieved 2026-09-28.

| Short name | Document | URL | SHA-256 (first 12) |
|---|---|---|---|
| WHO-2005 | WHO (2005). *Monitoring vaccine wastage at country level: Guidelines for programme managers*. WHO/V&B/03.18 Rev.1 | https://iris.who.int/server/api/core/bitstreams/bf88e08d-273b-48df-93b7-a1d7cb9ac02a/content | b967b6195c2a |
| WHO-2019 | WHO (2019, 8 April). *Revising global indicative wastage rates: a WHO initiative for better planning and forecasting of vaccine supply needs*. Concept note | https://www.who.int/docs/default-source/immunization/tools/revising-wastage-concept-note.pdf | 0c54b7124037 |
| KE-MOH-2013 | Ministry of Health, Kenya (2013). *National Policy Guidelines on Immunization 2013* (file name says 2012; cover says 2013: VERIFY the edition year before citing) | https://familyhealth.go.ke/wp-content/uploads/2018/02/Immunization-Policy-Guidline.pdf (TLS certificate error; downloaded from the mirror https://devinit.org/files/sites/default/files/mchipfiles/immunization%20policy%20guidline.pdf) | 3707299ee32c |

APA 7th reference entries are the author's to write; the table gives the facts needed.

## 1. WHO indicative wastage rates (D-18, D-23)

WHO-2019 p2, "Table 1: WHO Global Indicative Wastage Rates, 2002" (routine immunization column):

| Vial presentation (quoted) | Routine |
|---|---|
| Single Dose | 5% |
| 2 or 5-dose, regardless of MDVP | 10% |
| 10 or 20-dose: if opened vial can be re-used in subsequent sessions | 25% |
| 10 or 20-dose: if opened vial must be discarded at end of session or maximum in 6 hours from the time the vial was opened | 40% |
| 20-dose or more: if opened vial must be discarded at end of session | 50% |

Caveat, same page: "Indicative wastage rates have several significant limitations and do not reflect necessarily country context." They are planning figures for forecasting, not observed values or maximum limits.

**Formula**, WHO-2005 p15 and p20: "Vaccine wastage rate = 100 – vaccine usage rate", and "Vaccine wastage (rate) = Number of doses wasted / Number of doses supplied x 100", covering "wastage in both unopened and opened vials". The validator now reports `wastage_rate_who_pct` = (opened-vial wastage + unopened losses) / (administered + wastage + losses), as well as the earlier opened-vial-only `wastage_rate_pct`.

**Comparison with evidence run `sim-seed42-cf02cb90`** (WHO definition, 2021 to 2025, facility level only):

| Antigen | Presentation in `sim.yaml` | WHO category | WHO indicative | Simulated | Reading |
|---|---|---|---|---|---|
| BCG | 20-dose, discard | 20-dose or more, discard at end of session | 50% | 79.2% | Above |
| MR | 10-dose, discard | 10 or 20-dose, discard | 40% | 46.4% | Close, slightly above |
| OPV | 20-dose, reusable | 10 or 20-dose, re-used | 25% | 5.8% | Below |
| IPV | 5-dose, reusable | 2 or 5-dose | 10% | 4.6% | Below |
| PCV | 4-dose, reusable | nearest: 2 or 5-dose | 10% | 1.3% | Below (4-dose is not a listed size) |
| PENTA | 1-dose | Single dose | 5% | 0.3% | Below |
| ROTA | 1-dose | Single dose | 5% | 0.2% | Below |

Reading: the simulator's wastage is driven by session size and vial size (the WHO-2019 p2 "unavoidable open vial wastage ... primary source of vaccine wastage") and excludes stores above facility level, so values below the indicative planning rates are expected for single-dose and reusable vials. BCG is the outlier.

A published facility-level study reported BCG 54.9%, IPV 28.3% and MR 27.4% (Mandalay, Myanmar, 2018; *Tropical Medicine and Infectious Disease* 5(2):60, doi 10.3390/tropicalmed5020060). Figures taken from the search abstract only: VERIFY against the full text before citing.

## 2. Kenya open-vial policy and vial sizes (`sim.yaml` antigens)

KE-MOH-2013 p28, "OPEN VIAL POLICY": the multi-dose vial policy "applies to the following vaccines; OPV, TT, Hepatitis B, Pentavalent vaccine (liquid preparation)", and opened vials "may be used during subsequent immunization sessions for a maximum of four weeks" under conditions. For reconstituted vaccines: "Once these are reconstituted, the vials must be discarded at the end of each immunization session or at the end of 6 hours, whichever comes first."

| Item in `sim.yaml` | Source says | Status |
|---|---|---|
| BCG 20 doses, no open-vial policy | p30: "BCG is prepared in multi-dose lyophilized (freeze-dried) containing 20 doses per vial"; discard after six hours or end of session | Confirmed |
| MR no open-vial policy | Measles vaccine is "lyophilized" (measles section); reconstituted vaccines are discarded at session end (p28) | Confirmed (the guideline predates MR; measles monovalent described) |
| OPV open-vial policy | p28 MDVP list | Confirmed; OPV vial size not stated in the checked pages: VERIFY |
| PENTA open-vial policy, 1-dose | p28 lists "Pentavalent vaccine (liquid preparation)" under MDVP | Policy confirmed; vial size 1 not confirmed: VERIFY current presentation |
| PCV open-vial policy (4-dose) | p23: "This however does not apply to the PCV10, pneumococcal vaccine, which should be discarded after 6 hours from the time a vial is opened." | **Conflict** with `sim.yaml` (D-25). The 2013 text may predate the 4-dose PCV10 presentation: VERIFY current Kenyan practice |
| IPV open-vial policy, 5-dose | IPV not in the 2013 MDVP list | Not confirmed: VERIFY |
| ROTA 1-dose | Rotavirus section layout could not be parsed | VERIFY |

## 3. Age limits and schedule

| Item | Source says | Status |
|---|---|---|
| BCG maximum age (`dose_rules.BCG-1.max_age` 365 days) | p30: "Schedules: At birth and up to 59 months of age" | **Differs** (D-24). The simulator's 365 days is a modelling cut within the under-2 scope |
| Pentavalent 6, 10, 14 weeks | Hib section: "The infant schedule is at 6, 10 & 14 weeks of age" | Confirmed |
| Measles first dose at 9 months | Measles section: "administered at 9 months of age in the Kenya routine immunization schedule for infants" | Confirmed |
| Rotavirus upper age (BR-03) | Not extracted | VERIFY (WHO rotavirus position paper or current KEPI schedule) |

## 4. Defaulter definition (D-08)

KE-MOH-2013 p60: "health workers should regularly identify defaulters from the immunization permanent register and institute measures to promptly track and bring all defaulters back to complete the vaccination schedule." **No time threshold is given** in the pages checked. The 28-day grace period in D-08 therefore stays an ASSUMPTION, configurable, and must be presented as the author's operational definition.
