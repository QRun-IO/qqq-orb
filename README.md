# qqq-orb

CircleCI orb for QQQ framework projects.

**For:** Teams using CircleCI to build, test, and publish QQQ applications
**Status:** Stable (v0.4.0)

## Why This Exists

QQQ projects share common CI/CD patterns: build with Maven, run tests, publish to Maven Central or npm. Setting this up from scratch means duplicating workflow configuration across every repository.

This orb provides pre-built jobs for the complete QQQ development lifecycle. Add a few lines of YAML and your project has automated testing, version management, and publishing.

## Features

- **Maven and npm support** - Builds Java and Node.js projects
- **GitFlow integration** - Automated versioning based on branch type
- **Publishing automation** - Maven Central and npm registry publishing
- **Test coverage** - JaCoCo integration with coverage reporting
- **Version calculation** - Semantic versioning with SNAPSHOT, RC, and release support
- **Java 21 default** - Configurable Java version (17.0, 21.0)

## Quick Start

**Prerequisites:** CircleCI account, repository connected to CircleCI

```yaml
# .circleci/config.yml
version: 2.1
orbs:
  qqq-orb: qrun-io/qqq-orb@0.4

workflows:
  build_and_test:
    jobs:
      - qqq-orb/mvn_test_only

  publish_snapshot:
    when:
      equal: [develop, << pipeline.git.branch >>]
    jobs:
      - qqq-orb/mvn_publish:
          context: qqq-maven-registry-credentials
          branch_type: snapshot
```

## Usage

### Available Jobs

| Job | Purpose |
|-----|---------|
| `mvn_test_only` | Build and test Maven projects |
| `mvn_publish` | Build, test, and publish Maven artifacts |
| `mvn_frontend_test_only` | Build and test Maven projects with npm frontend |
| `mvn_frontend_publish` | Build, test, and publish Maven projects with npm frontend |
| `node_test_only` | Build and test Node.js projects |
| `node_publish` | Build, test, and publish Node.js packages |

### Branch Types

| Branch | Version Format |
|--------|----------------|
| `develop` | `1.5.0-SNAPSHOT` |
| `release/1.5` | `1.5.0-RC.1` |
| `main` | `1.5.0` (requires tag) |
| `hotfix/1.5.1` | `1.5.1` |
| `feature/*` | `1.5.0-feature-abc1234-SNAPSHOT` |

### Java Version

Default is Java 21. To use Java 17:

```yaml
jobs:
  - qqq-orb/mvn_test_only:
      java_version: "17.0"
```

### Required Context Variables

| Variable | Purpose |
|----------|---------|
| `MAVEN_USERNAME` | Sonatype username |
| `MAVEN_PASSWORD` | Sonatype password |
| `GPG_PRIVATE_KEY_B64` | Base64-encoded GPG key |
| `GPG_KEYNAME` | GPG key ID |
| `GPG_PASSPHRASE` | GPG passphrase |
| `GITHUB_TOKEN` | GitHub API token |

## Project Status

**Maturity:** Stable, used across all QQQ repositories
**Breaking changes:** See [CHANGELOG.md](CHANGELOG.md)

**Roadmap:**
- GitHub Actions support
- Parallel test execution
- Container image publishing

## Contributing

```bash
git clone git@github.com:QRun-IO/qqq-orb.git
cd qqq-orb
make test-all
```

See [QQQ Contribution Guidelines](https://github.com/Kingsrook/qqq/blob/develop/CONTRIBUTING.md).

## License

AGPL-3.0 - QRun-IO
