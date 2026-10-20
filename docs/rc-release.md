# RC completion without waiting runners

The reusable `qbit-release-rc.yml` keeps the existing cut entry point. `finalize: false`
(the default) briefly merges develop, then records `qbit-rc-intent-<merge SHA>` as a
90-day Actions artifact. It does not wait for CircleCI or Central. `finalize: true`
accepts `merge_sha`, `bump_sha`, `branch`, and `version` from a publisher callback
or explicit recovery retry. The callback is only a hint, never release authority.

The caller must remain `.github/workflows/release-rc.yml` on the repository default
branch. It handles `repository_dispatch` type `qbit-rc-published` and passes those
four fields and `finalize: true` to this reusable, with `secrets: inherit` and
`contents: write`, `actions: read`, `checks: read`. Existing manual dispatch and merged/labelled
PR cut behavior remains in the tiny caller. Add an explicit finalization retry
option to manual dispatch; retrying finalization must not request another cut.
GitHub documents dispatch/default-branch behavior at:
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#repository_dispatch

## Ownership and provenance

- A cut atomically creates `refs/heads/automation/qbit-rc-pending` before changing
  the release branch. The ref initially points at develop and then at the exact
  merge API response SHA. A second cut fails while it exists. CI must ignore this
  exact automation branch. The lock has no expiry or automatic takeover.
- Cut and finalizer share one repository concurrency group. The pending ref holds
  ownership between these short runs; workflow concurrency alone cannot do that.
- Finalization retrieves the unique unexpired intent artifact and verifies its
  originating successful `release-rc.yml` run, repository, trigger and attempt.
  Callback fields must match that immutable intent.
- The exact merge SHA must have a successful `publish_release_candidate` Check Run
  from CircleCI app ID `18001`; unrelated job statuses cannot authorize release.
  Terminal publisher failure stops finalization immediately. Pending/absent publication cannot authorize a tag.
  The RC bump must have exactly that one parent and the release branch must still
  point to it. A later unrelated bump or an old version is never substituted.
- The Central POM must identify the expected artifact/version and have a
  Last-Modified time after the cut. Missing Central visibility leaves the intent
  pending, with no tag, no lock release, no sleeping runner.
- Tags remain SSH-signed annotated tags using `QRUN_TAG_SIGNING_KEY`. Temporary
  key/repository/intent files are cleaned on all shell exits. Existing annotated
  tags must resolve to the exact bump; duplicate delivery cannot retarget a tag.
  A tag created before an interrupted release operation can finish the missing
  prerelease on retry. Ownership is compared again before lock deletion.

## Automatic retry and rollout

The orb's single centrally scheduled `rc_finalize_sweep` job uses the existing
`qqq-maven-registry-credentials` context's `GITHUB_TOKEN` (or `GH_TOKEN`) and an
explicit JSON allowlist, not `.github`'s repository-limited Actions token. It
reads only pending locks, validates cut provenance and exact publisher success,
checks Central availability, and redispatches the same immutable candidate.
Idle repositories cause one read and no finalizer job. Central delay causes a
later scheduled retry, not allocated polling. Terminal failure is visible in
sweep job failure; the lock stays for diagnosis. Bound: 64 repositories,
500 GitHub calls, 480 seconds plus the current bounded request; no infinite retry.
The root owns the single Circle schedule and confirms existing credential access
before enabling it. No new credential or service is required by this patch.

Roll out shared reusable and default-branch callers first, then the released orb
callback/profile plus automation-branch exclusion. Enable the one central sweep
only after checking the allowlist and representative cross-repository API access.
The orb callback must be opt-in until callers exist, RC-only, after successful
deployment AND successful pushed bump, with remote head and direct parent checks.
Do not emit a callback after the legacy warning-only failed version push.

## Recovery

A failed cut, expired artifact, failed publisher or conflicting tag deliberately
retains the lock. Inspect the cut run, lock SHA, release branch, Circle result,
Central artifact and tag/release before changing state. If the cut is recoverable,
retry the same publication/finalization; do not delete the lock merely to unblock
another version. For an abandoned cut, an authorized operator must compare the
current lock with the recorded expected SHA immediately before deleting that
exact ref, under the same release lane. Never delete a different cut's lock or
retag a published version. A missing/expired trusted artifact requires explicit
release-captain reconciliation; the sweep does not invent provenance.

## Local checks

`python -m unittest discover -s tests -v` exercises the exact inline evaluator.
`actionlint -shellcheck= .github/workflows/qbit-release-rc.yml` validates Actions
syntax. Full actionlint with Windows native ShellCheck hung locally and was
stopped; Linux actionlint/ShellCheck and end-to-end credential/callback rollout
verification remain required. The orb has separate sweep/dispatch fixture tests.
