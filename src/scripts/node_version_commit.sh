#!/bin/bash

############################################################################
## node_version_commit.sh
## Node.js Version Commit Management Script
##
## This script handles committing version changes to Git for Node.js projects.
## It checks if the package.json file has been modified and commits the changes if needed.
## It also pushes the changes back to the current branch.
##
## Process:
## 1. Skips for feature branches (ephemeral versions)
## 2. Checks if package.json has been modified
## 3. Extracts the new version from package.json
## 4. Commits the changes with skip ci flag
## 5. Pushes changes to the current branch (non-fatal on failure)
##
## Usage: Called by node_manage_version command
## Output: Commits and pushes version changes if package.json was modified
############################################################################

set -e

################################################################
## Skip version commit for feature branches                   ##
## Feature versions are ephemeral and don't need to be        ##
## persisted back to the repository                           ##
################################################################
if [[ "$BRANCH_TYPE" == "feature" ]]; then
  echo "Skipping version commit for feature branch (ephemeral versions)"
  exit 0
fi

################################################################
## Check if package.json was modified and commit if needed    ##
################################################################
echo "Checking for package.json version changes"
if [[ -n "$(git status --porcelain package.json)" ]]; then
  NEW_VERSION=$(grep '"version"' package.json | sed 's/.*"version": "//;s/".*//')
  git add package.json
  git commit -m "Bump version to $NEW_VERSION [skip ci]"

  # Determine target branch
  if [ -n "$CIRCLE_BRANCH" ]; then
    TARGET_BRANCH="$CIRCLE_BRANCH"
  else
    TARGET_BRANCH="main"
  fi

  # Try to push, but don't fail the build if push fails
  # This can happen if another build pushed first (race condition)
  if git push origin "HEAD:${TARGET_BRANCH}"; then
    echo "Version updated to: $NEW_VERSION and pushed to ${TARGET_BRANCH}"
  else
    echo "WARNING: Failed to push version commit to ${TARGET_BRANCH}"
    echo "This is not fatal - version will be updated on next build"
    echo "Common causes: concurrent builds, branch protection rules"
  fi
else
  echo "No version change needed"
fi
