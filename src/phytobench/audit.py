from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from .canonical import sha256_receipt
from .schema import schema_errors

SCHEMA_VERSION = "phytobench-audit-receipt-v1"
PUBLIC_LICENSE_STATUSES = {
    "VERIFIED_OPEN",
    "VERIFIED_PERMISSION",
    "METADATA_CITATION_ONLY",
}
PUBLIC_AUTHORIZATION_SCOPES = {"PUBLIC_FULL", "PUBLIC_METADATA"}
PRIVATE_LICENSE_STATUSES = PUBLIC_LICENSE_STATUSES | {"RESTRICTED"}
PRIVATE_AUTHORIZATION_SCOPES = PUBLIC_AUTHORIZATION_SCOPES | {"LOCAL_ANALYSIS_ONLY"}

COMMON_LOCK_FIELDS = (
    "trait_direction",
    "reference_assembly",
    "interval_coordinates",
    "evidence_cutoff_date",
    "study_id",
    "cohort_id",
    "population_id",
    "gene_family_id",
    "orthogroup_id",
    "lineage_root_digest",
    "phenotype_protocol_digest",
    "panel_digest",
    "pretruth_evidence_digest",
    "all_source_ids",
    "curator_a_id",
    "curator_b_id",
    "adjudicator_id",
    "curation_review_a_digest",
    "curation_review_b_digest",
    "adjudication_receipt_digest",
    "license_review_digest",
    "leakage_review_digest",
    "grouping_review_digest",
)
CAUSAL_LOCK_FIELDS = (
    "truth_gene_id",
    "truth_strength",
    "primary_truth_source_id",
    "pretruth_source_ids",
    "truth_disclosure_date",
    "truth_evidence_digest",
)
NULL_LOCK_FIELDS = (
    "null_type",
    "null_class",
    "null_authority_source_id",
    "null_generation_date",
    "construction_method_digest",
    "equivalence_margin_digest",
    "effect_interval_digest",
    "power_receipt_sha256",
    "positive_control_receipt_sha256",
    "independent_qc_receipt_sha256",
)
PREREGISTRATION_FIELDS = (
    "ruleset_sha256",
    "code_artifact_sha256",
    "analysis_plan_sha256",
    "power_analysis_sha256",
)


@dataclass(frozen=True)
class AuditIssue:
    severity: str
    code: str
    subject: str
    message: str


