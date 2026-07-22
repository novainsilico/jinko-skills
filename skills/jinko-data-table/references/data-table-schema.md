# Data Table Schema

Data tables can be used for trial overlays and calibration objectives. The row schema is the same for both; calibration fitness compatibility is reported by metadata when available.

## Point-Value Rows

Required columns:

- `obsId`
- `time`
- `value`

Optional columns include `unit`, `armScope`, `wideRangeLowBound`, `wideRangeHighBound`, `weight`, and `experimentRef`.

When wide bounds are present, they must strictly contain the narrow range. In particular, `wideRangeLowBound` must be less than `narrowRangeLowBound`, and `wideRangeHighBound` must be greater than `narrowRangeHighBound`.

## Range Rows

Required columns:

- `obsId`
- `time`
- `narrowRangeLowBound`
- `narrowRangeHighBound`

Optional columns include `unit`, `armScope`, `wideRangeLowBound`, `wideRangeHighBound`, `weight`, and `experimentRef`.

## Time Format

Use ISO-8601 durations for `time`, for example:

- `PT0S`
- `PT6H`
- `P1D`

## Fitness Function Validity

After creating or retrieving a table, check:

```python
content = data_table.content()
valid = content.metadata.public.validForFitnessFunction
```

If the SDK returns raw dictionaries in a given environment, use:

```python
valid = data_table.get("metadata", {}).get("public", {}).get("validForFitnessFunction")
```

The bundled scripts support both typed and dictionary-shaped responses.

For data tables attached through trial or calibration `dataTableDesigns`, require this value to be `True` before creating or launching the downstream item.
