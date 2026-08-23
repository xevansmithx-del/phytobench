from __future__ import annotations

from typing import Any

from phytobench.canonical import sha256_receipt


def receipt(label: str) -> str:
    return sha256_receipt({"fixture": label})


def source(
    source_id: str,
    role: str,
    publication_date: str,
    *,
    status: str = "VERIFIED_OPEN",
    authorization_scope: str = "PUBLIC_METADATA",
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "title": f"Synthetic source {source_id}",
        "canonical_url": f"https://example.org/{source_id}",
        "archived_url": "",
        "publisher": "Synthetic fixtures",
        "publication_date": publication_date,
        "accessed_at": "2026-08-23",
        "roles": [role],
        "parent_source_ids": [],
        "first_public_at": publication_date,
        "contains_truth_labels": "YES" if role in {"TRUTH_AUTHORITY", "NULL_AUTHORITY"} else "NO",
        "used_for_training": "NO",
        "content_sha256": receipt(f"content:{source_id}"),
        "metadata_sha256": receipt(f"metadata:{source_id}"),
        "lineage_root_digest": receipt(f"source-lineage:{source_id}"),
        "retrieval_method": "synthetic fixture",
        "license": {
            "status": status,
            "authorization_scope": authorization_scope,
            "license_id": "CC0-1.0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "evidence_sha256": receipt(f"license:{source_id}"),
            "reviewer_id": f"license-reviewer-{source_id}",
            "review_receipt_sha256": receipt(f"license-review:{source_id}"),
            "authorization_receipt_sha256": "",
        },
    }


def causal_row(index: int, split: str = "INTERNAL_HOLDOUT") -> dict[str, Any]:
    row_id = f"causal-{index:03d}"
    truth_source = f"truth-{index:03d}"
    pretruth_source = f"pretruth-{index:03d}"
    return {
        "row_id": row_id,
        "row_kind": "CAUSAL",
        "split": split,
        "species_taxon_id": "NCBITaxon:39947",
        "species_name": "Oryza sativa",
        "trait_id": f"TO:{index + 1:07d}",
        "trait_direction": "increased",
        "interval_id": f"interval-{index:03d}",
        "reference_assembly": "GCF_SYNTHETIC.1",
        "interval_coordinates": f"chr1:{index * 1000 + 1}-{index * 1000 + 900}",
        "truth_gene_id": f"GENE:{index:03d}",
        "null_type": "",
        "truth_strength": "CLONED_LOCUS_WITH_FUNCTIONAL_VALIDATION",
        "primary_truth_source_id": truth_source,
        "pretruth_source_ids": [pretruth_source],
        "all_source_ids": [pretruth_source, truth_source],
        "truth_disclosure_date": "2020-02-01",
        "evidence_cutoff_date": "2020-01-01",
        "study_id": f"study-c-{index:03d}",
        "cohort_id": f"cohort-c-{index:03d}",
        "population_id": f"population-c-{index:03d}",
        "gene_family_id": f"family-{index:03d}",
        "orthogroup_id": f"orthogroup-{index:03d}",
        "lineage_root_digest": receipt(f"lineage-c-{index:03d}"),
        "phenotype_protocol_digest": receipt(f"protocol-c-{index:03d}"),
        "panel_digest": receipt(f"panel-c-{index:03d}"),
        "truth_evidence_digest": receipt(f"truth-evidence-{index:03d}"),
        "pretruth_evidence_digest": receipt(f"pretruth-evidence-{index:03d}"),
        "curator_a_id": f"curator-a-{index:03d}",
        "curator_b_id": f"curator-b-{index:03d}",
        "adjudicator_id": f"adjudicator-{index:03d}",
        "curation_review_a_digest": receipt(f"curation-a-{index:03d}"),
        "curation_review_b_digest": receipt(f"curation-b-{index:03d}"),
        "adjudication_receipt_digest": receipt(f"adjudication-{index:03d}"),
        "license_review_digest": receipt(f"license-row-{index:03d}"),
        "leakage_review_digest": receipt(f"leakage-{index:03d}"),
        "grouping_review_digest": receipt(f"grouping-{index:03d}"),
    }


