# QQQ Orb

A comprehensive CircleCI orb for Maven-based projects using GitFlow branching strategy. This orb provides automated building, testing, version management, and releasing capabilities for Java projects.

## Overview

The QQQ Orb is designed to handle the complete CI/CD lifecycle for Maven-based projects within the Kingsrook/QRunIO ecosystem. It supports GitFlow branching strategy with automated version management, comprehensive testing, and artifact publishing to Maven Central.

## Features

- **Automated Version Management**: Intelligent version calculation based on branch type and GitFlow conventions
- **Maven Build & Test**: Optimized Maven builds with parallel execution and comprehensive testing
- **API Version Validation**: Ensures API compatibility across middleware components
- **Artifact Publishing**: Automated deployment to Maven Central with GPG signing
- **GitHub Release Management**: Automated Git tagging and GitHub release creation
- **Documentation Generation**: AsciiDoc to HTML documentation processing
- **Browser Testing Support**: Chrome/ChromeDriver installation for web testing

## Repository Structure

```
src/
├── @orb.yml                    # Main orb definition file
├── commands/                   # Reusable commands
│   ├── check_middleware_api_versions.yml
│   ├── create_github_release.yml
│   ├── install_asciidoctor.yml
│   ├── manage_version.yml
│   ├── mvn_build.yml
│   ├── mvn_jar_deploy.yml
│   ├── mvn_verify.yml
│   └── run_asciidoctor.yml
├── executors/                  # Execution environments
│   └── default.yml
├── jobs/                       # Complete workflow jobs
│   ├── api_version_check.yml
│   ├── build.yml
│   ├── mvn_deploy.yml
│   ├── publish_asciidoc.yml
│   ├── publish_hotfix.yml
│   ├── publish_rc.yml
│   ├── publish_release.yml
│   └── test.yml
├── scripts/                    # Shell scripts (inlined via <<include()>>)
│   ├── calculate_version.sh
│   ├── check_middleware_api_versions.sh
│   ├── collect_jacoco_reports.sh
│   ├── concatenate_test_output.sh
│   ├── create_github_release.sh
│   ├── manage_version_commit.sh
│   ├── manage_version_git_config.sh
│   ├── mvn_build_compile.sh
│   ├── mvn_jar_deploy_deploy.sh
│   ├── mvn_jar_deploy_gpg_setup.sh
│   ├── mvn_verify_save_test_results.sh
│   ├── mvn_verify_verify.sh
│   └── setup_maven_settings.sh
└── examples/                   # Usage examples
    └── build.yml
```

## Design Principles

### 1. Modular Architecture
- **Commands**: Reusable, single-purpose operations
- **Jobs**: Complete workflow definitions combining multiple commands
- **Scripts**: Shell scripts inlined via `<<include()>>` for maintainability

### 2. GitFlow Integration
- **develop**: SNAPSHOT versions (X.Y.Z-SNAPSHOT)
- **release/**: Release candidates (X.Y.0-RC.n)
- **main**: Production releases (X.Y.Z)
- **hotfix/**: Hotfix releases (X.Y.(Z+1))

### 3. Best Practices Compliance
- Follows CircleCI orb best practices (RC002, RC009, etc.)
- Uses `<<include()>>` for complex commands to avoid RC009 violations
- Comprehensive descriptions for all components
- Proper error handling and cleanup

## Development Workflow

### Prerequisites
- CircleCI CLI installed and authenticated
- Access to `kingsrook` namespace
- ShellCheck and yamllint for local development

### Local Development

1. **Install Dependencies**:
   ```bash
   # Install CircleCI CLI
   curl -fLSs https://raw.githubusercontent.com/CircleCI-Public/circleci-cli/main/install.sh | sudo bash
   
   # Install linting tools
   brew install shellcheck yamllint  # macOS
   # or
   sudo apt-get install shellcheck yamllint  # Ubuntu
   ```

2. **Development Commands**:
   ```bash
   # Pack the orb (resolves <<include()>> directives)
   make pack
   
   # Validate the packed orb
   make validate
   
   # Run all linting checks
   make lint
   
   # Clean build artifacts
   make clean
   
   # Development workflow (pack + validate)
   make dev
   ```

3. **Testing**:
   ```bash
   # Test with a sample configuration
   make test
   ```

### Publishing

1. **Development Version** (for testing):
   ```bash
   make publish-dev
   # Publishes as kingsrook/qqq-orb@dev:alpha
   ```

2. **Production Version**:
   ```bash
   # Update version in src/@orb.yml
   make publish
   # Publishes as kingsrook/qqq-orb@X.Y.Z
   ```

## Using the Orb in Your Repository

### 1. Basic Setup

Create `.circleci/config.yml` in your repository:

```yaml
version: 2.1

orbs:
  qqq-orb: kingsrook/qqq-orb@2.1

workflows:
  # Feature branch testing
  test_only:
    filters:
      branches:
        ignore:
          - develop
          - main
          - /release\/.*/
          - /hotfix\/.*/
    jobs:
      - qqq-orb/build:
          context: qqq-maven-registry-credentials
      - qqq-orb/test:
          context: qqq-maven-registry-credentials
          requires:
            - qqq-orb/build

  # Develop branch - publish snapshots
  publish_snapshot:
    filters:
      branches:
        only: develop
    jobs:
      - qqq-orb/publish_snapshot:
          context: qqq-maven-registry-credentials

  # Release branches - publish release candidates
  publish_release_candidate:
    filters:
      branches:
        only: /release\/.*/
    jobs:
      - qqq-orb/publish_release_candidate:
          context: qqq-maven-registry-credentials

  # Main branch - publish production releases
  production_release:
    filters:
      branches:
        only: main
    jobs:
      - qqq-orb/publish_release:
          context: qqq-maven-registry-credentials

  # Hotfix branches - publish hotfix releases
  hotfix_release:
    filters:
      branches:
        only: /hotfix\/.*/
    jobs:
      - qqq-orb/publish_hotfix_release:
          context: qqq-maven-registry-credentials
