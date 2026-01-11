#!/bin/bash

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

set -e

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
