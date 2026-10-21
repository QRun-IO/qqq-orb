# Managed patch updates

The canonical caller and manifest accept either an exact stable version such as
`0.8.0` or a quoted minor track such as `"0.8"`. CircleCI resolves a minor track
to its latest published patch. A major-only version, `latest`, `volatile`, and
wildcards are rejected. The caller import, setup parameter, and manifest must
still agree exactly.

Use a minor track after qualifying that release line. Future patch fixes then
arrive on the repository's next pipeline without a version-bump PR or an extra
fleet-wide build. Existing exact pins remain supported and are not changed by
publishing this capability. YAML minor versions must be quoted to remain strings.

The central batch tool applies the same update to all supplied checkouts:

```sh
python3 tools/rollout_version.py --orb-version 0.8 --write /path/to/repo1 /path/to/repo2
```

This changes only the two canonical CI declarations. Publication policies,
contexts, branch/tag filters, and profile options stay unchanged. Normal source
and publication checks still run when a pipeline is triggered; this setting does
not skip tests. GitHub reusable-worker commit pins are separate and unchanged.

Automatic patch adoption trades exact-version reproducibility for centrally
managed fixes. Keep patch releases backward compatible, qualify central changes
before production publication, and use an exact stable pin for a canary or
rollback. For example, the same tool can move a consumer from `0.8` back to
`0.8.0`. Historical pipeline reruns can resolve a newer patch; choose an exact
pin when reproducing an earlier run. Setup and continuation each resolve their
orb imports, so patch compatibility also matters when publication overlaps a run.

Changing minor tracks is an explicit migration. Do not use this feature to push
breaking changes into a patch release or to bypass repository checks.

Reference: [CircleCI orb semantic versioning](https://circleci.com/docs/orbs/use/orb-concepts/).

