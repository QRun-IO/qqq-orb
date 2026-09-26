#!/bin/bash

################################################################
## run_tests.sh                                               ##
## Test runner for calculate_version.sh script                ##
##                                                            ##
## This script runs the comprehensive test suite and provides ##
## different output formats for different use cases.          ##
##                                                            ##
## Usage: ./run_tests.sh [--verbose] [--ci]                   ##
################################################################
set -e

###################
## Configuration ##
###################
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_SCRIPT="$SCRIPT_DIR/test_calculate_version.sh"
SETTINGS_TEST_SCRIPT="$SCRIPT_DIR/test_maven_settings_output.sh"
VERBOSE=false
CI_MODE=false

##################################
## Parse command line arguments ##
##################################
while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose)
            VERBOSE=true
            shift
            ;;
        --ci)
            CI_MODE=true
            shift
            ;;
        *)
            echo "Usage: $0 [--verbose] [--ci]"
            echo "  --verbose  Show detailed test output"
            echo "  --ci       CI mode (minimal output, exit codes for CI)"
            exit 1
            ;;
    esac
done

####################
## Main execution ##
####################
main() {
    echo "🧪 Running calculate_version.sh test suite..."
    
    ###############################
    ## Verify test script exists ##
    ###############################
    if [[ ! -f "$TEST_SCRIPT" ]]; then
        echo "❌ Test script not found: $TEST_SCRIPT"
        exit 1
    fi
    if [[ ! -f "$SETTINGS_TEST_SCRIPT" ]]; then
        echo "❌ Test script not found: $SETTINGS_TEST_SCRIPT"
        exit 1
    fi
    
    ###############
    ## Run tests ##
    ###############
    local test_args=""
    if [[ "$VERBOSE" == "true" ]]; then
        test_args="--verbose"
    fi
    
    if [[ "$CI_MODE" == "true" ]]; then
        ###############################################
        ## CI mode: minimal output, focus on results ##
        ###############################################
        echo "Running tests in CI mode..."
        if { "$TEST_SCRIPT" $test_args && bash "$SETTINGS_TEST_SCRIPT"; } > /tmp/test_output.log 2>&1; then
            echo "✅ All tests passed!"
            exit 0
        else
            echo "❌ Tests failed!"
            echo "Test output:"
            cat /tmp/test_output.log
            exit 1
        fi
    else
        ###################################
        ## Interactive mode: full output ##
        ###################################
        "$TEST_SCRIPT" $test_args
        bash "$SETTINGS_TEST_SCRIPT"
    fi
}

#######################
## Run main function ##
#######################
main "$@"