@dataclass(frozen=True)
class AuditReport:
    schema_version: str
    status: str
    structurally_valid: bool
    evaluation_ready: bool
    empirical_n: int
    selected_rows: int
    causal_rows: int
    null_rows: int
    independent_units: int
    causal_independent_units: int
    null_independent_units: int
    target_split: str | None
    input_receipts: dict[str, str]
    component_by_row: dict[str, str]
    component_members: dict[str, list[str]]
    issues: tuple[AuditIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["issues"] = [asdict(issue) for issue in self.issues]
        return payload


class _DisjointSet:
    def __init__(self, identifiers: Iterable[str]) -> None:
        self.parent = {identifier: identifier for identifier in identifiers}

    def find(self, identifier: str) -> str:
        parent = self.parent[identifier]
        if parent != identifier:
            self.parent[identifier] = self.find(parent)
        return self.parent[identifier]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if left_root < right_root:
            self.parent[right_root] = left_root
        else:
            self.parent[left_root] = right_root


def _present(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    return value is not None


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _issue(issues: list[AuditIssue], severity: str, code: str, subject: str, message: str) -> None:
    issues.append(AuditIssue(severity, code, subject, message))


def _index_unique(
    values: list[dict[str, Any]], key: str, label: str, issues: list[AuditIssue]
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for _position, value in enumerate(values):
        identifier = value.get(key)
        if not isinstance(identifier, str) or not identifier:
            continue
        if identifier in indexed:
            _issue(
                issues,
                "ERROR",
                f"DUPLICATE_{label.upper()}_ID",
                identifier,
                f"{label} identifier occurs more than once",
            )
        else:
            indexed[identifier] = value
    return indexed


def _source_authorized(source: dict[str, Any], scope: str) -> tuple[bool, str]:
    license_record = source.get("license", {})
    status = license_record.get("status")
    authorization = license_record.get("authorization_scope")
    if scope == "PUBLIC":
        allowed_statuses = PUBLIC_LICENSE_STATUSES
        allowed_scopes = PUBLIC_AUTHORIZATION_SCOPES
    else:
        allowed_statuses = PRIVATE_LICENSE_STATUSES
        allowed_scopes = PRIVATE_AUTHORIZATION_SCOPES
    if status not in allowed_statuses:
        return False, f"license status {status!r} is not admissible for {scope.lower()} use"
    if authorization not in allowed_scopes:
        return (
            False,
            f"authorization scope {authorization!r} is not admissible for {scope.lower()} use",
        )
    if status == "VERIFIED_PERMISSION" and not license_record.get("authorization_receipt_sha256"):
        return False, "verified permission requires an authorization receipt"
    return True, ""


def _safe_text(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value.isascii()
        and all(character.isprintable() for character in value)
    )


def _audit_source_graph(sources: dict[str, dict[str, Any]], issues: list[AuditIssue]) -> None:
    for source_id, source in sorted(sources.items()):
        publication = _parse_date(source.get("publication_date", ""))
        first_public = _parse_date(source.get("first_public_at", ""))
        if publication and first_public and first_public > publication:
            _issue(
                issues,
                "ERROR",
                "FIRST_PUBLIC_AFTER_PUBLICATION",
                source_id,
                "first_public_at cannot be later than publication_date",
            )
        for parent_id in source.get("parent_source_ids", []):
            parent = sources.get(parent_id)
            if parent is None:
                _issue(
                    issues,
                    "ERROR",
                    "SOURCE_PARENT_MISSING",
                    source_id,
                    f"parent source {parent_id!r} is absent from the registry",
                )
                continue
            if parent.get("lineage_root_digest") != source.get("lineage_root_digest"):
                _issue(
                    issues,
                    "ERROR",
                    "SOURCE_LINEAGE_ROOT_MISMATCH",
                    source_id,
                    f"parent source {parent_id!r} has a different lineage root",
                )
            parent_first = _parse_date(parent.get("first_public_at", ""))
            if first_public and parent_first and parent_first > first_public:
                _issue(
                    issues,
                    "ERROR",
                    "SOURCE_ANCESTRY_DATE_INVERSION",
                    source_id,
                    f"parent source {parent_id!r} postdates its descendant",
                )

    state: dict[str, int] = {}

    def visit(source_id: str, path: tuple[str, ...]) -> None:
        if state.get(source_id) == 2:
            return
        if state.get(source_id) == 1:
            _issue(
                issues,
                "ERROR",
                "SOURCE_ANCESTRY_CYCLE",
                source_id,
                f"source ancestry contains a cycle: {list(path + (source_id,))}",
            )
            return
        state[source_id] = 1
        for parent_id in sources[source_id].get("parent_source_ids", []):
            if parent_id in sources:
                visit(parent_id, path + (source_id,))
        state[source_id] = 2

    for source_id in sorted(sources):
        visit(source_id, ())


def _source_ancestry(source_id: str, sources: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    ancestry: list[dict[str, Any]] = []
    pending = [source_id]
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current in seen or current not in sources:
            continue
        seen.add(current)
        source = sources[current]
        ancestry.append(source)
        pending.extend(source.get("parent_source_ids", []))
    return ancestry


def _audit_pretruth_source(
    row_id: str,
    source_id: str,
    cutoff: date | None,
    sources: dict[str, dict[str, Any]],
    issues: list[AuditIssue],
) -> None:
    source = sources.get(source_id)
    if source is None:
        return
    if "PRETRUTH_EVIDENCE" not in source["roles"]:
        _issue(
            issues,
            "ERROR",
            "SOURCE_ROLE_MISMATCH",
            row_id,
            f"source {source_id!r} lacks PRETRUTH_EVIDENCE role",
        )
    for ancestor in _source_ancestry(source_id, sources):
        ancestor_id = ancestor["source_id"]
        first_public = _parse_date(ancestor.get("first_public_at", ""))
        if first_public and cutoff and first_public > cutoff:
            _issue(
                issues,
                "ERROR",
                "POST_CUTOFF_ANCESTOR",
                row_id,
                f"source ancestor {ancestor_id!r} first appeared after the evidence cutoff",
            )
        if ancestor.get("contains_truth_labels") != "NO":
            _issue(
                issues,
                "ERROR",
                "TRUTH_TAINTED_ANCESTRY",
                row_id,
                f"source ancestor {ancestor_id!r} has truth labels or unknown truth status",
            )
        if ancestor.get("used_for_training") != "NO":
            _issue(
                issues,
                "ERROR",
                "TRAINING_TAINTED_ANCESTRY",
                row_id,
                f"source ancestor {ancestor_id!r} has training use or unknown training status",
            )


def _dependence_components(
    rows: list[dict[str, Any]], issues: list[AuditIssue]
) -> tuple[dict[str, str], dict[str, list[str]]]:
    identifiers = [row["row_id"] for row in rows]
    disjoint = _DisjointSet(identifiers)
    token_owners: dict[str, str] = {}
    for row in rows:
        row_id = row["row_id"]
        tokens: list[str] = []
        for field in (
            "study_id",
            "cohort_id",
            "population_id",
            "lineage_root_digest",
            "orthogroup_id",
        ):
            value = row.get(field)
            if _present(value):
                tokens.append(f"{field}:{value}")
        for source_id in row.get("all_source_ids", []):
            tokens.append(f"source:{source_id}")
        for token in tokens:
            owner = token_owners.setdefault(token, row_id)
            disjoint.union(owner, row_id)

    members_by_root: dict[str, list[str]] = defaultdict(list)
    for identifier in sorted(identifiers):
        members_by_root[disjoint.find(identifier)].append(identifier)

    component_by_row: dict[str, str] = {}
    component_members: dict[str, list[str]] = {}
    for members in sorted(members_by_root.values()):
        component = f"cluster:{sha256_receipt(members).split(':', 1)[1][:16]}"
        component_members[component] = members
        for identifier in members:
            component_by_row[identifier] = component
        splits = {row["split"] for row in rows if row["row_id"] in members}
        if len(splits) > 1:
            _issue(
                issues,
                "ERROR",
                "DEPENDENCE_COMPONENT_CROSSES_SPLITS",
                component,
                f"connected rows cross split assignments: {sorted(splits)}",
            )
    return component_by_row, component_members


def _target_split(purpose: str) -> str | None:
    if purpose == "EVALUATION":
        return "INTERNAL_HOLDOUT"
    if purpose == "EXTERNAL_REPLICATION":
        return "EXTERNAL_SPECIES_HOLDOUT"
    return None


def audit_documents(
    sources_document: dict[str, Any],
    rows_document: dict[str, Any],
    contract: dict[str, Any],
) -> AuditReport:
    issues: list[AuditIssue] = []
    for kind, document in (
        ("sources", sources_document),
        ("rows", rows_document),
        ("contract", contract),
    ):
        for message in schema_errors(kind, document):
            _issue(issues, "ERROR", "SCHEMA_VIOLATION", kind, message)

    input_receipts = {
        "sources": sha256_receipt(sources_document),
        "rows": sha256_receipt(rows_document),
        "contract": sha256_receipt(contract),
    }
    if any(issue.severity == "ERROR" for issue in issues):
        return AuditReport(
            SCHEMA_VERSION,
            "FAIL",
            False,
            False,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            _target_split(str(contract.get("purpose", ""))),
            input_receipts,
            {},
            {},
            tuple(issues),
        )

    sources = _index_unique(sources_document["sources"], "source_id", "source", issues)
    rows = _index_unique(rows_document["rows"], "row_id", "row", issues)
    _audit_source_graph(sources, issues)
    selected_ids = contract["selected_row_ids"]
    selected_rows: list[dict[str, Any]] = []
    for row_id in selected_ids:
        row = rows.get(row_id)
        if row is None:
            _issue(
                issues,
                "ERROR",
                "SELECTED_ROW_MISSING",
                row_id,
                "freeze contract selects a row absent from the intake document",
            )
        else:
            selected_rows.append(row)

    unused_selected = set(selected_ids) - set(rows)
    if not unused_selected and len(selected_rows) != len(selected_ids):
        _issue(
            issues,
            "ERROR",
            "SELECTED_ROW_CARDINALITY_MISMATCH",
            contract["freeze_id"],
            "selected row cardinality changed during indexing",
        )

    distribution_scope = contract["distribution_scope"]
    for row in selected_rows:
        row_id = row["row_id"]
        for field in (
            "row_id",
            "species_taxon_id",
            "species_name",
            "trait_id",
            "trait_direction",
            "interval_id",
            "reference_assembly",
            "interval_coordinates",
            "study_id",
            "cohort_id",
            "population_id",
            "gene_family_id",
            "orthogroup_id",
            "truth_gene_id",
            "curator_a_id",
            "curator_b_id",
            "adjudicator_id",
        ):
            value = row.get(field)
            if value not in (None, "") and not _safe_text(value):
                _issue(
                    issues,
                    "ERROR",
                    "UNSAFE_IDENTIFIER_TEXT",
                    row_id,
                    f"field {field!r} must contain printable ASCII text",
                )
        required = COMMON_LOCK_FIELDS + (
            CAUSAL_LOCK_FIELDS if row["row_kind"] == "CAUSAL" else NULL_LOCK_FIELDS
        )
        for field in required:
            if not _present(row.get(field)):
                _issue(
                    issues,
                    "ERROR",
                    "LOCK_FIELD_MISSING",
                    row_id,
                    f"required lock field {field!r} is missing or empty",
                )

        reviewers = [
            row.get("curator_a_id"),
            row.get("curator_b_id"),
            row.get("adjudicator_id"),
        ]
        if all(_present(reviewer) for reviewer in reviewers) and len(set(reviewers)) != 3:
            _issue(
                issues,
                "ERROR",
                "REVIEWER_INDEPENDENCE_FAILURE",
                row_id,
                "two curators and the adjudicator must be distinct identities",
            )

        all_source_ids = set(row.get("all_source_ids", []))
        if row["row_kind"] == "CAUSAL":
            if row.get("null_type") not in (None, ""):
                _issue(
                    issues,
                    "ERROR",
                    "CAUSAL_ROW_HAS_NULL_LABEL",
                    row_id,
                    "causal row cannot carry a null type",
                )
            truth_source_id = row.get("primary_truth_source_id", "")
            pretruth_ids = set(row.get("pretruth_source_ids", []))
            if truth_source_id in pretruth_ids:
                _issue(
                    issues,
                    "ERROR",
                    "TRUTH_SOURCE_USED_AS_PRETRUTH",
                    row_id,
                    "truth authority cannot be reused as pre-truth evidence",
                )
            if truth_source_id and truth_source_id not in all_source_ids:
                _issue(
                    issues,
                    "ERROR",
                    "TRUTH_SOURCE_NOT_DECLARED",
                    row_id,
                    "primary truth source is absent from all_source_ids",
                )
            missing_pretruth = pretruth_ids - all_source_ids
            if missing_pretruth:
                _issue(
                    issues,
                    "ERROR",
                    "PRETRUTH_SOURCE_NOT_DECLARED",
                    row_id,
                    f"pre-truth sources absent from all_source_ids: {sorted(missing_pretruth)}",
                )
            cutoff = _parse_date(row.get("evidence_cutoff_date", ""))
            disclosure = _parse_date(row.get("truth_disclosure_date", ""))
            if cutoff and disclosure and cutoff >= disclosure:
                _issue(
                    issues,
                    "ERROR",
                    "POST_TRUTH_LEAKAGE",
                    row_id,
                    "evidence cutoff must be earlier than truth disclosure",
                )
            truth_source = sources.get(truth_source_id)
            if truth_source is not None:
                if "TRUTH_AUTHORITY" not in truth_source["roles"]:
                    _issue(
                        issues,
                        "ERROR",
                        "SOURCE_ROLE_MISMATCH",
                        row_id,
                        "primary truth source lacks TRUTH_AUTHORITY role",
                    )
                source_date = _parse_date(truth_source["publication_date"])
                if source_date and disclosure and source_date != disclosure:
                    _issue(
                        issues,
                        "ERROR",
                        "TRUTH_DATE_MISMATCH",
                        row_id,
                        "truth disclosure date must match the registered truth source date",
                    )
            for source_id in sorted(pretruth_ids):
                source = sources.get(source_id)
                _audit_pretruth_source(row_id, source_id, cutoff, sources, issues)
                if source is None:
                    continue
                source_date = _parse_date(source["publication_date"])
                if source_date and cutoff and source_date > cutoff:
                    _issue(
                        issues,
                        "ERROR",
                        "POST_CUTOFF_SOURCE",
                        row_id,
                        f"pre-truth source {source_id!r} was published after the cutoff",
                    )
            if row.get("truth_evidence_digest") == row.get("pretruth_evidence_digest"):
                _issue(
                    issues,
                    "ERROR",
                    "TRUTH_PRETRUTH_DIGEST_COLLISION",
                    row_id,
                    "truth and pre-truth evidence receipts must differ",
                )
        else:
            if _present(row.get("truth_gene_id")):
                _issue(
                    issues,
                    "ERROR",
                    "NULL_ROW_HAS_TRUTH_GENE",
                    row_id,
                    "null row cannot carry a truth gene",
                )
            null_source_id = row.get("null_authority_source_id", "")
            if null_source_id and null_source_id not in all_source_ids:
                _issue(
                    issues,
                    "ERROR",
                    "NULL_SOURCE_NOT_DECLARED",
                    row_id,
                    "null authority source is absent from all_source_ids",
                )
            null_source = sources.get(null_source_id)
            if null_source is not None and "NULL_AUTHORITY" not in null_source["roles"]:
                _issue(
                    issues,
                    "ERROR",
                    "SOURCE_ROLE_MISMATCH",
                    row_id,
                    "null authority source lacks NULL_AUTHORITY role",
                )
            cutoff = _parse_date(row.get("evidence_cutoff_date", ""))
            generation = _parse_date(row.get("null_generation_date", ""))
            if cutoff and generation and cutoff >= generation:
                _issue(
                    issues,
                    "ERROR",
                    "POST_NULL_LEAKAGE",
                    row_id,
                    "evidence cutoff must be earlier than null disclosure/generation",
                )
            if null_source is not None:
                source_date = _parse_date(null_source.get("publication_date", ""))
                if source_date and generation and source_date != generation:
                    _issue(
                        issues,
                        "ERROR",
                        "NULL_DATE_MISMATCH",
                        row_id,
                        "null disclosure date must match the registered null authority date",
                    )
            pretruth_ids = set(row.get("pretruth_source_ids", []))
            if row.get("null_class") == "EMPIRICAL_EQUIVALENCE_NULL" and not pretruth_ids:
                _issue(
                    issues,
                    "ERROR",
                    "EMPIRICAL_NULL_PRETRUTH_MISSING",
                    row_id,
                    "empirical equivalence null requires pre-truth evidence sources",
                )
            if null_source_id in pretruth_ids:
                _issue(
                    issues,
                    "ERROR",
                    "NULL_SOURCE_USED_AS_PRETRUTH",
                    row_id,
                    "null authority cannot be reused as pre-truth evidence",
                )
            for source_id in sorted(pretruth_ids):
                if source_id not in all_source_ids:
                    _issue(
                        issues,
                        "ERROR",
                        "PRETRUTH_SOURCE_NOT_DECLARED",
                        row_id,
                        f"pre-truth source {source_id!r} is absent from all_source_ids",
                    )
                _audit_pretruth_source(row_id, source_id, cutoff, sources, issues)

        for source_id in sorted(all_source_ids):
            source = sources.get(source_id)
            if source is None:
                _issue(
                    issues,
                    "ERROR",
                    "UNREGISTERED_SOURCE",
                    row_id,
                    f"source {source_id!r} is absent from the source registry",
                )
                continue
            authorized, reason = _source_authorized(source, distribution_scope)
            if not authorized:
                _issue(
                    issues,
                    "ERROR",
                    "SOURCE_NOT_AUTHORIZED",
                    row_id,
                    f"source {source_id!r}: {reason}",
                )

    component_by_row, component_members = _dependence_components(selected_rows, issues)
    purpose = contract["purpose"]
    target_split = _target_split(purpose)
    target_rows = (
        [row for row in selected_rows if row["split"] == target_split]
        if target_split
        else selected_rows
    )
    target_ids = {row["row_id"] for row in target_rows}
    target_components = {
        component_by_row[row_id] for row_id in target_ids if row_id in component_by_row
    }
    for component in sorted(target_components):
        members = [member for member in component_members[component] if member in target_ids]
        if len(members) > 1:
            _issue(
                issues,
                "ERROR" if purpose != "CURATION" else "WARNING",
                "DEPENDENT_ROWS_SELECTED",
                component,
                f"target split selects multiple connected rows: {members}",
            )

    causal_rows = [row for row in target_rows if row["row_kind"] == "CAUSAL"]
    null_rows = [row for row in target_rows if row["row_kind"] == "NULL"]
    countable_null_rows = [
        row for row in null_rows if row.get("null_class") == "EMPIRICAL_EQUIVALENCE_NULL"
    ]
    for row in null_rows:
        if row.get("null_class") != "EMPIRICAL_EQUIVALENCE_NULL":
            _issue(
                issues,
                "WARNING",
                "NONEMPIRICAL_NULL_NOT_COUNTED",
                row["row_id"],
                "matched decoys and validator negatives do not count toward the null denominator",
            )
    causal_components = {
        component_by_row[row["row_id"]] for row in causal_rows if row["row_id"] in component_by_row
    }
    null_components = {
        component_by_row[row["row_id"]]
        for row in countable_null_rows
        if row["row_id"] in component_by_row
    }

    external_species = set(contract["external_holdout_species_taxon_ids"])
    actual_external_species = {
        row["species_taxon_id"]
        for row in selected_rows
        if row["split"] == "EXTERNAL_SPECIES_HOLDOUT"
    }
    nonexternal_species = {
        row["species_taxon_id"]
        for row in selected_rows
        if row["split"] != "EXTERNAL_SPECIES_HOLDOUT"
    }
    if actual_external_species != external_species:
        _issue(
            issues,
            "ERROR",
            "EXTERNAL_SPECIES_CONTRACT_MISMATCH",
            contract["freeze_id"],
            "external holdout species must exactly match the contract",
        )
    overlap = external_species & nonexternal_species
    if overlap:
        _issue(
            issues,
            "ERROR",
            "SPECIES_SPLIT_LEAKAGE",
            contract["freeze_id"],
            f"external species also occur outside the external split: {sorted(overlap)}",
        )
    if contract["require_orthogroup_disjoint"]:
        external_orthogroups = {
            row.get("orthogroup_id")
            for row in selected_rows
            if row["split"] == "EXTERNAL_SPECIES_HOLDOUT"
        }
        other_orthogroups = {
            row.get("orthogroup_id")
            for row in selected_rows
            if row["split"] != "EXTERNAL_SPECIES_HOLDOUT"
        }
        orthogroup_overlap = (external_orthogroups & other_orthogroups) - {None, ""}
        if orthogroup_overlap:
            _issue(
                issues,
                "ERROR",
                "ORTHOGROUP_SPLIT_LEAKAGE",
                contract["freeze_id"],
                f"external orthogroups occur in other splits: {sorted(orthogroup_overlap)}",
            )

    if purpose == "CURATION":
        _issue(
            issues,
            "BLOCKER",
            "CURATION_ONLY",
            contract["freeze_id"],
            "curation freeze is not an executable performance benchmark",
        )
    else:
        for field in PREREGISTRATION_FIELDS:
            if not _present(contract.get(field)):
                _issue(
                    issues,
                    "BLOCKER",
                    "PREREGISTRATION_RECEIPT_MISSING",
                    contract["freeze_id"],
                    f"{field} is required before evaluation",
                )
        if len(causal_components) < contract["min_causal_independent_units"]:
            _issue(
                issues,
                "BLOCKER",
                "CAUSAL_DENOMINATOR_TOO_SMALL",
                contract["freeze_id"],
                f"target split has {len(causal_components)} independent causal units; "
                f"requires >= {contract['min_causal_independent_units']}",
            )
        if len(null_components) < contract["min_null_independent_units"]:
            _issue(
                issues,
                "BLOCKER",
                "NULL_DENOMINATOR_TOO_SMALL",
                contract["freeze_id"],
                f"target split has {len(null_components)} independent null units; "
                f"requires >= {contract['min_null_independent_units']}",
            )
        if purpose == "EXTERNAL_REPLICATION" and not external_species:
            _issue(
                issues,
                "BLOCKER",
                "EXTERNAL_SPECIES_MISSING",
                contract["freeze_id"],
                "external replication requires at least one held-out species",
            )

    structurally_valid = not any(issue.severity == "ERROR" for issue in issues)
    blockers = any(issue.severity == "BLOCKER" for issue in issues)
    ready = structurally_valid and not blockers and purpose != "CURATION"
    status = "PASS" if ready else ("PASS_WITH_EMPIRICAL_BLOCKER" if structurally_valid else "FAIL")
    return AuditReport(
        SCHEMA_VERSION,
        status,
        structurally_valid,
        ready,
        len(target_rows) if ready else 0,
        len(selected_rows),
        len(causal_rows),
        len(null_rows),
        len(target_components),
        len(causal_components),
        len(null_components),
        target_split,
        input_receipts,
        component_by_row,
        component_members,
        tuple(issues),
    )
