# qqq-all Circle smoke evidence (opt-in, not yet adopted)

`qqq-all-release.yml` defaults to genuine GitHub Smoke evidence. Circle mode is
explicit `smoke_evidence: circle`, `circle_workflow_id: <UUID>`, with a separately
passed reusable secret `CIRCLECI_TOKEN` and `checks: read`. No credential is
created or assumed available. The protected worker writes the reviewed orb-owned `qqq_all_release_gate.py` and
`verify_all_circle_smoke.py` into its temporary directory and executes that gate
against `--root .` (the consumer checkout). No consumer adapter is required.

The reviewed verifier is embedded verbatim in the reusable worker (a regression
test prevents drift). It reads Circle workflow, pipeline, jobs and pipeline
workflows, then checks GitHub app 18001's latest same-SHA `verify-and-smoke` Check
Run and exact Circle workflow URL. Evidence requires QRun-IO/qqq-all, the release
SHA on develop without a tag, a webhook trigger with actor and received time,
successful workflow and all jobs, and exactly one successful build-and-test/core/full
job each. API/manual triggers are rejected. Circle's webhook metadata does not
expose a GitHub event subtype; this proves a develop webhook, not an asserted
`push` event field. It is never represented as a GitHub Smoke run.

Selective reruns are not accepted: explicit rerun ancestry/auto-rerun flags or
multiple same-name workflows within a pipeline fail closed. Paginated evidence
also fails closed; the tool does not infer omitted jobs or attempts. A newer
failed/pending check or different workflow UUID cannot be bypassed by selecting
an older success. Both API sources must be readable; errors deny authorization.
This conservative policy may require a fresh complete develop pipeline after a
failure. Hosted schema/credential verification is still required before enabling.

## Central gate and rollout

`src/scripts/qqq_all_release_gate.py` is copied from audited qqq-all commit
`e35f1f6b99639eb998340f082fab89c7ac12426c`. Every original validator body is
unchanged. Its CLI accepts exactly one complete evidence mode: the original
`--smoke-run`/`--smoke-jobs` pair, or `--circle-smoke`. Circle mode checks the schema,
repository and SHA, then invokes the same verifier on every nested evidence field.
It never treats an arbitrary Boolean or caller-uploaded receipt as proof.

The original `test_release_gate.py` and `test_release_rc.py` are retained in orb
tests with only module/path import adaptations. They still exercise GA/RC limits,
immutable dependencies, published POM matching, signed tags, public upstream state
and cold public downloads. New mode/parity tests ensure both central scripts match
their embedded worker definitions and all source-relative paths remain in the
consumer checkout. The consumer's product tests and release bundle script remain.

Rollout needs a tiny caller passing `smoke_evidence: circle`, the workflow UUID,
`checks: read`, and the existing explicitly authorized Circle credential. Validate
a real complete develop Circle workflow and secret scope before removing the old
GH Smoke workflow. No release-gate implementation should be copied back into a
consumer. Existing legacy consumers can keep `smoke_evidence: github` by default.

The protected `qqq-all-release` environment, release flags, exact annotated signed
tag checks, source identity, cold Maven verification, public input receipts,
GHCR checks and prepublication develop/tag recheck remain in place. No consumer
source changes, credential provisioning, release attempt or publication has been
performed. Do not remove the genuine GH Smoke path until the new evidence mode
has passed a real complete pipeline and central gate validation.
