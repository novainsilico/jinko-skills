---
name: jinko
description: >-
  Apex orchestrator for end-to-end Jinkō QSP / mechanistic modeling projects.
  Use whenever the user is doing anything Jinkō can do: building or editing a
  mechanistic or ODE (system-of-differential-equations) model — tumor-growth,
  viral, cellular-kinetics, PK, or exposure–response; gathering literature or
  clinical-trial evidence; extracting observed data; calibrating or fitting
  parameters to preclinical or clinical data; estimating parameters with
  credible intervals; sensitivity analysis; generating a virtual population for
  inter-subject variability; simulating dose scenarios or predicting a minimum
  effective dose; running in-silico trials; visualizing results; or writing a
  report. Trigger proactively at the start of any Jinkō modeling session, even
  when the user names only a single step: it sequences the project, keeps
  "where we are" legible, loads (or offers to install) the right jinko-* skill
  per step, and surfaces what Jinkō is doing. It orchestrates; jinko-* skills
  execute.
metadata:
  author: Nova In Silico
license: MIT
---

# Jinkō

This skill coordinates an **end-to-end** Jinkō modeling project inside an
agentic session in any skill-aware host. Its job is orchestration, not
execution: it decides *what comes next*, keeps *where we are* legible, and makes
sure the session *showcases* what Jinkō is doing at every step. Everything about
*how* to perform a given step lives in a dedicated `jinko-*` skill, and this
skill delegates to it rather than reimplementing it.

Three things this skill is responsible for, that no single `jinko-*` skill owns:

- **Sequence.** Drive the project through the pipeline spine below in dependency
  order, loading the right skill at each step.
- **Follow-up ("where we are").** Keep the state of the project continuously
  legible: an approved plan whose steps mirror the spine, updated live, and a
  named artifact produced at the end of every step so progress is tangible, not
  narrative.
- **Capability highlighting.** Make the session actively surface Jinkō's
  capabilities instead of treating the platform as invisible plumbing.

## How to use this skill

1. **Orient first.** At the start of a session, establish the spine for *this*
   project: which stages are needed, in what order, and where the user already
   is. Propose the plan and get the user's agreement before doing heavy work.
2. **Load the owner skill for the current step.** Each stage names the `jinko-*`
   skill that owns the *how*. Load that skill and let it perform the step. Do not
   duplicate its behavior here — this skill only sequences and tracks.
3. **Find or install what is missing.** If an owner skill is not available in
   the session, check the available skills for its name. If it is not found,
    tell the user to install it from `novainsilico/jinko-skills` before
   proceeding.
4. **Close every step with a named artifact** and update the plan (see
   *Keep "where we are" legible*).
5. **Skip or reorder stages a project does not need**, but keep the dependency
   order: a trial needs a model; a protocol or vpop needs model-defined inputs;
   calibration needs observed data and a model.

## Pipeline spine

Sequence the project through these stages. Each names the skill that owns the
"how"; decide from context what marks a step done and what artifact to produce.

- **Connect & orient** — `jinko-sdk-setup` (connection); `jinko-context`
  (vocabulary & navigation); `jinko-solution-and-product-guide` (library
  fast-start).
- **Observed data** — `jinko-data-table`.
- **Model build** — `jinko-model`.
- **Calibration** — `jinko-calibration-cmaes`.
- **Protocol** — `jinko-protocol`.
- **Virtual population** — `jinko-vpop`.
- **Trial** — `jinko-trial`.
- **Visualization** — `jinko-trial-viz`.
- **Report** — `jinko-document`.

Dependency notes: **Model build** precedes **Protocol**, **Virtual
population**, and **Trial**. **Calibration** needs **Observed data** and a built
model. **Evidence gathering** and **Observed data** can run early and in
parallel. **Visualization** and **Report** come after results exist.

## Keep "where we are" legible

- **Maintain a live plan** whose steps mirror the spine, and offer an
  at-a-glance answer to "where are we?" at any time — which stages are done, in
  progress, or skipped, and the artifact each produced.
- **End every step with a named artifact** (a model id, a vpop CSV, a results
  DataFrame, a figure, a document). Named artifacts are what make progress
  tangible and let a resumed session reconstruct state instantly. Save figures
  as artifacts and embed them inline.
- **Print the Jinkō link whenever possible.** Whenever a step produces a Jinkō
  resource with a SID, surface it as `https://jinko.ai/<sid>` so the user can
  open it directly. A resolvable link is the preferred form of an artifact.
- **On resume**, reconstruct state from the plan, the named artifacts, and the
  Jinkō project items *before* doing new work; report "where we are" in spine
  terms before proposing the next step.

## Highlighting Jinkō capabilities (required)

The session should not treat Jinkō as invisible plumbing. At each step, make the
platform capability explicit:

- **Name the capability at the moment it is exercised.** When a step runs a
  trial, generates a vpop, or calibrates, add a one-line note on *what Jinkō is
  doing and why it is the right tool for it* (calibration, in-silico trials,
  traceability via snapshots, collaborative native visualizations). Each step
  becomes a small, concrete capability demonstration.
- **Speak Jinkō's domain language.** Use `jinko-context` terminology —
  snapshots, sources, extracts, protocols, vpops, calibration — instead of
  generic "dataset / run / model".
- **Prefer native Jinkō surfaces for durable outputs.** Use fast in-session
  plots for iteration, then promote settled views into native
  **TrialVisualization** items (`jinko-trial-viz`) and a living **document**
  (`jinko-document`) so collaborators see results in Jinkō without opening the
  session.
- **Start from the library, not a blank slate.** Highlight the model library as
  a fast-start capability — begin from a candidate that matches the mechanism
  (`jinko-solution-and-product-guide`) rather than authoring from zero.
- **Motivate, don't oversell.** Follow `jinko-solution-and-product-guide`
  principles: tie each capability callout to the scientific or operational need
  it serves, and flag limitations and data dependencies honestly.

## Loading and installing skills

For each stage, load the owner skill listed in the spine and let it drive the
step. If a jinko skill is not available in the context, check the available skills
for its name. If it is not found, tell the user to install it from
`novainsilico/jinko-skills` before continuing. Never inline a skill's mechanics
here; if a needed capability has no owner skill available, say so and propose the
closest available path rather than improvising the "how".
