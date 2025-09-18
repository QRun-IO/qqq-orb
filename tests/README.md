# Calculate Version Script Test Suite

This directory contains comprehensive tests for the `calculate_version.sh` script.

## Test Files

- `test_calculate_version.sh` - Main test suite with comprehensive test cases
- `run_tests.sh` - Test runner with different output modes
- `README.md` - This documentation

## Running Tests

### Quick Test Run
```bash
./tests/run_tests.sh
```

### Verbose Test Run
```bash
./tests/run_tests.sh --verbose
```

### CI Mode (minimal output)
```bash
./tests/run_tests.sh --ci
```

### Direct Test Suite
```bash
./tests/test_calculate_version.sh
./tests/test_calculate_version.sh --verbose
```

## Test Coverage

The test suite covers:

### Branch Types
- **Main Branch**: Tests stable version handling, tag detection, RC conversion
- **Develop Branch**: Tests SNAPSHOT version management, release detection
- **Release Branch**: Tests RC version creation and incrementing
- **Hotfix Branch**: Tests patch version bumping
- **Feature Branch**: Tests version inheritance

### Edge Cases
- Invalid branch formats
- Unknown branch types
- Missing tags on main branch
- Various version formats (stable, SNAPSHOT, RC)

### Version Parsing
- Standard versions: `1.0.0`
- SNAPSHOT versions: `1.0.0-SNAPSHOT`
- RC versions: `1.0.0-RC.1`, `1.0.0-RC.10`
- Multi-digit versions: `10.20.30`

## Test Environment

The test suite:
1. Creates a temporary test directory
2. Initializes a test git repository
3. Creates test pom.xml files with different versions
4. Creates test branches and tags
5. Runs the calculate_version.sh script
6. Validates the output
7. Cleans up test data

## Integration with Make

The tests are integrated into the Makefile and can be run with:
```bash
make test-scripts
```

## Test Results

The test suite provides:
- ✅ Pass/fail status for each test
- 📊 Summary statistics
- 🔍 Detailed output in verbose mode
- 🚫 Clean exit codes for CI integration

## Adding New Tests

To add new test cases:

1. Add a new test function in `test_calculate_version.sh`
2. Call `run_test` with appropriate parameters:
   ```bash
   run_test "Test Name" "branch_name" "current_version" "expected_version" "tag_name"
   ```
3. Add the test function to the main execution flow
4. Update this README if needed

## Troubleshooting

### Common Issues

1. **Permission denied**: Make sure test scripts are executable
   ```bash
   chmod +x tests/*.sh
   ```

2. **Git not found**: Ensure git is installed and available in PATH

3. **Test failures**: Run with `--verbose` to see detailed output
   ```bash
   ./tests/run_tests.sh --verbose
   ```

### Debug Mode

For debugging, you can run individual test functions by modifying the main function in `test_calculate_version.sh` to call only specific test functions.