def null_row(index: int, split: str = "INTERNAL_HOLDOUT") -> dict[str, Any]:
    row_id = f"null-{index:03d}"
    null_source = f"null-source-{index:03d}"
    pretruth_source = f"null-pretruth-{index:03d}"
    return {
        "row_id": row_id,
        "row_kind": "NULL",
        "split": split,
        "species_taxon_id": "NCBITaxon:39947",
        "species_name": "Oryza sativa",
        "trait_id": f"TO:{index + 1000:07d}",
        "trait_direction": "unchanged",
        "interval_id": f"null-interval-{index:03d}",
        "reference_assembly": "GCF_SYNTHETIC.1",
        "interval_coordinates": f"chr2:{index * 1000 + 1}-{index * 1000 + 900}",
        "truth_gene_id": "",
        "null_type": "EMPIRICAL_EQUIVALENCE",
        "null_class": "EMPIRICAL_EQUIVALENCE_NULL",
        "truth_strength": "",
        "primary_truth_source_id": "",
        "pretruth_source_ids": [pretruth_source],
        "all_source_ids": [null_source, pretruth_source],
        "evidence_cutoff_date": "2020-01-01",
        "study_id": f"study-n-{index:03d}",
        "cohort_id": f"cohort-n-{index:03d}",
        "population_id": f"population-n-{index:03d}",
        "gene_family_id": f"null-family-{index:03d}",
        "orthogroup_id": f"null-orthogroup-{index:03d}",
        "lineage_root_digest": receipt(f"lineage-n-{index:03d}"),
        "phenotype_protocol_digest": receipt(f"protocol-n-{index:03d}"),
        "panel_digest": receipt(f"panel-n-{index:03d}"),
        "pretruth_evidence_digest": receipt(f"pretruth-null-{index:03d}"),
        "null_authority_source_id": null_source,
        "null_generation_date": "2020-01-02",
        "construction_method_digest": receipt(f"construction-n-{index:03d}"),
        "equivalence_margin_digest": receipt(f"margin-n-{index:03d}"),
        "effect_interval_digest": receipt(f"effect-interval-n-{index:03d}"),
        "power_receipt_sha256": receipt(f"null-power-n-{index:03d}"),
        "positive_control_receipt_sha256": receipt(f"positive-control-n-{index:03d}"),
        "independent_qc_receipt_sha256": receipt(f"null-qc-n-{index:03d}"),
        "curator_a_id": f"null-curator-a-{index:03d}",
        "curator_b_id": f"null-curator-b-{index:03d}",
        "adjudicator_id": f"null-adjudicator-{index:03d}",
        "curation_review_a_digest": receipt(f"null-curation-a-{index:03d}"),
        "curation_review_b_digest": receipt(f"null-curation-b-{index:03d}"),
        "adjudication_receipt_digest": receipt(f"null-adjudication-{index:03d}"),
        "license_review_digest": receipt(f"null-license-row-{index:03d}"),
        "leakage_review_digest": receipt(f"null-leakage-{index:03d}"),
        "grouping_review_digest": receipt(f"null-grouping-{index:03d}"),
    }


def documents(
    causal_count: int = 0,
    null_count: int = 0,
    *,
    purpose: str = "CURATION",
    causal_split: str | None = None,
    null_split: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if causal_split is None:
        causal_split = "INTERNAL_HOLDOUT" if purpose == "EVALUATION" else "DEVELOPMENT"
    if null_split is None:
        null_split = "INTERNAL_HOLDOUT" if purpose == "EVALUATION" else "DEVELOPMENT"
    causal = [causal_row(index, causal_split) for index in range(causal_count)]
    nulls = [null_row(index, null_split) for index in range(null_count)]
    rows = causal + nulls
    sources = []
    for index in range(causal_count):
        sources.extend(
            [
                source(f"truth-{index:03d}", "TRUTH_AUTHORITY", "2020-02-01"),
                source(f"pretruth-{index:03d}", "PRETRUTH_EVIDENCE", "2019-01-01"),
            ]
        )
    for index in range(null_count):
        sources.extend(
            [
                source(f"null-source-{index:03d}", "NULL_AUTHORITY", "2020-01-02"),
                source(
                    f"null-pretruth-{index:03d}",
                    "PRETRUTH_EVIDENCE",
                    "2019-01-01",
                ),
            ]
        )
    contract = {
        "schema_version": "phytobench-freeze-contract-v1",
        "benchmark_id": "synthetic-benchmark-v1",
        "freeze_id": "synthetic-freeze-v1",
        "purpose": purpose,
        "created_at": "2026-08-23T00:00:00Z",
        "distribution_scope": "PUBLIC",
        "selected_row_ids": [row["row_id"] for row in rows],
        "external_holdout_species_taxon_ids": (
            ["NCBITaxon:39947"] if purpose == "EXTERNAL_REPLICATION" else []
        ),
        "require_orthogroup_disjoint": True,
        "min_causal_independent_units": 35,
        "min_null_independent_units": 73,
        "ruleset_sha256": receipt("rules") if purpose != "CURATION" else "",
        "code_artifact_sha256": receipt("code") if purpose != "CURATION" else "",
        "analysis_plan_sha256": receipt("analysis") if purpose != "CURATION" else "",
        "power_analysis_sha256": receipt("power") if purpose != "CURATION" else "",
    }
    return (
        {"schema_version": "phytobench-source-registry-v1", "sources": sources},
        {"schema_version": "phytobench-benchmark-rows-v1", "rows": rows},
        contract,
    )
