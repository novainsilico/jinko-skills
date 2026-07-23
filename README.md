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

## Installation

The skills in this repository are inter-dependant, and not meant to be picked individually; we strongly recommend you install all the Jinkō skills at once, and use an update method that can reliably get new ones.

### Claude Code

In Claude Code, to add the Jinkō marketplace (this repo) and install its plugin:

```
/plugin marketplace add novainsilico/jinko-skills
/plugin install jinko-skills@jinko
/reload-plugins # Or restart claude code
```

### Claude Science

In Claude Science's settings, go to Skills > Add skill > Import from GitHub > type "novainsilico/jinko-skills" > Preview > Import skills.

### Codex

Add the Jinkō marketplace using either method:

- **Codex interface:** Open Codex, run `/plugins`, select `Add Marketplace`,
  and enter `novainsilico/jinko-skills`.
- **Terminal:**

```bash
codex plugin marketplace add novainsilico/jinko-skills
```

Then open `/plugins`, select the Jinkō marketplace, search for **Jinko**, and
install the plugin. Start a new Codex session after installation.

### Other agents and custom installations

Jinkō Skills work with most agents that support the
[Agent Skills specification](https://agentskills.io). Use the
[skills CLI](https://skills.sh) to install every skill in this repository; the
installer will guide you through the agent-specific setup:

```bash
npx skills add novainsilico/jinko-skills --skill '*'
```

You can also copy the `skills` directory to your agent's skills location and
manage updates manually.

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
| [`jinko`](./skills/jinko/SKILL.md) | Orchestrate end-to-end Jinkō modeling workflows across the published skill set. |
| [`jinko-calibration-cmaes`](./skills/jinko-calibration-cmaes/SKILL.md) | Create, run, poll, and inspect CMA-ES calibrations through the SDK. |
| [`jinko-context`](./skills/jinko-context/SKILL.md) | Core Jinkō concepts, navigation, and domain terminology. |
| [`jinko-data-table`](./skills/jinko-data-table/SKILL.md) | Create or inspect data tables for overlays and calibration. |
| [`jinko-document`](./skills/jinko-document/SKILL.md) | Create or update Jinkō documents from markdown through the SDK. |
| [`jinko-model`](./skills/jinko-model/SKILL.md) | Build, edit, sanity-check, and debug Jinkō computational models. |
| [`jinko-output-set`](./skills/jinko-output-set/SKILL.md) | Create, inspect, validate, and edit simple and advanced output sets through the SDK. |
| [`jinko-protocol`](./skills/jinko-protocol/SKILL.md) | Design or edit multi-arm protocol designs. |
| [`jinko-sdk-setup`](./skills/jinko-sdk-setup/SKILL.md) | Authenticate and configure access to a Jinkō project. |
| [`jinko-solution-and-product-guide`](./skills/jinko-solution-and-product-guide/SKILL.md) | Guidance on Jinkō solutions and product features. |
| [`jinko-trial`](./skills/jinko-trial/SKILL.md) | Set up, sanity-check, run, poll, and download in silico trial results. |
| [`jinko-trial-viz`](./skills/jinko-trial-viz/SKILL.md) | Create, inspect, sanity-check, and retrieve Jinkō trial visualizations. |
| [`jinko-vpop`](./skills/jinko-vpop/SKILL.md) | Create, generate, and inspect virtual populations. |

Need a Jinkō account? [Request a demo](https://www.jinko.ai/#Form) to get started.

## SDK compatibility

Skills that use the Jinkō SDK declare a compatible SDK version range in their
`SKILL.md` metadata (`requires_sdk`, a PEP 440 specifier). Install a matching
`jinko` SDK version:

```bash
pip install "jinko-sdk>=1.2,<2.0"
```

Start with `jinko-sdk-setup` to verify your credentials and SDK installation before
using the workflow skills.

## License

MIT: see [LICENSE](./LICENSE).

---

Maintained by [Nova In Silico](https://www.novainsilico.ai/). This repository is
published from an internal monorepo. You can open issues, discussions, and skill
requests directly in this public GitHub repository.
