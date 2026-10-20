# Next native workers

The orb repository owns the reusable workers in `.github/workflows/next-*.yml`.
`src/scripts/generate_next_workflow.py --ref FULL_ORB_COMMIT` emits the sole tiny
consumer `.github/workflows/next.yml` bridge; `--check PATH` validates its canonical
shape. Pins must be immutable 40-character commits. Do not point consumers at an
unreleased working tree or mutable default branch.

Native GitHub execution preserves the existing dynamic PR-label acceptance matrix,
native ARM64 dashboard image proof and ephemeral GitHub Packages token. It is not
a second copy of Circle's frontend tests. The consumer's old CI/acceptance/image
workflow bodies must be removed when the bridge is activated and its checks proven.

The initial extraction preserves all five CI jobs, real-backend plan/build/shards/
gate/quarantine jobs and AMD64/ARM64 image jobs. Acceptance remains 18 cells for
main/tag/manual/full-acceptance and four cells for ordinary PRs. Each cell retains
its isolated backend and existing serial-worker contract; one built artifact feeds
all cells. The report merger and every-planned-shard evidence check remain required.
Unrelated PR label edits no longer rerun validation: only `full-acceptance` label
changes rerun acceptance, while unit/browser/image jobs skip all label-only events.

The `frontend-next` Circle profile retains the existing tag-only delivery contract:
the tag build plus immutable npm/Maven version comparison, typecheck, lint, tests,
static export and signed JAR deployment. Its manifest accepts only `profile`,
`orb_version` and `default_branch`; its canonical setup caller ignores all branches.
The shared Java installer owns the existing unattended package-install policy.
Native workers own branch checks, with no duplicate Circle branch test/build jobs.
Tag validation intentionally still overlaps native validation during this initial
move. As before, JAR publication is independent of native acceptance; no new
cross-platform coordination gate or artifact-reuse guarantee is claimed.
Hosted permissions and protection-context migration still need canary validation.

`python3 tests/test_next_native.py` compares every worker job/step against the audited
baseline and executes the original selector fixture to prove 18/4 counts. It checks
the immutable caller references and label conditions. Run actionlint and hosted
canaries before consumer migration; generated required contexts may differ.
