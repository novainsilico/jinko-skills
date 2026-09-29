import json
from pathlib import Path

import paper2model_report as report
import pytest


def valid_spec() -> dict:
    spec = {
        "schema_version": "1.0",
        "paper": {
            "title": "Example",
            "citation": "Author. Example.",
            "identifier": "doi:example",
            "license": "CC BY 4.0",
        },
        "scope": "Reproduce one reported trajectory.",
        "sources": [
            {
                "id": "paper",
                "kind": "paper",
                "locator": "paper.pdf",
                "sha256": "a" * 64,
                "extraction": "native text",
                "reviewed": True,
            }
        ],
        "coverage": {
            kind: {"reported": 1, "implemented": 1} for kind in report.COVERAGE_KINDS
        },
        "assumptions": [],
        "interpretations": [],
        "implementation": {
            "status": "validated",
            "model_sid": "cm-example",
            "model_revision": 1,
            "unit_policy": "strict",
            "repairs": [],
            "unresolved_conflicts": [],
        },
        "validation": {
            "diagnostic_errors": 0,
            "solve_status": "passed",
            "checks": [
                {"name": "finite", "status": "passed", "evidence": "All values finite."}
            ],
        },
        "targets": [
            {
                "name": "trajectory",
                "source_locator": "Figure 1",
                "metric": "RMSE",
                "tolerance": "<= 0.1",
                "measured": "0.02",
                "status": "passed",
                "independent": True,
                "transformation": "none",
                "basis": "publication",
                "decision_ids": [],
            }
        ],
        "artifacts": [],
        "assessment": {
            "outcome": "reproduced",
            "confidence": "high",
            "rationale": "Measured target passed.",
            "curated_implementation": {
                "status": "not_assessed",
                "rationale": "No curated comparison requested.",
                "reference_artifact": None,
            },
        },
        "limitations": ["One scenario only."],
    }
    spec["project_items"] = []
    for kind, sid in (
        ("reference", "so-paper"),
        ("protocol", "pd-arm"),
        ("vpop", "vp-lines"),
        ("output_set", "md-output"),
        ("trial", "tr-run"),
    ):
        url = f"https://workspace.example/app/{sid}"
        spec["project_items"].append({
            "id": kind,
            "kind": kind,
            "sid": sid,
            "revision": None if kind == "vpop" else 2,
            "url": url,
            "fixed_url": None if kind == "vpop" else url + "?revision=2",
        })
    spec["retrievals"] = [
        {
            "url": "https://publisher.example/supplement",
            "purpose": "Find S2",
            "status": "inaccessible",
            "source_ids": [],
            "note": "HTTP 403; no file retrieved.",
        }
    ]
    spec["experiments"] = [
        {
            "id": "treated",
            "design_kind": "experimental_arm",
            "source_id": "paper",
            "source_locator": "Figure 1",
            "protocol_id": "protocol",
            "arm_id": "drug",
            "vpop_id": "vpop",
            "patient_ids": ["L1", "L2"],
            "variability_kind": "biological_variability",
            "variability_evidence": "Table 2 gives receptor values for L1 and L2.",
            "output_set_id": "output_set",
            "trial_id": "trial",
            "target_names": ["trajectory"],
            "observable_mapping": "Receptor activity for each line; time in hours.",
            "note": "Only the drug arm contributes to this target.",
        }
    ]
    return spec


def test_validate_and_render() -> None:
    spec = valid_spec()
    report.validate_spec(spec)
    rendered = report.render(spec, profile="audit")
    assert "Outcome: `reproduced`" in rendered
    assert "1/1 (100.0%)" in rendered
    assert "RMSE" in rendered


def test_reproduced_requires_measured_pass() -> None:
    spec = valid_spec()
    spec["targets"][0]["status"] = "unavailable"
    try:
        report.validate_spec(spec)
    except report.SpecError as exc:
        assert "all targets passed" in str(exc)
    else:
        raise AssertionError("invalid reproduced outcome was accepted")


