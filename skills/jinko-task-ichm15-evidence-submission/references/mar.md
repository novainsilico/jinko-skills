# Model analysis report template

Use this template once model evaluation results are available for a model
analysis conducted against a prior Model Analysis Plan (MAP), before
submitting model outcomes to regulators as MIDD evidence.

Parenthetical `(e.g. ...)` text after a field is a generic starting menu for
that field, adapted from standard M&S practice. Pick and tailor what is
relevant to this project, or replace it entirely. Never leave the
parenthetical itself in the delivered document.

## Document control

- Project:
- Model analysis report title:
- Version:
- Date:
- Authors and roles:
- Reviewers and roles:
- Related question(s) of interest:
- Related Model Analysis Plan: (link to the Jinkō MAP document when one
  exists; otherwise a text reference to the supplied MAP content)
- Related Jinkō model URL:
- Related model snapshot ID:
- Related trial, calibration, or simulation artifacts:

## 1. Executive summary

- Overview of the rationale for the analyses:
- Brief summary of the data and methods:
- Brief summary of the results:
- Brief summary of the conclusions:
- Answer to the question of interest, if available:
- Whether model outcomes are considered MIDD evidence:

## 2. Introduction

- Rationale for the analyses:
- Relevant background information and knowledge:
- Disease, drug, population, or mechanism context:
- Description of pre-existing analyses, if applicable:
- References to previous reports or submitted analyses, if applicable:

## 3. Objectives

- Primary objective:
- Secondary objectives:
- Intended application of the model:
- Question(s) of interest addressed:
- Context of use:

## 4. Data and methods

### 4.1 Data sources

| Source | Type | Use in Analysis | Inclusion Rationale | Exclusion or Bias Assessment |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

### 4.2 Data handling

- Source data inclusion and exclusion criteria:
- Relevant study or experiment design features:
- Transformations, imputations, and unit conversions:
- Derived variables:
- Data quality limitations:

### 4.3 Modeling and simulation methods

- M&S method and model class:
- Computational platform and version:
- Jinkō model, protocol, trial, calibration, or simulation artifacts:
- Model development sequence:
- Model structure and equations:
- Parameter sources and calibration approach:
- Numerical methods and solving options:
- Prediction and simulation methods and scenarios:
- Key assumptions and strategic choices:

### 4.4 Model evaluation methods

- Verification approach:
- Validation approach:
- Applicability assessment approach:
- Robustness and sensitivity analysis approach:
- External validation approach, if applicable:
- Technical criteria for model evaluation and model outcomes:

## 5. Results

### 5.1 Data description

- Graphical and/or tabular displays of source data:
- Description and rationale for excluded data:
- Data limitations relevant to interpretation:

### 5.2 Model development results

- Final model structure:
- Parameter estimates, fixed values, calibrated values, and uncertainty:
- Model outputs and simulations:
- Jinkō model URL and snapshot metadata:

### 5.3 Model evaluation results

- Verification results:
- Validation results:
- Applicability assessment results:
- Robustness and sensitivity results:
- External validation results, if applicable:
- Technical criteria assessment:

| Technical Criterion | Result | Pass/Concern/Fail | Interpretation |
| --- | --- | --- | --- |
|  |  |  |  |

### 5.4 Deviations from the MAP

| Deviation | Justification | Impact on Results | Mitigation |
| --- | --- | --- | --- |
|  |  |  |  |

## 6. Discussion

- Interpretation of results:
- Data adequacy:
- Model adequacy:
- Model applicability to the context of use:
- Limitations of the data and model:
- Clinical, nonclinical, or strategic implications:
- Relationship to relevant prior information and knowledge:
- Impact of deviations from the MAP:
- Residual uncertainty:
- Whether additional data, model refinement, calibration, or validation is
  needed:

## 7. Conclusions

- Conclusions of the analyses:
- Answer to the question of interest:
- Whether technical criteria were met:
- Whether model outcomes are appropriate to inform the decision:
- Recommended next steps:

## 8. MIDD evidence assessment summary

| Item | Entry | Rating | Justification or Summary |
| --- | --- | --- | --- |
| Question of interest |  | Not rated¹ |  |
| Context of use |  | Not rated¹ |  |
| Model influence |  | Low / Medium / High |  |
| Consequence of wrong decision |  | Low / Medium / High |  |
| Model risk |  | Low / Medium / High |  |
| Model impact |  | Low / Medium / High |  |
| Technical criteria |  | Not rated¹ |  |
| Appropriateness of proposed MIDD |  | Not rated¹ |  |
| Evaluation of model(s) and model outcomes |  | Not rated¹ |  |
| Outcome of the MIDD evidence assessment |  | Not rated¹ |  |

*¹ Question of Interest, Context of Use, Technical Criteria, Appropriateness
of Proposed MIDD, Evaluation of Model(s) and Model Outcomes, and Outcome of
MIDD Evidence Assessment are narrative elements per ICH M15 §2.1–2.2, not
classified low/medium/high like the four Key Assessment Elements above.*

## 9. Appendices

- Model Analysis Plan:
- References list covering sources of data used for the analyses:
- Supplemental data descriptions:
- Supplemental model development and evaluation results:
- Figures and tables:
- User-generated code for relevant model(s):
- Jinkō model, protocol, trial, calibration, and data-table metadata:
- Reproducibility commands:
