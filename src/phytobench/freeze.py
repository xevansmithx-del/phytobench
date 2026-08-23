from __future__ import annotations

import os
import secrets
import shutil
import tempfile
from pathlib import Path
from typing import Any

from . import __version__
from .audit import AuditReport, audit_documents
from .canonical import (
    canonical_bytes,
    file_sha256,
    load_json,
    sha256_hex,
    sha256_receipt,
    write_canonical_json,
)

FREEZE_RECEIPT_SCHEMA = "phytobench-freeze-receipt-v1"
RUNNER_SCHEMA = "phytobench-blind-runner-pack-v1"
SUPERVISOR_SCHEMA = "phytobench-supervisor-truth-pack-v1"
ATTEMPT_LEDGER_SCHEMA = "phytobench-attempt-ledger-v1"


class FreezeError(ValueError):
    """Raised when a requested freeze is unsafe or inadmissible."""


def _truth_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "row_id": row["row_id"],
        "row_kind": row["row_kind"],
        "truth_gene_id": row.get("truth_gene_id", ""),
        "null_type": row.get("null_type", ""),
        "truth_evidence_digest": row.get("truth_evidence_digest", ""),
        "construction_method_digest": row.get("construction_method_digest", ""),
    }


def _commit_truth(salt: str, payload: dict[str, Any]) -> str:
    material = salt.encode("ascii") + b"\n" + canonical_bytes(payload)
    return f"sha256:{sha256_hex(material)}"


def _runner_context(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row[key]
        for key in (
            "species_taxon_id",
            "species_name",
            "trait_id",
            "trait_direction",
            "interval_id",
            "reference_assembly",
            "interval_coordinates",
            "evidence_cutoff_date",
            "phenotype_protocol_digest",
            "panel_digest",
            "pretruth_evidence_digest",
            "lineage_root_digest",
        )
    }


def _write_manifest(root: Path) -> str:
    entries: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "SHA256SUMS.txt" and path.parent == root:
            continue
        if path.is_symlink():
            raise FreezeError(f"symlink cannot be sealed: {path}")
        entries.append((file_sha256(path), path.relative_to(root).as_posix()))
    data = "".join(f"{digest}  {name}\n" for digest, name in entries).encode("utf-8")
    manifest = root / "SHA256SUMS.txt"
    from .canonical import atomic_write

    atomic_write(manifest, data)
    return file_sha256(manifest)


