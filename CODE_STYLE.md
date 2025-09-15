# Code Style Guide

This document outlines the coding standards and style guidelines for QQQ Orb development.

## 🎯 Overview

QQQ Orb follows consistent coding standards to ensure maintainability, readability, and reliability across all components.

## 📁 File Organization

### Directory Structure

```
src/
├── @orb.yml              # Main orb definition
├── commands/             # Reusable commands
├── jobs/                 # Complete workflow jobs
├── scripts/              # Shell scripts
├── executors/            # Execution environments
└── examples/             # Usage examples
```

### Naming Conventions

- **Files**: Use lowercase with underscores (`mvn_build.yml`)
- **Directories**: Use lowercase with underscores (`commands/`)
- **Variables**: Use uppercase with underscores (`MAVEN_USERNAME`)
- **Functions**: Use lowercase with underscores (`calculate_version`)

## 🔧 YAML Configuration

### General Guidelines

- **Indentation**: Use 2 spaces (no tabs)
- **Line Length**: Maximum 120 characters
- **Quotes**: Use single quotes for strings when possible
- **Comments**: Use `#` for comments, explain complex logic

### Orb Definition Structure

```yaml
# @orb.yml
version: 2.1

description: >
  Brief description of the orb's purpose.

display:
  home_url: "https://www.qrun.io"
  source_url: "https://github.com/Kingsrook/qqq-orb"

orbs:
  dependency-orb: circleci/dependency@1.0.0
```

### Command Structure

```yaml
# commands/example_command.yml
description: "Brief description of what this command does"

parameters:
  param1:
    type: string
    default: "default_value"
    description: "Parameter description"

steps:
  - run:
      name: "Step Name"
      command: |
        echo "Command content"
        # Additional commands
```

### Job Structure

```yaml
# jobs/example_job.yml
description: "Brief description of what this job does"

executor: default

parameters:
  param1:
    type: string
    default: "default_value"
    description: "Parameter description"

steps:
  - checkout
  - qqq-orb/example-command:
      param1: << parameters.param1 >>
```

## 🐚 Shell Scripts

### General Guidelines

- **Shebang**: Always use `#!/bin/bash`
- **Error Handling**: Use `set -euo pipefail`
- **Variables**: Use `readonly` for constants
- **Functions**: Use descriptive names and document parameters

### Script Template

```bash
#!/bin/bash
set -euo pipefail

# Script description
# Usage: script_name [options] [arguments]

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_NAME="$(basename "$0")"

# Function documentation
# Parameters: $1 - description, $2 - description
function example_function() {
    local param1="$1"
    local param2="$2"
    
    # Function implementation
    echo "Processing: $param1, $param2"
}

# Main execution
main() {
    # Main logic here
    example_function "value1" "value2"
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
```

### Error Handling

```bash
# Check if command exists
if ! command -v mvn &> /dev/null; then
    echo "Error: Maven is not installed" >&2
    exit 1
fi

# Check if file exists
if [[ ! -f "pom.xml" ]]; then
    echo "Error: pom.xml not found" >&2
    exit 1
fi

# Handle command failures
if ! mvn clean compile; then
    echo "Error: Maven compilation failed" >&2
    exit 1
fi
```

## 📝 Documentation

### README Structure

- **Title**: Clear, descriptive title
- **Badges**: Status badges for version, license, etc.
- **Overview**: Brief description of purpose
- **Quick Start**: Getting started instructions
- **Usage**: Detailed usage examples
- **Development**: Development setup and guidelines
- **Contributing**: Contribution guidelines
- **License**: License information

### Inline Documentation

```yaml
# commands/mvn_build.yml
description: >
  Builds a Maven project with specified goals.
  Supports multi-module projects and custom settings.

parameters:
  goals:
    type: string
    default: "clean compile"
    description: >
      Maven goals to execute.
      Common values: clean, compile, test, package, install
```

### Shell Script Documentation

```bash
#!/bin/bash
# Script: calculate_version.sh
# Description: Calculates semantic version based on GitFlow branch
# Usage: calculate_version.sh [branch_name]
# Parameters:
#   branch_name - Git branch name (optional, defaults to current branch)
# Returns: Semantic version string
```

## 🧪 Testing Standards

### Test Structure

- **Unit Tests**: Test individual functions and commands
- **Integration Tests**: Test complete workflows
- **Validation Tests**: Test orb configuration and packing

### Test Naming

- **Test Files**: `test_<component>.yml`
- **Test Functions**: `test_<function_name>`
- **Test Descriptions**: Clear, descriptive test names

### Coverage Requirements

- **Commands**: All parameters and error conditions
- **Jobs**: All workflow paths and error handling
- **Scripts**: All functions and error conditions

## 🔍 Code Review Standards

### Review Checklist

- [ ] **Functionality**: Code works as intended
- [ ] **Style**: Follows project style guidelines
- [ ] **Documentation**: Adequate documentation and comments
- [ ] **Testing**: Appropriate test coverage
- [ ] **Security**: No security vulnerabilities
- [ ] **Performance**: Efficient implementation
- [ ] **Maintainability**: Code is maintainable and readable

### Review Process

1. **Self Review**: Author reviews their own code first
2. **Peer Review**: At least one peer review required
3. **Testing**: All tests must pass
4. **Documentation**: Documentation updated as needed
5. **Approval**: Required approvals before merge

## 🛠️ Development Tools

### Required Tools

- **CircleCI CLI**: For orb development and validation
- **ShellCheck**: For shell script linting
- **yamllint**: For YAML linting
- **Git**: For version control

### IDE Configuration

#### VS Code

```json
{
  "editor.tabSize": 2,
  "editor.insertSpaces": true,
  "editor.rulers": [120],
  "files.trimTrailingWhitespace": true,
  "files.insertFinalNewline": true,
  "yaml.schemas": {
    "https://json.schemastore.org/circle-ci-config.json": ".circleci/config.yml"
  }
}
```

#### IntelliJ IDEA

- **Code Style**: Use project code style settings
- **File Templates**: Use project file templates
- **Inspections**: Enable all relevant inspections

## 📋 Best Practices

### General Principles

- **DRY**: Don't Repeat Yourself
- **KISS**: Keep It Simple, Stupid
- **YAGNI**: You Aren't Gonna Need It
- **SOLID**: Follow SOLID principles where applicable

### Security Considerations

- **Secrets**: Never commit secrets or credentials
- **Input Validation**: Validate all inputs
- **Error Handling**: Don't expose sensitive information in errors
- **Dependencies**: Keep dependencies up to date

### Performance Considerations

- **Efficiency**: Use efficient algorithms and data structures
- **Caching**: Cache expensive operations when appropriate
- **Parallelization**: Use parallel execution where beneficial
- **Resource Usage**: Minimize resource consumption

## 🔗 Resources

- **CircleCI Orb Development**: https://circleci.com/docs/2.0/orb-author-intro/
- **Shell Script Best Practices**: https://google.github.io/styleguide/shellguide.html
- **YAML Best Practices**: https://yaml.org/spec/1.2/spec.html
- **GitFlow Workflow**: https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow

---

**Remember**: Consistent code style improves maintainability and reduces bugs. When in doubt, follow existing patterns in the codebase.