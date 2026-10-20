# Orb-owned native maintenance workflows

Four existing workflows retain their event contracts in generated tiny callers:

| Repository | Caller path | Orb worker |
| --- | --- | --- |
| QRun-IO/qqq | `.github/workflows/codeql.yml` | `core-codeql.yml` |
| QRun-IO/qqq | `.github/workflows/published-bom-consumer.yml` | `core-published-bom-consumer.yml` |
| QRun-IO/qqq | `.github/workflows/quickstart-lifecycle.yml` | `core-quickstart-lifecycle.yml` |
| QRun-IO/qbit-authentik | `.github/workflows/schema-drift.yml` | `qbit-schema-drift.yml` |

Generate a caller with `python src/scripts/generate_auxiliary_workflow.py KIND
--ref IMMUTABLE_ORB_COMMIT_SHA`; `--check PATH` detects drift. The estate auditor
recognizes these exact approved bridges. No consumer files are changed by the
generator unless its output is explicitly redirected by the rollout operator.

Worker jobs are structurally identical to audited QQQ commit
`bc0b0f11ef9d436c80b2e3c5268726a6bc0881c1` and Authentik commit
`dbae77da5b6236268900f1238ce083f9d078d66d`. Tests compare the complete job objects,
events and permissions against those fixtures. This preserves CodeQL's two
language analyses, BOM source/ref/version validation, immutable acceptance-tools
checkout, browser/OS matrix, private diagnostic handling and schema drift test.
The caller retains schedules, tag filters and dispatch choices. Reusable inputs
supply empty defaults on scheduled/tag runs, matching the original absent inputs;
quickstart tag runs still derive the candidate and source SHA in the original job.
No credentials are inherited beyond the automatic job token.

Publish the orb commit and verify reusable access before adoption. Hosted check
names may gain the reusable caller prefix: observe actual canary check names and
update required checks only after successful execution, preserving other rules.
Local structural tests cannot prove hosted CodeQL upload or native execution.
No consumer migration, rule update or publication is performed by these files.
