from __future__ import annotations

import json

import pytest

from phytobench.canonical import load_json
from phytobench.freeze import FreezeError, freeze_bundle, verify_bundle

from .helpers import documents


def test_empty_curation_freezes_with_explicit_zero_row_ceiling(tmp_path):
    sources, rows, contract = documents()
    output = tmp_path / "bundle"
    report = freeze_bundle(sources, rows, contract, output)
    assert report.empirical_n == 0
    assert verify_bundle(output) == []
    receipt = load_json(output / "FREEZE_RECEIPT.json")
    assert receipt["status"] == "PASS_WITH_EMPIRICAL_BLOCKER"
    assert receipt["locked_causal_rows"] == 0
    assert receipt["locked_null_rows"] == 0
    assert receipt["breakthrough_validated"] is False


def test_blind_pack_hides_roles_and_truth_and_commitments_replay(tmp_path):
    sources, rows, contract = documents(1, 1)
    output = tmp_path / "bundle"
    freeze_bundle(sources, rows, contract, output)
    assert verify_bundle(output) == []
    runner = load_json(output / "runner" / "cases.json")
    assert len(runner["cases"]) == 2
    serialized = json.dumps(runner)
    for forbidden in ("CAUSAL", "NULL", "truth_gene_id", "null_type", "row_id"):
        assert forbidden not in serialized


def test_evaluation_freeze_refuses_readiness_blockers(tmp_path):
    sources, rows, contract = documents(1, 1, purpose="EVALUATION")
    with pytest.raises(FreezeError, match="readiness blockers"):
        freeze_bundle(sources, rows, contract, tmp_path / "bundle")


def test_freeze_refuses_existing_output(tmp_path):
    sources, rows, contract = documents()
    output = tmp_path / "bundle"
    output.mkdir()
    with pytest.raises(FreezeError, match="already exists"):
        freeze_bundle(sources, rows, contract, output)


def test_tampering_breaks_manifest_and_commitment_verification(tmp_path):
    sources, rows, contract = documents(1)
    output = tmp_path / "bundle"
    freeze_bundle(sources, rows, contract, output)
    truth_path = output / "supervisor" / "truth.json"
    truth = load_json(truth_path)
    truth["cases"][0]["truth"]["truth_gene_id"] = "TAMPERED"
    truth_path.write_text(json.dumps(truth), encoding="utf-8")
    issues = verify_bundle(output)
    assert any("hash mismatch" in issue for issue in issues)
    assert any("commitment mismatch" in issue for issue in issues)
