# 09. Issues found in proposal draft 4

For the author to fix in their own words if a corrected proposal or Chapter 1 to 3 revision is needed. Claude does not rewrite these sections. Ordered by severity.

## 1. Content and consistency

| # | Location | Issue | What to do |
|---|---|---|---|
| P-01 | 1.1, first sentence | "one of the costliest public health interventions" says the opposite of the evidence that follows (lives saved per cost) | Check the intended meaning (most cost-effective) and correct |
| P-02 | Abstract, 3.2 vs 3.2.1 to 3.2.4 | 3.2 justifies evolutionary prototyping by hands-on healthcare worker feedback, but phases 3.2.1 to 3.2.4 describe only automated data-driven evaluation. Objective v and RQ v promise healthcare worker feedback and the abstract promises UAT | Add a UAT or usability step (Phase 6 in the plan) to the methodology, or reword the justification |
| P-03 | 3.6 | Testing section covers unit, integration, performance but not UAT or usability, though the abstract lists UAT and Brooke (1996, SUS) is in the references | Add UAT with SUS, cite Brooke |
| P-04 | 1.1, 2.3.3, 2.5.3, 2.6 vs 3.8.3 | The passport is described as retrievable "without requiring a live connection to a central database", but 3.8.3 stores it in the central PostgreSQL database and retrieves it through the web app | Make one consistent claim (central store plus a browser read cache, D-10) |
| P-05 | 2.5.1 and 3.8.1 | ARIMA is the fallback "for facilities with no historical data", but ARIMA also needs history | State the real rule (doc 05 section 1) |
| P-06 | 2.5.2 vs 3.8.2 | 2.5.2: most missed doses first, then nearest the upper age limit. 3.8.2 reads as if upper age range is ranked highest, and the sentence is garbled. 3.8.2 also omits the stock forecast as an input that 2.5.2 lists | Align both to one rule |
| P-07 | 3.2.3 | "more than 95% accuracy in predictive stock alerts and defaulter categorization" has no metric definition | Define it (D-07) |
| P-08 | 3.2.2 | "querying and rendering the stock levels (in the stock price and data)" does not make sense | Rewrite |
| P-09 | 1.7 | "The study is limited to the web platform and it is not developed native mobile applications to address this challenge" is garbled, and "prevalence of mobile app usage" argues against the delimitation | Rewrite the delimitation |
| P-10 | 2.3.3 | Second paragraph mixes the Rwanda and Kenya studies in one sentence with a parenthesis that breaks the meaning | Split into two clear findings |
| P-11 | 3.3 | Data sources named only as examples ("such as DHIS2 export schemas ...") | Superseded by P-12 |
| P-12 | 1.7, 3.2.1, 3.3, abstract | The project now uses a fully synthetic, seeded dataset calibrated to KDHS 2022 Table 11 (D-02), not profiled secondary datasets | In the final report, describe requirements as coming from the desk review and published coverage figures, and the data as synthetic and calibrated; keep 1.7's simulated-data statement |

## 2. Citations and references (APA 7th)

| # | Issue |
|---|---|
| R-01 | Cited in text but missing from references: Liu et al. (2005), Nelson et al. (2016), Boppana (2024), Gyldenkærne et al. (2025) |
| R-02 | In references but never cited: Brooke (1996), Desjardins et al. (2022), Musuka et al. (2026), Yaeesh et al. (2025). The DTaP rural study described as "Gyldenkærne et al., 2025" matches the Yaeesh et al. (2025) reference (VERIFY and fix the in-text name) |
| R-03 | "(PMC, 2025)" in 1.1 is a repository, not an author; cite the actual article |
| R-04 | Taliun (2023) and Dogtown Media (2023) are vendor blogs used to justify the stack; replace or supplement with official documentation or peer-reviewed sources |
| R-05 | Schwaber and Sutherland (2020, Scrum Guide) is cited for a claim about early defect detection in testing; the Scrum Guide does not make that claim |

## 3. Style (faculty guide: proposal in third person, future tense)

| # | Issue |
|---|---|
| S-01 | First person "we" in 1.7, 3.2.1, 3.3, 3.5, 3.8 |
| S-02 | Second person "help you see" in 3.3 |
| S-03 | A Turnitin summary page is embedded in the document body; confirm whether it belongs in the submission |
| S-04 | Gantt timeline (Appendix) shows design finishing in September and data preparation in September; update it with actual dates once D-16 is known |
