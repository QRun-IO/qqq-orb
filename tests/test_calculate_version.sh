#!/bin/bash

############################################################################
## test_calculate_version.sh
## Comprehensive test suite for calculate_version.sh script
## 
## This test suite validates all branch types and edge cases for the
## version calculation script.
##
## Usage: ./test_calculate_version.sh [--verbose]
############################################################################

set -e

###################
## Configuration ##
###################
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CALCULATE_VERSION_SCRIPT="$PROJECT_ROOT/src/scripts/calculate_version.sh"
TEST_DIR="$PROJECT_ROOT/tests/test_data"
VERBOSE=false

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

##################################
## Parse command line arguments ##
##################################
if [[ "$1" == "--verbose" ]]; then
    VERBOSE=true
fi

####################################
## Test Framework Functions       ##
####################################

# Create a temporary directory for test data
setup_test_environment() {
    echo "Setting up test environment..."
    
    # Remove existing test directory if it exists
    if [[ -d "$TEST_DIR" ]]; then
        rm -rf "$TEST_DIR"
    fi
    
    # Create fresh test directory
    mkdir -p "$TEST_DIR"
    
    # Create a test git repository
    cd "$TEST_DIR"
    git init --quiet
    git config user.name "Test User"
    git config user.email "test@example.com"
    
    echo "✅ Test environment ready"
}

# Clean up test environment
cleanup_test_environment() {
    echo "Cleaning up test environment..."
    cd "$PROJECT_ROOT"
    rm -rf "$TEST_DIR"
    echo "✅ Cleanup complete"
}

# Create a test pom.xml file
create_test_pom() {
    local version="$1"
    cat > "$TEST_DIR/pom.xml" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    
    <groupId>com.example</groupId>
    <artifactId>test-project</artifactId>
    <version>1.0.0</version>
    
    <properties>
        <revision>$version</revision>
    </properties>
</project>
EOF
}

# Create a test branch
create_test_branch() {
    local branch_name="$1"
    local tag_name="$2"
    
    cd "$TEST_DIR"
    
    # Create and checkout branch
    git checkout -b "$branch_name" 2>/dev/null || git checkout "$branch_name" 2>/dev/null || true
    
    # Create a commit if needed
    if [[ -z "$(git log --oneline 2>/dev/null)" ]]; then
        echo "Initial commit" > README.md
        git add README.md
        git commit -m "Initial commit" --quiet
    fi
    
    # Create tag if specified
    if [[ -n "$tag_name" ]]; then
        git tag -a "$tag_name" -m "Test tag $tag_name" 2>/dev/null || true
    fi
}

# Run a test case
run_test() {
    local test_name="$1"
    local branch_name="$2"
    local current_version="$3"
    local expected_version="$4"
    local tag_name="$5"
    
    TESTS_RUN=$((TESTS_RUN + 1))
    
    echo "🧪 Test: $test_name"
    
    # Setup test case
    create_test_pom "$current_version"
    create_test_branch "$branch_name" "$tag_name"
    
    # Run the script
    cd "$TEST_DIR"
    local output
    local exit_code=0
    
    if [[ "$VERBOSE" == "true" ]]; then
        echo "  Running: POM_FILE=pom.xml $CALCULATE_VERSION_SCRIPT --dry-run"
    fi
    
    output=$(cd "$TEST_DIR" && POM_FILE=pom.xml "$CALCULATE_VERSION_SCRIPT" --dry-run 2>&1) || exit_code=$?
    
    # Check if script ran successfully
    if [[ $exit_code -ne 0 ]]; then
        echo "  ❌ FAILED: Script exited with code $exit_code"
        echo "  Output: $output"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
    
    # Extract the calculated version from output
    local calculated_version
    calculated_version=$(echo "$output" | grep "Calculated next version:" | sed 's/.*: //')
    
    # Check if expected version contains wildcard pattern
    if [[ "$expected_version" == *"*"* ]]; then
        # Convert wildcard pattern to regex
        local regex_pattern
        # shellcheck disable=SC2001
        regex_pattern=$(echo "$expected_version" | sed 's/\*/[a-f0-9]{7}/g')
        
        if [[ "$calculated_version" =~ ^$regex_pattern$ ]]; then
            echo "  ✅ PASSED: Expected pattern $expected_version, got $calculated_version"
            TESTS_PASSED=$((TESTS_PASSED + 1))
            return 0
        else
            echo "  ❌ FAILED: Expected pattern $expected_version, got $calculated_version"
            if [[ "$VERBOSE" == "true" ]]; then
                echo "  Full output:"
                # Add indentation to each line
                while IFS= read -r line; do
                    echo "    $line"
                done <<< "$output"
            fi
            TESTS_FAILED=$((TESTS_FAILED + 1))
            return 1
        fi
    else
        # Exact match
        if [[ "$calculated_version" == "$expected_version" ]]; then
            echo "  ✅ PASSED: Expected $expected_version, got $calculated_version"
            TESTS_PASSED=$((TESTS_PASSED + 1))
            return 0
        else
            echo "  ❌ FAILED: Expected $expected_version, got $calculated_version"
            if [[ "$VERBOSE" == "true" ]]; then
                echo "  Full output:"
                # Add indentation to each line
                while IFS= read -r line; do
                    echo "    $line"
                done <<< "$output"
            fi
            TESTS_FAILED=$((TESTS_FAILED + 1))
            return 1
        fi
    fi
}

