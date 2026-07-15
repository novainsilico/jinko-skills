# CSV Vpop Upload

Use direct CSV or DataFrame upload when the user already has patient rows.

## Required Shape

The CSV should include one row per virtual patient. Use `patientIndex` as the first column and model component IDs as descriptor columns.

```csv
patientIndex,Dose,k_elim
1,1.0,0.08
2,1.2,0.12
```

`Dose` and `k_elim` match the toy model created by `jk-model/scripts/create_minimal_model.py`.

## SDK Methods

- `client.create_vpop_from_csv(csv_file_path=..., name=...)`
- `client.create_vpop_from_csv(csv_content=..., name=...)`
- `client.create_vpop_from_dataframe(df, name=..., folder=folder)`

Example single-folder create:

```python
folder = client.get_folder_by_name("2026-06-15-vpop-study", exact_match_only=True)
vpop = client.create_vpop_from_csv(
    csv_file_path="toy_vpop.csv",
    name="sdk-toy-vpop",
    folder=folder,
)
```

DataFrame upload serializes to CSV internally and requires pandas.

## Safety

Use `scripts/create_vpop_from_csv.py` without `--apply` first to validate the CSV header and row count.