def test_schema_rejects_extra_properties_and_empty_title() -> None:
    spec = valid_spec()
    spec["extra"] = True
    try:
        report.validate_spec(spec)
    except report.SpecError as exc:
        assert "unsupported property" in str(exc)
    else:
        raise AssertionError("extra property was accepted")
    spec = valid_spec()
    spec["paper"]["title"] = ""
    try:
        report.validate_spec(spec)
    except report.SpecError as exc:
        assert "too short" in str(exc)
    else:
        raise AssertionError("empty title was accepted")


def test_measured_target_cannot_be_null() -> None:
    spec = valid_spec()
    spec["targets"][0]["measured"] = None
    try:
        report.validate_spec(spec)
    except report.SpecError as exc:
        assert "measured result" in str(exc)
    else:
        raise AssertionError("passed target without a measurement was accepted")


def test_reproduced_rejects_failed_checks() -> None:
    spec = valid_spec()
    spec["validation"]["checks"][0]["status"] = "failed"
    try:
        report.validate_spec(spec)
    except report.SpecError as exc:
        assert "passed execution checks" in str(exc)
    else:
        raise AssertionError("failed execution check was accepted")


def test_outcome_confidence_and_coverage_are_consistent() -> None:
    spec = valid_spec()
    spec["assessment"].update(
        outcome="implemented_not_assessed",
        confidence="moderate",
        rationale="No target.",
    )
    spec["targets"] = []
    spec["experiments"][0]["target_names"] = []
    try:
        report.validate_spec(spec)
    except report.SpecError as exc:
        assert "low confidence" in str(exc)
    else:
        raise AssertionError("invalid confidence was accepted")
    spec = valid_spec()
    spec["coverage"]["states"]["implemented"] = 2
    try:
        report.validate_spec(spec)
    except report.SpecError as exc:
        assert "cannot exceed" in str(exc)
    else:
        raise AssertionError("invalid coverage was accepted")
    spec = valid_spec()
    spec["implementation"]["status"] = "failed"
    spec["validation"]["solve_status"] = "failed"
    spec["assessment"].update(
        outcome="failed_validation",
        confidence="moderate",
        rationale="Solve failed.",
    )
    try:
        report.validate_spec(spec)
    except report.SpecError as exc:
        assert "not_supportable confidence" in str(exc)
    else:
        raise AssertionError("failed validation with supported confidence was accepted")


def test_cli_refuses_overwrite(tmp_path: Path) -> None:
    spec_path = tmp_path / "spec.json"
    output_path = tmp_path / "report.md"
    spec_path.write_text(json.dumps(valid_spec()), encoding="utf-8")
    output_path.write_text("keep", encoding="utf-8")
    assert (
        report.main(["render", "--spec", str(spec_path), "--out", str(output_path)])
        == 2
    )
    assert output_path.read_text(encoding="utf-8") == "keep"


def bound_spec() -> dict:
    return valid_spec()


def test_bindings_and_sdk_cards() -> None:
    spec = bound_spec()
    report.validate_spec(spec)
    rendered = report.render(spec, profile="audit")
    for item in spec["project_items"]:
        assert f"\n\n{item['url']}\n\n" in rendered
        if item["fixed_url"]:
            assert f"[Fixed revision 2]({item['fixed_url']})" in rendered
            assert f"\n\n{item['fixed_url']}\n\n" not in rendered
    assert "`biological_variability`" in rendered
    assert "L1, L2" in rendered
    assert "`inaccessible`" in rendered


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_id", "missing", "unknown source"),
        ("protocol_id", "vpop", "known protocol"),
        ("target_names", ["missing"], "unknown target"),
        ("patient_ids", ["L1", "L1"], "duplicate patient_ids"),
        ("arm_id", None, "arm ID"),
        ("patient_ids", [], "patient IDs"),
        ("variability_kind", "none", "declare its variability"),
        ("variability_kind", "analytical_control", "cannot score"),
        ("output_set_id", None, "output set"),
        ("protocol_id", None, "requires a Protocol"),
        ("vpop_id", None, "requires a Vpop"),
    ],
)
def test_reject_invalid_experiment_binding(field, value, message) -> None:
    spec = bound_spec()
    spec["experiments"][0][field] = value
    with pytest.raises(report.SpecError, match=message):
        report.validate_spec(spec)


