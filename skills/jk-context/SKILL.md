---
name: jk-context
description: >-
  Explain core Jinkō context, navigation, version management, and domain language for agents and users. Use this skill whenever the user needs a mental model of Jinkō projects, folders, project items, snapshots, sources, extracts, protocols, trials, calibration, virtual populations, references, or modeling context; when translating between generic terms and Jinkō terminology; or when an agent needs orientation before navigating or modifying Jinkō artifacts. This skill is conceptual and terminology-focused; use dedicated jk-* workflow skills for creating or editing specific artifacts.
metadata:
  author: Nova In Silico
license: MIT
---

# Jinkō Context

Use this skill to explain Jinkō's shared mental model and vocabulary. Keep answers practical: the goal is to help a user or agent navigate Jinkō artifacts without confusing project organization, scientific content, and immutable versions.

## Navigation and Version Management

Jinkō project navigation behaves much like working in a Git repository, but for scientific modeling artifacts instead of source-code files.

- A **Project** is like the repository: it is the boundary for a concrete scientific modeling effort, including sources, data, models, protocols, trials, reports, and collaboration history.
- **Folders** are like repository directories: they organize related project items by workflow, experiment, disease area, evidence package, or analysis thread. Folders help humans and agents find context, but they are not themselves the scientific artifact.
- **Project Items** are like tracked files or domain objects in the repository: each item has an identity and represents a Jinkō artifact such as a model, protocol, trial, data table, source, output set, report, or folder-like organizational item.
- **Snapshots** are like immutable commits for a specific project item: each snapshot captures the content of that item at a point in time. The latest snapshot is the head, while older snapshots remain available for traceability and comparison.

This Git-like structure makes Jinkō easier for agents to navigate because agents can separate three questions:

- Where is the work organized? Look at the project and folders.
- Which artifact is being discussed? Identify the project item.
- Which exact state of the artifact matters? Use the snapshot, or use head when the user wants the latest state.

Use `Project`, `Project Item`, and `Snapshot` rather than generic words like workspace, file, upload, save, version, revision, or commit unless you are explicitly making the Git analogy.

## Domain Language

**Project**:
A concrete scientific modeling effort with its own sources, data, modeling artifacts, and reports.
Avoid: workspace, case, study folder.

**Folder**:
An organizational container inside a project used to group related project items. Folders support navigation and workflow hygiene; they do not replace item identity or snapshot identity.
Avoid: directory when speaking to end users unless making the Git analogy.

**Project Item**:
A named Jinkō object inside a project, such as a source, model, protocol, trial, data table, output set, report, or folder. A project item has stable identity across snapshots.
Avoid: file, asset, object when precision matters.

**Snapshot**:
An immutable version of a Jinkō model, protocol, trial, or related Jinkō core item. A snapshot captures one exact state of a project item and enables traceable comparison or restoration.
Avoid: revision, save, version, commit except when explaining the analogy.

**Source**:
An immutable scientific input, usually a paper PDF, used as evidence for extraction and modeling.
Avoid: document, file, upload.

**Extract**:
A structured piece of information derived from a source, such as a parameter value, clinical endpoint, experimental condition, mechanism statement, data series, or assumption. Extracts should stay linked to the source evidence that justifies them.
Avoid: note, snippet, untracked fact.

**Model**:
A Jinkō-compatible executable representation of the biological or pharmacological mechanism being modeled.
Avoid: model file, script.

**Protocol**:
The Jinkō artifact that defines trial arms, interventions, dosing or treatment conditions, and simulation timing.
Avoid: study design, scenario file.

**Trial**:
The Jinkō artifact that combines a protocol, model, output sets, and data tables for simulation or comparison.
Avoid: run, simulation setup.

**Calibration**:
The stage that adjusts model parameters so simulations fit selected experimental evidence.
Avoid: fitting, tuning.

**Calibration Candidate**:
A model-intrinsic parameter proposed for calibration. It may be marked with a `toCalibrate` model tag.
Avoid: free parameter, tuned knob.

**Virtual Population**:
A generated population of parameterized virtual subjects used for in-silico trial execution.
Avoid: cohort, sample.

**Reference**:
The trace from a model, dataset, or report assertion back to the source evidence or assumptions that justify it.
Avoid: citation, provenance.

**Modeling Context**:
The full scientific, protocol, trial, source, and artifact background needed to build or refine a Jinkō Model.
Avoid: extraction catalog, model input bundle.

## Relationships

- A **Project** contains one or more **Project Items**.
- A **Folder** organizes Project Items within a Project.
- A **Project Item** has one or more **Snapshots**.
- A **Snapshot** captures the immutable content of one Project Item at a point in time.
- A **Source** supports one or more **Extracts**.
- An **Extract** should retain a **Reference** to its Source evidence.
- A **Model** represents executable biological or pharmacological mechanisms.
- A **Protocol** defines arms, interventions, and timing used by a Trial.
- A **Trial** uses a **Protocol**, a **Model**, output sets or measures, and optional transformed data overlays.
- A **Calibration** uses selected evidence and outputs to adjust Calibration Candidates.
- A **Virtual Population** provides parameterized virtual subjects for Trial execution.
- A **Reference** links Project Items, Model components, Trial outputs, data tables, and reports back to Sources or explicit assumptions.
- A **Modeling Context** gathers the relevant Sources, Extracts, References, Models, Protocols, Trials, and reports needed to make a modeling decision.

## Response Guidance

- Translate user language into Jinkō language when it improves precision.
- Preserve the Git analogy for orientation, but do not imply Jinkō is literally Git.
- Distinguish stable item identity from immutable snapshot identity.
- Use head/latest only when the user wants the current state; name snapshots when exact reproducibility matters.
- Route implementation tasks to the relevant skill: `jk-model`, `jk-protocol`, `jk-trial`, `jk-vpop`, `jk-data-table`, or `jk-sdk-setup`.
