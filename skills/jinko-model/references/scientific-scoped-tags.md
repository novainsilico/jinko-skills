# Scientific scoped tags

Use these optional custom tags to make model structure easier to navigate,
group, and visualize. Apply the same interpretation across the model. They
complement `i::*`, `s::*`, and `output`; they do not replace those platform tags
or add readiness requirements.

## Scope definitions

| Scope | Question | Examples |
| --- | --- | --- |
| `granularity::*` | At what biological or spatial scale is the represented quantity defined? | `granularity::molecular`, `granularity::cellular`, `granularity::organ` |
| `phenomenon::*` | Which physical or biological process does the component represent? | `phenomenon::biochemical`, `phenomenon::hemodynamic`, `phenomenon::electrophysiological` |
| `module::*` | Which implemented mechanism or submodel contains the component? | `module::dna-damage-response`, `module::cell-cycle`, `module::hepatic-disposition` |
| `readout::*` | At what observation level is the quantity interpreted? | `readout::molecular`, `readout::cellular`, `readout::clinical` |

Scale, process, mechanism membership, and observation level are independent.
A molecular biomarker can belong to a cell-cycle mechanism and be measured in
a clinical study. A clinical observation level is separate from spatial scale.

The identifiers below are proposed naming examples for concepts used in the
literature. They are not a platform-controlled vocabulary or the tag names used
by those publications. The catalog covers major QSP, PBPK, and PK/PD domains
and is extensible. It is not a systematic, exhaustive survey of all literature.

## Selection and application

1. Inspect component definitions, descriptions, equations, units, and source
   evidence. Use a confirmed scientific interpretation. Do not derive scale from
   component type alone: a Species can represent a molecule or a cell population.
2. Use lowercase kebab-case values after `::`. Reuse an existing identifier when
   its description fits. Document a new value rather than creating a synonym.
3. Prefer one primary granularity for a layer view. A cross-scale component can
   carry more than one justified value, with an explicit placement rule in the
   visualization. The tags themselves do not define layer order.
4. Add phenomenon tags for processes represented by the component or its
   equations. Add module tags for mechanisms actually implemented. A disease,
   target, or outcome mentioned in a paper does not establish module membership.
5. Allow multiple module memberships for shared states, couplings, and kinetic
   parameters. Use directly governed processes to classify a kinetic parameter;
   whole-graph reachability alone is insufficient. Give an ODE its governed
   state's interpretation when that relationship is explicit.
6. Apply readout tags to observed quantities, output variables, or explicit
   observation functions. Add `readout::clinical` only when the quantity has a
   defined clinical observation or endpoint interpretation. A molecular output
   in a human-cell model does not acquire a clinical interpretation automatically.
7. Leave unsupported scopes unassigned and report the missing interpretation.
   Solver clocks, numerical conversion factors, and bookkeeping volumes may
   have no biological scale. Do not use an Unclassified tag to imply a scale.
8. Create only the custom declarations that the model needs with
   `model.create_tag(tag_id, description=..., color=...)`; reuse existing declarations.
   Use the family colors in the skill's Required Workflow section. Align existing
   tag colors with `tag.set_color(...)` when requested. Keep tag-family colors
   separate from graph component-type colors.
   Attach them through the component methods described in
   [model components](model-components.md). Batch related attachments, preserve
   existing tags, re-fetch, and verify the saved assignments. A metadata-only
   update should preserve equations, values, units, and solver settings.

For a new classification, record component ID, proposed tags, rationale, and
source in a local table first. Use immutable IDs to connect this table to graph
nodes. Preserve uncertain entries for review. A grouped graph remains a view of
the model; tags do not provide equations for a reduced or cross-scale model.

## Granularity examples

| Tag | Typical represented quantity |
| --- | --- |
| `granularity::atomic` | Explicit atomic interactions or structural coordinates |
| `granularity::molecular` | Resolved protein, metabolite, complex, receptor occupancy, or molecular reaction rate |
| `granularity::subcellular` | Organelle state, intracellular spatial domain, or membrane-domain quantity |
| `granularity::cellular` | Individual-cell state, cell count, cell phenotype, or lumped cellular response |
| `granularity::tissue` | Tissue-averaged process, extracellular matrix, or local microenvironment |
| `granularity::organ` | Organ volume, organ flow, or explicitly organ-aggregated function |
| `granularity::organism` | Whole-body physiology, body mass, or systemic balance |
| `granularity::population` | Explicit population-level quantity or transmission state, when the model represents it |

Choose scale from the modeled quantity and its aggregation. A compartment name
or a molecule's anatomical location alone does not determine scale. An empirical
PK peripheral compartment need not correspond to a specific organ. A Vpop of
organism-scale models does not make every component population-scale.

