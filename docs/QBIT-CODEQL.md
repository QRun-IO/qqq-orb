# Shared QBit source scanning

Generate the thin caller with `python3 src/scripts/generate_auxiliary_workflow.py qbit-codeql --ref <immutable-worker-sha>`.
The reusable worker selects supported languages from tracked files in the actual checked-out branch. Historical Java branches therefore do not request an absent Actions database. Java, JavaScript/TypeScript, Python and Actions share one job; Kotlin selects an actual build instead of silently omitting Kotlin from no-build Java analysis.

The caller scans pull requests, main/develop/release/hotfix pushes and weekly, cancels superseded PR scans, and contains no scan implementation. Set `codeql_worker_sha` in the estate enforcement policy to require the exact canonical caller independently of other native worker pins. Existing default-setup repositories remain unchanged until migrated.

Roll out to both active default and maintained branches. Verify the worker on representative branch contents and preserve existing query coverage before replacing GitHub default setup; do not run duplicate default and advanced scanners permanently. Default setup cannot select languages independently for historical branches. A branch with no supported application or workflow source is a placeholder to classify, not a passing application scan.

Local tests execute the embedded language-selection step against real git indexes, including absent Actions, untracked generated files, mixed source, Kotlin and placeholders. Hosted CodeQL database creation and SARIF upload must also pass before claiming rollout completion.

References: [GitHub setup types](https://docs.github.com/en/code-security/concepts/code-scanning/setup-types) and [CodeQL build modes](https://docs.github.com/en/code-security/reference/code-scanning/codeql/build-options-for-compiled-languages).
