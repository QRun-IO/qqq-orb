#!/usr/bin/env bash

############################################################################
## node_npm_publish.sh
## NPM Publishing Script with Prerelease Tag Support
##
## This script publishes npm packages with proper handling of prerelease
## versions. NPM requires a --tag flag for prerelease versions.
##
## Prerelease detection:
## - RC versions (e.g., 1.0.0-RC.1) -> --tag rc
## - SNAPSHOT versions (e.g., 1.0.0-SNAPSHOT) -> --tag snapshot
## - Alpha/Beta versions -> --tag next
## - Stable versions (e.g., 1.0.0) -> --tag latest (default)
##
## Usage: Called by CircleCI orb command node_publish
############################################################################

set +x
set -euo pipefail

if [[ "${QQQ_NPM_TRUSTED_PUBLISHING:-false}" == "true" || "${QQQ_NPM_TRUSTED_PUBLISHING:-false}" == "1" ]]; then
    NPM_CLI_VERSION=$(npm --version)
    node - "$NPM_CLI_VERSION" <<'NODE'
const atLeast = (actual, minimum) => {
    const parts = actual.split('.').map(Number);
    return minimum.every((part, index) => parts[index] === part)
        || minimum.some((part, index) => parts[index] > part
            && minimum.slice(0, index).every((value, previous) => parts[previous] === value));
};
if (!atLeast(process.versions.node, [22, 14, 0]) || !atLeast(process.argv[2], [11, 5, 1])) {
    console.error('Trusted publishing requires Node >=22.14.0 and npm >=11.5.1.');
    process.exit(1);
}
if (Object.keys(process.env).some(name => /^npm_config_.*(auth|password|username|userconfig|globalconfig)/i.test(name))) {
    console.error('Remove npm credential/config-path environment settings before using trusted publishing.');
    process.exit(1);
}
NODE

    # Do not inherit a project/user token or write the short-lived identity to disk.
    if [[ -f .npmrc ]]; then
        echo "Trusted publishing requires a publish directory without .npmrc." >&2
        exit 1
    fi
    unset NPM_TOKEN NODE_AUTH_TOKEN NPM_AUTH_TOKEN
    PUBLISH_CONFIG_DIR=$(mktemp -d)
    trap 'rm -rf "$PUBLISH_CONFIG_DIR"' EXIT
    export NPM_CONFIG_USERCONFIG="$PUBLISH_CONFIG_DIR/user.npmrc"
    export NPM_CONFIG_GLOBALCONFIG="$PUBLISH_CONFIG_DIR/global.npmrc"
    NPM_ID_TOKEN=$(circleci run oidc get --claims '{"aud":"npm:registry.npmjs.org"}')
    if [[ -z "$NPM_ID_TOKEN" ]]; then
        echo "CircleCI did not provide an npm OIDC token." >&2
        exit 1
    fi
    export NPM_ID_TOKEN
fi

# Extract version from package.json
VERSION=$(grep '"version"' package.json | sed 's/.*"version": "//;s/".*//')
echo "Publishing version: $VERSION"

# Determine the appropriate npm tag based on version
if [[ "$VERSION" =~ -RC\.[0-9]+$ ]]; then
    NPM_TAG="rc"
    echo "Detected RC version - using tag: $NPM_TAG"
elif [[ "$VERSION" =~ -SNAPSHOT$ ]]; then
    NPM_TAG="snapshot"
    echo "Detected SNAPSHOT version - using tag: $NPM_TAG"
elif [[ "$VERSION" =~ -(alpha|beta) ]]; then
    NPM_TAG="next"
    echo "Detected alpha/beta version - using tag: $NPM_TAG"
else
    NPM_TAG="latest"
    echo "Detected stable version - using tag: $NPM_TAG"
fi

# Publish with the appropriate tag
echo "Running: npm publish --access public --tag $NPM_TAG"
npm publish --access public --tag "$NPM_TAG"

echo "Successfully published $VERSION with tag $NPM_TAG"
