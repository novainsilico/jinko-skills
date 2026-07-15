# Jinkō Skills

Agent skills for using [Jinkō](https://jinko.ai) through AI assistants, coding
agents, and agentic workflows, following the
[agentskills.io](https://agentskills.io) specification.

Jinkō is a platform for biology-grounded modeling, virtual populations, and *In-Silico* trial simulation. These skills make Jinkō easier for agents to use safely and consistently through the typed python [`jinko-sdk`](https://pypi.org/project/jinko-sdk/).

## Vision

The scientific software of tomorrow is agent-ready.

That does not mean humans disappear from the workflow. It means agents can
perform scoped, repeatable work while scientists keep control of assumptions,
interpretation, and decisions.

These skills give AI coding agents specialized, task-focused workflows for
modelers working with biology-grounded models on Jinkō.

The Jinkō UI remains the shared workspace where humans and agents can review,
correct, validate, and continue work on mechanistic modeling and in silico trial
simulation together.

Headless does not mean UI-less. It means agent-ready.

## What is Jinkō?

[Jinkō](https://doc.jinko.ai) is [Nova In Silico's](https://novainsilico.ai)
platform for biology-grounded modeling and **in silico trial simulation**:
it combines computational models with AI/ML to build digital twins and virtual
cohorts, then runs simulations that help predict outcomes.

A complete project lifecycle can run through these skills and the SDK: scope
evidence, curate data and knowledge, build or adapt a model, design multi-arm
protocols, generate virtual populations, run trials at scale, and analyze
results.

Jinkō comes in two flavors: multi-tenant SaaS (managed by Nova) or **on-premise**, deployed as a dedicated instance within your own private cloud environment, such as instances on AWS, Azure or Google Cloud Platform.

## Why Jinkō is powerful for agents

Jinkō is engineered around guarantees that make autonomous and semi-autonomous
agents safe and effective:

- **Versioned & Deterministic**: Resources are versioned and immutable;
  simulations are reproducible from their referenced inputs. An agent can re-run, diff, and revert to any prior version in one step, with no hidden state.
- **Collaboration**: Models, trials, data tables, and results are shared,
  human-readable assets. Agents, modelers, scientists, and project teams all
  operate on the same linked objects, breaking silos between R&D roles.
- **Auditability**: Every action maps to a documented REST API operation.
  Each change spawns a labeled version snapshot recording *who*, *what payload*,
  and *when*, so an agent's work is fully traceable and reviewable.
- **Verifiable loops**: The SDK exposes an actionable harness for agent workflows:
  agents can create or edit assets, call **sanity checks**, get
  feedback, apply a focused fix, and check again. Automated diagnostics cover
  issues such as unit checking failures, missing variables, invalid references,
  circular references, and trial setup problems before expensive runs start.
- **Validation & diagnostics**: Built-in calibration, goodness-of-fit, and
  quantitative validation methods let agents compare model and trial outputs
  against data and surface actionable errors instead of silent failures.
- **Efficiency & scalability**: Out-of-the-box parallelization runs large
  virtual populations and trial sweeps across many cores or a cluster, so agents
  can explore broad scenario spaces quickly.

## Available skills

Together these skills cover a broad modeler workflow: from context, setup, and
evidence scoping, through model and population design, to running in silico
trials and analyzing results.

| Skill | Purpose |
| --- | --- |
| [`jk-context`](./skills/jk-context/SKILL.md) | Core Jinkō concepts, navigation, and domain terminology. |
| [`jk-data-table`](./skills/jk-data-table/SKILL.md) | Create or inspect data tables for overlays and calibration. |
| [`jk-document`](./skills/jk-document/SKILL.md) | Create or update Jinkō documents from markdown through the SDK. |
| [`jk-task-literature-search`](./skills/jk-task-literature-search/SKILL.md) | Find and shortlist citation-grounded biomedical publications. |
| [`jk-mistral-ocr`](./skills/jk-mistral-ocr/SKILL.md) | Run one PDF through Mistral OCR with annotations and image crops. |
| [`jk-model`](./skills/jk-model/SKILL.md) | Build, edit, sanity-check, and debug Jinkō computational models. |
| [`jk-protocol`](./skills/jk-protocol/SKILL.md) | Design or edit multi-arm protocol designs. |
| [`jk-sdk-setup`](./skills/jk-sdk-setup/SKILL.md) | Authenticate and configure access to a Jinkō project. |
| [`jk-solution-and-product-guide`](./skills/jk-solution-and-product-guide/SKILL.md) | Guidance on Jinkō solutions and product features. |
| [`jk-trial`](./skills/jk-trial/SKILL.md) | Set up, sanity-check, run, poll, and download in silico trial results. |
| [`jk-trial-data-scoping`](./skills/jk-trial-data-scoping/SKILL.md) | Scope public ClinicalTrials.gov records and results availability. |
| [`jk-trial-viz`](./skills/jk-trial-viz/SKILL.md) | Create, inspect, sanity-check, and retrieve Jinkō trial visualizations. |
| [`jk-vpop`](./skills/jk-vpop/SKILL.md) | Create, generate, and inspect virtual populations. |

Need a Jinkō account? [Request a demo](https://www.jinko.ai/#Form) to get started.

## Installation

Install a skill with the [skills CLI](https://skills.sh):

```bash
npx skills add novainsilico/jinko-skills@jk-sdk-setup
```

## SDK compatibility

Skills that use the Jinkō SDK declare a compatible SDK version range in their
`SKILL.md` metadata (`requires_sdk`, a PEP 440 specifier). Install a matching
`jinko` SDK version:

```bash
pip install "jinko-sdk>=1.2,<2.0"
```

Start with `jk-sdk-setup` to verify your credentials and SDK installation before
using the workflow skills.

## License

MIT: see [LICENSE](./LICENSE).

---

Maintained by [Nova In Silico](https://www.novainsilico.ai/). This repository is
published from an internal monorepo. You can open issues, discussions, and skill
requests directly in this public GitHub repository.
