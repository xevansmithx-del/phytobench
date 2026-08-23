# Threat model

PhytoBench assumes benchmark inputs, filenames, manifests, and curator assertions can be wrong or
adversarial. It treats missing evidence as a refusal, never as independence or permission.

## Covered threats

- Duplicate loci hidden behind aliases, assemblies, papers, panels, or repeated null transforms.
- Direct or transitive leakage from truth-bearing annotations, post-cutoff ancestors, training
  corpora, orthology labels, descriptive row IDs, and causal/null filenames.
- License laundering, mutable URLs without captured hashes, unknown terms, and permission receipts
  rebound to different content.
- Curator-selected independence identifiers, cross-split dependence, external-species reuse, and
  orthogroup overlap.
- Inflated denominators from correlated rows or nonempirical matched decoys.
- Truth replacement after commitment, case deletion, duplicate case IDs, hidden admissions, and
  denominator removal through missing outputs.
- Repeated external-holdout peeking or method/configuration changes after the primary run.
- Duplicate JSON keys, `NaN`/`Infinity`, wrong primitive types, Unicode-confusable identifiers,
  symlinks, traversal paths, manifest drift, accidental credentials, local paths, and restricted raw
  biological payloads.

## Current controls

- Strict schemas, safe JSON parsing, canonical receipts, manifest replay, source-lineage traversal,
  connected-component grouping, split audits, distinct human-review identities, and public-license
  scopes.
- Separate mixed runner and supervisor packs with opaque random case IDs and random-salted truth
  commitments.
- Only `EMPIRICAL_EQUIVALENCE_NULL` rows with power, interval, margin, positive-control, and
  independent-QC receipts count toward the null denominator.
- Runner validation is offline; source capture is a separate future operation.

## Residual risks

- Hashes do not establish that a paper is correct, a license interpretation is legally correct, two
  reviewers are genuinely independent, or a supplied grouping key is complete.
- Coordinates and phenotype context can identify a famous historical locus even when labels are
  removed. A true blind evaluation needs an independent supervisor, offline runner, historical
  source snapshot, and operator separation.
- The initial attempt ledger is sealed but not cryptographically signed or hosted by an independent
  append-only service. Repeated-use governance therefore remains a human and repository-control
  obligation until the successor workflow is implemented.
- No biological row exists in the locked release; empirical performance remains unknown.

## Non-goals

PhytoBench is not a sandbox for arbitrary code, a secure enclave, a legal opinion, a clinical tool,
an experiment design system, or an authorization mechanism for gene editing.
