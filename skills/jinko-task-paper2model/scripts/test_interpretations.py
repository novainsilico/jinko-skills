"""Interpretation policy, dependency history, and publication claim regressions."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import paper2model_report as report
import pytest
from test_paper2model_report import publication_spec as policy_spec


def decision(spec, identity="translation", **changes):
    item = {
        "id": identity,
        "status": "active",
        "supersedes": [],
        "kind": "equivalent_translation",
        "decision": "Use concentration states.",
        "alternatives": ["Amount states"],
        "evidence": "The source defines a fixed volume.",
        "target_informed": False,
        "source_statements": [
            {
                "source_id": "paper",
                "locator": "Equation 2",
                "statement": "The compartment volume is fixed.",
            }
        ],
        "affected_components": ["central"],
        "implementation_change": "Divide amount by fixed compartment volume.",
        "verification": [
            {
                "name": "unit conversion",
                "status": "passed",
                "evidence": "Concentration times volume equals amount.",
            }
        ],
        "affected_targets": ["trajectory"],
        "informed_by_targets": [],
        "approved_by": None,
    }
    item.update(changes)
    spec["interpretations"].append(item)
    if item["status"] == "active" and item["kind"] == "unresolved_conflict":
        spec["implementation"]["unresolved_conflicts"].append(identity)
    for target in spec["targets"]:
        if target["name"] in item["affected_targets"]:
            target["decision_ids"].append(identity)
    return item


def assumption_summary(item):
    return {
        "decision_id": item["id"],
        "statement": item["decision"],
        "basis": item["evidence"],
        "approved_by": item["approved_by"],
        "impact": item["implementation_change"],
    }


def add_target(spec, name="held-out", **changes):
    target = deepcopy(spec["targets"][0])
    target.update(name=name, decision_ids=[])
    target.update(changes)
    spec["targets"].append(target)
    spec["experiments"][0]["target_names"].append(name)
    return target


def curated_target(spec, **changes):
    values = {"status": "passed", "measured": "0.02", **changes}
    target = add_target(spec, "curated", basis="curated_implementation", **values)
    spec["artifacts"].append({
        "kind": "curated reference",
        "locator": "reference.py",
        "sha256": "a" * 64,
    })
    spec["assessment"]["curated_implementation"].update(
        status="passed",
        rationale="Compared with the frozen reference implementation.",
        reference_artifact="reference.py",
    )
    return target


@pytest.mark.parametrize(
    "kind", ["equivalent_translation", "platform_adaptation", "source_correction"]
)
def test_source_supported_changes_need_no_approval(kind):
    spec = policy_spec()
    decision(spec, kind=kind)
    before = deepcopy(spec)
    report.validate_spec(spec)
    for profile in ("concise", "jinko", "audit"):
        text = report.render(spec, profile)
        assert "## Publication fidelity" in text
        assert "## Curated implementation agreement" in text
        assert "## Active interpretation decisions" in text
        assert kind in text
        assert "Divide amount" in text
        assert "Independent: yes" in text
        assert "Transformation: none" in text
    assert spec == before


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "status",
        "supersedes",
        "kind",
        "source_statements",
        "affected_components",
        "implementation_change",
        "verification",
        "affected_targets",
        "informed_by_targets",
        "approved_by",
    ],
)
def test_requires_decision_fields(field):
    spec = policy_spec()
    item = decision(spec)
    del item[field]
    with pytest.raises(report.SpecError, match="is missing"):
        report.validate_spec(spec)


@pytest.mark.parametrize("field", ["basis", "decision_ids"])
def test_requires_target_fields(field):
    spec = policy_spec()
    del spec["targets"][0][field]
    with pytest.raises(report.SpecError, match="is missing"):
        report.validate_spec(spec)


def test_curated_assessment_is_required():
    spec = policy_spec()
    del spec["assessment"]["curated_implementation"]
    with pytest.raises(report.SpecError, match="curated_implementation"):
        report.validate_spec(spec)


@pytest.mark.parametrize(
    "kind", ["equivalent_translation", "platform_adaptation", "source_correction"]
)
@pytest.mark.parametrize(
    "status", ["failed", "unavailable", "not_applicable", "absent", "mixed"]
)
def test_active_translation_requires_passed_verification(kind, status):
    spec = policy_spec()
    item = decision(spec, kind=kind)
    if status == "absent":
        item["verification"] = []
    elif status == "mixed":
        item["verification"].append({
            "name": "second",
            "status": "failed",
            "evidence": "Mismatch.",
        })
    else:
        item["verification"][0]["status"] = status
    with pytest.raises(report.SpecError, match="passed verification"):
        report.validate_spec(spec)


def test_correction_requires_source_statement_and_assumption_requires_approval():
    spec = policy_spec()
    item = decision(spec, kind="source_correction", source_statements=[])
    with pytest.raises(report.SpecError, match="source evidence"):
        report.validate_spec(spec)
    item.update(kind="assumption", verification=[])
    for approval in (None, "", "   "):
        item["approved_by"] = approval
        with pytest.raises(report.SpecError):
            report.validate_spec(spec)
    item["approved_by"] = "Project scientist"
    spec["assumptions"] = [assumption_summary(item)]
    spec["assessment"]["confidence"] = "low"
    report.validate_spec(spec)


@pytest.mark.parametrize(
    "field", ["statement", "locator", "evidence", "implementation_change", "component"]
)
def test_blank_evidence_cannot_support_an_active_correction(field):
    spec = policy_spec()
    item = decision(spec, kind="source_correction")
    if field in {"statement", "locator"}:
        item["source_statements"][0][field] = "   "
    elif field == "evidence":
        item["verification"][0][field] = "   "
    elif field == "component":
        item["affected_components"] = ["   "]
    else:
        item[field] = "   "
    with pytest.raises(report.SpecError, match="must not be blank"):
        report.validate_spec(spec)


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("supersedes", ["missing"], "unknown interpretation"),
        ("affected_targets", ["missing"], "unknown target"),
        ("informed_by_targets", ["missing"], "unknown target"),
        (
            "source_statements",
            [
                {
                    "source_id": "missing",
                    "locator": "Eq. 2",
                    "statement": "Fixed volume.",
                }
            ],
            "unknown source",
        ),
        ("target_informed", True, "must match"),
        ("affected_targets", [], "bidirectional"),
    ],
)
def test_invalid_references_and_links(field, value, message):
    spec = policy_spec()
    item = decision(spec)
    item[field] = value
    with pytest.raises(report.SpecError, match=message):
        report.validate_spec(spec)


@pytest.mark.parametrize(
    "field",
    [
        "supersedes",
        "affected_components",
        "affected_targets",
        "informed_by_targets",
        "source_statements",
        "verification",
        "alternatives",
    ],
)
def test_duplicate_decision_entries(field):
    spec = policy_spec()
    item = decision(spec)
    if not item[field]:
        item[field] = ["trajectory"]
    item[field].append(deepcopy(item[field][0]))
    with pytest.raises(report.SpecError, match="Duplicate"):
        report.validate_spec(spec)


@pytest.mark.parametrize(
    "change", ["id", "target_link", "artifact", "unknown_link", "missing_link"]
)
def test_duplicate_ids_and_target_link_validation(change):
    spec = policy_spec()
    decision(spec)
    if change == "id":
        spec["interpretations"].append(deepcopy(spec["interpretations"][0]))
    elif change == "artifact":
        curated_target(spec)
        spec["artifacts"].append(deepcopy(spec["artifacts"][0]))
    else:
        spec["targets"][0]["decision_ids"] = {
            "target_link": ["translation", "translation"],
            "unknown_link": ["unknown"],
            "missing_link": [],
        }[change]
    with pytest.raises(report.SpecError):
        report.validate_spec(spec)


def selection_history():
    spec = policy_spec()
    spec["targets"][0]["independent"] = False
    add_target(spec)
    decision(
        spec,
        "old",
        status="superseded",
        kind="assumption",
        verification=[],
        target_informed=True,
        informed_by_targets=["trajectory"],
        affected_targets=["trajectory", "held-out"],
    )
    decision(
        spec, "current", supersedes=["old"], affected_targets=["trajectory", "held-out"]
    )
    spec["assessment"].update(outcome="partially_reproduced", confidence="moderate")
    return spec


def test_history_retains_selection_dependency_but_held_out_stays_independent():
    spec = selection_history()
    report.validate_spec(spec)
    assert report.interpretation_dependencies(spec) == {"current": {"trajectory"}}
    text = report.render(spec)
    assert "held-out: `passed`" in text
    assert "Choice dependencies (including history): trajectory" in text
    assert "old [superseded" not in text
    audit = report.render(spec, "audit")
    assert "## Interpretation history" in audit
    assert "old [superseded; assumption]" in audit
    spec["assessment"]["outcome"] = "reproduced"
    with pytest.raises(report.SpecError, match="target-informed"):
        report.validate_spec(spec)
    spec["assessment"].update(outcome="partially_reproduced", confidence="high")
    with pytest.raises(report.SpecError, match="high confidence"):
        report.validate_spec(spec)


@pytest.mark.parametrize("status", ["active", "superseded", "proposed", "rejected"])
def test_selection_target_cannot_claim_independence(status):
    spec = selection_history()
    spec["interpretations"][0]["status"] = status
    spec["targets"][0]["independent"] = True
    with pytest.raises(report.SpecError, match="cannot be independent"):
        report.validate_spec(spec)


@pytest.mark.parametrize(
    "change,message",
    [
        ("cycle", "acyclic"),
        ("self", "acyclic"),
        ("active_predecessor", "superseded predecessor"),
        ("orphan", "exactly one applied successor"),
        ("fork", "exactly one applied successor"),
    ],
)
def test_supersession_coherence(change, message):
    spec = selection_history()
    old, current = spec["interpretations"]
    if change == "cycle":
        old["supersedes"] = ["current"]
    elif change == "self":
        current["supersedes"] = ["current"]
    elif change == "active_predecessor":
        old.update(status="active", kind="unresolved_conflict")
    elif change == "orphan":
        current["supersedes"] = []
    else:
        decision(spec, "fork", supersedes=["old"])
    with pytest.raises(report.SpecError, match=message):
        report.validate_spec(spec)


def test_multilevel_history_and_proposed_successor():
    spec = selection_history()
    spec["interpretations"][1]["status"] = "superseded"
    decision(spec, "latest", supersedes=["current"])
    decision(
        spec, "proposal", status="proposed", supersedes=["latest"], verification=[]
    )
    report.validate_spec(spec)
    assert report.interpretation_dependencies(spec) == {"latest": {"trajectory"}}


def test_curated_selection_allows_genuinely_held_out_publication_claim():
    spec = policy_spec()
    curated_target(spec, independent=False)
    decision(spec, target_informed=True, informed_by_targets=["curated"])
    report.validate_spec(spec)
    assert spec["assessment"]["outcome"] == "reproduced"
    assert spec["targets"][0]["independent"]


@pytest.mark.parametrize("status", ["proposed", "rejected"])
def test_inactive_unresolved_decisions_do_not_qualify_publication(status):
    spec = policy_spec()
    decision(spec, status=status, kind="unresolved_conflict", verification=[])
    report.validate_spec(spec)


def test_active_unresolved_qualifies_only_affected_basis():
    spec = policy_spec()
    curated_target(spec)
    item = decision(
        spec, kind="unresolved_conflict", verification=[], affected_targets=["curated"]
    )
    report.validate_spec(spec)
    text = report.render(spec)
    assert "Unresolved qualification: translation" in text
    item["affected_targets"].append("trajectory")
    spec["targets"][0]["decision_ids"].append("translation")
    with pytest.raises(report.SpecError, match="no unresolved"):
        report.validate_spec(spec)
    spec["assessment"].update(outcome="partially_reproduced", confidence="moderate")
    report.validate_spec(spec)


@pytest.mark.parametrize(
    "statuses,expected",
    [
        ([], "not_assessed"),
        (["passed"], "passed"),
        (["failed"], "failed"),
        (["unavailable"], "not_assessed"),
        (["not_assessable"], "not_assessed"),
        (["passed", "unavailable"], "incomplete"),
        (["passed", "not_assessable"], "incomplete"),
        (["failed", "unavailable"], "failed"),
        (["passed", "failed"], "failed"),
    ],
)
def test_curated_status_is_derived(statuses, expected):
    spec = policy_spec()
    for index, status in enumerate(statuses):
        add_target(
            spec,
            f"curated-{index}",
            basis="curated_implementation",
            status=status,
            measured="0.2" if status in {"passed", "failed"} else None,
        )
    spec["artifacts"].append({
        "kind": "reference",
        "locator": "reference.py",
        "sha256": "a" * 64,
    })
    assessment = spec["assessment"]["curated_implementation"]
    assessment.update(status=expected, reference_artifact="reference.py")
    report.validate_spec(spec)
    assessment["status"] = "failed" if expected != "failed" else "passed"
    with pytest.raises(report.SpecError, match="status must be"):
        report.validate_spec(spec)


@pytest.mark.parametrize("change", ["absent", "unknown", "unhashed"])
@pytest.mark.parametrize("status", ["passed", "failed"])
def test_scored_curated_requires_hashed_reference(change, status):
    spec = policy_spec()
    curated_target(spec, status=status)
    assessment = spec["assessment"]["curated_implementation"]
    assessment["status"] = status
    if change == "absent":
        assessment["reference_artifact"] = None
    elif change == "unknown":
        assessment["reference_artifact"] = "unknown"
    else:
        spec["artifacts"][0]["sha256"] = None
    with pytest.raises(report.SpecError, match="reference_artifact"):
        report.validate_spec(spec)


def test_hash_verification_checks_curated_reference_bytes(tmp_path):
    spec = policy_spec()
    curated_target(spec)
    for item, content in (
        (spec["sources"][0], b"paper"),
        (spec["artifacts"][0], b"reference"),
    ):
        (tmp_path / item["locator"]).write_bytes(content)
        item["sha256"] = hashlib.sha256(content).hexdigest()
    report.verify_hashes(spec, tmp_path)
    (tmp_path / "reference.py").write_bytes(b"changed")
    with pytest.raises(report.SpecError, match="SHA-256 mismatch"):
        report.verify_hashes(spec, tmp_path)


def test_curated_only_cannot_establish_publication_reproduced_or_high():
    spec = policy_spec()
    curated_target(spec)
    spec["targets"].pop(0)
    spec["experiments"][0]["target_names"].remove("trajectory")
    with pytest.raises(report.SpecError, match="reproduced requires"):
        report.validate_spec(spec)
    spec["assessment"].update(outcome="implemented_not_assessed", confidence="high")
    with pytest.raises(report.SpecError, match="low confidence"):
        report.validate_spec(spec)
    spec["assessment"]["confidence"] = "low"
    report.validate_spec(spec)


@pytest.mark.parametrize("status", ["failed", "unavailable"])
def test_execution_checks_block_publication_reproduced_and_high(status):
    spec = policy_spec()
    spec["validation"]["checks"][0]["status"] = status
    with pytest.raises(report.SpecError, match="passed execution checks"):
        report.validate_spec(spec)
    spec["assessment"]["outcome"] = "partially_reproduced"
    with pytest.raises(report.SpecError, match="high confidence"):
        report.validate_spec(spec)
    spec["assessment"]["confidence"] = "low"
    report.validate_spec(spec)


@pytest.mark.parametrize("profile", ["concise", "jinko", "audit"])
def test_publication_failure_and_curated_pass_render_separately(profile):
    spec = policy_spec()
    spec["targets"][0].update(status="failed", measured="0.2")
    curated_target(spec)
    spec["assessment"].update(outcome="partially_reproduced", confidence="moderate")
    report.validate_spec(spec)
    text = report.render(spec, profile)
    publication, curated = text.split("## Curated implementation agreement", 1)
    assert "trajectory: `failed`" in publication
    assert "curated: `passed`" not in publication
    assert "curated: `passed`" in curated
    assert "reference.py" in curated
    spec["assessment"]["confidence"] = "high"
    with pytest.raises(report.SpecError, match="high confidence"):
        report.validate_spec(spec)


def test_cli_validation_and_render_are_offline(tmp_path):
    spec = policy_spec()
    decision(spec, kind="source_correction")
    paper = tmp_path / "paper.pdf"
    paper.write_bytes(b"Source text fixture")
    spec["sources"][0]["sha256"] = hashlib.sha256(paper.read_bytes()).hexdigest()
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    assert (
        report.main(["validate", "--spec", str(path), "--base-dir", str(tmp_path)]) == 0
    )
    output = tmp_path / "report.md"
    assert (
        report.main([
            "render",
            "--spec",
            str(path),
            "--base-dir",
            str(tmp_path),
            "--out",
            str(output),
            "--profile",
            "audit",
        ])
        == 0
    )
    assert "source_correction" in output.read_text()


def assumption_spec():
    spec = policy_spec()
    item = decision(spec, kind="assumption", approved_by="Project scientist")
    spec["assumptions"] = [assumption_summary(item)]
    spec["assessment"]["confidence"] = "low"
    return spec


@pytest.mark.parametrize("field", ["statement", "basis", "approved_by", "impact"])
def test_assumption_summary_must_match_authoritative_decision(field):
    spec = assumption_spec()
    spec["assumptions"][0][field] = "Different value"
    with pytest.raises(report.SpecError, match="must match decision"):
        report.validate_spec(spec)


@pytest.mark.parametrize(
    "change",
    ["missing_id", "unknown", "wrong_kind", "inactive", "missing", "duplicate"],
)
def test_assumption_summaries_require_one_active_assumption(change):
    spec = assumption_spec()
    if change == "missing_id":
        del spec["assumptions"][0]["decision_id"]
    elif change == "unknown":
        spec["assumptions"][0]["decision_id"] = "unknown"
    elif change == "wrong_kind":
        spec["interpretations"][0]["kind"] = "source_correction"
    elif change == "inactive":
        spec["interpretations"][0]["status"] = "proposed"
    elif change == "missing":
        spec["assumptions"] = []
    else:
        spec["assumptions"].append(deepcopy(spec["assumptions"][0]))
    with pytest.raises(report.SpecError):
        report.validate_spec(spec)


def test_publication_assumption_blocks_high_and_renders_defense():
    spec = assumption_spec()
    report.validate_spec(spec)
    text = report.render(spec)
    item = spec["interpretations"][0]
    for field in ("decision", "evidence", "implementation_change", "approved_by"):
        assert item[field] in text
    assert "Source paper, Equation 2" in text
    assert "Amount states" in text
    assert "active; assumption" in text
    spec["assessment"]["confidence"] = "high"
    with pytest.raises(report.SpecError, match="active publication assumption"):
        report.validate_spec(spec)


def test_curated_only_assumption_does_not_block_publication_high():
    spec = assumption_spec()
    curated_target(spec)
    spec["interpretations"][0]["affected_targets"] = ["curated"]
    spec["targets"][0]["decision_ids"] = []
    spec["targets"][1]["decision_ids"] = ["translation"]
    spec["assessment"]["confidence"] = "high"
    report.validate_spec(spec)


@pytest.mark.parametrize(
    "field,kind",
    [
        ("repairs", "source_correction"),
        ("repairs", "equivalent_translation"),
        ("repairs", "platform_adaptation"),
        ("unresolved_conflicts", "unresolved_conflict"),
    ],
)
def test_implementation_summaries_accept_active_appropriate_decisions(field, kind):
    spec = policy_spec()
    decision(spec, kind=kind)
    spec["implementation"][field] = ["translation"]
    if kind == "unresolved_conflict":
        spec["assessment"].update(outcome="partially_reproduced", confidence="low")
    report.validate_spec(spec)


@pytest.mark.parametrize("field", ["repairs", "unresolved_conflicts"])
@pytest.mark.parametrize("change", ["unknown", "wrong_kind", "inactive", "duplicate"])
def test_implementation_summaries_reject_invalid_decision_ids(field, change):
    spec = policy_spec()
    kind = "source_correction" if field == "repairs" else "unresolved_conflict"
    item = decision(spec, kind=kind)
    spec["implementation"][field] = ["translation"]
    if change == "unknown":
        spec["implementation"][field] = ["Unstructured explanation"]
    elif change == "wrong_kind":
        item["kind"] = (
            "unresolved_conflict" if field == "repairs" else "source_correction"
        )
    elif change == "inactive":
        item["status"] = "rejected"
    else:
        spec["implementation"][field].append("translation")
    with pytest.raises(report.SpecError, match=field):
        report.validate_spec(spec)


def test_unresolved_summary_cannot_hide_active_conflict():
    spec = policy_spec()
    decision(spec, kind="unresolved_conflict")
    spec["implementation"]["unresolved_conflicts"] = []
    with pytest.raises(report.SpecError, match="every active unresolved"):
        report.validate_spec(spec)


def test_out_of_scope_conflict_requires_named_limitation_and_allows_high():
    spec = policy_spec()
    decision(spec, kind="unresolved_conflict", affected_targets=[])
    with pytest.raises(report.SpecError, match="limitation naming its ID"):
        report.validate_spec(spec)
    spec["limitations"].append(
        "translation: The unsimulated pathway remains unresolved."
    )
    report.validate_spec(spec)
    assert "unsimulated pathway remains unresolved" in report.render(spec)


def test_proposed_assumption_makes_no_current_claim():
    spec = policy_spec()
    decision(spec, kind="assumption", status="proposed", verification=[])
    report.validate_spec(spec)
    assert "Use concentration states" not in report.render(spec)
    assert "proposed; assumption" in report.render(spec, "audit")


REQUIRED_FIELDS = [
    ("interpretations", field)
    for field in (
        "id",
        "status",
        "supersedes",
        "kind",
        "source_statements",
        "affected_components",
        "implementation_change",
        "verification",
        "affected_targets",
        "informed_by_targets",
        "approved_by",
    )
] + [
    ("targets", "basis"),
    ("targets", "decision_ids"),
    ("assessment", "curated_implementation"),
    ("assumptions", "decision_id"),
]


@pytest.mark.parametrize("collection,field", REQUIRED_FIELDS)
@pytest.mark.parametrize("engine", ["custom", "external"])
def test_required_fields_enforced_by_both_schema_engines(collection, field, engine):
    spec = assumption_spec()
    schema = json.loads(
        (
            Path(report.__file__).parents[1]
            / "assets"
            / "reproduction-spec.schema.json"
        ).read_text()
    )
    if engine == "external":
        jsonschema = pytest.importorskip("jsonschema")
        jsonschema.Draft202012Validator.check_schema(schema)
        validate = jsonschema.Draft202012Validator(schema).validate
        error = jsonschema.ValidationError
    else:
        validate = lambda value: report.validate_schema(value, schema, schema)
        error = report.SpecError
    validate(spec)
    container = spec[collection] if collection == "assessment" else spec[collection][0]
    del container[field]
    with pytest.raises(error):
        validate(spec)
