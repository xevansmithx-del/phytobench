from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .audit import audit_documents
from .canonical import DuplicateKeyError, load_json
from .freeze import FreezeError, freeze_bundle, verify_bundle


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="phytobench",
        description="Fail-closed plant benchmark intake, blinding, and leakage auditor",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="audit source, row, and freeze documents")
    _input_arguments(audit)
    audit.add_argument(
        "--require-ready",
        action="store_true",
        help="return a refusal code unless the selected benchmark is evaluation-ready",
    )

    freeze = subparsers.add_parser("freeze", help="create blinded runner and supervisor bundles")
    _input_arguments(freeze)
    freeze.add_argument("--output", type=Path, required=True)

    verify = subparsers.add_parser("verify", help="replay a sealed benchmark bundle")
    verify.add_argument("bundle", type=Path)
    return parser


def _input_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)


def _load_inputs(arguments: argparse.Namespace) -> tuple[dict, dict, dict]:
    for path in (arguments.sources, arguments.rows, arguments.contract):
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"input must be a regular non-symlink file: {path}")
    sources = load_json(arguments.sources)
    rows = load_json(arguments.rows)
    contract = load_json(arguments.contract)
    if not all(isinstance(value, dict) for value in (sources, rows, contract)):
        raise ValueError("all input documents must be JSON objects")
    return sources, rows, contract


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "verify":
            issues = verify_bundle(arguments.bundle)
            payload = {
                "schema_version": "phytobench-verification-receipt-v1",
                "status": "PASS" if not issues else "FAIL",
                "issues": issues,
            }
            print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
            return 0 if not issues else 2

        sources, rows, contract = _load_inputs(arguments)
        if arguments.command == "audit":
            report = audit_documents(sources, rows, contract)
            print(json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":")))
            if not report.structurally_valid:
                return 2
            if arguments.require_ready and not report.evaluation_ready:
                return 2
            return 0

        report = freeze_bundle(sources, rows, contract, arguments.output)
        print(json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":")))
        return 0
    except (DuplicateKeyError, FreezeError, OSError, ValueError) as error:
        print(
            json.dumps(
                {"schema_version": "phytobench-error-v1", "status": "FAIL", "error": str(error)},
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
