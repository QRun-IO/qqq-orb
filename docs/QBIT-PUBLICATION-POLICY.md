# Preserve existing QBit release selection

Migration now reads the audited job filters, not just the presence of a
publication job. The following bounded QBit-only manifest fields preserve the
recognized contracts:

| Field | Values | Behavior |
|---|---|---|
| `release_on_main` | boolean, default false | Main pushes select the existing release job when release publishing is enabled. |
| `release_tag_policy` | `stable`, `v-prefix`, `none` | Stable `v1.2.3`, the existing broad `/v.*/` contract, or no tags. |
| `test_branch_policy` | `all`, `non-release`, `non-release-no-integration`, `feature`, `non-release-no-main` | Selects one of the five audited test branch exclusions. |

`feature` preserves the original exclusion of develop, main, release branches,
and integration-prefixed branches; it is not a new feature-prefix-only rule.
All policies continue to exclude the RC coordination lock branch.
No consumer-supplied regex, command, job, or arbitrary branch-publication rule
is accepted.

An explicit tag policy also controls the canonical setup caller's tag filter.
`none` prevents even setup from running on tags for the four test-only repos.
Stable and broad policies run only their approved tags. Existing manifests
without the field retain their previous canonical caller for compatibility.
Every tag publication still verifies that the actual Git tag resolves to HEAD.
Main publication does not invent a tag requirement that the existing jobs lacked.
`publish.release: false` still disables release publication.

The 42 immutable source fixtures preserve eight main-push publishers, four broad
tag publishers, the remaining stable tag publishers, and four test-only repos.
Snapshot/RC inference accepts only the observed develop and release branch
filters. Unknown filters, duplicate publication/test jobs, and custom job options
fail migration rather than silently changing release behavior.

Use `tools/standardize_qbit.py --write` for the two-file migration. API callers
must pass the inferred policy to
`canonical_caller(version, manifest["release_tag_policy"])`; the legacy one-argument
form is only for manifests without an explicit policy.

Focused tests cover the immutable inventory, unknown-filter rejection, canonical
caller agreement, main opt-in, broad/stable tag selection, HEAD provenance,
publication opt-out and test exclusions. The packed generator suite also exercises
main, broad RC-shaped tags, and excluded integration branches.
