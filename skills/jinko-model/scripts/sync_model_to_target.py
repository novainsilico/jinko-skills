#!/usr/bin/env python3
"""Make an existing Jinkō model match a declarative target, through a computed diff.

The target is a JSON file that lists the components the model must contain:

    {
      "unit_check": "UnitCheckAndConvertAllSpeciesToExtentUnits",   # optional
      "parameters":   [{"id": "k", "formula": "0.1", "unit": "1/h", "tags": ["s::knowledge"],
                        "description": "...", "constant": null}],
      "compartments": [{"id": "central", "volume": "5", "unit": "L"}],
      "species":      [{"id": "Drug", "compartment": "central", "initial_condition": "0", "unit": "nmol"}],
      "odes":         [{"id": "ode_Drug", "left_side": "Drug", "right_side": "-k * Drug"}],
      "events":       [{"id": "dose", "updates": {"Drug": "Drug + dose"},
                        "time_trigger_first_time": "t0", "time_trigger_every": "tau",
                        "time_trigger_count": "n", "record": true}]
    }

The script reads the latest version of the model, computes create, edit, and
(with --prune) delete operations, and prints the plan. It is a dry run by
default. With --apply it commits the plan in batches, then reports diagnostics.
Pass --base-snapshot to refuse the sync when the model changed since you
inspected it. Tags are added, never removed. Events are only checked for
presence: a missing event is created, an existing event is left unchanged.
"""

from __future__ import annotations

import argparse
import ast
import cmath
import json
import math
import operator
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - depends on local environment
    load_dotenv = None

BATCH_SIZE = 150
KINDS = ("parameters", "compartments", "species", "odes", "events")


# ---------------------------------------------------------------------------
# Pure diff logic (no SDK calls)
# ---------------------------------------------------------------------------


_NUMBER = re.compile(
    r"(?<![A-Za-z_\d.])(\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)"
)
_UNIT_CALL = re.compile(r"u\(([^()]*)\)")

try:  # optional: semantic unit comparison
    import pint

    _UREG = pint.UnitRegistry()
except Exception:  # pragma: no cover - pint is optional
    _UREG = None


def canonical_unit(value: Any) -> str:
    """Canonical form of a unit string; Jinkō stores `nM` as `nanomolar` and `g/mol` as `g / mol`."""
    if value in (None, ""):
        return ""
    text = re.sub(r"\s+", "", str(value)).replace("^", "**")
    if text == "dimensionless":
        return text
    if _UREG is not None:
        try:
            q = _UREG.Quantity(1, text).to_base_units()
            dims = ",".join(f"{k}{v:g}" for k, v in sorted(q.dimensionality.items()))
            return f"{q.magnitude:.12g}|{dims}"
        except Exception:
            pass
    return text


def _strip_outer_parens(text: str) -> str:
    while text.startswith("(") and text.endswith(")"):
        depth = 0
        for i, ch in enumerate(text):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0 and i < len(text) - 1:
                return text
        text = text[1:-1]
    return text


