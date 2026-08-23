from __future__ import annotations

from copy import deepcopy

from phytobench.audit import audit_documents

from .helpers import causal_row, documents, source


def codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def test_empty_curation_is_structurally_valid_but_empirically_blocked():
    sources, rows, contract = documents()
    report = audit_documents(sources, rows, contract)
    assert report.structurally_valid
    assert not report.evaluation_ready
    assert report.status == "PASS_WITH_EMPIRICAL_BLOCKER"
    assert report.empirical_n == 0
    assert report.causal_rows == 0
    assert report.null_rows == 0
    assert "CURATION_ONLY" in codes(report)


def test_complete_independent_synthetic_denominators_can_reach_readiness():
    sources, rows, contract = documents(35, 73, purpose="EVALUATION")
    report = audit_documents(sources, rows, contract)
    assert report.structurally_valid
    assert report.evaluation_ready
    assert report.status == "PASS"
    assert report.empirical_n == 108
    assert report.causal_independent_units == 35
    assert report.null_independent_units == 73


def test_missing_lock_field_fails_closed():
    sources, rows, contract = documents(1)
    del rows["rows"][0]["panel_digest"]
    report = audit_documents(sources, rows, contract)
    assert not report.structurally_valid
    assert "LOCK_FIELD_MISSING" in codes(report)


def test_post_truth_cutoff_and_post_cutoff_source_are_rejected():
    sources, rows, contract = documents(1)
    rows["rows"][0]["evidence_cutoff_date"] = "2020-03-01"
    report = audit_documents(sources, rows, contract)
    assert not report.structurally_valid
    assert "POST_TRUTH_LEAKAGE" in codes(report)
    assert "POST_CUTOFF_SOURCE" not in codes(report)

    rows["rows"][0]["evidence_cutoff_date"] = "2020-01-01"
    sources["sources"][1]["publication_date"] = "2020-01-02"
    report = audit_documents(sources, rows, contract)
    assert "POST_CUTOFF_SOURCE" in codes(report)


def test_truth_source_cannot_be_reused_as_pretruth_or_share_digest():
    sources, rows, contract = documents(1)
    row = rows["rows"][0]
    row["pretruth_source_ids"] = [row["primary_truth_source_id"]]
    row["truth_evidence_digest"] = row["pretruth_evidence_digest"]
    report = audit_documents(sources, rows, contract)
    assert "TRUTH_SOURCE_USED_AS_PRETRUTH" in codes(report)
    assert "TRUTH_PRETRUTH_DIGEST_COLLISION" in codes(report)


def test_unknown_or_scope_incompatible_license_is_rejected():
    sources, rows, contract = documents(1)
    sources["sources"][0]["license"]["status"] = "UNKNOWN"
    sources["sources"][0]["license"]["authorization_scope"] = "NONE"
    report = audit_documents(sources, rows, contract)
    assert "SOURCE_NOT_AUTHORIZED" in codes(report)


def test_null_row_cannot_carry_truth_gene():
    sources, rows, contract = documents(0, 1)
    rows["rows"][0]["truth_gene_id"] = "LEAKED:GENE"
    report = audit_documents(sources, rows, contract)
    assert "NULL_ROW_HAS_TRUTH_GENE" in codes(report)


def test_duplicate_identifiers_fail_closed():
    sources, rows, contract = documents(1)
    sources["sources"].append(deepcopy(sources["sources"][0]))
    rows["rows"].append(deepcopy(rows["rows"][0]))
    report = audit_documents(sources, rows, contract)
    assert "DUPLICATE_SOURCE_ID" in codes(report)
    assert "DUPLICATE_ROW_ID" in codes(report)


def test_transitive_dependence_collapses_and_cross_split_fails():
    rows = [causal_row(index, "DEVELOPMENT") for index in range(3)]
    rows[1]["study_id"] = rows[0]["study_id"]
    rows[2]["cohort_id"] = rows[1]["cohort_id"]
    sources = []
    for index in range(3):
        sources.extend(
            [
                source(f"truth-{index:03d}", "TRUTH_AUTHORITY", "2020-02-01"),
                source(f"pretruth-{index:03d}", "PRETRUTH_EVIDENCE", "2019-01-01"),
            ]
        )
    _, _, contract = documents()
    contract["selected_row_ids"] = [row["row_id"] for row in rows]
    report = audit_documents(
        {"schema_version": "phytobench-source-registry-v1", "sources": sources},
        {"schema_version": "phytobench-benchmark-rows-v1", "rows": rows},
        contract,
    )
    assert len(set(report.component_by_row.values())) == 1
    assert "DEPENDENT_ROWS_SELECTED" in codes(report)

    rows[2]["split"] = "CALIBRATION"
    report = audit_documents(
        {"schema_version": "phytobench-source-registry-v1", "sources": sources},
        {"schema_version": "phytobench-benchmark-rows-v1", "rows": rows},
        contract,
    )
    assert "DEPENDENCE_COMPONENT_CROSSES_SPLITS" in codes(report)


