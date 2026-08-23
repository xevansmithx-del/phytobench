# PhytoBench

PhytoBench is a fail-closed benchmark intake, provenance, independence, blinding, and leakage
auditor for plant interval-to-gene research. It creates separate runner and supervisor bundles,
counts connected dependence components rather than file rows, and refuses evaluation freezes when
licensing, pre-truth, preregistration, statistical-denominator, or external-holdout controls are
missing.

**Status:** `0.1.0-alpha.3`, software-only research release. The public locked benchmark contains
zero causal rows, zero null rows, and empirical `N=0`. No biological performance, causal-gene,
gene-editing target, experimental authorization, or scientific-breakthrough claim is established.

## Why this exists

A benchmark can look large while containing repeated papers, related panels, duplicated loci,
orthologous families, or multiple transforms of the same null case. It can also leak its answers
through post-truth annotations, source ancestry, filenames, row labels, or repeated use of a held-out
set. PhytoBench turns those concerns into executable refusal conditions and auditable receipts.

The first downstream compatibility target is the immutable PhytoAllele `0.2.0a3` research alpha,
but PhytoBench is a separate repository and never rewrites that release.

## Core guarantees

- Draft 2020-12 schemas reject unknown fields, wrong primitive types, malformed dates, and partial
  SHA-256 receipts.
- Duplicate JSON keys, non-finite numbers, symlinked inputs, path traversal, manifest drift, and
  commitment substitution fail closed.
- Every selected row must bind its trait, assembly, interval, cohort, panel, phenotype protocol,
  evidence cutoff, source registry, lineage root, family, and orthogroup.
- Causal evidence must predate truth disclosure and cannot reuse the truth source or truth digest.
- Public freezes require explicit source-license and redistribution authorization; `UNKNOWN` is not
  permission.
- Union-find components connect shared studies, cohorts, populations, lineages, orthogroups, and
  sources. Multiple connected target rows cannot inflate the effective denominator.
- External species and, when requested, orthogroups are disjoint from non-external splits.
- Causal and null roles are mixed behind opaque case IDs and random-salted truth commitments.
- Runner bundles contain no truth gene, causal/null role, null type, source title, or original row ID.
- Evaluation freezes require preregistered rule, code, analysis-plan, and power-analysis receipts;
  at least 35 independent causal units and 73 independent null units are only minimum gates, not a
  universal power guarantee.
- The tool runs offline. It never fetches data during audit or verification.

Hashes establish byte identity, not scientific correctness, legal permission, independence, or
causality. Independent human truth and rights review remain mandatory.

## Quick start

Install the locked development environment:

```bash
uv sync --frozen --extra dev
```

Audit the intentionally empty public contract:

```bash
uv run --frozen phytobench audit \
  --sources examples/empty/source_registry.json \
  --rows examples/empty/benchmark_rows.json \
  --contract examples/empty/freeze_contract.json
```

The command exits successfully because the documents are structurally valid, but its receipt says
`PASS_WITH_EMPIRICAL_BLOCKER`, `empirical_n=0`, and `evaluation_ready=false`. Add
`--require-ready` to convert that blocker into a nonzero exit.

Create and replay a curation freeze:

```bash
uv run --frozen phytobench freeze \
  --sources examples/empty/source_registry.json \
  --rows examples/empty/benchmark_rows.json \
  --contract examples/empty/freeze_contract.json \
  --output empty-freeze
uv run --frozen phytobench verify empty-freeze
```

The supervisor directory must remain under independent control during a real benchmark. Only the
runner directory is delivered to the model or method being evaluated. Truth salts are revealed only
after the primary output receipt is sealed.

## Benchmark lifecycle

Candidate records move through:

```text
DISCOVERED -> RIGHTS_CLEAR -> PRIMARY_REPLAYED -> DUAL_CURATED -> ADJUDICATED
-> LEAKAGE_CLEAR -> INDEPENDENCE_LOCKED -> FROZEN
```

`REJECTED` and `QUARANTINED` are terminal for a freeze. Database annotations are discovery aids,
not causal truth; a cited primary experiment and replayable evidence are required.

See [benchmark protocol](docs/BENCHMARK_PROTOCOL.md), [threat model](docs/THREAT_MODEL.md), and
[architecture decision](docs/ADR-001-BENCHMARK-AUTHORITY.md).

## Publication and data boundary

The software is Apache-2.0. Third-party biological data retain their own terms and are not covered
by the code license. This repository must contain only synthetic fixtures, licensed metadata,
hash-only receipts, and explicitly redistributable source records—never controlled germplasm data,
human data, credentials, private local paths, or raw FASTA/FASTQ/BAM/CRAM/VCF payloads.

## Development

```bash
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pre-commit run --all-files
```

Security reports should follow [SECURITY.md](SECURITY.md). Contributions must preserve the claim
boundary and all fail-closed behavior.