@pytest.mark.parametrize("version", ["0.9", "1.1"])
def test_reject_unsupported_schema_with_complete_bindings(
    tmp_path: Path, version: str
) -> None:
    spec = valid_spec()
    report.validate_spec(spec)
    spec["schema_version"] = version
    with pytest.raises(report.SpecError, match=r"schema_version must equal '1.0'"):
        report.validate_spec(spec)
    spec_path = tmp_path / "unsupported.json"
    output_path = tmp_path / "report.md"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    assert (
        report.main(["render", "--spec", str(spec_path), "--out", str(output_path)])
        == 2
    )
    assert not output_path.exists()


@pytest.mark.parametrize("field", ["experiments", "retrievals", "project_items"])
def test_required_arrays_in_schema_and_semantic_validator(field) -> None:
    spec = valid_spec()
    del spec[field]
    schema_path = (
        Path(report.__file__).parents[1] / "assets" / "reproduction-spec.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    for validate in (
        lambda value: report.validate_schema(value, schema, schema),
        report.validate_bindings,
        report.validate_spec,
    ):
        with pytest.raises(report.SpecError, match=f"is missing: {field}"):
            validate(spec)


def test_every_target_requires_binding() -> None:
    spec = bound_spec()
    spec["experiments"] = []
    with pytest.raises(report.SpecError, match="Every target"):
        report.validate_spec(spec)


def test_reject_duplicate_and_invalid_retrieval() -> None:
    spec = bound_spec()
    spec["sources"].append(spec["sources"][0].copy())
    with pytest.raises(report.SpecError, match="Duplicate source"):
        report.validate_spec(spec)
    spec = bound_spec()
    spec["retrievals"][0]["source_ids"] = ["paper"]
    with pytest.raises(report.SpecError, match="Unsuccessful retrieval"):
        report.validate_spec(spec)


def test_reject_fixed_card_and_wrong_revision() -> None:
    spec = bound_spec()
    spec["project_items"][0]["url"] += "?revision=2"
    with pytest.raises(report.SpecError, match="unversioned"):
        report.validate_spec(spec)
    spec = bound_spec()
    spec["project_items"][0]["fixed_url"] += "0"
    with pytest.raises(report.SpecError, match="recorded revision"):
        report.validate_spec(spec)


def test_control_without_publication_target_and_pending_binding() -> None:
    spec = bound_spec()
    control = dict(
        spec["experiments"][0],
        id="zero-control",
        design_kind="analytical_check",
        variability_kind="analytical_control",
        patient_ids=["zero"],
        target_names=[],
    )
    spec["experiments"].append(control)
    report.validate_spec(spec)
    pending = spec["experiments"][0]
    for field in ("protocol_id", "vpop_id", "trial_id", "output_set_id"):
        pending[field] = None
    spec["implementation"]["status"] = "blocked"
    spec["targets"][0].update(status="unavailable", measured=None)
    spec["assessment"].update(outcome="blocked_evidence", confidence="not_supportable")
    report.validate_spec(spec)
    pending["arm_id"] = None
    with pytest.raises(report.SpecError, match="arm ID"):
        report.validate_spec(spec)


@pytest.mark.parametrize(
    "kind", ["none", "biological_variability", "initial_condition_sweep"]
)
def test_single_row_population_preserves_scientific_label(kind) -> None:
    spec = bound_spec()
    spec["experiments"][0].update(patient_ids=["L1"], variability_kind=kind)
    before = json.dumps(spec, sort_keys=True)
    report.validate_spec(spec)
    assert json.dumps(spec, sort_keys=True) == before
    assert f"`{kind}`" in report.render(spec, profile="audit")