## Phenomenon examples

Each value in the second column takes the prefix `phenomenon::`. Choose a broad
value for an overview or a more specific value when the equations support it.
Document the intended relationship if broad and specific values coexist.

| Family | Example values | Typical use |
| --- | --- | --- |
| Biochemical reactions | `biochemical`, `binding`, `unbinding`, `enzymatic-catalysis`, `phosphorylation`, `dephosphorylation`, `proteolysis`, `metabolic-conversion` | Molecular interactions, catalytic rates, and biochemical networks |
| Gene and protein regulation | `gene-expression`, `transcription`, `translation`, `protein-synthesis`, `protein-degradation`, `protein-turnover`, `receptor-turnover`, `signal-transduction` | Expression, signaling, and regulated protein abundance |
| Physical chemistry | `ionization`, `acid-base-equilibrium`, `partitioning`, `dissolution`, `precipitation`, `aggregation`, `adsorption` | Formulation, tissue partitioning, and pH-dependent behavior |
| Passive transport | `diffusion`, `convection`, `advection`, `membrane-permeation`, `osmosis`, `filtration`, `gas-exchange`, `oxygen-transport` | Concentration transport, membranes, and fluid or gas exchange |
| Active and vesicular transport | `active-transport`, `transporter-mediated-uptake`, `transporter-mediated-efflux`, `endocytosis`, `exocytosis`, `intracellular-trafficking`, `nuclear-transport`, `lymphatic-transport` | Transporters, organelles, biologics, and cellular trafficking |
| Mechanics | `mechanical`, `elasticity`, `viscoelasticity`, `contraction`, `mechanotransduction`, `pressure-flow-coupling` | Tissue deformation, cardiac mechanics, and mechanically regulated responses |
| Hemodynamics and fluid balance | `hemodynamic`, `perfusion`, `vascular-resistance`, `fluid-balance`, `sodium-balance`, `glomerular-filtration` | Circulation, renal physiology, and volume regulation |
| Electrophysiology | `electrophysiological`, `ion-channel-gating`, `membrane-depolarization`, `action-potential-propagation`, `calcium-dynamics`, `synaptic-transmission` | Cardiac or neuronal electrical activity and excitation coupling |
| Cell dynamics | `cell-proliferation`, `cell-cycle-progression`, `cell-differentiation`, `cell-migration`, `cell-death`, `apoptosis`, `necrosis`, `senescence` | Cell populations, growth, and fate mechanisms |
| Immune and inflammatory processes | `immune-activation`, `antigen-presentation`, `immune-cell-recruitment`, `inflammatory-signaling`, `complement-activation`, `immune-mediated-killing`, `antibody-production` | Innate/adaptive responses, inflammation, and immunotherapy |
| Pathogen dynamics | `pathogen-replication`, `viral-entry`, `viral-release`, `bacterial-growth`, `pathogen-clearance` | Infection and antimicrobial response |
| Tissue maintenance | `tissue-remodeling`, `wound-healing`, `extracellular-matrix-turnover`, `fibrosis`, `bone-turnover`, `angiogenesis`, `tissue-injury` | Repair, structural change, and progressive disease |
| Homeostatic regulation | `hormonal-feedback`, `glucose-homeostasis`, `lipid-homeostasis`, `iron-homeostasis`, `calcium-phosphate-homeostasis`, `circadian-regulation`, `thermoregulation` | Endocrine axes and physiological balances |
| Drug disposition | `drug-absorption`, `drug-distribution`, `drug-metabolism`, `drug-excretion`, `plasma-protein-binding`, `blood-cell-partitioning`, `enterohepatic-recirculation` | ADME and PBPK |
| Drug action and adaptation | `drug-target-binding`, `target-mediated-drug-disposition`, `enzyme-inhibition`, `enzyme-induction`, `receptor-desensitization`, `tolerance`, `sensitization`, `drug-resistance` | PK/PD, target interactions, and adaptive responses |
| Hemostasis | `coagulation`, `platelet-activation`, `fibrinolysis`, `thrombus-formation` | Clotting, antithrombotic effects, and related disease models |

An empirical Emax function can describe drug effect without establishing which
biochemical mechanism produces it. Use a supported module such as direct effect
and leave the mechanistic phenomenon unassigned if it is unknown.

## Module examples

Each value below takes the prefix `module::`. A module names an implemented
mechanism or submodel. Select the appropriate subset; do not instantiate the
catalog as unused declarations. Use organ names for explicit PBPK organ
submodels, not to infer anatomy for empirical compartments.

