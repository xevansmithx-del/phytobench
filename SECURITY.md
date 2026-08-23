# Security policy

## Supported versions

PhytoBench is an alpha research tool. Only the newest GitHub release receives security fixes.

## Reporting

Use GitHub private vulnerability reporting for security-sensitive issues. Do not open a public issue
containing credentials, restricted datasets, unpublished biological records, or an unpatched
exploit. Ordinary correctness and documentation issues may use the public issue tracker.

## Security boundary

PhytoBench validates local, untrusted JSON and sealed directory trees without network access. It
rejects duplicate JSON keys, non-finite numbers, unknown schema fields, symlinked inputs and bundle
members, unsafe manifest paths, duplicate case identifiers, hash drift, and truth-commitment drift.

Hashes establish byte identity, not truth, permission, or independence. The tool is not a secure
multi-party computation system, a legal opinion, a clinical device, an experiment authorizer, or a
substitute for an independent benchmark supervisor. The supervisor bundle and salts must be kept
outside the runner's access boundary until the primary output is sealed.
