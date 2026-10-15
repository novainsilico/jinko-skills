# Model combination and conflicts

Use this reference to merge one model into another with `combine_with`, then
read and resolve the conflicts that the combination creates.

## Combine two models

`model.combine_with(other, version="...")` adds the components of `other` to
`model`. It updates `model` in place to a new snapshot and returns it. `other`
does not change.

Before you combine:

1. Run `model.compare_to(other, print_pretty_output=True)` to see what the
   combination brings in.
2. Record `model.snapshot_id`. It is the state to return to if the result is
   wrong.

After the combination, `model.snapshot_before_combine()` returns the same
snapshot id. It returns `None` for a model that was never combined. The SDK has
no method to restore a snapshot. Report the id to the user, and let them restore
it in Jinkō.

## Read conflicts

Every id that both models hold becomes a conflict: parameters, species,
compartments, ODEs, reactions, events, algebraic rules, baseline checks,
categorical parameters, and tags. This includes ids whose two versions hold the
same content. The model stays conflicted until every conflict has a resolution,
so do not stop after the conflicts that differ.

```python
conflicts = model.conflicts
print(conflicts)  # one line per conflict
print(conflicts.differing().ids())  # the versions disagree
print(conflicts.identical().ids())  # same content, still a conflict
conflict = conflicts.get("k_clearance")
print(conflict.kind, conflict.from_, conflict.to)
```

- `model.conflicts` reads the current head each time. The view does not update
  after a resolution, so read `model.conflicts` again.
- `from_` is the version in `model`. `to` is the incoming version. Both hold
  only the fields that differ, and both are `None` for an identical conflict.
- `for_kind("Parameter", "Species")` and `by_kind()` group the view by kind.

## Resolve conflicts

Each conflict takes one of three strategies:

- `"AcceptCurrent"` keeps the version in `model`.
- `"AcceptIncoming"` keeps the incoming version.
- `"AcceptBoth"` keeps both. The incoming version needs a new id in
  `incoming_new_name`. The current version keeps its id unless you give
  `current_new_name`.

A single strategy applies to every conflict in the view. Filter the view first
to narrow it. A mapping keyed by component id resolves only those conflicts.
Each call creates one snapshot and returns `model` at the new head.

```python
model.conflicts.identical().resolve("AcceptCurrent", version="resolve identical")

model.conflicts.resolve(
    {
        "k_clearance": "AcceptIncoming",
        "dTumor": {"strategy": "AcceptBoth", "incoming_new_name": "dTumor_incoming"},
    },
    version="resolve differing",
)

model.conflicts.get("V_central").resolve("AcceptCurrent")
```

Choose a strategy for each differing conflict from the evidence or from the
user. Do not pick `"AcceptIncoming"` or `"AcceptCurrent"` for all of them only to
clear the model. An identical conflict loses nothing with either single-version
strategy.

## Check the result

1. Confirm that `model.conflicts` is empty.
2. For `"AcceptBoth"`, check that the formulas, events, and tags that use the
   id point to the intended version.
3. Run the validation in `model-validation.md`: no error diagnostics, then
   `simple_solve()` on representative `output` components.
