# Batch consumer enrollment

Use one target file for canonical consumers of every supported Circle profile and
legacy QBits whose jobs and publication filters the shared converter recognizes:

```json
[
  {"checkout": "/work/qbit-example", "default_branch": "main"},
  {"checkout": "/work/qqq", "default_branch": "develop"}
]
```

The branch values must come from repository inventory. Run on clean isolated
checkouts of the branches being migrated.

```sh
python tools/enroll_consumers.py targets.json --orb-version 0.8
python tools/enroll_consumers.py targets.json --orb-version 0.8 --write
```

The command validates the entire batch before writing. Existing manifests keep
all publication and profile options; only the managed orb version changes.
Recognized legacy QBits receive the canonical caller and inferred publication
policy. An unknown job, filter, profile option, duplicate target, symlink, or
concurrent declaration edit rejects the batch. Repeating a completed enrollment
makes no changes. Filesystem errors during the write phase can leave a partial
batch; rerun after correcting the error. This is not a filesystem transaction.

Only `.circleci/config.yml` and `.qqq-ci.yml` are changed. The tool does not delete
other workflows, infer publication from repository names, or enroll unknown
custom pipelines. Their behavior must first be represented by a central profile.
After committing and qualifying the exact source, apply the shared
[branch enforcement tool](branch-enforcement.md) to supported gate profiles.

This command provides batch source conversion. Use the coordinator below for remote signed submissions. Local conversion alone does not prove fleet deployment or release success.

## Remote signed submissions

Supply observed current branches, without cloning each repository yourself:

```json
[
  {"repository": "QRun-IO/qbit-example", "branch": "main"},
  {"repository": "QRun-IO/qqq", "branch": "develop"}
]
```

```sh
python tools/reconcile_enrollment.py --targets remote-targets.json --orb-version 0.8 --output plan.json
python tools/reconcile_enrollment.py --targets remote-targets.json --orb-version 0.8 --output result.json --apply
```

Use existing `gh` authentication, GitHub SSH access, Git author identity and a
working Git signing configuration. The coordinator never installs credentials
or changes authentication. Every target is inspected at an immutable head and
validated before any remote mutation. Only changed targets are cloned. A moved
target stops submission; refresh the plan instead of overwriting it.

An automation branch derives from the source commit and proposed declarations.
The coordinator signs its commit, pushes without force, verifies the remote
signature, parent, exact changed paths and declaration bytes, then opens a PR.
An interrupted push or PR creation can be resumed with the same invocation:
matching signed branches and PRs are reused. A mismatched branch is rejected.
Closed existing PRs are reported as existing; they are not silently reopened.
Reports include repository, branch, immutable head and submission URL, without
embedding declaration contents or credentials. Keep the report if a later target
fails; earlier valid submissions remain intact.

This handles explicit remote target lists and signed submissions. Organization
discovery is available through `audit_estate.py`; automatic target selection,
qualification-aware merging, enforcement reconciliation and scheduling are still
separate work. A submitted PR is not a completed migration. Unknown profiles and
native workflows require their own central conversion, not deletion by this tool.
