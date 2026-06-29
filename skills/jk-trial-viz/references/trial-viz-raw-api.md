# TrialVisualization Raw API

TrialVisualization content is a top-level JSON object keyed by visualization sections. Only `trialId` is required at creation, but useful visualizations usually include one or more plot sections.

## Identifiers

Use a trial project item's core id and snapshot id:

```json
{
  "trialId": {
    "coreItemId": "TRIAL_CORE_UUID",
    "snapshotId": "TRIAL_SNAPSHOT_UUID"
  }
}
```

If the user provides a trial SID, resolve it with:

```python
trial = client.get_trial("tr-...")
trial_id = {"coreItemId": trial.core_id, "snapshotId": trial.snapshot_id}
```

## Raw Requests

```python
from jinko import JinkoClient

client = JinkoClient()

created = client.raw_request(
    "POST",
    "/core/v2/result_manager/trial_visualization",
    json_body=payload,
    headers=headers,
)

content = client.raw_request(
    "GET",
    f"/core/v2/result_manager/trial_visualization/{trial_viz_core_id}",
)

updated = client.raw_request(
    "PATCH",
    f"/core/v2/result_manager/trial_visualization/{trial_viz_core_id}",
    json_body=patch,
    headers=headers,
)

sanity = client.raw_request(
    "GET",
    f"/core/v2/result_manager/trial_visualization/{trial_viz_core_id}/snapshots/{snapshot_id}/sanity",
    params={"only": ["timeseries", "scatterPlots"]},
)
```

Project-item creation metadata is passed in headers. The SDK has `jinko._project_item_headers.build_project_item_headers(...)`; the bundled script uses the same base64 header convention.

## Minimal Create Payload

```json
{
  "trialId": {
    "coreItemId": "TRIAL_CORE_UUID",
    "snapshotId": "TRIAL_SNAPSHOT_UUID"
  },
  "selectedArms": null
}
```

`selectedArms: null` lets the backend use default arm selection. Set a string array when the user explicitly wants a subset.

## Time-Series Plot

Use known output ids from the trial output set. The selector ids must match result ids, not display labels.

```json
{
  "timeseries": {
    "selectors": ["Drug", "TumorVolume"],
    "layout": {},
    "dataOptions": {},
    "percentilesOptions": {
      "narrowRangeHighBoundPercentile": 0.75,
      "wideRangeHighBoundPercentile": 0.95
    },
    "values": "median",
    "showVarianceLegend": true
  }
}
```

## Scalar Plots

```json
{
  "scalars": {
    "selectors": ["AUC", "Cmax"],
    "layout": {},
    "centralLocationPlotsOptions": {
      "location": "median",
      "showLegend": true,
      "mean": {
        "barplots": true,
        "sdRange": 1
      },
      "median": {
        "interquantileHighBound": 0.75
      }
    }
  }
}
```

## Scatter Plots

X-vs-X compares one variable across arms:

```json
{
  "scatterPlots": {
    "layout": {},
    "scatterPlotConfig": [
      {
        "id": "Drug_control_vs_treated",
        "mode": "XvsX",
        "variable": "Drug",
        "arms": {
          "x": "control",
          "y": ["treated"]
        },
        "groupedByArm": true
      }
    ]
  }
}
```

X-vs-Y compares two variables across one or more arms:

```json
{
  "scatterPlots": {
    "layout": {},
    "scatterPlotConfig": [
      {
        "id": "AUC_vs_Cmax",
        "mode": "XvsY",
        "variables": {
          "x": "AUC",
          "y": "Cmax"
        },
        "arms": ["control", "treated"],
        "groupedByArm": true
      }
    ],
    "regression": {
      "showLineEquation": false,
      "lineEquationLegend": {}
    }
  }
}
```

## Survival Analysis

```json
{
  "survivalAnalysis": {
    "selectors": ["time_to_progression"],
    "layout": {},
    "dataOptions": {},
    "observationWindow": "FromStartUntilEnd",
    "survivalPlotsOptions": {
      "hasConfidenceInterval": true
    }
  }
}
```

## Contribution Analysis

```json
{
  "contributionAnalysis": {
    "selectors": ["AUC"],
    "layout": {},
    "quantile": 0.5,
    "baseline": {
      "tag": "InputBaselineOnly"
    }
  }
}
```

## Data Overlay

Data-table ids also use core item id and snapshot id:

```json
{
  "dataOverlay": {
    "ranges": true,
    "tables": [
      {
        "dataTableId": {
          "coreItemId": "DATA_TABLE_CORE_UUID",
          "snapshotId": "DATA_TABLE_SNAPSHOT_UUID"
        },
        "include": true,
        "options": {
          "label": "Observed data",
          "timeTolerance": null,
          "weight": null
        }
      }
    ]
  }
}
```

## Patch Semantics

Patch operates at top-level keys:

- Omitted keys keep the existing value.
- A present key replaces that top-level section.
- A key set to `null` deletes that section and falls back to backend defaults when defined.

Patch only the plot section the user wants to change unless they explicitly ask to replace the entire configuration.

## Sanity Routing

Use scoped sanity checks after updates:

- `selectedArms`
- `groups`
- `filters`
- `overlay`
- `dataOverlay`
- `timeseries`
- `scalars`
- `scatterPlots`
- `contributionAnalysis`
- `survivalAnalysis`

If sanity reports missing selectors or arms, fetch the trial summary/output ids with `jk-trial` workflows, then patch with valid ids.