def _make_pack_documents(
    rows: list[dict[str, Any]], contract: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    runner_cases: list[dict[str, Any]] = []
    supervisor_cases: list[dict[str, Any]] = []
    for row in rows:
        salt = secrets.token_hex(32)
        case_id = f"PB-{secrets.token_hex(12)}"
        truth = _truth_payload(row)
        commitment = _commit_truth(salt, truth)
        runner_cases.append(
            {
                "case_id": case_id,
                "truth_commitment": commitment,
                "context": _runner_context(row),
            }
        )
        supervisor_cases.append(
            {
                "case_id": case_id,
                "truth_commitment": commitment,
                "salt": salt,
                "truth": truth,
                "row": row,
            }
        )
    secrets.SystemRandom().shuffle(runner_cases)
    supervisor_cases.sort(key=lambda case: case["case_id"])
    runner = {
        "schema_version": RUNNER_SCHEMA,
        "benchmark_id": contract["benchmark_id"],
        "freeze_id": contract["freeze_id"],
        "cases": runner_cases,
    }
    supervisor = {
        "schema_version": SUPERVISOR_SCHEMA,
        "benchmark_id": contract["benchmark_id"],
        "freeze_id": contract["freeze_id"],
        "cases": supervisor_cases,
    }
    return runner, supervisor


def freeze_bundle(
    sources_document: dict[str, Any],
    rows_document: dict[str, Any],
    contract: dict[str, Any],
    output: Path,
) -> AuditReport:
    report = audit_documents(sources_document, rows_document, contract)
    if not report.structurally_valid:
        raise FreezeError("audit failed; unsafe inputs cannot be frozen")
    if contract["purpose"] != "CURATION" and not report.evaluation_ready:
        raise FreezeError("evaluation freeze refused because readiness blockers remain")
    if output.exists() or output.is_symlink():
        raise FreezeError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        selected = set(contract["selected_row_ids"])
        selected_rows = [row for row in rows_document["rows"] if row["row_id"] in selected]
        runner_document, supervisor_document = _make_pack_documents(selected_rows, contract)
        runner = temporary / "runner"
        supervisor = temporary / "supervisor"
        runner.mkdir()
        supervisor.mkdir()

        write_canonical_json(runner / "cases.json", runner_document)
        runner_receipt = {
            "schema_version": "phytobench-runner-receipt-v1",
            "tool_version": __version__,
            "benchmark_id": contract["benchmark_id"],
            "freeze_id": contract["freeze_id"],
            "case_count": len(runner_document["cases"]),
            "cases_sha256": sha256_receipt(runner_document),
            "roles_hidden": True,
            "truth_hidden": True,
            "network_required": False,
        }
        write_canonical_json(runner / "RECEIPT.json", runner_receipt)
        runner_manifest_sha256 = _write_manifest(runner)

        write_canonical_json(supervisor / "truth.json", supervisor_document)
        write_canonical_json(supervisor / "source_registry.json", sources_document)
        write_canonical_json(supervisor / "benchmark_rows.json", rows_document)
        write_canonical_json(supervisor / "freeze_contract.json", contract)
        attempt_ledger = {
            "schema_version": ATTEMPT_LEDGER_SCHEMA,
            "benchmark_id": contract["benchmark_id"],
            "freeze_id": contract["freeze_id"],
            "primary_attempt_available": contract["purpose"] != "CURATION",
            "attempts": [],
            "method_receipts": {
                key: contract[key]
                for key in (
                    "ruleset_sha256",
                    "code_artifact_sha256",
                    "analysis_plan_sha256",
                    "power_analysis_sha256",
                )
            },
        }
        write_canonical_json(supervisor / "ATTEMPT_LEDGER.json", attempt_ledger)
        supervisor_receipt = {
            "schema_version": "phytobench-supervisor-receipt-v1",
            "tool_version": __version__,
            "benchmark_id": contract["benchmark_id"],
            "freeze_id": contract["freeze_id"],
            "case_count": len(supervisor_document["cases"]),
            "truth_sha256": sha256_receipt(supervisor_document),
            "commitments_revealable": True,
            "primary_attempts_recorded": 0,
        }
        write_canonical_json(supervisor / "RECEIPT.json", supervisor_receipt)
        supervisor_manifest_sha256 = _write_manifest(supervisor)

        write_canonical_json(temporary / "AUDIT_RECEIPT.json", report.to_dict())
        freeze_receipt = {
            "schema_version": FREEZE_RECEIPT_SCHEMA,
            "tool_version": __version__,
            "benchmark_id": contract["benchmark_id"],
            "freeze_id": contract["freeze_id"],
            "purpose": contract["purpose"],
            "status": report.status,
            "evaluation_ready": report.evaluation_ready,
            "empirical_n": report.empirical_n,
            "locked_causal_rows": report.causal_rows,
            "locked_null_rows": report.null_rows,
            "locked_causal_independent_n": report.causal_independent_units,
            "locked_null_independent_n": report.null_independent_units,
            "breakthrough_validated": False,
            "runner_manifest_sha256": f"sha256:{runner_manifest_sha256}",
            "supervisor_manifest_sha256": f"sha256:{supervisor_manifest_sha256}",
            "input_receipts": report.input_receipts,
            "claim_ceiling": (
                "Benchmark intake and blinding software only; no biological performance, "
                "causal-gene, experimental, or breakthrough claim is established."
            ),
        }
        write_canonical_json(temporary / "FREEZE_RECEIPT.json", freeze_receipt)
        _write_manifest(temporary)
        os.replace(temporary, output)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return report


def _manifest_issues(root: Path) -> list[str]:
    manifest = root / "SHA256SUMS.txt"
    if not manifest.is_file() or manifest.is_symlink():
        return [f"missing or unsafe manifest: {manifest}"]
    expected: dict[str, str] = {}
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        try:
            digest, name = line.split("  ", 1)
        except ValueError:
            return [f"malformed manifest line {line_number} in {manifest}"]
        candidate = Path(name)
        if (
            len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or candidate.is_absolute()
            or ".." in candidate.parts
            or name in expected
        ):
            return [f"unsafe manifest entry {name!r} in {manifest}"]
        expected[name] = digest
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != manifest
    }
    if set(expected) != actual:
        return [
            f"manifest inventory mismatch at {root}: "
            f"missing={sorted(actual - set(expected))}, extra={sorted(set(expected) - actual)}"
        ]
    issues: list[str] = []
    for name, digest in sorted(expected.items()):
        path = root / name
        if path.is_symlink():
            issues.append(f"manifest member is a symlink: {name}")
        elif file_sha256(path) != digest:
            issues.append(f"manifest hash mismatch: {name}")
    return issues