| Domain | Example values |
| --- | --- |
| Molecular and cell regulation | `dna-damage-response`, `dna-repair`, `cell-cycle`, `p53-mdm2-feedback`, `receptor-signaling`, `mapk-signaling`, `pi3k-akt-mtor-signaling`, `jak-stat-signaling`, `nf-kb-signaling`, `wnt-signaling`, `notch-signaling`, `tgf-beta-signaling`, `protein-turnover`, `apoptosis` |
| Oncology and immuno-oncology | `tumor-growth`, `tumor-microenvironment`, `angiogenesis`, `tumor-immune-interaction`, `immune-checkpoint-regulation`, `checkpoint-blockade`, `t-cell-engagement`, `car-t-cell-dynamics`, `antibody-drug-conjugate-delivery`, `drug-resistance` |
| Immunology and inflammation | `innate-immunity`, `adaptive-immunity`, `antigen-presentation`, `t-cell-activation`, `b-cell-activation`, `antibody-production`, `cytokine-network`, `complement`, `macrophage-polarization`, `immune-cell-trafficking`, `inflammation`, `autoimmunity`, `immunogenicity`, `cytokine-release` |
| Infection and vaccination | `viral-life-cycle`, `bacterial-growth`, `host-pathogen-interaction`, `antimicrobial-response`, `vaccine-response` |
| Cardiovascular regulation | `systemic-circulation`, `pulmonary-circulation`, `cardiac-electrophysiology`, `cardiac-mechanics`, `vascular-tone`, `blood-pressure-regulation`, `cardiac-remodeling` |
| Renal and volume regulation | `renin-angiotensin-aldosterone-system`, `renal-hemodynamics`, `glomerular-filtration`, `tubular-transport`, `water-sodium-balance`, `acid-base-balance` |
| Respiratory physiology | `ventilation`, `gas-exchange`, `airway-mechanics`, `airway-inflammation`, `alveolar-transport`, `mucociliary-clearance` |
| Metabolic and endocrine physiology | `glucose-insulin`, `pancreatic-beta-cell`, `hepatic-glucose-production`, `glucose-utilization`, `incretin-signaling`, `lipid-metabolism`, `lipoprotein-metabolism`, `hepatic-steatosis`, `energy-balance`, `thyroid-axis`, `hypothalamic-pituitary-adrenal-axis`, `reproductive-hormones`, `calcium-phosphate-homeostasis`, `bone-remodeling` |
| Hematology and hemostasis | `hematopoiesis`, `erythropoiesis`, `granulopoiesis`, `thrombopoiesis`, `platelet-activation`, `coagulation`, `fibrinolysis`, `iron-homeostasis` |
| Neuroscience | `neuronal-excitability`, `synaptic-transmission`, `neurotransmitter-turnover`, `neuroinflammation`, `amyloid-beta-turnover`, `tau-pathology`, `sleep-wake-regulation` |
| Tissue injury and repair | `tissue-injury`, `wound-healing`, `extracellular-matrix`, `fibrosis`, `hepatic-injury`, `renal-injury` |
| PBPK absorption and formulation | `oral-absorption`, `gastrointestinal-transit`, `dissolution`, `precipitation`, `intestinal-permeation`, `intestinal-metabolism`, `subcutaneous-depot`, `intramuscular-depot`, `inhalation-deposition`, `dermal-absorption` |
| PBPK distribution and clearance | `tissue-distribution`, `hepatic-disposition`, `renal-disposition`, `biliary-excretion`, `enterohepatic-recirculation`, `plasma-protein-binding`, `blood-cell-partitioning`, `transporter-kinetics`, `lymphatic-distribution`, `enzyme-turnover`, `transporter-turnover`, `drug-drug-interaction` |
| Explicit PBPK organ submodels | `pbpk-liver`, `pbpk-kidney`, `pbpk-brain`, `pbpk-lung`, `pbpk-heart`, `pbpk-spleen`, `pbpk-muscle`, `pbpk-adipose`, `pbpk-bone`, `pbpk-skin`, `pbpk-gut`, `pbpk-placenta`, `pbpk-fetus`, `pbpk-arterial-blood`, `pbpk-venous-blood` |
| Biologics disposition | `target-mediated-disposition`, `fcrn-recycling`, `receptor-internalization`, `antibody-catabolism`, `antibody-drug-conjugate-payload`, `ocular-disposition`, `intrathecal-disposition` |
| Classical PK/PD | `absorption`, `central-pk`, `peripheral-pk`, `effect-compartment`, `receptor-occupancy`, `direct-effect`, `indirect-response`, `transit-response`, `signal-transduction`, `disease-progression`, `tolerance`, `drug-induced-myelosuppression`, `exposure-response`, `population-covariates` |

