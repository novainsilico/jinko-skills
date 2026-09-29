#!/usr/bin/env python3
"""Validate a paper reproduction specification and render its report."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

OUTCOMES = {
    "reproduced",
    "partially_reproduced",
    "implemented_not_assessed",
    "failed_validation",
    "blocked_evidence",
}
CONFIDENCE = {"high", "moderate", "low", "not_supportable"}
TARGET_STATUSES = {"passed", "failed", "unavailable", "not_assessable"}
CHECK_STATUSES = {"passed", "failed", "unavailable", "not_applicable"}
COVERAGE_KINDS = (
    "states",
    "parameters",
    "equations",
    "initial_conditions",
    "events",
    "scenarios",
)


class SpecError(ValueError):
    """A deterministic specification validation failure."""


def load_spec(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpecError(f"Cannot read specification: {exc}") from exc
    if not isinstance(data, dict):
        raise SpecError("Specification root must be an object")
    return data


def require_keys(item: dict[str, Any], keys: tuple[str, ...], location: str) -> None:
    missing = [key for key in keys if key not in item]
    if missing:
        raise SpecError(f"{location} is missing: {', '.join(missing)}")


def validate_schema(
    instance: Any, schema: dict[str, Any], root: dict[str, Any], path: str = "$"
) -> None:
    if "$ref" in schema:
        reference = schema["$ref"]
        if not reference.startswith("#/$defs/"):
            raise SpecError(f"Unsupported schema reference: {reference}")
        validate_schema(
            instance, root["$defs"][reference.removeprefix("#/$defs/")], root, path
        )
        return
    if "const" in schema and instance != schema["const"]:
        raise SpecError(f"{path} must equal {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        raise SpecError(f"{path} has unsupported value {instance!r}")
    expected = schema.get("type")
    if expected:
        names = expected if isinstance(expected, list) else [expected]
        matches = any(
            (name == "object" and isinstance(instance, dict))
            or (name == "array" and isinstance(instance, list))
            or (name == "string" and isinstance(instance, str))
            or (
                name == "integer"
                and isinstance(instance, int)
                and not isinstance(instance, bool)
            )
            or (name == "boolean" and isinstance(instance, bool))
            or (name == "null" and instance is None)
            for name in names
        )
        if not matches:
            raise SpecError(f"{path} must have type {' or '.join(names)}")
    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        missing = set(schema.get("required", [])) - set(instance)
        if missing:
            raise SpecError(f"{path} is missing: {', '.join(sorted(missing))}")
        additional = schema.get("additionalProperties", True)
        for key, value in instance.items():
            if key in properties:
                validate_schema(value, properties[key], root, f"{path}.{key}")
            elif additional is False:
                raise SpecError(f"{path} contains unsupported property {key!r}")
            elif isinstance(additional, dict):
                validate_schema(value, additional, root, f"{path}.{key}")
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            raise SpecError(f"{path} has too few items")
        if "items" in schema:
            for index, value in enumerate(instance):
                validate_schema(value, schema["items"], root, f"{path}[{index}]")
    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            raise SpecError(f"{path} is too short")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            raise SpecError(f"{path} does not match the required pattern")
    if (
        isinstance(instance, (int, float))
        and not isinstance(instance, bool)
        and "minimum" in schema
    ):
        if instance < schema["minimum"]:
            raise SpecError(f"{path} is below the minimum")


def validate_spec(spec: dict[str, Any]) -> None:
    schema_path = Path(__file__).parents[1] / "assets" / "reproduction-spec.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validate_schema(spec, schema, schema)
    validate_bindings(spec)
    validate_interpretations(spec)
    validate_curated_assessment(spec)

    implementation = spec["implementation"]
    require_keys(
        implementation,
        (
            "status",
            "model_sid",
            "model_revision",
            "unit_policy",
            "repairs",
            "unresolved_conflicts",
        ),
        "implementation",
    )
    validation = spec["validation"]
    require_keys(
        validation, ("diagnostic_errors", "solve_status", "checks"), "validation"
    )
    assessment = spec["assessment"]
    outcome = assessment["outcome"]
    confidence = assessment["confidence"]
    if outcome not in OUTCOMES:
        raise SpecError(f"Unknown outcome: {outcome}")
    if confidence not in CONFIDENCE:
        raise SpecError(f"Unknown confidence: {confidence}")

    errors = validation["diagnostic_errors"]
    solve = validation["solve_status"]
    targets = spec["targets"]
    measured_targets = [
        target for target in targets if target["status"] in {"passed", "failed"}
    ]
    if any(
        not isinstance(target["measured"], str) or not target["measured"].strip()
        for target in measured_targets
    ):
        raise SpecError("passed and failed targets require a measured result")
    for kind in COVERAGE_KINDS:
        item = spec["coverage"][kind]
        if item["implemented"] > item["reported"]:
            raise SpecError(f"coverage.{kind}.implemented cannot exceed reported")
    executable = (
        implementation["status"] == "validated" and errors == 0 and solve == "passed"
    )
    failed_checks = any(
        check["status"] in {"failed", "unavailable"} for check in validation["checks"]
    )
    targets = [target for target in targets if target["basis"] == "publication"]
    publication_names = {target["name"] for target in targets}
    dependencies = interpretation_dependencies(spec)
    target_informed = any(
        publication_names & informed for informed in dependencies.values()
    )
    unresolved = any(
        item["status"] == "active"
        and item["kind"] == "unresolved_conflict"
        and publication_names.intersection(item["affected_targets"])
        for item in spec["interpretations"]
    )
    if outcome == "reproduced" and (
        not executable
        or failed_checks
        or not targets
        or any(target["status"] != "passed" for target in targets)
        or unresolved
        or target_informed
    ):
        raise SpecError(
            "reproduced requires passed execution checks, all targets passed, and no unresolved or target-informed interpretation"
        )
    if outcome == "implemented_not_assessed" and (
        not executable
        or any(target["status"] in {"passed", "failed"} for target in targets)
    ):
        raise SpecError(
            "implemented_not_assessed requires a validated solve and no assessed target"
        )
    if outcome == "partially_reproduced" and (
        not executable
        or not targets
        or not (
            any(target["status"] != "passed" for target in targets)
            or unresolved
            or target_informed
            or failed_checks
        )
    ):
        raise SpecError(
            "partially_reproduced requires a validated solve and a failed target, unavailable target, unresolved conflict, or target-informed interpretation"
        )
    if outcome == "failed_validation" and executable:
        raise SpecError("failed_validation is inconsistent with a validated solve")
    if outcome == "blocked_evidence" and implementation["status"] not in {
        "not_started",
        "blocked",
    }:
        raise SpecError(
            "blocked_evidence requires implementation status not_started or blocked"
        )
    if outcome == "blocked_evidence" and confidence != "not_supportable":
        raise SpecError("blocked_evidence requires not_supportable confidence")
    if outcome == "failed_validation" and confidence != "not_supportable":
        raise SpecError("failed_validation requires not_supportable confidence")
    if outcome == "implemented_not_assessed" and confidence != "low":
        raise SpecError("implemented_not_assessed requires low confidence")
    if confidence == "high":
        reviewed = all(source["reviewed"] for source in spec["sources"])
        independent_pass = any(
            target["status"] == "passed" and target["independent"] for target in targets
        )
        if (
            not executable
            or not reviewed
            or not independent_pass
            or unresolved
            or target_informed
            or failed_checks
            or outcome != "reproduced"
            or any(
                item["status"] == "active"
                and item["kind"] == "assumption"
                and publication_names.intersection(item["affected_targets"])
                for item in spec["interpretations"]
            )
        ):
            raise SpecError(
                "high confidence requires reviewed sources, a validated solve, an independent passed target, and no material conflict, target-informed interpretation, or active publication assumption"
            )
    if confidence == "not_supportable" and outcome not in {
        "failed_validation",
        "blocked_evidence",
    }:
        raise SpecError(
            "not_supportable confidence is reserved for blocked evidence or failed validation"
        )


def interpretation_dependencies(spec: dict[str, Any]) -> dict[str, set[str]]:
    """Return selection targets for active choices, retaining all ancestor evidence.

    Supersession does not prove that evidence was discarded. Keep every
    ancestor's selection targets. Affected held-out targets are not
    selection targets and can remain independent.
    """
    decisions = {item["id"]: item for item in spec["interpretations"]}
    dependencies = {}
    for identity, item in decisions.items():
        if item["status"] != "active":
            continue
        informed = set()
        pending = [identity]
        visited = set()
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            ancestor = decisions[current]
            informed.update(ancestor["informed_by_targets"])
            pending.extend(ancestor["supersedes"])
        dependencies[identity] = informed
    return dependencies


def validate_interpretations(spec: dict[str, Any]) -> None:
    """Check decision references, evidence, and history after schema validation."""

    def unique(values: list, label: str) -> None:
        encoded = [json.dumps(value, sort_keys=True) for value in values]
        if len(set(encoded)) != len(encoded):
            raise SpecError(f"Duplicate {label}")

    for item in spec["interpretations"]:
        for field in ("id", "decision", "evidence", "implementation_change"):
            if not item[field].strip():
                raise SpecError(f"Interpretation {field} must not be blank")
        for statement in item["source_statements"]:
            if any(not value.strip() for value in statement.values()):
                raise SpecError("Source statements must not be blank")
        for check in item["verification"]:
            if not check["name"].strip() or not check["evidence"].strip():
                raise SpecError("Verification name and evidence must not be blank")
        if any(not name.strip() for name in item["affected_components"]):
            raise SpecError("Affected component names must not be blank")
    unique(
        [item["id"] for item in spec["interpretations"]], "interpretation identifiers"
    )
    decisions = {item["id"]: item for item in spec["interpretations"]}
    targets = {target["name"]: target for target in spec["targets"]}
    sources = {source["id"] for source in spec["sources"]}
    successors = {identity: [] for identity in decisions}
    for target in targets.values():
        unique(target["decision_ids"], "target decision_ids")
        if set(target["decision_ids"]) - decisions.keys():
            raise SpecError("Target refers to an unknown interpretation")
    for identity, item in decisions.items():
        for field in (
            "supersedes",
            "affected_components",
            "affected_targets",
            "informed_by_targets",
            "source_statements",
            "alternatives",
        ):
            unique(item[field], f"interpretation {identity} {field}")
        unique([check["name"] for check in item["verification"]], "verification names")
        if any(
            statement["source_id"] not in sources
            for statement in item["source_statements"]
        ):
            raise SpecError("Interpretation refers to an unknown source")
        for field in ("affected_targets", "informed_by_targets"):
            if set(item[field]) - targets.keys():
                raise SpecError(f"Interpretation {field} refers to an unknown target")
        if item["target_informed"] != bool(item["informed_by_targets"]):
            raise SpecError("target_informed must match local informed_by_targets")
        for name in item["informed_by_targets"]:
            if targets[name]["independent"]:
                raise SpecError("An informed_by target cannot be independent")
        for target in targets.values():
            if (target["name"] in item["affected_targets"]) != (
                identity in target["decision_ids"]
            ):
                raise SpecError("Affected targets require bidirectional decision links")
        for predecessor in item["supersedes"]:
            if predecessor not in decisions:
                raise SpecError("Supersession refers to an unknown interpretation")
            successors[predecessor].append(identity)
        if item["status"] == "active":
            if item["kind"] in {
                "source_correction",
                "equivalent_translation",
                "platform_adaptation",
            }:
                checks = item["verification"]
                if not any(check["status"] == "passed" for check in checks) or any(
                    check["status"] in {"failed", "unavailable"} for check in checks
                ):
                    raise SpecError(
                        "Active correction or translation requires passed verification"
                    )
            if item["kind"] == "source_correction" and not item["source_statements"]:
                raise SpecError("Active source_correction requires source evidence")
            if item["kind"] == "assumption" and not (item["approved_by"] or "").strip():
                raise SpecError("Active assumption requires approved_by")

    # Iterative topological traversal also handles long histories without recursion.
    remaining = {
        identity: len(item["supersedes"]) for identity, item in decisions.items()
    }
    ready = [identity for identity, count in remaining.items() if count == 0]
    visited = 0
    while ready:
        predecessor = ready.pop()
        visited += 1
        for successor in successors[predecessor]:
            remaining[successor] -= 1
            if remaining[successor] == 0:
                ready.append(successor)
    if visited != len(decisions):
        raise SpecError("Supersession must be acyclic")
    for identity, item in decisions.items():
        applied_successors = [
            successor
            for successor in successors[identity]
            if decisions[successor]["status"] in {"active", "superseded"}
        ]
        if item["status"] == "superseded" and len(applied_successors) != 1:
            raise SpecError(
                "Superseded interpretation requires exactly one applied successor"
            )
        if applied_successors and item["status"] != "superseded":
            raise SpecError("Applied supersession requires a superseded predecessor")
    validate_decision_summaries(spec, decisions)


def validate_decision_summaries(
    spec: dict[str, Any], decisions: dict[str, dict]
) -> None:
    """Keep summary fields aligned with authoritative decisions."""
    active_assumptions = {
        identity
        for identity, item in decisions.items()
        if item["status"] == "active" and item["kind"] == "assumption"
    }
    summarized = set()
    for summary in spec["assumptions"]:
        identity = summary["decision_id"]
        if identity not in active_assumptions:
            raise SpecError("Assumption decision_id must refer to an active assumption")
        if identity in summarized:
            raise SpecError("Duplicate assumption decision_id")
        summarized.add(identity)
        item = decisions[identity]
        for summary_field, decision_field in (
            ("statement", "decision"),
            ("basis", "evidence"),
            ("approved_by", "approved_by"),
            ("impact", "implementation_change"),
        ):
            if summary[summary_field] != item[decision_field]:
                raise SpecError(
                    f"Assumption {summary_field} must match decision {decision_field}"
                )
    if summarized != active_assumptions:
        raise SpecError("Every active assumption requires exactly one summary")

    kinds = {
        "repairs": {
            "equivalent_translation",
            "platform_adaptation",
            "source_correction",
        },
        "unresolved_conflicts": {"unresolved_conflict"},
    }
    for field, allowed in kinds.items():
        identities = spec["implementation"][field]
        if len(identities) != len(set(identities)):
            raise SpecError(f"Duplicate implementation.{field} decision IDs")
        for identity in identities:
            item = decisions.get(identity)
            if (
                item is None
                or item["status"] != "active"
                or item["kind"] not in allowed
            ):
                raise SpecError(
                    f"implementation.{field} requires active decision IDs of the appropriate kind"
                )
    unresolved = {
        identity
        for identity, item in decisions.items()
        if item["status"] == "active" and item["kind"] == "unresolved_conflict"
    }
    if set(spec["implementation"]["unresolved_conflicts"]) != unresolved:
        raise SpecError(
            "unresolved_conflicts must list every active unresolved decision"
        )
    for identity in unresolved:
        if not decisions[identity]["affected_targets"] and not any(
            re.search(rf"(?<![\w-]){re.escape(identity)}(?![\w-])", limitation)
            for limitation in spec["limitations"]
        ):
            raise SpecError(
                "An unresolved decision with no affected targets requires a limitation naming its ID"
            )


def validate_curated_assessment(spec: dict[str, Any]) -> None:
    curated = spec["assessment"]["curated_implementation"]
    targets = [
        target
        for target in spec["targets"]
        if target["basis"] == "curated_implementation"
    ]
    statuses = [target["status"] for target in targets]
    if "failed" in statuses:
        expected = "failed"
    elif statuses and all(status == "passed" for status in statuses):
        expected = "passed"
    elif "passed" in statuses:
        expected = "incomplete"
    else:
        expected = "not_assessed"
    if curated["status"] != expected:
        raise SpecError(f"curated_implementation.status must be {expected}")
    artifacts = {item["locator"]: item for item in spec["artifacts"]}
    reference = curated["reference_artifact"]
    if reference is not None and reference not in artifacts:
        raise SpecError("Curated reference_artifact requires a recorded artifact")
    if any(status in {"passed", "failed"} for status in statuses) and (
        reference is None or artifacts[reference]["sha256"] is None
    ):
        raise SpecError(
            "Scored curated comparison requires a hashed reference_artifact"
        )
    if not curated["rationale"].strip():
        raise SpecError("Curated assessment requires a rationale")


def validate_bindings(spec: dict[str, Any]) -> None:
    require_keys(spec, ("retrievals", "project_items", "experiments"), "specification")

    def indexed(rows: list[dict], key: str, label: str) -> dict:
        result = {row[key]: row for row in rows}
        if len(result) != len(rows):
            raise SpecError(f"Duplicate {label} identifiers")
        return result

    sources = indexed(spec["sources"], "id", "source")
    targets = indexed(spec["targets"], "name", "target")
    artifacts = {item["locator"] for item in spec["artifacts"]}
    indexed(spec["artifacts"], "locator", "artifact")
    for rows, field in (
        (spec["retrievals"], "source_ids"),
        (spec.get("visual_evidence", []), "target_names"),
    ):
        for row in rows:
            if len(row[field]) != len(set(row[field])):
                raise SpecError(f"Duplicate {field}")
    for visual in spec.get("visual_evidence", []):
        if (
            visual["result_artifact"] not in artifacts
            or visual["image"] not in artifacts
        ):
            raise SpecError(
                "Visual evidence requires recorded image and result artifacts"
            )
        if any(
            name not in targets or targets[name]["status"] not in {"passed", "failed"}
            for name in visual["target_names"]
        ):
            raise SpecError(
                "Visual evidence requires measured targets, including failed comparisons"
            )
    items = indexed(spec["project_items"], "id", "project item")
    experiments = indexed(spec["experiments"], "id", "experiment")
    for item in items.values():
        url = urlsplit(item["url"])
        if not url.hostname or "revision" in parse_qs(url.query):
            raise SpecError("Card URL must be an unversioned SDK URL")
        if url.path.rstrip("/").split("/")[-1] != item["sid"]:
            raise SpecError("Card URL must identify the recorded SID")
        if item["fixed_url"] is not None:
            fixed = urlsplit(item["fixed_url"])
            if (fixed.scheme, fixed.netloc, fixed.path) != (
                url.scheme,
                url.netloc,
                url.path,
            ):
                raise SpecError("Fixed URL must identify the same project item")
            if item["revision"] is not None and parse_qs(fixed.query).get(
                "revision"
            ) != [str(item["revision"])]:
                raise SpecError("Fixed URL must match the recorded revision")
    for attempt in spec["retrievals"]:
        if set(attempt["source_ids"]) - sources.keys():
            raise SpecError("Retrieval refers to an unknown source")
        if attempt["status"] != "retrieved" and attempt["source_ids"]:
            raise SpecError("Unsuccessful retrieval cannot bind retrieved sources")
    bound_targets = set()
    for experiment in experiments.values():
        if experiment["source_id"] not in sources:
            raise SpecError("Experiment refers to an unknown source")
        for kind in ("protocol", "vpop", "output_set", "trial"):
            identity = experiment[f"{kind}_id"]
            if identity is not None and (
                identity not in items or items[identity]["kind"] != kind
            ):
                raise SpecError(f"Experiment requires a known {kind} item")
        for field in ("patient_ids", "target_names"):
            if len(set(experiment[field])) != len(experiment[field]):
                raise SpecError(f"Experiment has duplicate {field}")
        if set(experiment["target_names"]) - targets.keys():
            raise SpecError("Experiment refers to an unknown target")
        bound_targets.update(experiment["target_names"])
        if (
            experiment["protocol_id"] is not None
            or experiment["design_kind"] == "experimental_arm"
        ) and experiment["arm_id"] is None:
            raise SpecError("Protocol binding requires an arm ID")
        if experiment["vpop_id"] is not None and not experiment["patient_ids"]:
            raise SpecError("Vpop binding requires patient IDs")
        if (
            experiment["variability_kind"] == "none"
            and len(experiment["patient_ids"]) > 1
        ):
            raise SpecError("Vpop binding must declare its variability kind")
        if (
            experiment["variability_kind"] == "analytical_control"
            and experiment["target_names"]
        ):
            raise SpecError("Analytical controls cannot score publication targets")
        # A validated model does not imply that every experiment was executed.
        assessed = any(
            targets[name]["status"] in {"passed", "failed"}
            for name in experiment["target_names"]
        )
        if experiment["trial_id"] is not None or assessed:
            if (
                experiment["trial_id"] is not None
                and experiment["output_set_id"] is None
            ):
                raise SpecError("Trial binding requires an output set")
            if (
                experiment["design_kind"] == "experimental_arm"
                and experiment["protocol_id"] is None
            ):
                raise SpecError("Executed experimental arm requires a Protocol")
            if (
                experiment["variability_kind"] != "none"
                and experiment["vpop_id"] is None
            ):
                raise SpecError("Executed variability requires a Vpop")
    if set(targets) - bound_targets:
        raise SpecError("Every target requires an experiment binding")


def verify_hashes(spec: dict[str, Any], base_dir: Path) -> None:
    for collection in ("sources", "artifacts"):
        for index, item in enumerate(spec[collection]):
            expected = item["sha256"]
            if expected is None:
                continue
            path = Path(item["locator"])
            if not path.is_absolute():
                path = base_dir / path
            if not path.is_file():
                if "://" not in item["locator"] and not item["locator"].startswith((
                    "doi:",
                    "PMID:",
                    "bitbucket.org/",
                )):
                    raise SpecError(
                        f"{collection}[{index}] hashed file does not exist: {path}"
                    )
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual.lower() != expected.lower():
                raise SpecError(f"{collection}[{index}] SHA-256 mismatch for {path}")


def coverage_text(item: dict[str, int]) -> str:
    reported = item["reported"]
    implemented = item["implemented"]
    percentage = "n/a" if reported == 0 else f"{100 * implemented / reported:.1f}%"
    return f"{implemented}/{reported} ({percentage})"


def render_comparisons(spec: dict[str, Any]) -> list[str]:
    """Keep publication claims and curated agreement separate in every profile."""
    dependencies = interpretation_dependencies(spec)
    decisions = {item["id"]: item for item in spec["interpretations"]}
    lines = []
    for basis, heading in (
        ("publication", "Publication fidelity"),
        ("curated_implementation", "Curated implementation agreement"),
    ):
        lines.extend([f"## {heading}", ""])
        if basis == "publication":
            lines.append(
                f"Outcome: `{spec['assessment']['outcome']}`; "
                f"confidence: `{spec['assessment']['confidence']}`."
            )
        else:
            assessment = spec["assessment"]["curated_implementation"]
            lines.append(
                f"Status: `{assessment['status']}`. {assessment['rationale']} "
                f"Reference artifact: {assessment['reference_artifact'] or 'none'}."
            )
        targets = [target for target in spec["targets"] if target["basis"] == basis]
        for target in targets:
            lines.append(
                f"- {target['name']}: `{target['status']}`. {target['metric']}: "
                f"{target['measured'] or 'unavailable'}; declared tolerance: {target['tolerance']}. "
                f"Source: {target['source_locator']}. "
                f"Independent: {'yes' if target['independent'] else 'no'}. "
                f"Transformation: {target['transformation'] or 'none'}."
            )
            active = [
                identity
                for identity in target["decision_ids"]
                if identity in dependencies
            ]
            informed = set().union(*(dependencies[identity] for identity in active))
            selected = [
                identity
                for identity, names in dependencies.items()
                if target["name"] in names
            ]
            unresolved = [
                identity
                for identity in active
                if decisions[identity]["kind"] == "unresolved_conflict"
            ]
            lines.append(
                f"  Active decisions: {', '.join(active) or 'none'}. "
                f"Choice dependencies (including history): {', '.join(sorted(informed)) or 'none'}. "
                f"Used to choose: {', '.join(selected) or 'none'}. "
                f"Unresolved qualification: {', '.join(unresolved) or 'none'}."
            )
        if not targets:
            lines.append(
                "No quantitative target is available in the current evidence packet."
            )
        lines.append("")
    return lines


def render_decisions(spec: dict[str, Any], history: bool = False) -> list[str]:
    lines = [
        "## Interpretation history"
        if history
        else "## Active interpretation decisions",
        "",
    ]
    dependencies = interpretation_dependencies(spec)
    items = [
        item
        for item in spec["interpretations"]
        if history or item["status"] == "active"
    ]
    for item in items:
        lines.append(
            f"- {item['id']} [{item['status']}; {item['kind']}]: {item['decision']} "
            f"Change: {item['implementation_change']} "
            f"Components: {', '.join(item['affected_components']) or 'none'}. "
            f"Affected targets: {', '.join(item['affected_targets']) or 'none'}. "
            f"Selection targets (including history for active choices): "
            f"{', '.join(sorted(dependencies.get(item['id'], set(item['informed_by_targets'])))) or 'none'}. "
            f"Approved by: {item['approved_by'] or 'not recorded'}."
        )
        lines.append(
            f"  Evidence: {item['evidence']} "
            f"Alternatives: {', '.join(item['alternatives']) or 'none'}."
        )
        lines.extend(
            f"  Source {statement['source_id']}, {statement['locator']}: {statement['statement']}"
            for statement in item["source_statements"]
        )
        if history:
            lines.append(
                f"  Supersedes: {', '.join(item['supersedes']) or 'none'}. "
                f"Local target-informed: {'yes' if item['target_informed'] else 'no'}."
            )
        lines.extend(
            f"  Verification {check['name']}: `{check['status']}`. {check['evidence']}"
            for check in item["verification"]
        )
    if not items:
        lines.append("No interpretation decisions recorded.")
    lines.append("")
    return lines


def _render_audit(spec: dict[str, Any]) -> str:
    paper = spec["paper"]
    implementation = spec["implementation"]
    validation = spec["validation"]
    assessment = spec["assessment"]
    digest = hashlib.sha256(
        json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    lines = [
        f"# Reproduction report: {paper['title']}",
        "",
        "## Claim and outcome",
        "",
        f"- Scope: {spec['scope']}",
        f"- Citation: {paper['citation']}",
        f"- Identifier: {paper['identifier']}",
        f"- Outcome: `{assessment['outcome']}`",
        f"- Reproduction confidence: `{assessment['confidence']}`",
        f"- Rationale: {assessment['rationale']}",
        f"- Specification SHA-256: `{digest}`",
        "",
        "## Sources and extraction",
        "",
        "| Source | Kind | Locator | Extraction | Reviewed | SHA-256 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{source['id']}` | {source['kind']} | {source['locator']} | {source['extraction']} | "
        f"{'Yes' if source['reviewed'] else 'No'} | `{source['sha256']}` |"
        for source in spec["sources"]
    )
    if spec["retrievals"]:
        lines.extend(["", "## Supplementary retrieval", ""])
        for attempt in spec["retrievals"]:
            lines.append(
                f"- {attempt['purpose']}: `{attempt['status']}`. {attempt['url']}. {attempt['note']} Sources: {', '.join(attempt['source_ids']) or 'none'}."
            )
    if spec["experiments"]:
        lines.extend(["", "## Experiment bindings", ""])
        for experiment in spec["experiments"]:
            lines.extend([
                f"### {experiment['id']}",
                "",
                f"- Design: `{experiment['design_kind']}`. Source: {experiment['source_id']}, {experiment['source_locator']}.",
                f"- Protocol: {experiment['protocol_id'] or 'none'}; arm: {experiment['arm_id'] or 'none'}.",
                f"- Vpop: {experiment['vpop_id'] or 'none'}; rows: {', '.join(experiment['patient_ids']) or 'none'}.",
                f"- Variability: `{experiment['variability_kind']}`. {experiment['variability_evidence']}",
                f"- Output set: {experiment['output_set_id'] or 'none'}; Trial: {experiment['trial_id'] or 'none'}.",
                f"- Targets: {', '.join(experiment['target_names']) or 'none'}. Mapping: {experiment['observable_mapping']}",
                f"- Note: {experiment['note']}",
                "",
            ])
    lines.append("")
    lines.extend(render_decisions(spec, history=True))
    lines.extend(["", "Assumptions:"])
    if spec["assumptions"]:
        lines.extend(
            f"- {item['statement']} Basis: {item['basis']}. Approved by: {item['approved_by'] or 'not approved'}. Impact: {item['impact']}"
            for item in spec["assumptions"]
        )
    else:
        lines.append("- None recorded.")
    if spec["project_items"]:
        lines.extend(["", "## Jinkō project items", ""])
        seen_urls = set()
        for item in spec["project_items"]:
            lines.extend([f"{item['kind']}: [{item['id']}]({item['url']})", ""])
            if item["url"] not in seen_urls:
                lines.extend([item["url"], ""])
                seen_urls.add(item["url"])
            if item["fixed_url"] and item["revision"] is not None:
                lines.extend([
                    f"[Fixed revision {item['revision']}]({item['fixed_url']})",
                    "",
                ])
    lines.extend([
        "",
        "## Reconstructed model",
        "",
        f"- Implementation status: `{implementation['status']}`",
        f"- Jinkō model: `{implementation['model_sid'] or 'not created'}`",
        f"- Fixed revision: `{implementation['model_revision'] if implementation['model_revision'] is not None else 'not available'}`",
        f"- Unit policy: {implementation['unit_policy'] or 'not established'}",
        "",
        "## Source fidelity",
        "",
        "| Element | Coverage |",
        "| --- | ---: |",
    ])
    lines.extend(
        f"| {kind.replace('_', ' ').title()} | {coverage_text(spec['coverage'][kind])} |"
        for kind in COVERAGE_KINDS
    )
    lines.extend(["", "## Implementation fidelity", ""])
    lines.append("Repairs:")
    if implementation["repairs"]:
        lines.extend(f"- {item}" for item in implementation["repairs"])
    else:
        lines.append("- None")
    lines.append("")
    lines.append("Unresolved conflicts:")
    if implementation["unresolved_conflicts"]:
        lines.extend(f"- {item}" for item in implementation["unresolved_conflicts"])
    else:
        lines.append("- None")
    lines.extend([
        "",
        "## Execution fidelity",
        "",
        f"- Error diagnostics: `{validation['diagnostic_errors']}`",
        f"- Solve status: `{validation['solve_status']}`",
        "",
        "| Check | Status | Evidence |",
        "| --- | --- | --- |",
    ])
    lines.extend(
        f"| {item['name']} | `{item['status']}` | {item['evidence']} |"
        for item in validation["checks"]
    )
    lines.append("")
    lines.extend(render_comparisons(spec))
    lines.extend(["", "## Artifacts", ""])
    if spec["artifacts"]:
        lines.extend(
            f"- {item['kind']}: {item['locator']}"
            + (f" (`{item['sha256']}`)" if item["sha256"] else "")
            for item in spec["artifacts"]
        )
    else:
        lines.append("- None recorded.")
    lines.extend([
        "",
        "## Confidence",
        "",
        f"`{assessment['confidence']}`: {assessment['rationale']}",
        "",
        "## Limitations and next steps",
        "",
    ])
    if spec["limitations"]:
        lines.extend(f"- {item}" for item in spec["limitations"])
    else:
        lines.append("- None recorded")
    return "\n".join(lines) + "\n"


def link_identities(text: str, spec: dict[str, Any]) -> str:
    """Link recorded SIDs without changing URLs or existing Markdown links."""
    identities = {item["sid"]: item["url"] for item in spec["project_items"]}
    sid = spec["implementation"]["model_sid"]
    if sid and sid not in identities:
        identities[sid] = None
    parts = re.split(r"(\[[^\]\n]*\]\(https?://[^\s)]+\)|https?://[^\s)<>]+)", text)
    for index in range(0, len(parts), 2):
        for identity, url in sorted(identities.items(), key=lambda pair: -len(pair[0])):
            replacement = f"[Project item]({url})" if url else "Model link unavailable"
            parts[index] = re.sub(
                rf"(?<![\w-])`?{re.escape(identity)}`?(?![\w-])",
                lambda match: replacement,
                parts[index],
            )
    return "".join(parts)


SID_PATTERN = re.compile(r"(?<![\w-])[a-z]{2}-[A-Za-z0-9]{4}-[A-Za-z0-9]{4}(?![\w-])")


def naked_sids(text: str) -> list[str]:
    """SIDs that appear as bare text rather than inside a link.

    Every human-facing SID belongs in a full SDK link, so a reader can open it.
    Raw identifiers stay in the machine-readable specification. Checking the
    rendered Markdown is deterministic, which reading it over is not.
    """
    outside_links = re.split(
        r"\[[^\]\n]*\]\(https?://[^\s)]+\)|https?://[^\s)<>]+", text
    )
    return sorted({
        match for part in outside_links for match in SID_PATTERN.findall(part)
    })


def render(spec: dict[str, Any], profile: str = "concise") -> str:
    """Render a concise report or a complete local audit without changing targets."""
    if profile not in {"concise", "jinko", "audit"}:
        raise SpecError(f"Unknown report profile: {profile}")
    items = spec["project_items"]
    if profile == "jinko":
        model_sid = spec["implementation"]["model_sid"]
        if model_sid and not any(item["sid"] == model_sid for item in items):
            raise SpecError("Publishing requires the model's SDK .url in project_items")
    lines = [f"# Reproduction report: {spec['paper']['title']}", ""]
    seen = set()
    for item in sorted(items, key=lambda item: item["kind"] == "reference"):
        if item["url"] not in seen:
            lines.extend([item["url"], ""])
            seen.add(item["url"])
    assessment = spec["assessment"]
    lines.extend([
        "## Essential findings",
        "",
        f"- Outcome: `{assessment['outcome']}`",
        f"- Reproduction confidence: `{assessment['confidence']}`",
        f"- {assessment['rationale']}",
        f"- Scope: {spec['scope']}",
        "",
    ])
    lines.extend(render_comparisons(spec))
    lines.extend(render_decisions(spec))
    for visual in spec.get("visual_evidence", []):
        lines.extend([
            "",
            f"![{visual['caption']}]({visual['image']})",
            "",
            f"{visual['caption']} Source: {visual['source_locator']}. "
            f"Targets: {', '.join(visual['target_names'])}. "
            f"Uncertainty: {visual['uncertainty']}.",
        ])
    lines.extend(["", "## Limitations and next steps", ""])
    lines.extend(f"- {item}" for item in spec["limitations"])
    for attempt in spec["retrievals"]:
        if attempt["status"] == "awaiting_user_source":
            lines.append(
                f"- `awaiting_user_source`: {attempt['purpose']}. {attempt['note']}"
            )
    lines.extend(["", f"Source: {spec['paper']['citation']}", ""])
    for item in items:
        if item["fixed_url"]:
            lines.append(
                f"{item['kind']}: [Fixed revision {item['revision']}]({item['fixed_url']})"
            )
    if profile == "audit":
        lines.extend([
            "",
            "## Local audit appendix",
            "",
            _render_audit(spec).split("\n", 1)[1],
        ])
    text = link_identities("\n".join(lines).rstrip() + "\n", spec)
    bare = naked_sids(text)
    if bare:
        raise SpecError(
            "Rendered report contains bare SIDs; record each one in project_items "
            "so it renders as a link: " + ", ".join(bare)
        )
    return text


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--spec", type=Path, required=True)
    validate.add_argument("--base-dir", type=Path, default=Path.cwd())
    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("--spec", type=Path, required=True)
    render_parser.add_argument("--out", type=Path, required=True)
    render_parser.add_argument("--base-dir", type=Path, default=Path.cwd())
    render_parser.add_argument("--overwrite", action="store_true")
    render_parser.add_argument(
        "--profile", choices=("concise", "jinko", "audit"), default="concise"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        spec = load_spec(args.spec)
        validate_spec(spec)
        verify_hashes(spec, args.base_dir)
        if args.command == "render":
            if args.out.exists() and not args.overwrite:
                raise SpecError(f"Refusing to overwrite {args.out}; pass --overwrite")
            args.out.parent.mkdir(parents=True, exist_ok=True)
            rendered = render(spec, profile=args.profile)
            args.out.write_text(rendered, encoding="utf-8")
            print(f"Wrote {args.out}")
        else:
            print("Specification is valid")
        return 0
    except SpecError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