def verify_bundle(root: Path) -> list[str]:
    if not root.is_dir() or root.is_symlink():
        return [f"bundle root is missing or unsafe: {root}"]
    issues = _manifest_issues(root)
    issues.extend(_manifest_issues(root / "runner"))
    issues.extend(_manifest_issues(root / "supervisor"))
    required = (
        root / "AUDIT_RECEIPT.json",
        root / "FREEZE_RECEIPT.json",
        root / "runner" / "cases.json",
        root / "supervisor" / "truth.json",
        root / "supervisor" / "source_registry.json",
        root / "supervisor" / "benchmark_rows.json",
        root / "supervisor" / "freeze_contract.json",
        root / "supervisor" / "ATTEMPT_LEDGER.json",
    )
    if any(not path.is_file() or path.is_symlink() for path in required):
        issues.append("bundle is missing one or more required regular files")
        return issues
    try:
        runner = load_json(root / "runner" / "cases.json")
        supervisor = load_json(root / "supervisor" / "truth.json")
        sources = load_json(root / "supervisor" / "source_registry.json")
        rows = load_json(root / "supervisor" / "benchmark_rows.json")
        contract = load_json(root / "supervisor" / "freeze_contract.json")
    except (OSError, ValueError) as error:
        issues.append(f"bundle JSON cannot be decoded safely: {error}")
        return issues
    if runner.get("schema_version") != RUNNER_SCHEMA:
        issues.append("runner schema version mismatch")
    if supervisor.get("schema_version") != SUPERVISOR_SCHEMA:
        issues.append("supervisor schema version mismatch")
    runner_by_case = {case.get("case_id"): case for case in runner.get("cases", [])}
    supervisor_by_case = {case.get("case_id"): case for case in supervisor.get("cases", [])}
    if len(runner_by_case) != len(runner.get("cases", [])):
        issues.append("runner pack contains duplicate case identifiers")
    if len(supervisor_by_case) != len(supervisor.get("cases", [])):
        issues.append("supervisor pack contains duplicate case identifiers")
    if set(runner_by_case) != set(supervisor_by_case):
        issues.append("runner/supervisor case inventories differ")
    for case_id in sorted(set(runner_by_case) & set(supervisor_by_case)):
        runner_case = runner_by_case[case_id]
        supervisor_case = supervisor_by_case[case_id]
        calculated = _commit_truth(supervisor_case.get("salt", ""), supervisor_case["truth"])
        commitments = {
            calculated,
            runner_case.get("truth_commitment"),
            supervisor_case.get("truth_commitment"),
        }
        if len(commitments) != 1:
            issues.append(f"truth commitment mismatch for {case_id}")
        leaked_keys = {"row_kind", "truth_gene_id", "null_type", "row_id"} & set(runner_case)
        if leaked_keys:
            issues.append(f"runner case {case_id} leaks keys: {sorted(leaked_keys)}")
    replay = audit_documents(sources, rows, contract)
    stored = load_json(root / "AUDIT_RECEIPT.json")
    if replay.to_dict() != stored:
        issues.append("stored audit receipt does not match semantic replay")
    return issues
