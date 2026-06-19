# Jinkō Skills

Agent skills for [Jinkō](https://jinko.ai) QSP modeling workflows, following the
[agentskills.io](https://agentskills.io) specification.

These skills give AI coding agents specialized, task-focused workflows for
building and running quantitative systems pharmacology (QSP) models on Jinkō
through the [`jinko` Python SDK](https://pypi.org/project/jinko/).

## What is Jinkō?

[Jinkō](https://doc.jinko.ai) is [Nova In Silico's](https://novainsilico.ai)
cloud platform for **in-silico clinical trials**: it combines mechanistic
disease modeling (QSP / PK-PD) with AI/ML to build virtual patients and entire
virtual populations, then runs simulated trials that predict clinical outcomes.
The approach has been validated against real studies — for example
[prospectively reproducing the Phase III FLAURA2 lung-cancer trial](https://www.novainsilico.ai/wp-content/uploads/2024/06/FLAURA2_2024_POSTER_NSCLC_ASCO.pdf)
within hours.

A complete project lifecycle runs through these skills and the SDK: curate
data and knowledge, build or adapt a model, design multi-arm protocols,
generate virtual populations, run trials at scale, and analyze results — all
without leaving your agentic toolchain.

## Why Jinkō is powerful for agents

Jinkō is engineered around guarantees that make autonomous and semi-autonomous
agents safe and effective:

- **Collaboration**: Models, trials, data tables, and results are shared,
  human-readable assets. Agents, modelers, scientists, and trial managers all
  operate on the same linked objects, breaking silos between R&D roles.
- **Auditability**: Every action maps to a documented REST API operation.
  Each change spawns a labeled version snapshot recording *who*, *what payload*,
  and *when*, so an agent's work is fully traceable and reviewable.
- **Deterministic & immutable**: Resources are versioned and immutable;
  simulations are reproducible from their referenced inputs. An agent can re-run,
  diff, and revert to any prior version in one step, with no hidden state.
- **Validation & diagnostics**: Built-in calibration, goodness-of-fit, and
  quantitative validation methods let agents check model and trial outputs
  against data and surface actionable errors instead of silent failures.
- **Efficiency & scalability**: Out-of-the-box parallelization runs large
  virtual populations and trial sweeps across many cores or a cluster, so agents
  can explore broad scenario spaces quickly.

The platform's own AI assistant, [Kōhai](https://doc.jinko.ai/docs/platform/core-features-AI/kohai-philosophy/),
embodies the same contract: it can do nothing a user could not do via the UI or
API, keeps the human in the loop, and records every action as a reversible
version. These skills give external agents that same bounded, auditable surface.

## Available skills

Together these skills cover the full in-silico trial lifecycle — from context
and setup, through modeling and population design, to running trials and
analyzing results.

| Skill | Purpose |
| --- | --- |
| `jk-context` | Core Jinkō concepts, navigation, and domain terminology. |
| `jk-sdk-setup` | Authenticate and configure access to a Jinkō project. |
| `jk-model` | Build or edit Jinkō computational models (QSP / PK-PD). |
| `jk-protocol` | Design or edit multi-arm protocol designs. |
| `jk-vpop` | Create, generate, and inspect virtual populations. |
| `jk-data-table` | Create or inspect data tables for overlays and calibration. |
| `jk-trial` | Set up, run, poll, and download in-silico trial results. |
| `jk-solution-and-product-guide` | Guidance on Jinkō solutions and product features. |

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
pip install "jinko>=1.2,<2.0"
```

Start with `jk-sdk-setup` to verify your credentials and SDK installation before
using the workflow skills.

## License

MIT — see [LICENSE](./LICENSE).

---

Maintained by [Nova In Silico](https://novainsilico.ai). This repository is
published from an internal monorepo; please open issues and discussion at the
public repository.
