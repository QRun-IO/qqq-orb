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

This handles remote target lists and signed submissions. Organization discovery is described below. Qualification-aware merging and classic branch enforcement are described below; scheduling and ruleset reconciliation remain separate work. A submitted PR is not a completed migration. Unknown profiles and
native workflows require their own central conversion, not deletion by this tool.

## Organization discovery

The coordinator can select observed current branches directly from GitHub:

```sh
python tools/reconcile_enrollment.py --organization QRun-IO --orb-version 0.8 --output organization-plan.json
python tools/reconcile_enrollment.py --organization QRun-IO --orb-version 0.8 --output organization-result.json --apply
```

Repository and branch inventories are paginated. Only existing main/develop
branches are considered; historical release branches are excluded. Archived
repositories and the orb's own bootstrap repository are reported separately.
Each supported branch receives the same immutable preflight as explicit targets.
Unknown workflows, missing entrypoints, unsupported branch layouts and unavailable
APIs stay `unresolved` in the output. They are never counted as conforming or
silently converted. No-CI and native-only repositories may therefore appear as
unresolved here; use the estate auditor for their separate policy classification.

Discovery finishes before any submission. `--apply` processes qualified plans
and retains unresolved entries for follow-up; one unsupported repository does
not prevent independent valid submissions. An explicit `--targets` batch keeps
its stricter behavior: any preflight failure stops the whole batch. By default neither mode merges PRs or changes branch protections. Use the explicit completion flags below.

## Qualification and enforcement

```sh
python tools/reconcile_enrollment.py --targets remote-targets.json --orb-version 0.8 --output result.json --apply --merge-ready --enforce
```

Both flags require `--apply` and are optional. `--merge-ready` revalidates the
signed submission, exact parent/files/content and current base, requires successful
CircleCI-app `setup` and `verify` checks and every advertised latest check/status,
then requests a normal exact-head squash merge. It never uses admin override or
force pushes. The resulting signed merge must have the qualified source tree.
Pending/failed checks and changed bases are reported without merging. Repeated
runs can advance the same PR once checks complete; there is no polling loop that
holds a CI executor open.

`--enforce` independently checks the actual current target branch, which must
pass its own orb gates before shared classic protection enforcement. Existing
protections and other required checks are preserved. Supported gate profiles are
QBit, Core, frontend-core, frontend-material and repository-policy. Other profiles
remain explicitly unsupported for completion even when source enrollment works.
Existing active repository rulesets with app-bound gates and no bypass actors are verified without writes. Unsupported or incomplete rulesets remain unresolved; none are rewritten or layered with classic protection. API/plan restrictions remain visible.

A merged source update and an enforced branch are separate reported outcomes.
Neither proves artifact publication or deployment. Scheduling and ruleset
reconciliation remain outstanding.
