# Source and rights policy

PhytoBench separates discovery metadata from locked benchmark authority. The public
`registry/DISCOVERY_QUEUE.json` contains official URLs and high-level terms summaries only. It is not
valid input to the freeze command and establishes no causal or null row.

Before a source can enter `LOCKED_SOURCE_REGISTRY.json`, an independent reviewer must capture the
exact bytes or metadata record, immutable version, retrieval date, content and response-metadata
hashes, earliest-public date, parent lineage, truth/training status, license terms, authorization
scope, and review receipt. `UNKNOWN` never means permitted.

## Preferred discovery sources

- [Planteome](https://planteome.org/documents), [Gene Ontology](https://geneontology.org/docs/go-citation-policy/),
  [UniProt](https://www.uniprot.org/help/license), and
  [Expression Atlas](https://www.ebi.ac.uk/gxa/licence.html) for identifiers, ontologies, experimental
  references, and covariates—not causal truth.
- [TAIR public releases](https://phoenixbioinformatics.atlassian.net/wiki/spaces/COM/pages/42216430/TAIR+Terms+of+Use)
  only when the exact file is designated public; subscriber material remains outside this repository.
- [Crossref](https://www.crossref.org/documentation/retrieve-metadata/) and
  [Europe PMC](https://europepmc.org/RestfulWebService) for DOI, version, correction, retraction, and
  earliest-publication checks. Article text follows its own license.
- [Dryad](https://datadryad.org/publication_policy) and
  [Zenodo](https://about.zenodo.org/policies/) for versioned replayable datasets, subject to the exact
  record and file licenses.
- [NCBI](https://www.ncbi.nlm.nih.gov/home/about/policies/) and
  [Ensembl](https://protists.ensembl.org/info/about/legal/disclaimer.html) for versioned assemblies,
  accessions, and catalog normalization while retaining submitter and upstream-rights caveats.

## Quarantine defaults

Association/QTL/GWAS alone, expression correlation, orthology transfer, reviews, database summaries,
unverified interventions, ambiguous backgrounds, unavailable historical snapshots, inaccessible
evidence, post-truth annotations, unclear redistribution terms, and nonsignificant-only “nulls” are
quarantined. A primary causal experiment plus orthogonal confirmation is required for a causal row;
an adequately powered equivalence result with a predeclared negligible-effect margin and working
positive controls is required for a countable null.

The source queue should begin substantially above the final denominator because strict rights,
pre-truth, identity, and independence gates will reject many leads. Planning targets are not empirical
sample counts and must never be reported as benchmark results.
