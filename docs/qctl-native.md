# qctl native platform worker

`qctl-native.yml` centrally owns qctl's source tests, native builds, release,
Docker, Homebrew, Scoop and AUR jobs. This is the explicit native-runner exception
to Circle profiles: macOS and Windows release binaries use GitHub-hosted runners.
The orb owns the tiny caller generator and canonical-definition check; consumers
retain no platform matrix or custom build/release logic.

Every PR and main/develop push runs the complete `mvn clean verify` source suite.
Ordinary branch pushes additionally qualify Linux AMD64. Tags qualify all five
Linux/macOS AMD64/ARM64 and Windows AMD64 binaries, then reuse those artifacts in
release and packaging jobs. Manual `full_native: true` qualifies all five without
publishing; false runs the source suite only. Publishing requires a tag push;
fork PRs cannot enter native/publishing jobs and test tokens have read-only
contents permissions. Existing Homebrew credential and packaging PR behavior stay
unchanged. Tag runs are not auto-canceled.

The Intel macOS runner is explicitly `macos-15-intel`; `macos-15` is ARM64.
Each native build also checks its actual machine architecture before compilation.
See https://docs.github.com/en/actions/reference/runners/github-hosted-runners.

## Adoption

After publishing this worker at a reviewed immutable commit SHA, set
`QCTL_SHARED_REF` to that SHA and run the orb's
`src/scripts/generate_qctl_workflow.py` to produce `.github/workflows/build.yml`.
`--check .github/workflows/build.yml` rejects local drift. The corresponding orb
command is `generate_qctl_workflow`; the optional rendering job is
`qctl_generate_workflow`. This is separate from the Circle pipeline generator.

Canary the caller before deleting/replacing the existing workflow. Verify full
source tests, representative branch native build, manual five-platform output,
and existing publishing/packaging permissions. Confirm actual hosted required
check names before changing any rules: reusable calls may change their prefixes.
Local configuration tests and actionlint do not prove native builds or release
credentials. Keep the working native workflow until equivalent hosted evidence
exists. No consumer migration or release has been performed by this patch.