def mixed_spec(status="unavailable", design="theoretical_scenario") -> dict:
    spec = bound_spec()
    spec["targets"].append(
        dict(spec["targets"][0], name="stochastic", status=status, measured=None)
    )
    spec["experiments"].append(
        dict(
            spec["experiments"][0],
            id="pending",
            design_kind=design,
            protocol_id=None,
            vpop_id=None,
            trial_id=None,
            output_set_id=None,
            target_names=["stochastic"],
            note="Stochastic semantics remain unresolved.",
        )
    )
    spec["assessment"].update(outcome="partially_reproduced", confidence="low")
    return spec


@pytest.mark.parametrize("status", ["unavailable", "not_assessable"])
@pytest.mark.parametrize("design", ["theoretical_scenario", "experimental_arm"])
def test_completed_and_unexecuted_experiments(status, design) -> None:
    spec = mixed_spec(status, design)
    before = json.dumps(spec, sort_keys=True)
    report.validate_spec(spec)
    rendered = report.render(spec, profile="audit")
    assert "Outcome: `partially_reproduced`" in rendered
    assert f"`{status}`" in rendered
    assert "Trial: none" in rendered
    assert json.dumps(spec, sort_keys=True) == before
    spec["assessment"]["outcome"] = "reproduced"
    with pytest.raises(report.SpecError, match="all targets passed"):
        report.validate_spec(spec)


@pytest.mark.parametrize("status", ["passed", "failed"])
@pytest.mark.parametrize("model_status", ["validated", "blocked"])
@pytest.mark.parametrize(
    ("design", "message"),
    [
        ("theoretical_scenario", "requires a Vpop"),
        ("experimental_arm", "requires a Protocol"),
    ],
)
def test_assessed_targets_require_execution_bindings(
    status, model_status, design, message
) -> None:
    spec = mixed_spec(design=design)
    spec["implementation"]["status"] = model_status
    spec["targets"][1].update(status=status, measured="0.2")
    with pytest.raises(report.SpecError, match=message):
        report.validate_spec(spec)


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("output_set_id", "output set"),
        ("protocol_id", "requires a Protocol"),
        ("vpop_id", "requires a Vpop"),
    ],
)
def test_trial_requires_bindings_even_when_targets_unavailable(field, message) -> None:
    spec = mixed_spec(design="experimental_arm")
    pending = spec["experiments"][1]
    pending.update(
        trial_id="trial",
        output_set_id="output_set",
        protocol_id="protocol",
        vpop_id="vpop",
    )
    pending[field] = None
    with pytest.raises(report.SpecError, match=message):
        report.validate_spec(spec)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_id", "missing", "unknown source"),
        ("vpop_id", "missing", "known vpop"),
        ("patient_ids", ["L1", "L1"], "duplicate patient_ids"),
        ("variability_kind", "none", "declare its variability"),
        ("variability_kind", "analytical_control", "cannot score"),
        ("target_names", ["missing"], "unknown target"),
    ],
)
def test_unexecuted_experiment_keeps_consistency_gates(field, value, message) -> None:
    spec = mixed_spec()
    spec["experiments"][1][field] = value
    with pytest.raises(report.SpecError, match=message):
        report.validate_spec(spec)


def test_single_row_none_still_requires_patient_identity() -> None:
    spec = bound_spec()
    spec["experiments"][0].update(variability_kind="none", patient_ids=[])
    with pytest.raises(report.SpecError, match="patient IDs"):
        report.validate_spec(spec)


def publication_spec():
    spec = bound_spec()
    spec["project_items"].append({
        "id": "model",
        "kind": "model",
        "sid": "cm-example",
        "revision": 1,
        "url": "https://workspace.example/app/cm-example",
        "fixed_url": "https://workspace.example/app/cm-example?revision=1",
    })
    return spec


def test_concise_cards_first_and_no_naked_sid():
    spec = publication_spec()
    spec["limitations"].append("Inspect `cm-example` and tr-run.")
    before = json.dumps(spec, sort_keys=True)
    report.validate_spec(spec)
    text = report.render(spec, profile="jinko")
    paragraphs = text.split("\n\n")
    expected = [
        item["url"] for item in spec["project_items"] if item["kind"] != "reference"
    ]
    expected += [
        item["url"] for item in spec["project_items"] if item["kind"] == "reference"
    ]
    assert paragraphs[1 : 1 + len(expected)] == expected
    assert "## Essential findings" == paragraphs[1 + len(expected)]
    assert "| ---" not in text
    assert "`cm-example`" not in text
    assert "[Project item](https://workspace.example/app/tr-run)" in text
    assert json.dumps(spec, sort_keys=True) == before


