# Marketing pipeline ownership

The `marketing` profile accepts only `profile`, `orb_version`, and
`default_branch: main`. The QQQ version must match the setup caller's explicit
orb version. The canonical QQQ setup produces one final continuation containing
jobs from the pinned `kof22/munitor@0.3.11` orb. It never invokes Munitor's setup
generator or creates another continuation.

The profile is the exact semantic graph rendered by Munitor 0.3.11 from
marketing-website commit `4eb5f63b9fbfac8e5529fcd638324870cea08ae2`, with its
manifest's floating `0.3` pin changed to `0.3.11` for the baseline render.
The checked-in fixture records that real render; the JSON resource contains the
same jobs, parameters, contexts, filters and dependency edges.

There are five workflows and 33 job invocations: PR checks (7), develop (7),
staging (7), release candidate (8), and production (4). They preserve Node 22,
Chromium Playwright and Lighthouse, the existing scan and quality jobs, advisory
SAST, and the existing synthetic zero-threshold coverage command. That command
does not measure actual coverage.

Production follows build → image build/Trivy/push/health → independent CD update
and GitHub release. Both final jobs depend on the image job; neither depends on
the other. Only main updates
`KofTwentyTwo/cluster-gitops/tenants/qrun/website/kustomization.yaml`, using the
existing `github` context; image publication uses `ghcr`. Production-only means
no non-main deployment update, not no non-main artifacts: develop/staging image
publishing and release-candidate GitHub releases remain unchanged.

Keep `.munitor.yml` as declarative worker input when migrating the consumer.
Munitor's `generate_dockerfile` reads it from the attached workspace and requires
`pipeline: node-webapp` and `docker.use_repo_dockerfile: true` to preserve the
repository Dockerfile. The profile does not replace that file or validate all
of its values. Changes to worker input require review alongside the centralized
profile; arbitrary manifest job overrides are not supported. Health remains `/`
on port 3000; the repository Dockerfile remains responsible for the standalone
runtime without npm or npx.

`MarketingContractTests` checks whole-graph equality and explicit release/test
contracts. The normal generator suite additionally checks source/packed parity.
These are configuration tests, not a claim of hosted delivery, credentials,
container health, or production deployment verification.
