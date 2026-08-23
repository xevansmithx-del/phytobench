# Contributing

Contributions are welcome when they preserve the fail-closed and claim-boundary contracts.

1. Fork the repository and create a focused branch.
2. Do not add real restricted data, credentials, local paths, raw sequence/alignment/variant files,
   or biological rows without complete rights and provenance receipts.
3. Add positive and adversarial tests for every new state transition or gate.
4. Run `uv sync --frozen --extra dev`, the full tests, Ruff, pre-commit, the privacy scanner, and the
   release validator.
5. Submit a pull request describing the threat addressed and the exact acceptance evidence.

No contribution may weaken empirical `N=0`, promote a discovery candidate to causal truth, or imply
experimental authority merely because software checks pass.
