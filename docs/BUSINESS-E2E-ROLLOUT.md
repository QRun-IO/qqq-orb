# Business-platform E2E ownership

The reusable `.github/workflows/business-e2e.yml` preserves the exact audited jobs
from `QRun-IO/qqq-business-platform` commit `8af799fce97e972f81f195df969d79a959f71dbc`,
including actual Compose services, blocking Playwright tests, deployment dependency,
alerts, summaries, artifacts, failure logs and unconditional cleanup. Tool versions
and environment values are unchanged. The optional existing alert secret is declared
and forwarded explicitly. No new credential is introduced.

The tiny caller is generated with:

```sh
python src/scripts/generate_auxiliary_workflow.py business-e2e --ref <IMMUTABLE40SHA>
```

It belongs at the SAME consumer path `.github/workflows/e2e.yml`. Events, schedule,
manual dispatch and read permission remain identical. The caller owns the existing
concurrency group; the worker has no second copy that could cancel its own caller.
The worker is `workflow_call` only and cannot run its own schedule.

## Disabled coverage stays disabled

The existing consumer workflow is `disabled_inactivity`, as reported by the release
owner. This source extraction does not enable, trigger, dispatch or alter settings.
Before and after any later caller replacement, read back that same workflow ID/path
and state; stop if disabled status changed. Do not call an enable API, rename the
workflow path, or treat a source-only PR as coverage restoration. Any intentional
reactivation is a separate authorized operation requiring working live-service proof.

This centralizes code ownership; disabled E2E coverage remains an explicit limitation.
Likewise, `tools/no-ci-policy.json` records audited CI absence, not product readiness,
quality approval or a claim that tests have passed.

Local contract tests compare every job/step to an immutable fixture and verify events,
permissions, explicit secret mapping, pinned worker and concurrency ownership:

```sh
python3 -m unittest discover -s tests -p test_business_e2e.py -v
actionlint .github/workflows/business-e2e.yml
```

Hosted E2E success is not claimed. Consumer/settings changes are outside this patch.
