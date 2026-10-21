# Estate audit policy

`tools/audit_estate.py` classifies repositories from explicit mappings and observed source.
It never changes consumers, branch rules or publication settings.

Source auditing reads the repository's current default branch unless
`--live --source-branch main` (or an explicit `release/...` or `hotfix/...` branch)
is supplied. Run separate audits for each maintained source branch: a clean
default-branch report does not establish conformity on main or release branches.
The selected branch is resolved to an immutable commit before any files are read.
Reports identify both `source_branch` and the repository's `default_branch`;
the manifest's `default_branch` must still match the repository default.
Unavailable selected branches remain unknown without falling back to default.
Explicit branch selection requires live lookup and cannot relabel an offline SHA.
Required-check policy still controls which branch settings are inspected;
`--source-branch` changes source selection, not that enforcement policy.

- Circle profiles include android, mcp-policy and marketing. Their manifest and canonical
  setup caller remain mandatory; a missing configuration is a finding.
- MCP, business-platform and the organization `.github` repository use approved native
  bridges from `src/scripts/templates/auxiliary-bridges.json`. Unknown remaining workflows
  are findings. Legacy Circle configuration remains a finding until retired after equivalent
  native checks pass on the actual consumer head. Business E2E is not implicitly approved.
- `qqq-orb` is the owner/bootstrap exception, not a consumer of itself. Audit requires its
  lint/pack/review/ShellCheck graph and continuation dependencies, executable command and
  pipeline-contract test jobs, and develop/main publishers gated by those tests. Both
  publishers must pack, validate and publish. This structural check is not hosted proof.
- `tools/no-ci-policy.json` approves exactly nine named repositories with rationale,
  immutable baseline SHA and required identity paths. Their approved state has no Circle,
  Actions, manifest, Jenkins or GitLab entrypoint at the declared paths. A new workflow or
  missing identity path is drift; an unknown repository never inherits this exemption.
  Baseline SHA records audit provenance, not a requirement to freeze documentation forever.

`managed_branches` is an explicit, nonempty unique list of `main` and/or `develop`,
provided only after branch inventory readback. Its default is both for compatibility.
The auditor queries only listed branches. A missing policy remains unknown; an API
403/404 does not prove a branch is absent and remains unknown. A policy entry alone
never proves a branch exists: successful `Snapshot.checks` first reads the branch.

Only the exact approved no-CI repositories may declare an empty expected context list.
They pass that check only after successful readback returns an actually empty set.
Stale required contexts are findings. Ordinary, native and owner profiles still reject
empty context policies. No-CI classification documents absence, not product readiness.

Required-check policy is independent of classification. Without an explicit observed
context policy and successful branch-rule readback, check status stays `unknown`, including
no-CI and bootstrap repositories. No classification fabricates a passing merge check.

## Organization workflow lint bridge

Generate only after the worker is published at an immutable commit:

```sh
python src/scripts/generate_auxiliary_workflow.py github-workflow-lint --ref <40SHA>
```

The output belongs at `.github/workflows/workflow-lint.yml` in `QRun-IO/.github`.
The orb owns `.github/workflows/workflow-lint.yml` as a reusable worker. It retains the
original Circle `cimg/go:1.24` image and exact actionlint v1.7.7 command over
`.github/workflows/*.yml`, with checkout and read-only contents permission. Branch pushes
run lint; fork PRs also run it without secrets. Same-repository PR events do not duplicate
push lint, and tags do not add new builds. Manual dispatch is available for verification.

Keep the existing Circle actionlint pipeline and legacy RC worker until a hosted native
canary proves tool/runtime equivalence and the required-check migration is reviewed.
Do not remove the old RC coordinator while any consumer still references it.

## Checks

```sh
python3 -m unittest discover -s tests -p test_audit_estate.py -v
python3 -m unittest discover -s tests -p test_workflow_lint.py -v
python3 -m unittest discover -s tests -p test_auxiliary_workflows.py -v
actionlint .github/workflows/workflow-lint.yml
```

Tests cover exact no-CI allowlists and drift, unknown repositories, missing configured
profiles/native bridges, retained legacy workflows, bootstrap dependency/gate removal,
required-check unknown states, and the lint image/tool/command/caller contract.

## Batch orb-version rollout

Upgrade existing canonical CircleCI consumers with one command:

```sh
python tools/rollout_version.py --orb-version 0.7.11 /checkouts/qbit-one /checkouts/qqq-cli
python tools/rollout_version.py --orb-version 0.7.11 --write /checkouts/qbit-one /checkouts/qqq-cli
```

The first command previews the batch. The second updates only `.qqq-ci.yml` and
`.circleci/config.yml`, after every supplied checkout passes the existing manifest
and canonical-caller validators. It preserves publication opt-outs, release filters,
credential context names and forwarded profile parameters. Already-current files
are unchanged. Duplicate checkouts, custom jobs, invalid options and mismatched
pins reject the batch before writing; resolve these in the central profile first.

Use isolated checkouts of the intended repository heads, inspect the resulting
patches, then commit and push through the normal automated gates. The tool does not
commit, push, publish packages, change GitHub rules or modify native/RC worker pins.
A version update does not prove a publication succeeded: retain exact-head hosted
verification and artifact evidence. The requested version must already be published.

```sh
python3 -m unittest discover -s tests -p test_rollout_version.py
```
