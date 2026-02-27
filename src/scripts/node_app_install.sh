#!/bin/bash

############################################################################
## node_app_install.sh
## Node Application Dependency Installation
##
## Installs dependencies for a Node.js application project using the
## configured package manager (pnpm, npm, or yarn). Enables corepack
## when using pnpm or yarn.
##
## Environment Variables:
##   NODE_PKG_MANAGER - Package manager to use (default: pnpm)
##
## Usage: Called by CircleCI orb command node_app_install
## Output: Installed node_modules and validated lockfile
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

banner "Install Dependencies (${NODE_PKG_MANAGER})"

###########################
## Enable Corepack       ##
###########################
if [[ "${NODE_PKG_MANAGER}" == "pnpm" || "${NODE_PKG_MANAGER}" == "yarn" ]]; then
    if command -v "${NODE_PKG_MANAGER}" &>/dev/null; then
        echo "${NODE_PKG_MANAGER} already available: $(${NODE_PKG_MANAGER} --version)"
    else
        echo "Installing ${NODE_PKG_MANAGER} via corepack..."
        # corepack enable requires write access to /usr/local/bin; use sudo if available
        if sudo -n corepack enable 2>/dev/null; then
            echo "corepack enable succeeded (sudo)"
        else
            corepack enable --install-directory "${HOME}/.local/bin"
            export PATH="${HOME}/.local/bin:${PATH}"
        fi
        corepack prepare "${NODE_PKG_MANAGER}@latest" --activate
    fi
fi

require_tool "${NODE_PKG_MANAGER}"

###########################
## Lockfile Validation   ##
###########################
case "${NODE_PKG_MANAGER}" in
    pnpm)
        if [[ ! -f pnpm-lock.yaml ]]; then
            echo "WARNING: pnpm-lock.yaml not found"
        fi
        ;;
    npm)
        if [[ ! -f package-lock.json ]]; then
            echo "WARNING: package-lock.json not found"
        fi
        ;;
    yarn)
        if [[ ! -f yarn.lock ]]; then
            echo "WARNING: yarn.lock not found"
        fi
        ;;
    *)
        echo "ERROR: Unsupported package manager '${NODE_PKG_MANAGER}'"
        exit 1
        ;;
esac

###########################
## Install               ##
###########################
case "${NODE_PKG_MANAGER}" in
    pnpm)
        pnpm install --frozen-lockfile
        ;;
    npm)
        npm ci
        ;;
    yarn)
        yarn install --immutable
        ;;
esac

echo "Dependencies installed successfully with ${NODE_PKG_MANAGER}"
