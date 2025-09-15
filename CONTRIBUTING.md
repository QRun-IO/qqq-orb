# Contributing to QQQ Orb

First off, thanks for taking the time to contribute! ❤️

QQQ Orb is **open source** and welcomes contributions from the community. This document provides a quick overview - for detailed guides, see our [Complete Documentation Wiki](https://github.com/Kingsrook/qqq/wiki).

## 🚀 Quick Start

**New to QQQ?** Start with our [Developer Onboarding Guide](https://github.com/Kingsrook/qqq/wiki/Developer-Onboarding) to get your environment set up.

## 📚 Documentation & Guides

All detailed information is in our [Wiki](https://github.com/Kingsrook/qqq/wiki):

- **[🏠 Home](https://github.com/Kingsrook/qqq/wiki/Home)** - Project overview
- **[🔧 Development](https://github.com/Kingsrook/qqq/wiki/Developer-Onboarding)** - Complete setup guide
- **[📝 Contribution Process](https://github.com/Kingsrook/qqq/wiki/Contribution-Guidelines)** - Detailed contribution workflow
- **[🔍 Code Standards](https://github.com/Kingsrook/qqq/wiki/Code-Review-Standards)** - Coding standards and review process
- **[🧪 Testing](https://github.com/Kingsrook/qqq/wiki/Testing)** - Testing strategy and requirements
- **[🏗️ Architecture](https://github.com/Kingsrook/qqq/wiki/High-Level-Architecture)** - System design and principles

## 🤝 How to Contribute

### **1. Report Issues**
Found a bug or have a feature request? [Create an issue](https://github.com/Kingsrook/qqq/issues).

### **2. Code Contributions**
Want to contribute code? Follow our [Contribution Guidelines](https://github.com/Kingsrook/qqq/wiki/Contribution-Guidelines).

**Key Requirements:**
- CircleCI CLI and orb development tools
- Follow QQQ's [Code Review Standards](https://github.com/Kingsrook/qqq/wiki/Code-Review-Standards)
- Meet testing coverage requirements
- Use conventional commit messages
- Validate orb configuration with `make lint`

### **3. Documentation**
Improve our docs by updating the [Wiki](https://github.com/Kingsrook/qqq/wiki) or suggesting improvements via issues.

## 🔧 Development Setup

**Prerequisites:**
- **macOS** (QQQ dev tools are macOS-optimized)
- **CircleCI CLI** for orb development
- **ShellCheck** and **yamllint** for linting
- **Git** with SSH access

**Quick Setup:**
```bash
# Install CircleCI CLI
curl -fLSs https://raw.githubusercontent.com/CircleCI-Public/circleci-cli/main/install.sh | sudo bash

# Install linting tools (macOS)
brew install shellcheck yamllint

# Clone the repository
git clone git@github.com:Kingsrook/qqq.git
cd qqq/qqq-orb

# Run development workflow
make dev
```

For complete setup instructions, see [Developer Onboarding](https://github.com/Kingsrook/qqq/wiki/Developer-Onboarding).

## 📋 Contribution Checklist

Before submitting your contribution:

- [ ] **Environment**: Development environment properly set up
- [ ] **Code Style**: Follows QQQ's [Code Review Standards](https://github.com/Kingsrook/qqq/wiki/Code-Review-Standards)
- [ ] **Testing**: All tests pass with `make test`
- [ ] **Linting**: All linting checks pass with `make lint`
- [ ] **Documentation**: Updated relevant wiki pages
- [ ] **Commit Messages**: Follow conventional commit format
- [ ] **Orb Validation**: Orb packs and validates successfully

## 🧪 Testing

### Running Tests

```bash
# Run all tests
make test

# Run linting checks
make lint

# Validate orb configuration
make validate

# Development workflow
make dev
```

### Test Coverage

The orb includes comprehensive testing:
- **YAML Validation**: CircleCI orb configuration validation
- **Shell Script Testing**: ShellCheck for shell script validation
- **Orb Packing**: Tests orb packing and resolution
- **Integration Testing**: End-to-end workflow testing

## 📦 Publishing

### Development Publishing

```bash
# Publish snapshot for testing
make publish-snapshot
```

### Production Publishing

```bash
# Publish production release
make publish-release
```

## 🆘 Getting Help

- **📖 [Wiki](https://github.com/Kingsrook/qqq/wiki)**: Start here for comprehensive guides
- **🐛 [Issues](https://github.com/Kingsrook/qqq/issues)**: Search existing issues or create new ones
- **💬 [Discussions](https://github.com/Kingsrook/qqq/discussions)**: Ask questions and get help

## 📄 Legal Notice

When contributing to this project, you must agree that you have authored 100% of the content, that you have the necessary rights to the content, and that the content you contribute may be provided under the project license.

## 🏢 About Kingsrook

QQQ Orb is built by **[Kingsrook](https://qrun.io)** - making engineers more productive through intelligent automation and developer tools.

---

**Ready to contribute?** [Start with our Developer Onboarding Guide](https://github.com/Kingsrook/qqq/wiki/Developer-Onboarding)!