# Print test summary
print_summary() {
    echo ""
    echo "=== Test Summary ==="
    echo "Tests run: $TESTS_RUN"
    echo "Tests passed: $TESTS_PASSED"
    echo "Tests failed: $TESTS_FAILED"
    
    if [[ $TESTS_FAILED -eq 0 ]]; then
        echo "🎉 All tests passed!"
        return 0
    else
        echo "❌ Some tests failed!"
        return 1
    fi
}

####################################
## Test Cases                     ##
####################################

# Test main branch scenarios
test_main_branch() {
    echo ""
    echo "=== Testing MAIN Branch ==="
    
    # Test 1: Main branch with matching tag
    run_test "Main branch with matching tag" "main" "1.5.0" "1.5.0" "v1.5.0"
    
    # Test 2: Main branch with RC version and tag
    run_test "Main branch with RC version" "main" "1.5.0-RC.1" "1.5.0" "v1.5.0"
    
    # Test 3: Main branch with SNAPSHOT version and tag
    run_test "Main branch with SNAPSHOT version" "main" "1.5.0-SNAPSHOT" "1.5.0" "v1.5.0"
    
    # Test 4: Main branch on tag (HEAD state)
    run_test "Main branch on tag (HEAD)" "HEAD" "1.5.0" "1.5.0" "v1.5.0"
    
    # Test 5: Main branch with v-prefixed version in pom.xml
    run_test "Main branch with v-prefixed version" "main" "v0.2.1" "0.2.1" "v0.2.1"
}

# Test develop branch scenarios
test_develop_branch() {
    echo ""
    echo "=== Testing DEVELOP Branch ==="
    
    # Test 1: Develop branch with SNAPSHOT version (no recent activity)
    run_test "Develop branch - no recent activity" "develop" "1.5.0-SNAPSHOT" "1.5.0-SNAPSHOT" ""
    
    # Test 2: Develop branch with RC version (should bump)
    run_test "Develop branch with RC version" "develop" "1.5.0-RC.1" "1.6.0-SNAPSHOT" ""
    
    # Test 3: Develop branch with stable version (should bump)
    run_test "Develop branch with stable version" "develop" "1.5.0" "1.6.0-SNAPSHOT" ""
}

# Test release branch scenarios
test_release_branch() {
    echo ""
    echo "=== Testing RELEASE Branch ==="
    
    # Test 1: Release branch - first RC
    run_test "Release branch - first RC" "release/1.5" "1.5.0-SNAPSHOT" "1.5.0-RC.1" ""
    
    # Test 2: Release branch - increment RC
    run_test "Release branch - increment RC" "release/1.5" "1.5.0-RC.1" "1.5.0-RC.2" ""
    
    # Test 3: Release branch - increment RC from RC.5
    run_test "Release branch - increment RC.5" "release/1.5" "1.5.0-RC.5" "1.5.0-RC.6" ""
}

# Test hotfix branch scenarios
test_hotfix_branch() {
    echo ""
    echo "=== Testing HOTFIX Branch ==="
    
    # Test 1: Hotfix branch - bump patch
    run_test "Hotfix branch - bump patch" "hotfix/fix-bug" "1.5.0" "1.5.1" ""
    
    # Test 2: Hotfix branch - bump patch from RC
    run_test "Hotfix branch - bump patch from RC" "hotfix/fix-bug" "1.5.0-RC.1" "1.5.1" ""
}

