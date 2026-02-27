#!/bin/bash

############################################################################
## node_app_e2e.sh
## Node Application End-to-End Test Runner
##
## Installs Playwright browsers and runs e2e tests producing JUnit output.
##
## Environment Variables:
##   NODE_PKG_MANAGER - Package manager to use (default: pnpm)
##   E2E_SCRIPT       - Script name for e2e tests (default: test:e2e)
##
## Usage: Called by CircleCI orb command node_app_e2e
## Output: JUnit test results in test-results/e2e/ and Playwright traces
############################################################################

set -e

# Source shared helpers (no-op in packed orb — file won't exist at runtime)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/qqq_helpers.sh" 2>/dev/null || true

# Fallback stubs when helpers couldn't be sourced (packed orb environment)
if ! type banner &>/dev/null; then
    banner() { echo ""; echo "========================================"; echo "  ${1:-}"; echo "========================================"; echo ""; }
    require_tool() { command -v "$1" &>/dev/null || { echo "ERROR: Required tool '$1' is not installed."; exit 1; }; }
fi

NODE_PKG_MANAGER="${NODE_PKG_MANAGER:-pnpm}"
E2E_SCRIPT="${E2E_SCRIPT:-test:e2e}"

banner "End-to-End Tests (Playwright)"

require_tool "${NODE_PKG_MANAGER}"

###########################
## Install Browsers      ##
###########################
echo "Installing Playwright browsers..."
npx playwright install --with-deps chromium

###########################
## Run E2E Tests         ##
###########################
mkdir -p test-results/e2e

echo "Running e2e tests..."
"${NODE_PKG_MANAGER}" run "${E2E_SCRIPT}" || E2E_EXIT=$?

if [[ "${E2E_EXIT:-0}" -ne 0 ]]; then
    echo "E2E tests failed with exit code ${E2E_EXIT}"
    exit "${E2E_EXIT}"
fi

echo "E2E tests completed successfully"
