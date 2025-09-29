# QQQ Orb

[![CircleCI Orb](https://img.shields.io/badge/CircleCI%20Orb-kingsrook%2Fqqq--orb-blue.svg)](https://circleci.com/developer/orbs/orb/kingsrook/qqq-orb)
[![Version](https://img.shields.io/badge/version-0.3.8-blue.svg)](https://circleci.com/developer/orbs/orb/kingsrook/qqq-orb)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **CircleCI Orb for QQQ Framework Projects**

CircleCI orb for Maven and Node.js projects using GitFlow. Provides automated building, testing, version management, and publishing to Maven Central and npm registries.

## 🚀 Overview

QQQ Orb is a **CircleCI orb** that provides standardized CI/CD workflows for projects in the QQQ ecosystem. It handles the complete development lifecycle from building and testing to publishing releases.

### What This Repository Contains

- **CircleCI Orb**: Reusable CI/CD workflows and commands
- **GitFlow Integration**: Automated branching and version management with intelligent version calculation
- **Multi-Platform Support**: Maven (Java) and npm (Node.js) project support
- **Publishing Automation**: Automated publishing to Maven Central and npm
- **Comprehensive Testing**: Full test suite with dynamic test environments
- **Quality Gates**: Enforced linting, testing, and validation before publishing

### What This Repository Does NOT Contain

- **QQQ Framework**: The actual low-code engine and backend
- **Application Code**: Business logic or application-specific code
- **Runtime Dependencies**: Libraries or frameworks used by applications

## 🏗️ Architecture

### Technology Stack

- **CircleCI Orbs**: Reusable configuration components
- **GitFlow**: Branching strategy for release management
- **Maven**: Java project build and dependency management
- **npm**: Node.js package management
- **Shell Scripts**: Automation and utility scripts with comprehensive testing
- **YAML**: Configuration and workflow definitions

### Core Capabilities

- **Automated Building**: Maven and npm project compilation
- **Testing**: Unit tests, integration tests, and coverage reporting
- **Intelligent Version Management**: Automated semantic versioning based on GitFlow with feature branch support
- **Publishing**: Maven Central and npm registry publishing with quality gates
- **Documentation**: Automated documentation generation and publishing

## 🚀 Quick Start

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

| Variable | Description | Required For |
|----------|-------------|--------------|
| `MAVEN_USERNAME` | Sonatype username | Maven publishing |
| `MAVEN_PASSWORD` | Sonatype password | Maven publishing |
| `GPG_PRIVATE_KEY_B64` | Base64 encoded GPG private key | Maven signing |
| `GPG_KEYNAME` | GPG key identifier | Maven signing |
| `GPG_PASSPHRASE` | GPG passphrase | Maven signing |
| `GITHUB_TOKEN` | GitHub API token | GitHub releases |
| `RDBMS_PASSWORD` | Database password | Integration testing |

### Project Requirements

- **Maven Projects**: `pom.xml` with `<revision>` property
- **Node.js Projects**: `package.json` with version field
- **Settings**: `/tmp/circleci/mvn-settings.xml` (auto-generated if missing)
- **Documentation**: `docs/index.adoc` (optional, for documentation)

## 📁 Repository Structure

```
src/
├── @orb.yml                    # Main orb definition
├── commands/                   # Reusable commands
│   ├── mvn_build.yml          # Maven build command
│   ├── mvn_verify.yml         # Maven test and verify
│   ├── mvn_jar_deploy.yml     # Maven deployment
│   ├── node_build_package.yml # Node.js build and package
│   ├── node_publish.yml        # npm publishing
│   └── ...                    # Additional commands
├── jobs/                      # Complete workflow jobs
│   ├── mvn_publish.yml        # Maven publishing workflow
│   ├── mvn_test_only.yml      # Maven testing workflow
│   ├── node_publish.yml        # npm publishing workflow
│   └── node_test_only.yml     # npm testing workflow
├── scripts/                   # Shell scripts
│   ├── calculate_version.sh   # Intelligent version calculation
│   ├── mvn_build_compile.sh   # Maven compilation
│   ├── node_npm_auth.sh       # npm authentication
│   └── ...                    # Additional scripts
├── executors/                 # Execution environments
│   └── default.yml            # Default executor configuration
└── examples/                  # Usage examples
    └── build.yml             # Example configuration

tests/                        # Comprehensive test suite
├── test_calculate_version.sh # Version calculation tests
├── run_tests.sh             # Test runner with CI support
└── README.md                # Test documentation
```

## 🎯 Available Jobs

| Job | Branch | Output | Description |
|-----|--------|--------|-------------|
| `build` | Any | Compiled artifacts | Build project without testing |
| `test` | Any | Test results + JaCoCo | Run tests with coverage |
| `publish` | Any | Published artifacts | Unified publishing based on branch_type |

### Publish Job Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `branch_type` | string | "snapshot" | Branch type: snapshot, release_candidate, release, hotfix |

## 🔧 Development

### Prerequisites

```bash
# Install CircleCI CLI
curl -fLSs https://raw.githubusercontent.com/CircleCI-Public/circleci-cli/main/install.sh | sudo bash

# Install linting tools (macOS)
brew install shellcheck yamllint

# Install linting tools (Ubuntu/Debian)
sudo apt-get install shellcheck yamllint
```

### Development Commands

```bash
# Core development
make pack            # Pack orb (resolves <<include()>>)
make validate        # Validate packed orb
make lint            # Run all linting checks (YAML, ShellCheck, CircleCI orb)
make dev             # Pack + validate + show status
make clean           # Clean build artifacts and test data

# Testing
make test            # Pack and validate orb
make test-scripts    # Run comprehensive calculate_version.sh tests
make test-all        # Run all tests (orb + scripts)

# Publishing (with full build cycle)
make publish-snapshot  # Publish as kingsrook/qqq-orb@dev:snapshot
make publish-release   # Publish as kingsrook/qqq-orb@X.Y.Z
```

### Quality Gates

All publishing commands enforce a complete quality gate:

1. **check-clean**: Ensures working directory is clean
2. **lint**: Runs all linting checks (YAML, ShellCheck, CircleCI orb validation)
3. **clean**: Removes all generated files for fresh build
4. **dev**: Development workflow (pack + validate)
5. **test-all**: Comprehensive testing (orb + scripts)

## 📋 Intelligent Version Management

Automated version calculation with GitFlow integration and feature branch support:

| Branch Pattern | Version Change | Example |
|----------------|----------------|---------|
| `develop` | Minor bump | `1.5.0-SNAPSHOT` → `1.6.0-SNAPSHOT` |
| `release/1.5` | RC versions | `1.5.0-RC.1`, `1.5.0-RC.2`, ... |
| `main` | Stable release | `1.5.0-RC.3` → `1.5.0` **requires v* tag** |
| `hotfix/1.5.1` | Patch bump | `1.5.0` → `1.5.1` |
| `feature/new-feature` | Feature-specific | `1.5.0-SNAPSHOT` → `1.5.0-NEW-abc1234-SNAPSHOT` |

### Feature Branch Versioning

Feature branches create unique, traceable versions:
- **Format**: `{version}-{feature_branch_name}-{commit_hash}-SNAPSHOT`
- **Example**: `feature/new-feature` → `1.5.0-new-feature-abc1234-SNAPSHOT`
- **Dynamic Updates**: Automatically updates when commit hash changes
- **Safe Abbreviations**: 3-character uppercase feature name abbreviation

### Version Parsing Support

The version calculator handles multiple formats:
- **Standard**: `1.5.0`, `1.5.0-SNAPSHOT`, `1.5.0-RC.1`
- **V-prefixed**: `v1.5.0` → `1.5.0` (clean conversion)
- **Feature-specific**: `1.5.0-new-feature-name-abc1234-SNAPSHOT`

**Main branch requires release tags**: 
```bash
git tag -a v1.5.0 -m "Release 1.5.0"
git push origin v1.5.0
```

## 🧪 Comprehensive Testing

### Test Suite Features

- **Dynamic Test Environment**: Creates isolated git repositories for each test run
- **Pattern Matching**: Supports wildcard patterns for commit hash testing
- **Comprehensive Coverage**: Tests all branch types and edge cases
- **CI Integration**: Clean exit codes and minimal output for CI systems
- **Automatic Cleanup**: Test data removed automatically after tests

### Running Tests

```bash
# Run all tests
make test-all

# Run specific test suites
make test            # Orb tests only
make test-scripts    # Script tests only

# Run with verbose output
./tests/run_tests.sh --verbose

# Run in CI mode
./tests/run_tests.sh --ci

# Run linting checks
make lint
```

### Test Coverage

The orb includes comprehensive testing:
- **YAML Validation**: CircleCI orb configuration validation
- **Shell Script Testing**: ShellCheck for shell script validation
- **Orb Packing**: Tests orb packing and resolution
- **Version Calculation**: 20+ test cases covering all branch types
- **Integration Testing**: End-to-end workflow testing
- **Edge Case Testing**: Invalid formats, missing tags, error conditions

## 📦 Usage Examples

### Maven Project (Backend Only)

```yaml
jobs:
  - qqq-orb/publish:
      context: qqq-maven-registry-credentials
      branch_type: snapshot
```

### Node.js Project (Frontend Only)

```yaml
jobs:
  - qqq-orb/publish:
      context: qqq-maven-registry-credentials
      branch_type: release
```

### Hybrid Project (Maven + Node.js)

```yaml
jobs:
  - qqq-orb/publish:
      context: qqq-maven-registry-credentials
      branch_type: release_candidate
```

## 🤝 Contributing

**Important**: This repository is a component of the QQQ framework. All contributions, issues, and discussions should go through the main QQQ repository.

### Development Workflow

1. **Fork the main QQQ repository**: https://github.com/Kingsrook/qqq
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes** (including orb changes if applicable)
4. **Run tests**: `make test-all`
5. **Run linting**: `make lint`
6. **Commit your changes**: `git commit -m 'Add amazing feature'`
7. **Push to the branch**: `git push origin feature/amazing-feature`
8. **Open a Pull Request** to the main QQQ repository

### Code Standards

- **YAML**: Follow CircleCI orb best practices
- **Shell Scripts**: Use ShellCheck for validation, comprehensive testing
- **Documentation**: Update README and inline documentation
- **Testing**: Comprehensive test coverage with dynamic test environments
- **Quality Gates**: All changes must pass linting and testing

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

```
QQQ Orb
Copyright (C) 2021-2024 Kingsrook, LLC
651 N Broad St Ste 205 # 6917 | Middletown DE 19709 | United States
contact@kingsrook.com | https://github.com/Kingsrook/
```

## 🆘 Support & Community

### ⚠️ Important: Use Main QQQ Repository

**All support, issues, discussions, and community interactions should go through the main QQQ repository:**

- **Main Repository**: https://github.com/Kingsrook/qqq
- **Issues**: https://github.com/Kingsrook/qqq/issues
- **Discussions**: https://github.com/Kingsrook/qqq/discussions
- **Wiki**: https://github.com/Kingsrook/qqq/wiki

### Why This Repository Exists

This repository is maintained separately from the main QQQ repository to:
- **Enable independent orb development** and versioning
- **Allow orb-specific CI/CD** and deployment pipelines
- **Provide clear separation** between orb and framework concerns
- **Support different release cycles** for CI/CD tools vs. core framework

### Getting Help

- **Documentation**: Check the [QQQ Wiki](https://github.com/Kingsrook/qqq/wiki)
- **Issues**: Report bugs and feature requests on [Main QQQ Issues](https://github.com/Kingsrook/qqq/issues)
- **Discussions**: Join community discussions on [Main QQQ Discussions](https://github.com/Kingsrook/qqq/discussions)
- **Questions**: Ask questions in the main QQQ repository

### Contact Information

- **Company**: Kingsrook, LLC
- **Email**: contact@kingsrook.com
- **Website**: https://qrun.io
- **Main GitHub**: https://github.com/Kingsrook/qqq
- **CircleCI Registry**: [kingsrook/qqq-orb](https://circleci.com/developer/orbs/orb/kingsrook/qqq-orb)

## 🙏 Acknowledgments

- **CircleCI Team**: For the excellent CI/CD platform and orb system
- **Maven Team**: For the powerful Java build system
- **npm Team**: For the Node.js package management system
- **QQQ Framework Team**: For the underlying low-code platform
- **Open Source Community**: For the tools and libraries that make this possible

---

**Built with ❤️ by the Kingsrook Team**

**This is a CI/CD component of the QQQ framework. For complete information, support, and community, visit: https://github.com/Kingsrook/qqq**
