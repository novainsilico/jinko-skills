#!/usr/bin/env python3
"""Fetch, validate, and deterministically filter the public Jinkō model library."""

from __future__ import annotations

import argparse
import json
from typing import Any
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

LIBRARY_URL = "https://doc.jinko.ai/model-library.json"
TRUSTED_HOST = "doc.jinko.ai"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
REQUIRED_FIELDS = (
    "projectName",
    "type",
    "groupName",
    "description",
    "contextOfUse",
    "inputs",
    "outputs",
    "Access",
)


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def fetch_library() -> bytes:
    request = Request(
        LIBRARY_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "jinko-skills-model-library/1",
        },
    )
    opener = build_opener(NoRedirectHandler())
    with opener.open(request, timeout=20) as response:  # noqa: S310 - fixed URL
        final_url = urlsplit(response.geturl())
        if final_url.scheme != "https" or final_url.hostname != TRUSTED_HOST:
            raise ValueError(
                f"Refusing model-library redirect to {response.geturl()!r}"
            )
        declared_size = response.headers.get("Content-Length")
        if declared_size and int(declared_size) > MAX_RESPONSE_BYTES:
            raise ValueError("Model-library response exceeds the 5 MiB limit")
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ValueError("Model-library response exceeds the 5 MiB limit")
    return payload


def validate_library(payload: bytes) -> list[dict[str, str]]:
    parsed = json.loads(payload)
    if not isinstance(parsed, list):
        raise ValueError("Model library must be a JSON array")

    records: list[dict[str, str]] = []
    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise ValueError(f"Model record {index} is not an object")
        missing = [field for field in REQUIRED_FIELDS if field not in item]
        if missing:
            raise ValueError(f"Model record {index} is missing: {', '.join(missing)}")
        invalid = [
            field for field in REQUIRED_FIELDS if not isinstance(item[field], str)
        ]
        if invalid:
            raise ValueError(
                f"Model record {index} has non-string fields: {', '.join(invalid)}"
            )
        records.append({field: item[field] for field in REQUIRED_FIELDS})
    return records


def filter_library(
    records: list[dict[str, str]],
    *,
    query: str | None,
    model_type: str | None,
    group: str | None,
    access: str | None,
) -> list[dict[str, str]]:
    query_value = query.casefold() if query else None

    def matches(record: dict[str, str]) -> bool:
        if model_type and record["type"].casefold() != model_type.casefold():
            return False
        if group and record["groupName"].casefold() != group.casefold():
            return False
        if access and record["Access"].casefold() != access.casefold():
            return False
        if query_value and not any(
            query_value in record[field].casefold() for field in REQUIRED_FIELDS
        ):
            return False
        return True

    return sorted(
        (record for record in records if matches(record)),
        key=lambda record: (
            record["projectName"].casefold(),
            record["type"].casefold(),
            record["groupName"].casefold(),
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--query", help="Case-insensitive text contained in any required field"
    )
    parser.add_argument("--type", dest="model_type", help="Exact model type")
    parser.add_argument("--group", help="Exact group name")
    parser.add_argument("--access", help="Exact Access value")
    parser.add_argument("--limit", type=int, default=20, choices=range(1, 101))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = validate_library(fetch_library())
    matches = filter_library(
        records,
        query=args.query,
        model_type=args.model_type,
        group=args.group,
        access=args.access,
    )
    output: dict[str, Any] = {
        "source": LIBRARY_URL,
        "total_records": len(records),
        "matching_records": len(matches),
        "returned_records": min(len(matches), args.limit),
        "models": matches[: args.limit],
    }
    print(json.dumps(output, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