# Test feature branch scenarios
test_feature_branch() {
    echo ""
    echo "=== Testing FEATURE Branch ==="
    
    # Test 1: Feature branch - convert SNAPSHOT to feature-specific version
    run_test "Feature branch - convert SNAPSHOT to feature-specific version" "feature/new-feature" "1.5.0-SNAPSHOT" "1.5.0-NEW-*-SNAPSHOT" ""
    
    # Test 2: Feature branch - convert stable version to feature-specific SNAPSHOT
    run_test "Feature branch - convert stable version to feature-specific SNAPSHOT" "feature/user-auth" "1.5.0" "1.5.0-USE-*-SNAPSHOT" ""
    
    # Test 3: Feature branch - update existing feature-specific version with new commit hash
    run_test "Feature branch - update existing feature-specific version" "feature/existing-feature" "1.5.0-EXI-abc1234-SNAPSHOT" "1.5.0-EXI-*-SNAPSHOT" ""
}

# Test edge cases
test_edge_cases() {
    echo ""
    echo "=== Testing Edge Cases ==="
    
    # Test 1: Invalid release branch format (should fail)
    echo "🧪 Test: Invalid release branch format (should fail)"
    TESTS_RUN=$((TESTS_RUN + 1))
    
    create_test_pom "1.5.0-SNAPSHOT"
    create_test_branch "release/invalid" ""
    
    cd "$TEST_DIR"
    local output
    local exit_code=0
    
    output=$(cd "$TEST_DIR" && POM_FILE=pom.xml "$CALCULATE_VERSION_SCRIPT" --dry-run 2>&1) || exit_code=$?
    
    if [[ $exit_code -ne 0 ]]; then
        echo "  ✅ PASSED: Script correctly failed with invalid release branch format"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo "  ❌ FAILED: Script should have failed with invalid release branch format"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    
    # Test 2: Unknown branch type
    run_test "Unknown branch type" "unknown-branch" "1.5.0-SNAPSHOT" "1.5.0-SNAPSHOT" ""
    
    # Test 3: Main branch with no tags (should fail)
    echo "🧪 Test: Main branch with no tags (should fail)"
    TESTS_RUN=$((TESTS_RUN + 1))
    
    create_test_pom "1.5.0-SNAPSHOT"
    create_test_branch "main" ""  # No tag
    
    cd "$TEST_DIR"
    output=$(cd "$TEST_DIR" && POM_FILE=pom.xml "$CALCULATE_VERSION_SCRIPT" --dry-run 2>&1) || exit_code=$?
    
    if [[ $exit_code -ne 0 ]]; then
        echo "  ✅ PASSED: Script correctly failed with no tags on main branch"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo "  ❌ FAILED: Script should have failed with no tags on main branch"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

# Test version parsing
test_version_parsing() {
    echo ""
    echo "=== Testing Version Parsing ==="
    
    # Test various version formats
    local test_versions=(
        "1.0.0"
        "1.0.0-SNAPSHOT"
        "1.0.0-RC.1"
        "1.0.0-RC.10"
        "10.20.30"
        "10.20.30-SNAPSHOT"
        "10.20.30-RC.5"
        "v1.0.0"
        "v1.0.0-SNAPSHOT"
        "v1.0.0-RC.1"
        "v10.20.30"
    )
    
    for version in "${test_versions[@]}"; do
        echo "🧪 Testing version parsing: $version"
        
        # Create a simple test to verify version parsing doesn't crash
        create_test_pom "$version"
        create_test_branch "main" ""
        
        cd "$TEST_DIR"
        local output
        local exit_code=0
        
        output=$(cd "$TEST_DIR" && POM_FILE=pom.xml "$CALCULATE_VERSION_SCRIPT" --dry-run 2>&1) || exit_code=$?
        
        if [[ $exit_code -eq 0 ]]; then
            echo "  ✅ PASSED: Version $version parsed successfully"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        else
            echo "  ❌ FAILED: Version $version parsing failed"
            echo "  Output: $output"
            TESTS_FAILED=$((TESTS_FAILED + 1))
        fi
        
        TESTS_RUN=$((TESTS_RUN + 1))
    done
}

####################
## Main execution ##
####################
main() {
    echo "=== QQQ Version Calculator Test Suite ==="
    echo "Testing script: $CALCULATE_VERSION_SCRIPT"
    echo ""
    
    # Verify script exists
    if [[ ! -f "$CALCULATE_VERSION_SCRIPT" ]]; then
        echo "❌ Script not found: $CALCULATE_VERSION_SCRIPT"
        exit 1
    fi
    
    # Setup test environment
    setup_test_environment
    
    # Run all test suites
    test_main_branch
    test_develop_branch
    test_release_branch
    test_hotfix_branch
    test_feature_branch
    test_edge_cases
    test_version_parsing
    
    # Cleanup and show results
    cleanup_test_environment
    print_summary
}

# Run main function
main "$@"
