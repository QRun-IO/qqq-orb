# qqq-orb

CircleCI orb for QQQ framework projects.

**For:** Teams using CircleCI to build, test, and publish QQQ applications  
**Status:** Stable (v0.3.8)

## Why This Exists

QQQ projects share common CI/CD patterns: build with Maven, run tests, publish to Maven Central or npm. Setting this up from scratch means duplicating workflow configuration across every repository.

This orb provides pre-built jobs for the complete QQQ development lifecycle. Add a few lines of YAML and your project has automated testing, version management, and publishing.

## Features

- **Maven and npm Support** - Builds Java and Node.js projects
- **GitFlow Integration** - Automated versioning based on branch type
- **Publishing Automation** - Maven Central and npm registry publishing
- **Test Coverage** - JaCoCo integration with coverage reporting
- **Version Calculation** - Semantic versioning with SNAPSHOT, RC, and release support

## Quick Start

### Prerequisites

- CircleCI account
- Repository connected to CircleCI
- `qqq-maven-registry-credentials` context with publishing credentials

### Basic Configuration

```yaml
# .circleci/config.yml
version: 2.1
orbs:
  qqq-orb: kingsrook/qqq-orb@2.1

workflows:
  build_and_test:
    jobs:
      - qqq-orb/build
      - qqq-orb/test:
          requires: [qqq-orb/build]

  publish_snapshot:
    when:
      equal: [develop, << pipeline.git.branch >>]
    jobs:
      - qqq-orb/publish:
          context: qqq-maven-registry-credentials
          branch_type: snapshot
```

## Usage

### Available Jobs

| Job | Purpose |
|-----|---------|
| `build` | Compile project |
| `test` | Run tests with coverage |
| `publish` | Build and publish artifacts |

### Branch Types

| Branch | Version Format |
|--------|----------------|
| `develop` | `1.5.0-SNAPSHOT` |
| `release/1.5` | `1.5.0-RC.1` |
| `main` | `1.5.0` (requires tag) |
| `hotfix/1.5.1` | `1.5.1` |
| `feature/*` | `1.5.0-feature-abc1234-SNAPSHOT` |

### Full GitFlow Configuration

```yaml
workflows:
  test_only:
    when:
      not:
        or:
          - equal: [develop, << pipeline.git.branch >>]
          - equal: [main, << pipeline.git.branch >>]
          - matches: { pattern: "^release/.*", value: << pipeline.git.branch >> }
    jobs:
      - qqq-orb/build
      - qqq-orb/test:
          requires: [qqq-orb/build]

  publish_snapshot:
    when:
      equal: [develop, << pipeline.git.branch >>]
    jobs:
      - qqq-orb/publish:
          context: qqq-maven-registry-credentials
          branch_type: snapshot

  publish_release_candidate:
    when:
      matches: { pattern: "^release/.*", value: << pipeline.git.branch >> }
    jobs:
      - qqq-orb/publish:
          context: qqq-maven-registry-credentials
          branch_type: release_candidate

  publish_release:
    when:
      equal: [main, << pipeline.git.branch >>]
    jobs:
      - qqq-orb/publish:
          context: qqq-maven-registry-credentials
          branch_type: release
```

## Configuration

### Required Context Variables

| Variable | Purpose |
|----------|---------|
| `MAVEN_USERNAME` | Sonatype username |
| `MAVEN_PASSWORD` | Sonatype password |
| `GPG_PRIVATE_KEY_B64` | Base64-encoded GPG key |
| `GPG_KEYNAME` | GPG key ID |
| `GPG_PASSPHRASE` | GPG passphrase |
| `GITHUB_TOKEN` | GitHub API token |

### Project Requirements

Maven projects need a `pom.xml` with a `<revision>` property. The orb updates this property during builds.

## Development

```bash
# Validate orb
make validate

# Run tests
make test-all

# Publish dev version
make publish-snapshot
```

## Project Status

Stable and used across all QQQ repositories.

### Roadmap

- GitHub Actions support
- Parallel test execution
- Container image publishing

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run `make test-all`
4. Submit a pull request

## License

MIT - Kingsrook, LLC
