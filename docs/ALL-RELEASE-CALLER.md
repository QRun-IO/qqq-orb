# qqq-all manual release caller

Generate the tiny caller at the existing consumer path `.github/workflows/release.yml`:

```sh
python src/scripts/generate_auxiliary_workflow.py all-release --ref <IMMUTABLE40SHA>
```

No consumer files or workflow settings are changed by this patch. The immutable baseline
is qqq-all `e35f1f6b99639eb998340f082fab89c7ac12426c`. The caller is manual-only, retaining
its original name, version choice/default (`4.1.0` or `4.1.0-RC.1`) and required release SHA.
No push, tag or scheduled release is introduced.

All five worker inputs are forwarded as inputs: `version`, `release_sha`, `smoke_run_id`,
`smoke_evidence`, `circle_workflow_id`. Evidence defaults to `github`. The old required
Smoke run field becomes optional in the dispatch form solely so Circle mode can omit it;
the worker still requires a numeric Smoke run ID in GitHub mode and independently verifies
it. Circle mode requires the exact successful workflow UUID, API-verified provenance,
matching receipt and existing optional `CIRCLECI_TOKEN`. Missing evidence fails closed.

Original contents/packages write and actions read permissions remain; checks read is added
for the central Circle-check validator. Only the optional existing Circle secret is mapped
explicitly; Actions supplies the native GitHub token. No secret values or script inputs
are added.

The protected `qqq-all-release` environment, enabled/license variables, exact version/tag,
develop SHA, public artifacts/GHCR, independent cold verification and publication rechecks
remain in the worker. Its concurrency group is the sole owner, avoiding caller/worker
collision. Generation does not approve the environment or bypass central gates. Hosted
approval/publication and token access remain unproven until an authorized release run.

```sh
python3 -m unittest discover -s tests -p test_generate_all_release.py -v
```

Root must actionlint the generated caller and worker. Legacy orchestration stays until the
pinned worker and consumer evidence adapter are available and relevant tests pass.
