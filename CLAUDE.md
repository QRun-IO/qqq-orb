# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CircleCI orb for QQQ framework projects. Provides pre-built jobs for building, testing, and publishing Maven and Node.js projects using GitFlow branching strategy.

## Build Commands

```bash
make pack              # Pack orb to target/qqq-orb-packed.yml
make validate          # Pack and validate orb
make test              # Pack and validate (alias for validate)
make test-scripts      # Run calculate_version.sh test suite
make test-all          # Run all tests (orb + scripts)
make lint              # Run yamllint, shellcheck, and CircleCI validation
make dev               # Development workflow: pack, validate, show status
make clean             # Remove target/ and tests/test_data/
make publish-snapshot  # Publish to kingsrook/qqq-orb@dev:snapshot
make publish-release   # Interactive production release with git tagging
```

## Running Individual Tests

```bash
./tests/run_tests.sh              # Standard test run
./tests/run_tests.sh --verbose    # Verbose output
./tests/run_tests.sh --ci         # CI mode (minimal output)
./tests/test_calculate_version.sh # Direct test suite execution
```

## Architecture

### Directory Structure

- `src/@orb.yml` - Main orb definition entry point
- `src/commands/` - Reusable orb commands (YAML files that include scripts)
- `src/jobs/` - Complete job definitions combining commands
- `src/executors/` - Docker executor definitions (java.yml, default.yml)
- `src/scripts/` - Bash scripts included in commands
- `tests/` - Test suite for calculate_version.sh

### Key Components

**Executors:**
- `java` - cimg/openjdk image with configurable version (17.0, 21.0), resource_class: large
- `default` - cimg/node image for Node.js projects

**Jobs:**
- `mvn_publish` - Full publish workflow (build, version, test, deploy, git ops, GitHub release)
- `mvn_test_only` - Build and test for feature branches
- `mvn_frontend_publish` / `mvn_frontend_test_only` - Same with frontend support
- `node_publish` / `node_test_only` - Pure Node.js workflows

**Version Calculation:**
The core logic is in `src/scripts/calculate_version.sh`. It determines version based on branch type:
- `develop` -> `X.Y.Z-SNAPSHOT`
- `release/*` -> `X.Y.Z-RC.N`
- `main` (tagged) -> `X.Y.Z`
- `hotfix/*` -> Patch version bump
- `feature/*` -> `X.Y.Z-feature-{name}-{hash}-SNAPSHOT`

### Orb Packing

The orb uses CircleCI's "unpacked" format. YAML files in `src/` are packed into a single `target/qqq-orb-packed.yml`. Commands reference scripts via `<<include(scripts/scriptname.sh)>>` syntax.

### CI Pipeline

`.circleci/config.yml` runs lint/pack/review/shellcheck, then continues to `.circleci/test-deploy.yml` which runs command tests and publishes on release tags (`v*.*.*`).

## Linting Requirements

- YAML: yamllint for commands/jobs/examples
- Shell: shellcheck for all .sh files in src/scripts/ and tests/
- Orb: `circleci orb validate` for orb syntax

## Required Context Variables for Publishing

- `MAVEN_USERNAME`, `MAVEN_PASSWORD` - Sonatype credentials
- `GPG_PRIVATE_KEY_B64`, `GPG_KEYNAME`, `GPG_PASSPHRASE` - GPG signing
- `GITHUB_TOKEN` - GitHub API access
