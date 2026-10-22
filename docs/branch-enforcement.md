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
unavailable APIs and unknown profiles fail closed. Existing repository rulesets are verified as described below.

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

## Existing rulesets

When effective branch rules come from repository rulesets, the tool can verify
existing enforcement without adding classic protection. Each contributing ruleset
must be active for branches, have no bypass actors and require both setup and
verify from CircleCI app18001. The current branch must also have successful gate
runs. The tool rechecks the branch, effective rules and full ruleset records before
reporting verified. Rule drift or an unbound/missing gate stops verification.

This path writes nothing. It preserves scanner requirements, conditions and the
existing up-to-date-branch policy, including a false strict setting that avoids
unnecessary rebuilds. Reports identify protection_mode=rulesets and the observed
strict value. Unsupported organization-level rulesets, bypass actors and missing
gates remain unresolved rather than being rewritten or ignored.

For classic protection, an empty push allowlist with admin enforcement disabled
requires an explicit access-policy resolution before enabling admin enforcement.
The tool rejects that case before any writes to avoid locking every actor out.
