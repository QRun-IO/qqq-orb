# Changelog

All notable changes to QQQ Orb will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Support for publishing snapshots for feature branches
- Comprehensive README with detailed usage examples
- CONTRIBUTING.md with development guidelines
- SECURITY.md with security policy and reporting procedures
- CHANGELOG.md for tracking changes

### Changed
- Updated README to follow QQQ framework standards
- Enhanced documentation structure and organization

## [0.3.7] - 2025-09-18

### Added
- Comprehensive README with current functionality and testing framework documentation

### Changed
- Enhanced documentation structure and organization

## [0.3.6] - 2025-09-16

### Fixed
- Updated handling for tagged releases in main branch to properly promote to latest tag
- Fixed git commit operations on main branch for production releases

## [0.3.5] - 2025-09-16

### Fixed
- Updated git commit on main branch to work correctly for tag releases in production releases

## [0.3.4] - 2025-09-15

### Fixed
- Removed conditionals around git operations after version checks for main and hotfix branches
- Updated standard GitHub documentation to point to top-level project documentation

## [0.3.3] - 2025-09-15

### Added
- Made publish_asciidoc a parameterized run option

### Changed
- Enhanced parameterization for better flexibility

## [0.3.2] - 2025-09-15

### Added
- Base level repository files and updated README

### Changed
- Updated check_middleware_api_versions to run based on parameter configuration

## [0.3.1] - 2025-09-15

### Fixed
- Version bump corrections
- Fixed bad sync RC update
- Updated example version references

## [0.3.0] - 2025-09-15

### Added
- Support for pure Node.js projects
- Support for building integrated frontend (npm) within Maven projects
- Support for publishing snapshots and tags
- Enhanced feature branch versioning with dynamic commit hash updates
- Comprehensive test suite and improved linting for calculate_version.sh

### Changed
- Reverted to only handle POM files (npm handled within its own job)
- Adjusted default execution state for scripts
- Converted longer commands to scripts per organization linting standards
- Refactored calculate_version.sh for cleaner branch level code

### Fixed
- Multiple linting fixes from CircleCI integration
- Improved error handling and validation

## [0.2.0] - 2025-09-15

### Added
- Initial CircleCI orb implementation
- Basic Maven project support
- Core CI/CD workflows
- Initial documentation for orb

### Changed
- Migrated from custom CI/CD to CircleCI orbs
- Updated CircleCI to use new QQQ orb for workflows

### Fixed
- Implemented initial linting fixes from CircleCI
- Initial import of scripts and jobs from QQQ base repository

---

**Note**: For detailed release information and breaking changes, see the [QQQ Wiki](https://github.com/Kingsrook/qqq/wiki).