# Inspecting a Subsampling Design and Its Outputs

```python
design = client.get_subsampling_design("sd-...")
print(design.content())
print(design.diagnostics.explain())
print(design.source_trial.sid)

for generated in design.generated_vpops.list_with_details():
    print(generated.vpop.sid, generated.revision)
    print(generated.options)
    print(generated.subsampling_fitness)
```

`generated_vpops.list()` returns only Vpop items.
Use `list_with_details()` to retain the generator options, source design revision, and the optional raw `subsampling_fitness` payload.
That payload is returned as an OpenAPI model or raw dict and is not a scientific pass/fail verdict.
Inspect the Vpop itself with `jinko-vpop`.

To inspect a previous revision, use `design.diagnostics_at(revision)` and `design.generated_vpops.list_with_details_at(revision)`.
The revision refers to the subsampling design, not the generated Vpop.
