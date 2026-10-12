# Terms

Shared terminology for the ICH M15 review skills. Definitions from ICH M15 Step 5 (June 2026), Appendix 3 Glossary.

## Key Assessment Elements (§2.1)

- `Question of Interest`: the question that MIDD is intended to answer (§2.1.1)
- `Context of Use`: the role and scope of the model(s) used to answer the question of interest; includes the model, its role and scope, the data used to build it, and any additional evidence (§2.1.2)
- `Model Influence`: the intended weight of the model outcomes in decision-making, considering the contribution of additional data or evidence; rated low / medium / high with justification (§2.1.3)
- `Consequence of Wrong Decision`: the potential negative effect (e.g., on patient safety and/or lack of efficacy) resulting from an incorrect decision based on all available information; rated low / medium / high, combining severity and likelihood (§2.1.4)
- `Model Risk`: the contribution of the model outcomes to a possible wrong decision and subsequent potential undesirable consequences; derived by combining Model Influence and Consequence of Wrong Decision; rated low / medium / high; determines required model evaluation rigor (§2.1.5)

  Default combination matrix (Model Influence x Consequence of Wrong Decision):

  | Influence \ Consequence | Low | Medium | High |
  | --- | --- | --- | --- |
  | Low | Low | Low | Medium |
  | Medium | Low | Medium | High |
  | High | Medium | High | High |

  Both elements weigh equally by default: matching ratings carry straight across
  the diagonal, and an off-diagonal pair moves one step toward the higher rating.
  A documented rationale may justify a different outcome for a specific question
  (e.g. treating one element as dominant); state that rationale explicitly rather
  than deviating silently.
- `Model Impact`: the extent to which the proposed MIDD strategy varies from regulatory standards, or expectations when no regulatory standard is in place, for answering the question of interest; rated low / medium / high with justification (§2.1.6)

## Additional Considerations (§2.2)

- `Technical Criteria`: key criteria for evaluating the model and model outcomes needed to inform MIDD evidence acceptance, specific to the question of interest and commensurate with model risk (§2.2.1)
- `Appropriateness of Proposed MIDD`: the rationale for why the proposed MIDD is suitable to answer the question of interest (§2.2.2)
- `Evaluation of Model(s) and Model Outcomes`: a brief discussion of the key results and conclusions of the technical evaluation of the model and model outcomes (§2.2.3)
- `Outcome of MIDD Evidence Assessment`: the multidisciplinary team's assessment and conclusion on whether the model outcomes are considered MIDD evidence; does not refer to regulatory review activities (§2.2.4)

## Model Evaluation Elements (§3)

- `verification`: activities that ensure user-generated code for processing data and conducting analysis is error-free, equations reflecting model assumptions are correctly represented in the programming language or software, and calculations are accurate
- `validation and applicability assessment`: activities that assess model performance and robustness, including adequacy and relevance of the data, model conceptual form, model assumptions, approach to model development, graphical and numerical diagnostics, and external validation; also referred to as "fit-for-purpose"
- `applicability assessment`: focuses on the adequacy of the data and model for each intended use (distinct from appropriateness of proposed MIDD, which assesses whether the MIDD strategy is suitable)

## Reporting (§4)

- `MAP`: Model Analysis Plan; pre-defined documentation of intended model analysis, including objectives, data, methods, planned evaluation activities, and technical criteria (§4.1)
- `MAR`: Model Analysis Report; documents the results of each model analysis submitted to regulators; MAP included as appendix (§4.2)


## Development Stages

- `MIDD planning stage`: any timepoint when drug developers are planning MIDD activities, generally prior to availability of model outcomes relevant to the question of interest
- `MIDD evidence submission stage`: any timepoint when model outcomes are considered as MIDD evidence and submitted to regulators


## Other Terms

- `MIDD evidence`: model outcomes that have been determined, by application of the MIDD evidence assessment framework including model evaluation, to be appropriate to inform the answer to the question of interest
- `Model outcomes`: results derived from M&S (via model-based predictions or simulations) and associated conclusions, typically aligned to a question of interest
- `Model evaluation`: performing verification, validation, and applicability assessment of the model
- `Multidisciplinary team`: a team of subject matter experts from functional areas relevant to the question of interest and context of use
- `User-generated code`: instructions written by the user of a programming language or software

