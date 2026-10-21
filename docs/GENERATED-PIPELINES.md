# Standardized QQQ pipelines

The orb owns workflow selection and job configuration. A consumer declares a
small manifest; it does not copy pipeline jobs. The initial supported profile is
`qbit`; `core` owns the framework's complete acceptance/release graph. Frontend
and CLI profiles described below retain their own publication contracts. Additional
profiles belong in reviewed `PROFILE_TEMPLATES` renderers in
`src/scripts/generate_pipeline.py`, with profile-specific schema and tests. There
is no arbitrary script or job-YAML passthrough.

Use the same **published** orb version in all three positions below. `0.7.0` is
an illustrative version, not a claim that this change is published. A development
orb version can be used for a controlled canary.

`.circleci/config.yml`:

```yaml
version: 2.1
setup: true
orbs:
  qqq-orb: kingsrook/qqq-orb@0.7.0
workflows:
  setup:
    jobs:
      - qqq-orb/generate_pipeline:
          orb_version: "0.7.0"
          filters:
            branches:
              ignore: automation/qbit-rc-pending
            tags:
              only: /.*/
```

`.qqq-ci.yml`:

```yaml
profile: qbit
orb_version: "0.7.0"
default_branch: develop
java_version: "21"
browsers: false
api_checks: false
docs_only: false
publish:
  snapshot: true
  release_candidate: true
  release: true
  asciidoc: false
```

Only `profile`, `orb_version` and `default_branch` are required. `default_branch`
must be `develop` or `main`; Java must be the string `17` or `21`. Browsers default
to **true** for compatibility: opt out only after verifying that the consumer has
no browser tests. API checks and docs-only default to false. Publication defaults
to true for snapshots, RCs and tagged releases; AsciiDoc publication defaults to
false. Unknown/duplicate keys, unexpected types, unsupported profiles and a setup
parameter/manifest version mismatch fail before continuation. The canonical-caller
validator also verifies the setup import, filters and profile-specific parameter
declarations; additional jobs, commands, workflows or orbs fail validation. The
parser is pinned to PyYAML 6.0.3 and uses its safe loader.

