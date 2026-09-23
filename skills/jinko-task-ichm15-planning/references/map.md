# Model Analysis Plan Template

Use this template during the MIDD planning stage, before accessing analysis data or performing the planned model analysis when appropriate for the context of use.

Parenthetical `(e.g. ...)` text after a field is a generic starting menu for that
field, adapted from standard M&S practice — pick and tailor what's relevant to
this project, or replace it entirely. Never leave the parenthetical itself in
the delivered document.

## Document Control

- Project:
- Model analysis plan title:
- Version:
- Date:
- Authors and roles:
- Reviewers and roles:
- Related question(s) of interest:
- Related modeling strategy artifact:
- Related sources and data artifacts:

## 1. Executive Summary

- Briefly state the planned analysis.
- State the decision or scientific question the analysis is intended to inform.
- State the context of use and expected model influence.
- State whether the intended use is exploratory, supportive, confirmatory, or regulatory-facing.

## 2. Question of Interest and Context of Use

| Item | Planned Entry |
| --- | --- |
| Question of interest |  |
| Context of use |  |
| Intended role and scope of model(s) |  |
| Data used to build model(s) |  |
| Additional data or evidence informing the answer |  |
| Decision supported |  |

## 3. MIDD Evidence Assessment Planning Table

| Item | Planned Entry | Rating | Justification |
| --- | --- | --- | --- |
| Model influence |  | Low / Medium / High |  |
| Consequence of wrong decision |  | Low / Medium / High |  |
| Model risk |  | Low / Medium / High |  |
| Model impact |  | Low / Medium / High |  |
| Technical criteria |  | Not rated |  |
| Appropriateness of proposed MIDD |  | Not rated |  |

*Technical Criteria and Appropriateness of Proposed MIDD are narrative elements per ICH M15 §2.2, not classified low/medium/high like the four Key Assessment Elements above.*

## 4. Objectives

- Primary objective:
- Secondary objectives:
- Intended model application:
- Outputs or model outcomes needed to answer the question of interest:
- Analyses explicitly out of scope:

## 5. Data

### 5.1 Data Sources

| Source | Type | Intended Use | Inclusion Rationale | Exclusion or Bias Concerns |
| --- | --- | --- | --- | --- |
|  |  | Calibration / qualification / validation / scenario definition / population descriptors |  |  |

### 5.2 Data Handling

- Inclusion and exclusion criteria:
- Transformations:
- Unit conversions:
- Imputations or missing-data handling:
- Derived variables:
- Data provenance and traceability:
- Known limitations:

## 6. Modeling and Simulation Methods

- Model class or approach:
- Minimal model structure and granularity:
- Submodels and linking equations planned:
- States, algebraic outputs, events, switches, and assumptions:
- Parameters fixed from prior knowledge:
- Parameters planned for calibration:
- Scenario parameters:
- Computational platform and Jinko artifacts planned:
- Numerical methods and solver settings:
- Protocols or simulation scenarios:
- Virtual population descriptors and variability assumptions:

## 7. Assumptions and Alternatives

| Assumption | Rationale | Impact if Wrong | Alternative Considered | Planned Sensitivity or Mitigation |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

## 8. Model Evaluation Plan

### 8.1 Verification

- Code checks: (e.g. version-controlled implementation; peer-reviewed diff of equations, parameters, and logic before merge)
- Equation and implementation checks: (e.g. dimensional/unit consistency check across all equations, variables, and parameters)
- Calculation checks: (e.g. solver correctness verified against an analytical or reference solution; convergence checked under decreasing solver tolerance)
- Software and reproducibility checks: (e.g. reproducibility of simulation outputs across releases/re-runs; version-pinned computational environment)

### 8.2 Validation and Applicability Assessment

- Internal validation activities:
- External validation activities, if available:
- Graphical diagnostics: (e.g. visual predictive check, goodness-of-fit plots, residual plots — pick per endpoint, don't apply the full menu blindly)
- Numerical diagnostics: (e.g. bias and precision metrics, RMSE, residual distribution statistics — pick per endpoint, don't apply the full menu blindly)
- Robustness and sensitivity analyses:
- Applicability assessment for each intended use:

### 8.3 Technical Criteria

| Criterion | Target or Acceptance Rule | Rationale | Linked Question or Output |
| --- | --- | --- | --- |
|  |  |  |  |

## 9. Analysis Workflow

- Planned sequence of model development, calibration, simulation, validation, and reporting steps:
- Human-in-the-loop decision points:
- Criteria for stopping iteration: (typically: the Technical Criteria in §8.3 are met, or a pre-specified maximum number of calibration/refinement rounds is reached without improvement)
- Criteria for escalating model complexity: (typically: a documented model-fit failure traced to a specific missing mechanism or structural limitation)
- Criteria for excluding a data source or model component: (typically: a documented, stated quality or relevance concern confirmed before exclusion — not performance-driven cherry-picking after seeing results)

## 10. Reporting Plan

- Planned figures:
- Planned tables:
- Planned model outputs:
- Planned uncertainty summaries:
- Planned comparison to technical criteria:
- Planned limitations and sensitivity analyses:

## 11. Deviations From Plan

Use this section during execution to record any deviations that must be justified in the MAR.

| Date | Deviation | Reason | Expected Impact | Approved By |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

## 12. References

- ICH M15 Guideline on general principles for model-informed drug development.
- Project literature and source artifacts:
- Prior model analysis plans or reports:

## 13. Appendices

- Assessment table details:
- Source inventory:
- Data dictionary:
- Preliminary model architecture:
- Code or command references:
