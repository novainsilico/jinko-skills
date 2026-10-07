# Changelog

## 1.13.0 (2026-10-07)

### Highlights

- Organization API keys now reach several projects: `JinkoOrgClient` lists the projects a key sees and opens a project client for any of them, and the connection check works without a project id.
- `jinko-model` can now tag model components by scale, phenomenon, module, and readout, so a model is easier to navigate and visualize.

### Skills

#### Added

- `jinko-model`: optional scientific scoped tags, `granularity::*`, `phenomenon::*`, `module::*`, and `readout::*`, with a reference that gives the selection rules, the family colors, and a catalog of QSP, PBPK, and PK/PD examples.

#### Changed

- `jinko-sdk-setup`: tells you when to use `JinkoClient` and when to use `JinkoOrgClient`, describes what the connection check reports with and without `JINKO_PROJECT_ID`, and marks the project id as optional in the example `.env`.

### SDK

#### Added

- `JinkoOrgClient`, a client for the organization routes that needs no project id. It lists the projects an API key sees, opens a regular `JinkoClient` for one of them, creates a project in a group, and lists, reads, creates, and renames groups.

#### Changed

- `python -m jinko.cli.check_jinko_connection` no longer requires `JINKO_PROJECT_ID`. Without it, the check lists the projects the key sees. With it, the success line also names the key type.
- `PopCalibration.pwres()` and `PopCalibration.npde()` now take the distribution sample count, which the Jinkō core requires.
- Model interface diff types now carry `from`, `to`, and `isIdentical` instead of `current` and `incoming`.

#### Fixed

- Supplementary material uploaded to a reference now comes back as the matching project item type instead of always a raw file.

Skills in this release require `jinko-sdk>=1.13,<2.0`.