def norm_formula(value: Any) -> str:
    """Normalize a formula or literal the way Jinkō canonicalizes it.

    Jinkō rewrites `8` as `8.0`, `0.055` as `5.5e-2`, drops redundant outer
    parentheses, and spells units in long form inside `u(...)`.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return repr(float(value))
    text = re.sub(r"\s+", "", str(value)).replace("**", "^")
    text = _UNIT_CALL.sub(lambda m: f"u({canonical_unit(m.group(1))})", text)
    text = _NUMBER.sub(lambda m: repr(float(m.group(1))), text)
    return _strip_outer_parens(text)


def norm_unit(value: Any) -> str:
    return canonical_unit(value)


def same_number(a: Any, b: Any) -> bool:
    try:
        x, y = float(a), float(b)
    except (TypeError, ValueError):
        return False
    return math.isclose(x, y, rel_tol=1e-12, abs_tol=0.0)


_IDENT = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


def _unit_factor(text: str) -> float:
    if _UREG is not None:
        try:
            return float(
                _UREG.Quantity(1, text.replace("^", "**")).to_base_units().magnitude
            )
        except Exception:
            pass
    return float(abs(hash(re.sub(r"\s+", "", text))) % 997 + 2)


def _evaluable(text: str) -> str:
    text = _UNIT_CALL.sub(lambda m: repr(_unit_factor(m.group(1))), str(text))
    return text.replace("^", "**")


_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _arithmetic(tree: ast.Expression, env: dict[str, float]) -> Any:
    """Evaluate numbers, symbols, the four operations, and powers; refuse the rest.

    The walk uses its own stack, so a long sum does not reach Python's
    recursion limit.
    """
    values: list[Any] = []
    stack: list[tuple[ast.AST, bool]] = [(tree.body, False)]
    while stack:
        node, operands_done = stack.pop()
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            # A float power overflows; an int power would grow without bound.
            values.append(float(node.value))
        elif isinstance(node, ast.Name):
            values.append(env[node.id])
        elif isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            if operands_done:
                right, left = values.pop(), values.pop()
                values.append(_BINARY[type(node.op)](left, right))
            else:
                stack += [(node, True), (node.right, False), (node.left, False)]
        elif isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            if operands_done:
                values.append(_UNARY[type(node.op)](values.pop()))
            else:
                stack += [(node, True), (node.operand, False)]
        else:
            raise ValueError(f"not arithmetic: {type(node).__name__}")
    return values.pop()


def same_by_evaluation(a: Any, b: Any, trials: int = 3) -> bool:
    """Equal when both expressions give the same value at random positive symbol values.

    Catches rewrites that Jinkō applies on storage (dropped parentheses, leading
    `+`, `8` for `8.0`). Only arithmetic is evaluated, never as Python code:
    expressions with functions or conditionals compare as different, which only
    adds a harmless edit.
    """
    import random

    ea, eb = _evaluable(a), _evaluable(b)
    try:
        ta, tb = ast.parse(ea, mode="eval"), ast.parse(eb, mode="eval")
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        # Invalid text, a null byte, or nesting deeper than the parser accepts.
        return False
    names = (set(_IDENT.findall(ea)) | set(_IDENT.findall(eb))) - {"e"}
    rng = random.Random(len(ea) + len(eb))
    for _ in range(trials):
        env = {n: rng.uniform(0.5, 2.0) for n in names}
        try:
            va = _arithmetic(ta, env)
            vb = _arithmetic(tb, env)
        except Exception:
            return False
        if not cmath.isclose(complex(va), complex(vb), rel_tol=1e-9, abs_tol=1e-12):
            return False
    return True


def same_formula(a: Any, b: Any) -> bool:
    if norm_formula(a) == norm_formula(b) or same_number(a, b):
        return True
    return isinstance(a, str) and isinstance(b, str) and same_by_evaluation(a, b)


@dataclass
class Plan:
    creates: list[tuple[str, dict]] = field(default_factory=list)
    edits: list[tuple[str, str, dict]] = field(
        default_factory=list
    )  # kind, id, {field: (old, new)}
    tag_adds: list[tuple[str, str, list[str]]] = field(default_factory=list)
    deletes: list[tuple[str, str]] = field(default_factory=list)
    unmanaged: list[tuple[str, str]] = field(default_factory=list)

    def empty(self) -> bool:
        return not (self.creates or self.edits or self.tag_adds or self.deletes)

    def summary(self) -> dict:
        return {
            "create": len(self.creates),
            "edit": len(self.edits),
            "add_tags": len(self.tag_adds),
            "delete": len(self.deletes),
            "present_in_model_only": len(self.unmanaged),
        }


FIELDS = {
    "parameters": (
        ("formula", same_formula),
        ("unit", lambda a, b: norm_unit(a) == norm_unit(b)),
        ("description", lambda a, b: (a or "") == (b or "")),
    ),
    "compartments": (
        ("volume", same_formula),
        ("unit", lambda a, b: norm_unit(a) == norm_unit(b)),
    ),
    "species": (
        ("compartment", lambda a, b: a == b),
        ("initial_condition", same_formula),
        ("unit", lambda a, b: norm_unit(a) == norm_unit(b)),
    ),
    "odes": (("left_side", lambda a, b: a == b), ("right_side", same_formula)),
}


def compute_plan(target: dict, current: dict, prune: bool = False) -> Plan:
    """Compare a target with the current components.

    ``current`` maps each kind to ``{id: {field: value, "tags": [...]}}``.
    Only fields present in a target entry are compared, so a target can leave
    a field unmanaged by omitting it.
    """
    plan = Plan()
    for kind in KINDS:
        cur = current.get(kind, {})
        wanted = {c["id"]: c for c in target.get(kind, [])}
        for cid, spec in wanted.items():
            if cid not in cur:
                plan.creates.append((kind, spec))
                continue
            if kind == "events":  # presence only
                continue
            changes = {}
            for name, eq in FIELDS[kind]:
                if name in spec and not eq(cur[cid].get(name), spec[name]):
                    changes[name] = (cur[cid].get(name), spec[name])
            if changes:
                plan.edits.append((kind, cid, changes))
            missing_tags = [
                t for t in spec.get("tags", []) if t not in cur[cid].get("tags", [])
            ]
            if missing_tags:
                plan.tag_adds.append((kind, cid, missing_tags))
        for cid in cur:
            if cid not in wanted:
                (plan.deletes if prune else plan.unmanaged).append((kind, cid))
    return plan


# ---------------------------------------------------------------------------
# SDK side
# ---------------------------------------------------------------------------


def read_current(model, tag_names: set[str]) -> dict:
    """Read the components of the model head.

    Tag membership is read with one filtered listing per tag named in the
    target, because reading ``component.tags`` costs one request per component.
    """
    comps = model.components
    members: dict[str, set[str]] = {}
    for name in sorted(tag_names):
        try:
            members[name] = {c.id for c in comps.list(tags_any=[name])}
        except Exception:  # tag not declared in this model yet
            members[name] = set()

    def tags(c):
        return [name for name, ids in members.items() if c.id in ids]

    return {
        "parameters": {
            c.id: {
                "formula": c.formula,
                "unit": c.unit,
                "description": c.description,
                "tags": tags(c),
            }
            for c in comps.list_parameters()
        },
        "compartments": {
            c.id: {"volume": c.volume, "unit": c.unit, "tags": tags(c)}
            for c in comps.list_compartments()
        },
        "species": {
            c.id: {
                "compartment": c.compartment,
                "initial_condition": c.initial_condition,
                "unit": c.unit,
                "tags": tags(c),
            }
            for c in comps.list_species()
        },
        "odes": {
            c.id: {
                "left_side": c.left_side,
                "right_side": c.right_side,
                "tags": tags(c),
            }
            for c in comps.list_odes()
        },
        "events": {c.id: {"tags": tags(c)} for c in comps.list_events()},
    }


CREATE_ARGS = {
    "parameters": ("id", "formula", "unit", "constant", "description", "tags"),
    "compartments": ("id", "volume", "unit", "constant", "description", "tags"),
    "species": (
        "id",
        "compartment",
        "initial_condition",
        "unit",
        "constant",
        "description",
        "tags",
    ),
    "odes": ("id", "left_side", "right_side", "description", "tags"),
    "events": (
        "id",
        "updates",
        "condition_trigger",
        "time_trigger_first_time",
        "time_trigger_every",
        "time_trigger_count",
        "time_trigger_until",
        "record",
        "description",
        "tags",
    ),
}
CREATE_METHOD = {
    "parameters": "create_parameter",
    "compartments": "create_compartment",
    "species": "create_species",
    "odes": "create_ode",
    "events": "create_event",
}
EDIT_METHOD = {
    "parameters": "edit_parameter",
    "compartments": "edit_compartment",
    "species": "edit_species",
    "odes": "edit_ode",
}
# Create order matters: compartments before species, species before odes and events.
CREATE_ORDER = ("parameters", "compartments", "species", "odes", "events")


def operations(plan: Plan) -> list[tuple]:
    ops: list[tuple] = []
    for kind in CREATE_ORDER:
        ops += [("create", kind, spec) for k, spec in plan.creates if k == kind]
    ops += [("edit", kind, cid, ch) for kind, cid, ch in plan.edits]
    ops += [("tags", kind, cid, tg) for kind, cid, tg in plan.tag_adds]
    # delete equations before the species they define
    for kind in ("events", "odes", "species", "compartments", "parameters"):
        ops += [("delete", k, cid) for k, cid in plan.deletes if k == kind]
    return ops


def apply_op(batch, op) -> None:
    action, kind = op[0], op[1]
    if action == "create":
        spec = op[2]
        kwargs = {
            k: spec[k] for k in CREATE_ARGS[kind] if k in spec and spec[k] is not None
        }
        getattr(batch, CREATE_METHOD[kind])(**kwargs)
    elif action == "edit":
        draft = getattr(batch, EDIT_METHOD[kind])(op[2])
        for name, (_, new) in op[3].items():
            getattr(draft, f"set_{name}")(new)
    elif action == "tags":
        draft = getattr(batch, EDIT_METHOD.get(kind, "edit_event"))(op[2])
        for tag in op[3]:
            draft.add_tag(tag)
    elif action == "delete":
        batch.delete(op[2])


def print_plan(plan: Plan, limit: int) -> None:
    print("Plan:", json.dumps(plan.summary()))
    for kind, spec in plan.creates[:limit]:
        print(f"  create {kind[:-1]} {spec['id']}")
    for kind, cid, ch in plan.edits[:limit]:
        for name, (old, new) in ch.items():
            print(
                f"  edit {kind[:-1]} {cid}.{name}: {str(old)[:80]!r} -> {str(new)[:80]!r}"
            )
    for kind, cid, tg in plan.tag_adds[:limit]:
        print(f"  add tags {kind[:-1]} {cid}: {tg}")
    for kind, cid in plan.deletes[:limit]:
        print(f"  delete {kind[:-1]} {cid}")
    if plan.unmanaged:
        print(
            f"  {len(plan.unmanaged)} components exist only in the model; pass --prune to delete them, "
            f"for example {[c for _, c in plan.unmanaged[:5]]}"
        )
    shown = max(
        len(plan.creates), len(plan.edits), len(plan.tag_adds), len(plan.deletes)
    )
    if shown > limit:
        print(f"  ... output truncated to {limit} lines per action (--show to change)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync an existing Jinkō model to a declarative target."
    )
    parser.add_argument(
        "--model-sid", required=True, help="Computational model SID, for example cm-..."
    )
    parser.add_argument(
        "--target", required=True, type=Path, help="Target components JSON file."
    )
    parser.add_argument(
        "--base-snapshot",
        help="Refuse to sync if the model head is not this snapshot id.",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Delete components that are not in the target.",
    )
    parser.add_argument("--version-name", default="sync to target")
    parser.add_argument(
        "--show", type=int, default=40, help="Lines of plan to print per action."
    )
    parser.add_argument("--apply", action="store_true", help="Commit the plan.")
    args = parser.parse_args()

    target = json.loads(args.target.read_text())
    if load_dotenv is not None:
        load_dotenv()
    try:
        from jinko import JinkoClient
        from jinko.exceptions import JinkoError
    except ImportError:
        print(
            "Cannot import jinko. Install the SDK: pip install jinko-sdk",
            file=sys.stderr,
        )
        return 1

    try:
        client = JinkoClient()
        model = client.get_model(args.model_sid)
        print(f"Model {model.sid} head snapshot {model.snapshot_id}")
        if args.base_snapshot and model.snapshot_id != args.base_snapshot:
            print(
                f"Model changed since snapshot {args.base_snapshot}; inspect it and rerun.",
                file=sys.stderr,
            )
            return 4
        tag_names = {
            t for kind in KINDS for c in target.get(kind, []) for t in c.get("tags", [])
        }
        plan = compute_plan(target, read_current(model, tag_names), prune=args.prune)
        unit_check = target.get("unit_check")
        unit_change = bool(unit_check) and model.get_unit_check() != unit_check
        print_plan(plan, args.show)
        if unit_change:
            print(f"  set unit check: {model.get_unit_check()} -> {unit_check}")
        if plan.empty() and not unit_change:
            print("Model already matches the target.")
            return 0
        if not args.apply:
            print(
                f"Dry run. Rerun with --apply --base-snapshot {model.snapshot_id} to commit."
            )
            return 0

        if unit_change:
            model.set_unit_check(unit_check)
        ops = operations(plan)
        for n, start in enumerate(range(0, len(ops), BATCH_SIZE)):
            with model.components.batch(
                version=f"{args.version_name} ({n + 1})"
            ) as batch:
                for op in ops[start : start + BATCH_SIZE]:
                    apply_op(batch, op)
        refreshed = client.get_model(args.model_sid)
        errors = list(refreshed.diagnostics.errors())
        print(f"Committed {len(ops)} operations; head snapshot {refreshed.snapshot_id}")
        if errors:
            print("Model diagnostics contain errors:", file=sys.stderr)
            for entry in errors[:40]:
                d = entry.diagnostic
                print(f"- {entry.component.id}: {d.code} {d.message}", file=sys.stderr)
            return 3
        return 0
    except JinkoError as exc:
        print(f"Jinkō SDK request failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
