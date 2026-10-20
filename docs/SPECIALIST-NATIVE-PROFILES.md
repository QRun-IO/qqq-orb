# Specialist native ownership

`generate_auxiliary_workflow.py mcp-rag --ref FULL_ORB_COMMIT` and
`business-db --ref FULL_ORB_COMMIT` emit canonical immutable bridges.
Worker policy lives in this repository. No Circle pipeline is added for either
bridge, and no consumer has been migrated by adding these definitions.

## MCP RAG

Audited source: `7ff9bc7af7e949eee164efb90e3b4a2b931b2278`.
One `mvn -B -ntp clean verify` includes the POM-bound Checkstyle validate phase,
Error Prone compiler, unit tests, Failsafe integration-test/verify and existing
coverage checks. This replaces the separate native lint/compile and verify jobs.
It does not introduce skipped tests or the old Circle-only PMD skip.

The worker keeps Java 21, Maven caching, the explicit optional
`QQQ_MCP_VOYAGE_API_KEY` secret, JAR artifact handoff, and the original dependent
main-push-only image job. GHCR authentication remains the ephemeral GitHub token
with packages write permission. The repository Dockerfile, commit-SHA and latest
tags are unchanged. Test reports are retained even when verification fails.

The caller covers all branch pushes (the old Circle coverage), PRs targeting main,
and manual runs. A same-repository PR can still have both a branch-head and a
merge-ref run: those inputs are not proven equivalent, so this migration does not
silently drop merge validation. Superseded non-main runs of the same event/ref
cancel; main publication is not cancelled. Native runtime cost still counts
towards total CI cost; no measured savings are claimed.

Consumer Circle retirement requires hosted equivalence and an audit of existing
`qstudio-ci` environment variables. Local source identifies the named Voyage
secret, but cannot prove that a private Circle context has no other inputs.
No credentials were copied, replaced or assumed. Hosted image publication,
native permissions and required-check migration remain unverified here.

## Business database migrations

Audited source: `8af799fce97e972f81f195df969d79a959f71dbc`.
The native worker retains the exact `mvn -B -pl db verify` job, Java 21,
Maven cache, PR path filters and main push path filters. Its source paths are
`db/**`, `pom.xml`, and the existing PR workflow path. It introduces no new
schedule, publication, secret or Circle pipeline.

The existing disabled business-platform E2E workflow is an explicit exception.
This implementation neither re-enables it nor claims that its live-service
coverage has been standardized. Enablement is an external workflow setting,
not something proven by the audited YAML. Consumer retirement/adoption must
preserve that disabled state.

`tests/test_auxiliary_workflows.py` checks exact database worker/event equality,
MCP image-job equality, the declared secret, all-branch coverage, and the actual
POM phase bindings used to remove duplicate lint/compile work.
