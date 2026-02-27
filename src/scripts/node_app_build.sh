#!/bin/bash

############################################################################
## node_app_build.sh
## Node Application Production Build
##
## Runs the production build for a Node.js application with timing output.
##
## Environment Variables:
##   NODE_PKG_MANAGER - Package manager to use (default: pnpm)
##   BUILD_SCRIPT     - Script name for the build step (default: build)
##
## Usage: Called by CircleCI orb command node_app_build_step
## Output: Production build artifacts
############################################################################

set -e

# Source shared helpers
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/qqq_helpers.sh" 2>/dev/null || true

NODE_PKG_MANAGER="${NODE_PKG_MANAGER:-pnpm}"
BUILD_SCRIPT="${BUILD_SCRIPT:-build}"

banner "Production Build"

require_tool "${NODE_PKG_MANAGER}"

START_TIME=$(date +%s)

"${NODE_PKG_MANAGER}" run "${BUILD_SCRIPT}"

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
echo "Build completed in ${ELAPSED}s"
