#!/bin/bash

############################################################################
## node_app_test.sh
## Node Application Test Runner
##
## Runs type-checking, linting, and unit tests for a Node.js application.
## Each step can be overridden via environment variables to support
## projects with non-standard script names.
##
## Environment Variables:
##   NODE_PKG_MANAGER   - Package manager to use (default: pnpm)
##   TYPECHECK_SCRIPT    - Script name for type checking (default: typecheck)
##   LINT_SCRIPT         - Script name for linting (default: lint)
##   TEST_SCRIPT         - Script name for unit tests (default: test)
##
## Usage: Called by CircleCI orb command node_app_test
## Output: Test results and lint/typecheck status
############################################################################

set -e

# Source shared helpers
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/qqq_helpers.sh" 2>/dev/null || true

NODE_PKG_MANAGER="${NODE_PKG_MANAGER:-pnpm}"
TYPECHECK_SCRIPT="${TYPECHECK_SCRIPT:-typecheck}"
LINT_SCRIPT="${LINT_SCRIPT:-lint}"
TEST_SCRIPT="${TEST_SCRIPT:-test}"

############################################################################
## has_script - check if a script exists in package.json
############################################################################
has_script() {
    local name="$1"
    node -e "
        const pkg = require('./package.json');
        process.exit(pkg.scripts && pkg.scripts['${name}'] ? 0 : 1);
    "
}

############################################################################
## run_step - run a package.json script if it exists
############################################################################
run_step() {
    local label="$1"
    local script="$2"

    banner "${label}"

    if has_script "${script}"; then
        "${NODE_PKG_MANAGER}" run "${script}"
    else
        echo "SKIP: No '${script}' script found in package.json"
    fi
}

###########################
## Run Steps             ##
###########################
run_step "Type Check" "${TYPECHECK_SCRIPT}"
run_step "Lint"       "${LINT_SCRIPT}"
run_step "Unit Tests" "${TEST_SCRIPT}"

echo "All test steps completed successfully"
