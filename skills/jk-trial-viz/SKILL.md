---
name: jk-trial-viz
description: >-
  Create, update, inspect, sanity-check, and retrieve Jinkō TrialVisualization project items for completed or running trials. Use this skill whenever the user wants a trial visualization, trial viz, time-series plot setup, scalar result plots, scatter plots, contribution analysis, survival analysis, data overlays, or to fetch the current visualization JSON. TrialVisualization has only limited high-level SDK helpers; use SDK metadata listing/getting when available and raw Jinkō requests for content creation and plot configuration.
compatibility: >-
  Check set-up with the `jk-sdk-setup` skill. Creating or patching trial visualizations requires write access to the Jinkō project. The current SDK exposes metadata helpers for trial visualizations but not rich content create/update helpers, so raw requests are expected.
metadata:
  author: Nova In Silico
  requires_sdk: ">=1.2,<2.0"
license: MIT
---

# Jinkō Trial Visualization Workflows

Use this skill for TrialVisualization project items: creating a visualization for a trial, configuring plot sections, retrieving the stored visualization payload, and running visualization sanity checks.

Keep trial execution and result downloads in `jk-trial`. Use this skill after a trial exists and the user wants the Jinkō visualization artifact or its plot configuration.

## Core Workflow

1. Resolve the trial identifier.
   - If the user gives a trial SID, use `client.get_trial(trial_sid)` and read `trial.core_id` and `trial.snapshot_id`.
   - If the user gives core item id and snapshot id directly, use those as `trialId`.
2. Decide the plot sections needed:
   - `timeseries` for time-course outputs.
   - `scalars` for scalar result distributions and central-location plots.
   - `scatterPlots` for X-vs-X arms or X-vs-Y variables.
   - `survivalAnalysis` for time-to-event visualizations.
   - `contributionAnalysis` for tornado-style sensitivity/contribution views.
   - `dataOverlay` when observed data tables should appear in the visualization.
3. Create the TrialVisualization with raw `POST /core/v2/result_manager/trial_visualization`.
4. Fetch the created content and run sanity, especially when plot ids, arm ids, data tables, or selectors were inferred.
5. Patch top-level plot sections with raw `PATCH /core/v2/result_manager/trial_visualization/{coreItemId}` when the user asks to add or change plots.

## SDK Surface

The SDK currently exposes metadata helpers:

- `client.list_trial_visualizations(...)`
- `client.iter_trial_visualizations(...)`
- `client.get_trial_visualization(sid)`

The SDK `TrialVisualizationsService` does not yet implement rich `create_raw`, `get_content`, or `update_raw` helpers. Use `client.raw_request(...)` for content operations.

## Raw Request Endpoints

Read `references/trial-viz-raw-api.md` before writing a custom payload or raw request. It contains the endpoint list, minimal payloads, and plot-section examples.

Common paths:

- Create: `POST /core/v2/result_manager/trial_visualization`
- Get latest content: `GET /core/v2/result_manager/trial_visualization/{coreItemId}`
- Get snapshot content: `GET /core/v2/result_manager/trial_visualization/{coreItemId}/snapshots/{snapshotId}`
- Patch latest content: `PATCH /core/v2/result_manager/trial_visualization/{coreItemId}`
- Sanity: `GET /core/v2/result_manager/trial_visualization/{coreItemId}/snapshots/{snapshotId}/sanity`

## Bundled Script

Use the script for repeatable create, patch, get, list, and sanity operations.

```bash
python skills/jk-trial-viz/scripts/trial_viz_raw.py list --limit 20
python skills/jk-trial-viz/scripts/trial_viz_raw.py create --trial-sid tr-... --name "My trial viz" --timeseries Drug --scalar AUC
python skills/jk-trial-viz/scripts/trial_viz_raw.py create --trial-core-id 00000000-0000-0000-0000-000000000000 --trial-snapshot-id 11111111-1111-1111-1111-111111111111 --payload-file viz.json --name "Configured viz"
python skills/jk-trial-viz/scripts/trial_viz_raw.py get --trial-viz-sid tv-... --output-file viz.content.json
python skills/jk-trial-viz/scripts/trial_viz_raw.py patch --trial-viz-sid tv-... --payload-file patch.json
python skills/jk-trial-viz/scripts/trial_viz_raw.py sanity --trial-viz-sid tv-... --only timeseries --only scatterPlots
```

Prefer `--payload-file` for non-trivial scatter, survival, contribution, overlay, grouping, or filter configuration. Use the quick flags only for simple time-series/scalar selector setup.

## Project Folder Hygiene

- Prefer creating trial visualizations in the same folder as the trial or in a dedicated analysis folder.
- If only a folder id is available, pass it through creation headers with the bundled script's `--folder-id`.
- Reuse existing trial visualizations when the user wants an additional plot on the same analysis; patch the relevant top-level section instead of creating duplicates.

## Output Expectations

When creating or modifying a visualization, report:

- TrialVisualization SID, core item id, snapshot id, revision when available, and URL when available.
- Plot sections created or patched.
- Any sanity errors or warnings, preserving the backend field names so the next fix is direct.

When retrieving a visualization, return or save the full JSON content if the user needs to inspect, diff, or reuse plot settings.