| Event | Workflow | Job contract |
| --- | --- | --- |
| develop | verify | existing mvn_publish, snapshot |
| release/* | verify | existing mvn_publish, release_candidate |
| vX.Y.Z tag resolving to the checkout | verify | existing mvn_publish, release |
| main, feature/*, hotfix/*, other/unknown branch | verify | existing mvn_test_only |
| Disabled publication or unrecognized/unproven tag | verify | full verification, no publication |

Generated `qbit`, `core`, `frontend-core`, and `frontend-material` pipelines use
the stable workflow name `verify`. All selected jobs, dependencies and filters
remain intact; this adds no executor or duplicate build. Other profiles retain
their existing workflow names and native checks.

When upgrading from legacy workflow names, upgrade the immutable RC worker pin
alongside the orb so finalization recognizes both names. Confirm the CircleCI
app's successful `verify` check on the exact migration commit before replacing
legacy required contexts. Require `setup` and `verify` on managed branches,
preserving other required checks and controls. Human approval is not required;
automated checks authorize the migration.

The pipeline SHA must match the checkout when Circle supplies it. A tagged release
must resolve to that checkout; missing local tags are fetched individually. A main
push does **not** publish a release. Migrating a legacy main-publishing consumer
therefore requires explicit review of its release contract. Existing direct orb
callers remain supported.

The setup filter and generated jobs exclude `automation/qbit-rc-pending`, the
shared RC orchestrator's persistent release lock. Lock updates must not trigger
Maven test or publication work.

The shared jobs keep the `qqq-maven-registry-credentials` context, complete verify,
coverage and configured API checks. Publishing retains version management, signed
artifact deployment, Git operations and release handling. Generated calls disable
the redundant preliminary compile; they do not skip tests or verification. Existing
callers retain the compatibility defaults in the jobs.

## Core profile

QBit alone accepts `release_completion: true` (default false). It enables the
shared Maven RC job's `notify_rc_published` only for RC publication, including
fail-closed verification that the bumped version was pushed before dispatching
the completion event. Enable this on a consumer only after its default branch
contains the shared completion caller. Snapshot and GA jobs never receive this
opt-in; other profiles reject the key.

Use `profile: core` for the QQQ framework. The orb owns the complete baseline
acceptance, broker conformance, cold bootstrap, coverage, diagnostics, static
analysis and publication graph. Core scripts remain in the core source repository.
The independent baseline fixture pins job sets, dependency edges, contexts,
coverage requirements and actual verification commands across all six workflows.

Core additionally supports `publish.feature` and `publish.hotfix` (both true by
default), preserving `publish*` tag and hotfix branch publication. QBit supports
both keys as explicit opt-ins (false by default). QBit feature publishing requires
a `publish*` tag resolving to the checked-out commit; feature branch pushes remain
test-only. Snapshot, RC and GA behavior remains distinct; RC/GA/hotfix
publication still requires the complete source coverage gate. Cold bootstrap and
fresh consumer Maven repositories remain uncached. Shared installer policy replaces
local package preparation; preliminary compilation is disabled before clean
lifecycles and the dependency cache is saved after successful verification.

Lambda XML copies remain in sample coverage evidence. The sample JUnit collector
excludes those two copied reports because their original module directories are
already uploaded, avoiding duplicate test identities without dropping evidence.

External core API triggers require these declarations in the tiny **setup** config:

```yaml
parameters:
  mongo_bind_diagnostics:
    type: boolean
    default: false
  next_acceptance_bundle_url:
    type: string
    default: ""
  next_acceptance_bundle_sha256:
    type: string
    default: ""
  next_acceptance_receipt_sha256:
    type: string
    default: ""
```

Forward each value on `qqq-orb/generate_pipeline`, for example
`mongo_bind_diagnostics: << pipeline.parameters.mongo_bind_diagnostics >>`, and
likewise for the three bundle parameters. Requested values become defaults in the
continued configuration; the continuation POST deliberately omits `parameters` to
avoid CircleCI's setup/continuation/API parameter conflict. Verify both default and
explicit API-triggered parameter values in the hosted canary before migrating
triggering consumers. Other profiles reject non-default core parameters.

## Frontend profiles

`frontend-material` preserves the Maven frontend build/test/package/publication
jobs, Java21/Node20 defaults, registry context, feature-tag, RC, GA and hotfix
contracts. Declare setup pipeline parameter `run_playwright` (boolean, default
false) and forward `run_playwright: << pipeline.parameters.run_playwright >>` on
the generator job. Test/snapshot events select exactly one base or Playwright graph,
so enabling visual tests cannot publish twice. Visual testing retains the pinned
Playwright image, npm ci with legacy peer dependencies and report uploads; only
npm downloads (`~/.npm`) are cached, never node_modules.

`frontend-core` preserves Node24.21, npm trusted publishing and both existing
registry/build-sample contexts. Unlike QBit, its existing main-push **and v-tag**
release contract remains intentional. Both frontend profiles support explicit
numeric-string `node_version` and publication toggles including feature/hotfix.
Material also supports `java_version`. Browser/API/AsciiDoc flags are rejected
rather than silently ignored on these profiles. Existing direct jobs remain usable.

## CLI profile

`cli` owns npm install, generated-client drift, build, unit tests and the real
Prism smoke contract through `cli_verify_publish`. Publication is **disabled by
default**. To enable the existing v-tag publication, declare `publish.release:
true` plus `publish_context: VERIFIED_CONTEXT_NAME`, after verifying that an
existing trusted CircleCI context grants the required GitHub Packages permission.
No context name or credential availability is inferred from the former Actions
GITHUB_TOKEN. A tag must resolve to the current checkout; the job additionally
checks the client version before publishing its three fixed workspaces with the
existing rc dist-tag. Main pushes never publish. CLI docs-only is currently
rejected because generated-client verification remains mandatory.

## Conservative documentation routing

With `docs_only: true`, only feature/hotfix and main changes can take the light
route. Feature/hotfix branches fetch the declared default branch without tags and
compare its merge base with HEAD, covering the whole branch. Main compares its first
parent. Develop, release branches and all tags remain full. Shallow repositories,
missing ancestry, fetch/diff errors, empty diffs and unknown paths remain full.

Only root README.md, CHANGELOG.md, CONTRIBUTING.md and Markdown files below docs/
are eligible. Renames are treated as deletion plus addition, so moving code into
docs cannot hide it. The lightweight job checks whitespace over the proven diff;
manifest validation already ran in setup. It adds no new security scanner and
makes no security-scanning claim. Keep docs-only disabled if those paths are build
inputs or packaged application content.

The light route keeps workflow `verify` and names its job
`qqq-orb/mvn_test_only`. Verify actual CircleCI/GitHub status contexts on the canary
before changing any protection rule; workflow/job identity alone is not proof of
the hosted context name. Current protections must not be removed speculatively.

## Implementation and verification

The setup job checks out source, installs the pinned parser, runs the embedded
Python resource and invokes CircleCI's native continuation API once. JSON output
is valid CircleCI configuration YAML; it is saved at
`/tmp/qqq-generated-config.json`. No external framework or per-consumer generator
installation is required. Readable templates live in src/scripts/templates. scripts/pack_pipeline.py embeds
them as base64 into packed_generate_pipeline.py before orb packing, preventing
CircleCI from interpolating template expressions during setup. The orb includes
the complete generated resource; no runtime source-tree template access is needed.
make pack regenerates it and CI rejects a stale generated resource.
Continuation credentials and response bodies are never printed.

Run `make test-pipelines` with CircleCI CLI, Python3/PyYAML and Bash available.
Tests use offline temporary Git repositories and a bare origin to cover selection,
whole-branch changes, tags, errors, defaults and source/packed parity. The hosted
pipeline-contract-test runs the source suite and shared Maven behavioral tests;
the full local target additionally extracts and executes the actual packed command.

## Android and MCP policy profiles

`android` and `mcp-policy` accept only profile, orb_version and default_branch.
Android retains the audited Android/GCP orb versions and every active unit,
emulator and Maven-publication step. The emulator now runs on main as well as
feature branches so main publication cannot omit its required instrumentation
gate. Dormant Firebase benchmark and release-build definitions referencing absent
app/macrobenchmark modules are not scheduled or copied into the profile.

MCP policy validation remains a small Python container validating all visible YAML
and required pattern fields. Its existing PyYAML dependency is pinned to 6.0.3.
Neither profile introduces Maven/JUnit stand-ins for its actual tests.

`tests/test_mobile_policy_profiles.py` protects Android steps and dependency edges
and executes the policy validator with valid, incomplete and malformed documents.
The generator suite verifies source/packed parity for both profiles.
