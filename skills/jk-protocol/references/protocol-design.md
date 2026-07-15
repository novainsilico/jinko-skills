# Protocol Design

Use protocol designs to assign arm-specific values to model inputs.

## Separation Of Concerns

Model-level responsibilities:

- Define dosing events.
- Define dose parameters such as `Dose`.
- Define schedule parameters such as interval, duration, or start time.
- Define categorical switches such as `route`, treatment activation flags, or administration mode.
- Define formulas that interpret those inputs.

Protocol-level responsibilities:

- Define arms.
- Assign different values to the model inputs per arm.
- Define control-arm relationships for comparison.

The protocol should not encode dosing mechanics. It should only instantiate values for the model-level treatment-regimen function.

## SDK Create Pattern

```python
model = client.get_model("cm-...")
folder = client.get_folder_by_name("2026-06-15-regimens", exact_match_only=True)
protocol = client.create_protocol_design(
    [
        {
            "armControl": None,
            "armIsActive": True,
            "armName": "iv_low_dose",
            "armOverrides": [
                {"key": "Dose", "formula": "1.0"},
                {"key": "route", "formula": "iv"},
            ],
            "armWeight": 1,
        },
        {
            "armControl": "iv_low_dose",
            "armIsActive": True,
            "armName": "po_mid_dose",
            "armOverrides": [
                {"key": "Dose", "formula": "2.0"},
                {"key": "route", "formula": "po"},
            ],
            "armWeight": 1,
        },
    ],
    model=model,
    folder=folder,
)
```

## SDK Create From CSV Pattern

`create_protocol_design_from_csv` posts the CSV file as-is; the platform
parses and validates it server-side against its own protocol design CSV
schema, one row per arm. `armControl`, `armIsActive`, and `armWeight` are
optional columns; every other column is an override key, matching the same
`Dose`/`route` overrides used in the JSON example above.

`assets/toy_protocol_arms.csv` (equivalent to the JSON arms above, minus
`iv_high_dose`'s override values differing only by dose):

```csv
armName,armControl,armIsActive,armWeight,Dose,route
iv_low_dose,,true,1,1.0,iv
po_mid_dose,iv_low_dose,true,1,2.0,po
iv_high_dose,iv_low_dose,true,1,3.0,iv
```

```python
folder = client.get_folder_by_name("2026-06-15-regimens", exact_match_only=True)
protocol = client.create_protocol_design_from_csv(
    csv_file_path="skills/jk-protocol/assets/toy_protocol_arms.csv",
    folder=folder,
)
```

This path does not accept a `model` argument. To bind a model, use
`client.create_protocol_design(arms, model=model)` with an explicit arm list
instead.

## Override Keys

The override `key` must target a model input that can be overridden by the protocol. For the toy model, `Dose` and `route` are model components. If these inputs are absent, use `jk-model` first.

## Editing An Existing Design's Arms

Edit arms through `protocol.arms`, the design's arm mutator service, rather than replacing the whole payload:

```python
protocol = client.get_protocol_design("pd-...")

arm = protocol.arms.get("iv_low_dose")
arm.set_override("Dose", "1.5")
arm.set_weight(2)

protocol.arms.create(
    "iv_new_dose",
    control="iv_low_dose",
    overrides={"Dose": "4.0", "route": "iv"},
    weight=1,
    active=True,
)
```

`protocol.arms.list()` and `protocol.arms.get(arm_id)` return `ProtocolArm` handles; `arm.delete()` removes an arm, and `arm.compare_to(other_arm_id)` (or `protocol.arms.compare_overrides(...)`) diffs overrides between two arms.

## Arm Payload Shape

See `assets/protocol.json` for the schema subset used by the scripts.
