#!/bin/bash
set -e

# NPM Version Synchronization Script for qqq-frontend-core
# This script updates package.json version based on the current GitFlow branch and versioning policy

PACKAGE_JSON="package.json"
DRY_RUN=false

if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "DRY RUN MODE - No changes will be made"
fi

# Get current branch
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: $CURRENT_BRANCH"

# Get current NPM version
NPM_VERSION=$(grep '"version"' $PACKAGE_JSON | sed 's/.*"version": "//;s/".*//')
echo "Current NPM version: $NPM_VERSION"

# Determine target version based on GitFlow branch
if [[ "$CURRENT_BRANCH" == "main" ]]; then
    # Main branch - should be a release version (e.g., 1.0.0)
    # Extract major.minor from current version
    MAJOR_MINOR="${NPM_VERSION%.*}"
    TARGET_VERSION="$MAJOR_MINOR.0"
    echo "Main branch detected - targeting release version: $TARGET_VERSION"
elif [[ "$CURRENT_BRANCH" == "develop" ]]; then
    # Develop branch - should be a snapshot version (e.g., 1.0.127-SNAPSHOT)
    # Increment patch version for develop
    MAJOR_MINOR_PATCH="${NPM_VERSION%-*}"
    MAJOR_MINOR="${MAJOR_MINOR_PATCH%.*}"
    PATCH="${MAJOR_MINOR_PATCH##*.}"
    NEW_PATCH=$((PATCH + 1))
    TARGET_VERSION="$MAJOR_MINOR.$NEW_PATCH-SNAPSHOT"
    echo "Develop branch detected - targeting snapshot version: $TARGET_VERSION"
elif [[ "$CURRENT_BRANCH" == release/* ]]; then
    # Release branch - should be a release candidate (e.g., 1.0.0-RC.1)
    RELEASE_VERSION=$(echo "$CURRENT_BRANCH" | sed 's/release\///')
    TARGET_VERSION="$RELEASE_VERSION-RC.1"
    echo "Release branch detected - targeting RC version: $TARGET_VERSION"
elif [[ "$CURRENT_BRANCH" == hotfix/* ]]; then
    # Hotfix branch - should be a patch version (e.g., 1.0.1)
    HOTFIX_VERSION=$(echo "$CURRENT_BRANCH" | sed 's/hotfix\///')
    TARGET_VERSION="$HOTFIX_VERSION"
    echo "Hotfix branch detected - targeting patch version: $TARGET_VERSION"
else
    # Feature branch - should be a snapshot version
    MAJOR_MINOR_PATCH="${NPM_VERSION%-*}"
    MAJOR_MINOR="${MAJOR_MINOR_PATCH%.*}"
    PATCH="${MAJOR_MINOR_PATCH##*.}"
    NEW_PATCH=$((PATCH + 1))
    TARGET_VERSION="$MAJOR_MINOR.$NEW_PATCH-SNAPSHOT"
    echo "Feature branch detected - targeting snapshot version: $TARGET_VERSION"
fi

echo "Target version: $TARGET_VERSION"

if [[ "$NPM_VERSION" == "$TARGET_VERSION" ]]; then
    echo "✅ Versions are already synchronized"
    exit 0
fi

if [[ "$DRY_RUN" == "true" ]]; then
    echo "DRY RUN: Would update package.json version from '$NPM_VERSION' to '$TARGET_VERSION'"
    echo "Command: sed -i 's/\"version\": \"$NPM_VERSION\"/\"version\": \"$TARGET_VERSION\"/' $PACKAGE_JSON"
    exit 0
fi

echo "Updating package.json version from '$NPM_VERSION' to '$TARGET_VERSION'"

# Update version in package.json (macOS compatible)
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/\"version\": \"$NPM_VERSION\"/\"version\": \"$TARGET_VERSION\"/" $PACKAGE_JSON
else
    sed -i "s/\"version\": \"$NPM_VERSION\"/\"version\": \"$TARGET_VERSION\"/" $PACKAGE_JSON
fi

# Verify the update
ACTUAL_NPM_VERSION=$(grep '"version"' $PACKAGE_JSON | sed 's/.*"version": "//;s/".*//')
if [[ "$ACTUAL_NPM_VERSION" == "$TARGET_VERSION" ]]; then
    echo "✅ NPM version successfully updated to: $ACTUAL_NPM_VERSION"
else
    echo "❌ NPM version update failed. Expected: $TARGET_VERSION, Got: $ACTUAL_NPM_VERSION"
    exit 1
fi

echo ""
echo "=== NPM version synchronization complete ==="
echo "Previous: $NPM_VERSION"
echo "Current:  $ACTUAL_NPM_VERSION"
echo "Branch:   $CURRENT_BRANCH"
