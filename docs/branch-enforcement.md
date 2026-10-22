# Shared orb check enforcement

`tools/enforce_orb_checks.py` replaces repository-specific scripts for the shared
CircleCI `setup` and `verify` branch gates. One invocation processes an explicit
batch of current `main` and `develop` branches using existing `gh` authentication.

Create a targets file:

```json
[
  {"repository": "QRun-IO/qbit-example", "branch": "main"},
  {"repository": "QRun-IO/qbit-example", "branch": "develop"}
]
```

Preview, then apply the same batch:

```sh
python tools/enforce_orb_checks.py --targets targets.json --orb-version 0.8 --output enforcement-plan.json
python tools/enforce_orb_checks.py --targets targets.json --orb-version 0.8 --output enforcement-result.json --apply
```

Every branch must already contain the exact canonical caller for its manifest and
have successful `setup` and `verify` checks from CircleCI app 18001 at its current
commit. Supported profiles are QBit, Core, frontend-core, frontend-material and repository-policy.
The complete batch is inspected before any mutation. Source/head/protection drift,
unavailable APIs, unknown profiles, and ruleset-managed branches fail closed.

The tool appends the app-bound checks, enables strict checks and administrator
enforcement, and reads the result back. Existing required checks remain required.
For protected branches it uses the narrow status-check/admin endpoints, preserving
reviews, signatures, linear history, restrictions and other settings. For a
previously unprotected branch it creates protection without adding human reviews.
It never changes scanner configuration, repository visibility, billing, or source.

Output records the planned head and original protection, then verification as each
branch completes. A batch is not transactional: if an API call fails, inspect the
output and rerun; successful protections are retained rather than rolled back.
An already-correct branch needs no mutation.

This command covers the shared orb gate pair only. Continue to run the estate
audit for scanner/native-worker requirements and other policy. Automatic repository
discovery, source enrollment and scheduled reconciliation remain separate work.

GitHub API reference: [protected branches](https://docs.github.com/en/rest/branches/branch-protection).

```sh
python -m unittest discover -s tests -p test_enforce_orb_checks.py -v
```