```

### 2. Required Context Variables

Set up the following context in CircleCI:

- `qqq-maven-registry-credentials`:
  - `MAVEN_USERNAME`: Sonatype username
  - `MAVEN_PASSWORD`: Sonatype password
  - `GPG_PRIVATE_KEY_B64`: Base64-encoded GPG private key
  - `GPG_KEYNAME`: GPG key name
  - `GPG_PASSPHRASE`: GPG passphrase
  - `GITHUB_TOKEN`: GitHub personal access token
  - `RDBMS_PASSWORD`: Database password for testing

### 3. Project Requirements

Your Maven project should have:

- `pom.xml` with `<revision>` property for version management
- `.circleci/mvn-settings.xml` (or the orb will create one dynamically)
- `docs/index.adoc` for documentation generation (optional)

### 4. Available Jobs

| Job | Purpose | Branch | Output |
|-----|---------|--------|--------|
| `build` | Compile project | Any | Compiled artifacts |
| `test` | Run tests + reports | Any | Test results, JaCoCo reports |
| `api_version_check` | Validate API versions | Any | API compatibility report |
| `publish_snapshot` | Deploy snapshots | develop | X.Y.Z-SNAPSHOT to snapshots |
| `publish_release_candidate` | Deploy RC | release/* | X.Y.0-RC.n to releases |
| `publish_release` | Deploy production | main | X.Y.Z to releases + GitHub release |
| `publish_hotfix_release` | Deploy hotfix | hotfix/* | X.Y.(Z+1) to releases + GitHub release |

### 5. Available Commands

| Command | Purpose |
|---------|--------|
| `mvn_build` | Compile Maven project with caching |
| `mvn_verify` | Run tests and collect reports |
| `mvn_jar_deploy` | Deploy to Maven Central |
| `manage_version` | Calculate and set version |
| `check_middleware_api_versions` | Validate API compatibility |
| `create_github_release` | Create Git tag and GitHub release |
| `publish_asciidoc` | Generate HTML documentation |

## Version Management

The orb automatically manages versions based on GitFlow:

- **develop**: Increments minor version (1.5.0-SNAPSHOT → 1.6.0-SNAPSHOT)
- **release/1.5**: Creates RC versions (1.5.0-RC.1, 1.5.0-RC.2, etc.)
- **main**: Converts RC to stable (1.5.0-RC.3 → 1.5.0)
- **hotfix/1.5.1**: Increments patch (1.5.0 → 1.5.1)

## Troubleshooting

### Common Issues

1. **Orb not found**: Ensure you're using the correct namespace and version
2. **Authentication errors**: Verify context variables are set correctly
3. **Version conflicts**: Check that your `pom.xml` uses `<revision>` property
4. **Script not found**: Ensure `<<include()>>` directives are properly resolved

### Debugging

1. **Local validation**:
   ```bash
   make lint  # Check for issues
   make dev   # Pack and validate
   ```

2. **CircleCI debugging**: Check the "Debug" tab in failed jobs for detailed logs

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes following the existing patterns
4. Test with `make lint` and `make dev`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues and questions:
- Create an issue in this repository
- Check the [CircleCI Orb Registry](https://circleci.com/developer/orbs/orb/kingsrook/qqq-orb)
- Review the [CircleCI Orb Documentation](https://circleci.com/docs/2.0/orb-intro/)