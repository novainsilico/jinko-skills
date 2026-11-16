# Iterate on the same project item

Use this table to find the update path for each Project Item type. Each path
saves a new version on the same SID. Pass `version="<short name>"` where the
method accepts it. The owning skill has the full mechanics.

| Project Item | Update path | Owning skill |
| --- | --- | --- |
| Model | `with model.components.batch(version=...)`, component edit methods, or `scripts/sync_model_to_target.py --model-sid` | `jinko-model` |
| Protocol design | `protocol.arms` methods, or `python -m jinko.cli.edit_protocol_design_arms --protocol-design-sid` | `jinko-protocol` |
| Vpop design | `design.descriptors` and `design.correlations`, or `python -m jinko.cli.edit_vpop_design --vpop-design-sid` | `jinko-vpop` |
| Vpop | Cannot be edited. Edit the vpop design, then generate a new Vpop. | `jinko-vpop` |
| Simple output set | `replace_all_measures`, `add_measures`, `remove_measures`, `update_measure`, or `python -m jinko.cli.create_simple_output_set --output-set-sid` | `jinko-output-set` |
| Advanced output set | `scoring_design.components.add_*`, or `python -m jinko.cli.edit_advanced_output_set --sid` | `jinko-output-set` |
| Data table | `data_table.replace_csv`, `replace_sqlite`, `update_mappings`, or `python -m jinko.cli.create_data_table --data-table-sid` | `jinko-data-table` |
| Trial | `trial.set_components`, `edit_solving_options`, or `python -m jinko.cli.setup_and_run_trial --trial-sid` | `jinko-trial` |
| Calibration | `calibration.set_components`, `edit_solving_options` | `jinko-calibration-cmaes` |
| Subsampling design | Typed edits such as `design.marginals`, and `design.set_trial` before first use | `jinko-calibration-subsampling` |
| Trial visualization | The setter of the relevant section | `jinko-trial-viz` |
| Document | `document.update_markdown` or `update_markdown_from_file` | `jinko-document` |
| Reference | Find and reuse a matching Reference. Do not upload the same PDF again. | `jinko-reference` |

## Downstream items keep their snapshots

A Trial or Calibration records the exact Snapshot of each component. An edit of
an upstream item does not change the Trial or Calibration. Update the consumer
after each upstream edit:

```python
with model.components.batch(version="fix dosing event timing") as batch:
    batch.edit_parameter("t_dose").set_formula("24 * 3600")  # new model version
trial.set_components(model=model, version="use fixed dosing timing")
trial.run()
```

`set_components` changes only the components that you give. `data_tables`
replaces the complete list. Earlier Trial and Calibration versions keep their
results.

## When a new item is correct

- First creation of the item.
- An independent scenario that the user asks for, for example a second
  population or a different study question.
- A type that cannot be edited, such as a generated Vpop.
- An edit would remove a result that the user asked to keep, and the item has
  no version access for that result.

State the reason when you create a new item for a later iteration.
