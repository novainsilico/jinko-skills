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
folder = client.folders.get_by_name("2026-06-15-regimens", exact_match_only=True)
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

## Override Keys

The override `key` must target a model input that can be overridden by the protocol. For the toy model, `Dose` and `route` are model components. If these inputs are absent, use `jk-model` first.

## Arm Payload Shape

See `assets/protocol.json` for the schema subset used by the scripts.