def test_external_species_and_orthogroup_overlap_are_rejected():
    sources, rows, contract = documents(
        1,
        1,
        purpose="EXTERNAL_REPLICATION",
        causal_split="EXTERNAL_SPECIES_HOLDOUT",
        null_split="DEVELOPMENT",
    )
    report = audit_documents(sources, rows, contract)
    assert "SPECIES_SPLIT_LEAKAGE" in codes(report)

    rows["rows"][1]["species_taxon_id"] = "NCBITaxon:4577"
    rows["rows"][1]["species_name"] = "Zea mays"
    rows["rows"][1]["orthogroup_id"] = rows["rows"][0]["orthogroup_id"]
    report = audit_documents(sources, rows, contract)
    assert "ORTHOGROUP_SPLIT_LEAKAGE" in codes(report)


def test_schema_rejects_string_boolean_and_unknown_fields():
    sources, rows, contract = documents()
    contract["require_orthogroup_disjoint"] = "false"
    contract["unexpected"] = True
    report = audit_documents(sources, rows, contract)
    assert not report.structurally_valid
    assert "SCHEMA_VIOLATION" in codes(report)


def test_source_ancestry_cycles_missing_parents_and_truth_taint_fail_closed():
    sources, rows, contract = documents(1)
    pretruth = sources["sources"][1]
    parent = source("ancestor-001", "PRETRUTH_EVIDENCE", "2018-01-01")
    parent["contains_truth_labels"] = "YES"
    parent["parent_source_ids"] = ["missing-parent"]
    pretruth["parent_source_ids"] = [parent["source_id"]]
    pretruth["lineage_root_digest"] = parent["lineage_root_digest"]
    sources["sources"].append(parent)
    report = audit_documents(sources, rows, contract)
    assert "SOURCE_PARENT_MISSING" in codes(report)
    assert "TRUTH_TAINTED_ANCESTRY" in codes(report)

    parent["parent_source_ids"] = [pretruth["source_id"]]
    report = audit_documents(sources, rows, contract)
    assert "SOURCE_ANCESTRY_CYCLE" in codes(report)


def test_training_taint_and_post_cutoff_ancestor_propagate():
    sources, rows, contract = documents(1)
    pretruth = sources["sources"][1]
    pretruth["used_for_training"] = "UNKNOWN"
    pretruth["first_public_at"] = "2020-01-02"
    pretruth["publication_date"] = "2020-01-02"
    report = audit_documents(sources, rows, contract)
    assert "TRAINING_TAINTED_ANCESTRY" in codes(report)
    assert "POST_CUTOFF_ANCESTOR" in codes(report)


def test_reviewers_must_be_distinct_and_identifiers_ascii():
    sources, rows, contract = documents(1)
    row = rows["rows"][0]
    row["curator_b_id"] = row["curator_a_id"]
    row["truth_gene_id"] = "GENE:\u0391"
    report = audit_documents(sources, rows, contract)
    assert "REVIEWER_INDEPENDENCE_FAILURE" in codes(report)
    assert "UNSAFE_IDENTIFIER_TEXT" in codes(report)


def test_matched_decoys_do_not_count_toward_null_denominator():
    sources, rows, contract = documents(35, 73, purpose="EVALUATION")
    for row in rows["rows"]:
        if row["row_kind"] == "NULL":
            row["null_class"] = "MATCHED_DECOY"
            row["null_type"] = "PHENOTYPE_PERMUTATION"
    report = audit_documents(sources, rows, contract)
    assert not report.evaluation_ready
    assert report.null_independent_units == 0
    assert "NONEMPIRICAL_NULL_NOT_COUNTED" in codes(report)
    assert "NULL_DENOMINATOR_TOO_SMALL" in codes(report)