Keep model family and mechanism distinct. A PBPK model can include a target
binding module. A QSP model can include empirical PK and an organ physiology
module. PK/PD delay or disease-progression structure does not by itself establish
a molecular pathway. An administration schedule also retains its `i::protocol`
inputs; a module tag does not make those inputs overridable.

## Readout examples

| Tag | Interpretation |
| --- | --- |
| `readout::molecular` | Protein/metabolite abundance, receptor occupancy, or molecular activity |
| `readout::cellular` | Cell count, cell viability, phenotype, or cell-level function |
| `readout::tissue` | Tissue histology, matrix burden, or tissue-local measurement |
| `readout::organ` | Organ-level volume, function, imaging, or flow measurement |
| `readout::organism` | Whole-body balance or integrated physiological measurement |
| `readout::clinical` | Defined patient biomarker, clinical measurement, or endpoint observation |

Separate the observation function from the biological state when the model
contains both. For example, a clinical tumor-diameter measurement can map from
a tumor-cell state. Tag each according to its interpretation and preserve the
mapping. Do not imply a clinical endpoint from an unvalidated visual grouping.

## Worked selections

- **Cell-cycle/DNA-damage model:** a source-identified p53 protein state can carry
  `granularity::molecular`, `phenomenon::biochemical`, and
  `module::dna-damage-response`. Add `readout::molecular` when it is an output.
  A lumped damage-intensity state can instead be cellular-scale. Shared p21
  checkpoint components can carry both damage-response and cell-cycle modules.
- **PBPK liver submodel:** an explicit liver volume can carry
  `granularity::organ` and `module::pbpk-liver`. Hepatic metabolic rates can
  carry `phenomenon::drug-metabolism` and `module::hepatic-disposition`.
  Tag each quantity at its own scale rather than copying the volume's scale to
  every enzyme, transporter, and concentration in that submodel.
- **PK/PD turnover model:** an indirect-response equation can carry
  `module::indirect-response`. Assign its granularity and readout from the
  modeled response variable. A cell count supports a cellular interpretation;
  a defined patient biomarker can support a clinical readout. The equation form
  alone does not identify its biology.

## Literature basis

These sources establish the model families and representative mechanisms used
in the catalog. The naming convention and identifiers are proposed here.

- Iwamoto et al. (2011). *Mathematical modeling of cell cycle regulation in
  response to DNA damage: Exploring mechanisms of cell-fate determination*.
  BioSystems 103, 384–391. [DOI](https://doi.org/10.1016/j.biosystems.2010.11.011).
  Sections 2.1–2.5 and supplementary Tables S1–S3 support the cell-cycle example.
- Knight-Schrijver et al. (2016). *The promises of quantitative systems
  pharmacology modelling for drug development*. Computational and Structural
  Biotechnology Journal 14, 363–370.
  [Full text](https://europepmc.org/articles/PMC5064996).
  Reviews QSP and related disease-model coverage.
- Gadkar et al. (2016). *Quantitative systems pharmacology: a promising approach
  for translational pharmacology*. Drug Discovery Today: Technologies 21–22,
  57–65. [DOI](https://doi.org/10.1016/j.ddtec.2016.11.001).
  Includes asthma, MAPK signaling, and pediatric PBPK examples.
- Jones and Rowland-Yeo (2013). *Basic concepts in physiologically based
  pharmacokinetic modeling in drug discovery and development*. CPT:
  Pharmacometrics & Systems Pharmacology 2, e63.
  [Full text](https://europepmc.org/articles/PMC3828005).
  Covers organ compartments, perfusion/permeability, ADME, binding, transport,
  oral absorption, and population physiology.
- Mager and Jusko (2001). *General pharmacokinetic model for drugs exhibiting
  target-mediated drug disposition*. Journal of Pharmacokinetics and
  Pharmacodynamics 28, 507–532.
  [DOI](https://doi.org/10.1023/A:1014414520282).
- Dayneka, Garg, and Jusko (1993). *Comparison of four basic models of indirect
  pharmacodynamic responses*. Journal of Pharmacokinetics and Biopharmaceutics
  21, 457–478. [DOI](https://doi.org/10.1007/BF01061691).
- Friberg et al. (2002). *Model of chemotherapy-induced myelosuppression with
  parameter consistency across drugs*. Journal of Clinical Oncology 20,
  4713–4721. [DOI](https://doi.org/10.1200/JCO.2002.02.140).
- Rieger, Allen, and Musante (2022). *A quantitative systems pharmacology model
  of liver lipid metabolism for investigation of non-alcoholic fatty liver
  disease*. Frontiers in Pharmacology 13, 910789.
  [Full text](https://europepmc.org/articles/PMC9343875).
