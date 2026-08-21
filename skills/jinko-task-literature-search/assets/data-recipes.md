# Data Search Recipe

Use Data searches for studies likely to report values for named model variables.
Before querying, require the variables, population and disease state, evidence
type, and whether aggregate summaries or within-population distributions are
needed.

## Angles

Choose at least three angles with the strongest available identifiers:

- trial or study acronym;
- generic, brand, and research-code drug names;
- known authors;
- population plus outcome or endpoint;
- population plus intervention and severity, comorbidity, or sampling details.

Add supplied anchor PMIDs with `--seed-pmids`. Use `humans[mh] AND english[lang]`
for human evidence, `animals[mh]` for animal evidence, or
`"in vitro techniques"[mh]` for in-vitro evidence. Treat publication type as a
post-search signal rather than a hard filter so older trials and substudies are
not silently excluded.

For human clinical, biological, or PK/PD evidence, run
`jinko-task-trial-data-scoping` in parallel and add high-priority NCT identifiers
as `<NCT_ID>[si]` publication angles. Do not union registry records and
publications without preserving their distinct evidence types.

## Priority

Inspect title, abstract, and available full-text excerpt for evidence matching
the requested variable:

- endpoint values, timepoints, arms, dose/regimen, population, or sample size;
- tables, figures, supplementary material, units, summary statistics, or
  distributions;
- PK/PD measures such as Cmax, AUC, Tmax, half-life, clearance, concentration
  time courses, or dose response;
- biomarker or clinical-outcome trajectories.

Set `verification_passed` only when the inspected text supports a relevant data
signal. State exactly what was observed in `verification_note`; otherwise
downgrade priority rather than claiming extractable data.

Use `--fetch-pmc-fulltext` selectively for candidates with a PMCID when the
abstract is insufficient.