def test_local_render_and_publication_requires_model_url():
    spec = valid_spec()
    report.validate_spec(spec)
    assert "cm-example" not in report.render(spec, profile="audit")
    with pytest.raises(report.SpecError, match="SDK .url"):
        report.render(spec, profile="jinko")


def test_awaiting_user_source_preserves_outcome_and_targets():
    spec = mixed_spec()
    spec["retrievals"][0].update(
        status="awaiting_user_source", note="Can you upload Supplement S2?"
    )
    before = json.dumps(spec, sort_keys=True)
    report.validate_spec(spec)
    text = report.render(spec)
    assert "awaiting_user_source" in text and "Can you upload Supplement S2?" in text
    assert "partially_reproduced" in text
    assert json.dumps(spec, sort_keys=True) == before
    spec["retrievals"][0]["source_ids"] = ["paper"]
    with pytest.raises(report.SpecError, match="Unsuccessful retrieval"):
        report.validate_spec(spec)


def visual_spec():
    spec = publication_spec()
    spec["targets"][0].update(status="failed", measured="0.2")
    spec["assessment"].update(outcome="partially_reproduced", confidence="low")
    spec["artifacts"] = [
        {"kind": "overlay", "locator": "overlay.png", "sha256": "a" * 64},
        {"kind": "comparison", "locator": "comparison.csv", "sha256": "b" * 64},
    ]
    spec["visual_evidence"] = [
        {
            "image": "overlay.png",
            "caption": "Figure 1 comparison, time in hours",
            "source_locator": "Figure 1",
            "target_names": ["trajectory"],
            "result_artifact": "comparison.csv",
            "uncertainty": "Digitization uncertainty unavailable",
        }
    ]
    return spec


def test_visual_failed_comparison_and_no_placeholder():
    spec = visual_spec()
    report.validate_spec(spec)
    text = report.render(spec, profile="jinko")
    assert "](overlay.png)" in text and "`failed`" in text
    assert "RMSE: 0.2; declared tolerance: <= 0.1" in text
    assert "Digitization uncertainty unavailable" in text
    assert "![" not in report.render(valid_spec())


@pytest.mark.parametrize("change", ["target", "result", "image"])
def test_visual_requires_actual_evidence_bindings(change):
    spec = visual_spec()
    if change == "target":
        spec["targets"][0].update(status="unavailable", measured=None)
    elif change == "result":
        spec["visual_evidence"][0]["result_artifact"] = "missing.csv"
    else:
        spec["visual_evidence"][0]["image"] = "placeholder.png"
    with pytest.raises(report.SpecError, match="Visual evidence requires"):
        report.validate_spec(spec)


def test_paper_requires_a_licence() -> None:
    spec = valid_spec()
    del spec["paper"]["license"]
    with pytest.raises(report.SpecError, match="paper"):
        report.validate_spec(spec)


def test_licence_accepts_a_recorded_absence() -> None:
    for value in ("CC BY 4.0", "Elsevier TDM", "not provided", "not found"):
        spec = valid_spec()
        spec["paper"]["license"] = value
        report.validate_spec(spec)


def test_bare_sid_in_the_rendered_report_is_refused() -> None:
    assert report.naked_sids("see [Model](https://jinko.ai/cm-ABCD-1234) and it") == []
    assert report.naked_sids("see https://jinko.ai/cm-ABCD-1234 now") == []
    assert report.naked_sids("the model cm-ABCD-1234 solves") == ["cm-ABCD-1234"]
    spec = valid_spec()
    spec["scope"] = "Reproduce the trajectory of cm-ABCD-1234."
    with pytest.raises(report.SpecError, match="bare SIDs"):
        report.render(spec)
