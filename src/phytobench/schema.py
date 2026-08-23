from __future__ import annotations

from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

SCHEMAS = {
    "sources": "source_registry.schema.json",
    "rows": "benchmark_rows.schema.json",
    "contract": "freeze_contract.schema.json",
}


def load_schema(kind: str) -> dict[str, Any]:
    if kind not in SCHEMAS:
        raise ValueError(f"unknown schema kind: {kind}")
    resource = files("phytobench").joinpath("schema", SCHEMAS[kind])
    import json

    return json.loads(resource.read_text(encoding="utf-8"))


def schema_errors(kind: str, document: Any) -> list[str]:
    validator = Draft202012Validator(load_schema(kind), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.absolute_path))
    messages: list[str] = []
    for error in errors:
        path = "/" + "/".join(str(part) for part in error.absolute_path)
        messages.append(f"{kind}{path}: {error.message}")
    return messages
