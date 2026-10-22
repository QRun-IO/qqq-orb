# Marketing pipeline ownership

The `marketing` profile accepts only `profile`, `orb_version`, and
`default_branch: main`. The QQQ version must match the setup caller's explicit
orb version. The canonical QQQ setup produces one final continuation containing
jobs from the pinned `kof22/munitor@0.3.11` orb. It never invokes Munitor's setup
generator or creates another continuation.

The baseline fixture records the original Munitor 0.3.11 render. The shared
profile selects one workflow for the current branch and exposes it as `verify`:
PR checks for feature/hotfix/automation branches, develop, staging, release
candidate, or production for main. Tags and the RC bookkeeping branch do not
run these jobs. Existing deployment dependencies and contexts are preserved.

The build job installs dependencies once, lints, builds, runs Chromium
Playwright tests, crawls local links and runs Lighthouse. The link crawl waits
at most 60 attempts for the app on port 3005, propagates failures, and stops its
server on exit. Playwright and Lighthouse reports are retained as artifacts,
including on failure. The old synthetic coverage job was removed because it
fabricated 100% rather than measuring coverage; actual tests and scans remain.

Production follows build → image build/Trivy/push/health → independent CD update
and GitHub release. Both final jobs depend on the image job; neither depends on
the other. Only main updates
`KofTwentyTwo/cluster-gitops/tenants/qrun/website/kustomization.yaml`, using the
existing `github` context; image publication uses `ghcr`. Production-only means
no non-main deployment update, not no non-main artifacts: develop/staging image
publishing and release-candidate GitHub releases remain unchanged.

Consumers need only the QQQ caller and `.qqq-ci.yml`. Before tests, the shared
profile writes minimal `.munitor.yml` worker input into the build workspace:
`pipeline: node-webapp`, Node 22, and `docker.use_repo_dockerfile: true`.
Munitor's Docker worker still requires this file; the orb owns its contents.
This preserves the repository Dockerfile rather than generating a replacement.
Container health remains `/` on port 3000, distinct from the local test server
on port 3005. The repository Dockerfile remains responsible for the standalone
runtime without npm or npx.

The duplicate consumer GitHub test workflow can be removed only after these
central checks qualify. Application test settings and assertions remain in the
application repository; orchestration belongs here.

`MarketingContractTests` checks whole-graph equality and explicit release/test
contracts. The normal generator suite additionally checks source/packed parity.
These are configuration tests, not a claim of hosted delivery, credentials,
container health, or production deployment verification.
