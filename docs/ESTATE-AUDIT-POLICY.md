# Estate audit policy

`tools/audit_estate.py` classifies repositories from explicit mappings and observed source.
It never changes consumers, branch rules or publication settings.

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
