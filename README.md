# QQQ Orb

CircleCI orb for Maven projects using GitFlow. Provides automated building, testing, version management, and Maven Central publishing.

## Quick Start

### Using the Orb

```yaml
# .circleci/config.yml
version: 2.1
orbs:
  qqq-orb: kingsrook/qqq-orb@2.1

workflows:
  test_only:
    filters:
      branches:
        ignore: [develop, main, /release\/.*/, /hotfix\/.*/]
    jobs:
      - qqq-orb/build
      - qqq-orb/test:
          requires: [qqq-orb/build]

  publish_snapshot:
    filters: { branches: { only: develop } }
    jobs:
      - qqq-orb/publish:
          context: qqq-maven-registry-credentials
          branch_type: snapshot

  publish_release_candidate:
    filters: { branches: { only: /release\/.*/ } }
    jobs:
      - qqq-orb/publish:
          context: qqq-maven-registry-credentials
          branch_type: release_candidate

  production_release:
    filters: { branches: { only: main } }
    jobs:
      - qqq-orb/publish:
          context: qqq-maven-registry-credentials
          branch_type: release

  hotfix_release:
    filters: { branches: { only: /hotfix\/.*/ } }
    jobs:
      - qqq-orb/publish:
          context: qqq-maven-registry-credentials
          branch_type: hotfix
```

### Required Context

Set up `qqq-maven-registry-credentials` context in CircleCI:
- `MAVEN_USERNAME`, `MAVEN_PASSWORD`: Sonatype credentials
- `GPG_PRIVATE_KEY_B64`, `GPG_KEYNAME`, `GPG_PASSPHRASE`: GPG signing
- `GITHUB_TOKEN`: GitHub releases
- `RDBMS_PASSWORD`: Database testing

### Project Requirements

- `pom.xml` with `<revision>` property
- `/tmp/circleci/mvn-settings.xml` (auto-generated if missing)
- `docs/index.adoc` (optional, for documentation)

## Development

### Prerequisites
```bash
# Install CircleCI CLI
curl -fLSs https://raw.githubusercontent.com/CircleCI-Public/circleci-cli/main/install.sh | sudo bash

# Install linting tools
brew install shellcheck yamllint  # macOS
```

### Commands
```bash
make pack      # Pack orb (resolves <<include()>>)
make validate  # Validate packed orb
make lint      # Run all linting checks
make dev       # Pack + validate
make clean     # Clean build artifacts
```

### Publishing
```bash
make publish-dev  # Publish as kingsrook/qqq-orb@dev:alpha
make publish      # Publish as kingsrook/qqq-orb@X.Y.Z
```

## Version Management

Automated version calculation based on branch:
- `develop`: Minor bump (1.5.0-SNAPSHOT → 1.6.0-SNAPSHOT)
- `release/1.5`: RC versions (1.5.0-RC.1, 1.5.0-RC.2, ...)
- `main`: Stable release (1.5.0-RC.3 → 1.5.0) **requires v* tag**
- `hotfix/1.5.1`: Patch bump (1.5.0 → 1.5.1)

**Main branch requires release tags**: `git tag -a v1.5.0 -m "Release 1.5.0" && git push origin v1.5.0`

## Available Jobs

| Job | Branch | Output |
|-----|--------|--------|
| `build` | Any | Compiled artifacts |
| `test` | Any | Test results + JaCoCo |
| `publish` | Any | Unified publishing based on branch_type parameter |

### Publish Job Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `branch_type` | string | "snapshot" | Branch type: snapshot, release_candidate, release, hotfix |

## Repository Structure

```
src/
├── @orb.yml              # Orb definition
├── commands/              # Reusable commands
├── jobs/                  # Complete workflow jobs
├── scripts/               # Shell scripts (<<include()>>)
└── examples/              # Usage examples
```

## Project Links

- **Main Project**: [QQQ Framework](https://github.com/Kingsrook/qqq)
- **Issues & Planning**: [QQQ Issues](https://github.com/Kingsrook/qqq/issues)
- **Documentation**: [QQQ Docs](https://github.com/Kingsrook/qqq/tree/main/docs)
- **CircleCI Registry**: [kingsrook/qqq-orb](https://circleci.com/developer/orbs/orb/kingsrook/qqq-orb)

## Usage Examples

**Backend only (default)**:
```yaml
jobs:
  - qqq-orb/publish:
      context: qqq-maven-registry-credentials
      branch_type: snapshot
```

**Release with GitHub release**:
```yaml
jobs:
  - qqq-orb/publish:
      context: qqq-maven-registry-credentials
      branch_type: release
```

## License

MIT License - see [LICENSE](LICENSE)
