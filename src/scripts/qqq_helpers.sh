#!/bin/bash

############################################################################
## qqq_helpers.sh
## QQQ Orb Shared Helper Functions
##
## Provides common utilities used across node_app_* scripts:
##   - Double-source guard to prevent re-initialization
##   - Banner display for step identification
##   - Tool existence checking
##
## Usage: source qqq_helpers.sh (from other scripts)
## Output: Exports helper functions into the calling script
############################################################################

# Double-source guard
if [[ -n "${_QQQ_HELPERS_LOADED:-}" ]]; then
    # shellcheck disable=SC2317
    return 0 2>/dev/null || true
fi
_QQQ_HELPERS_LOADED=1

############################################################################
## banner
## Print a visible section header
##
## Usage: banner "Step Name"
############################################################################
banner() {
    local msg="$1"
    echo ""
    echo "========================================"
    echo "  ${msg}"
    echo "========================================"
    echo ""
}

############################################################################
## require_tool
## Verify a CLI tool is available, exit 1 if missing
##
## Usage: require_tool "pnpm"
############################################################################
require_tool() {
    local tool="$1"
    if ! command -v "${tool}" &>/dev/null; then
        echo "ERROR: Required tool '${tool}' is not installed."
        exit 1
    fi
}
