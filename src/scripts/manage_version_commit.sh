#!/bin/bash

############################################################################
## manage_version_commit.sh
## Version Commit Management Script
## 
## This script handles committing version changes to Git. It checks if
## the pom.xml file has been modified and commits the changes if needed.
## It also pushes the changes back to the current branch.
##
## Process:
## 1. Checks if pom.xml has been modified
## 2. Extracts the new version from pom.xml
## 3. Commits the changes with skip ci flag
## 4. Pushes changes to the current branch
##
## Usage: Called by CircleCI orb command manage_version
## Output: Commits and pushes version changes if pom.xml was modified
############################################################################

set -e

################################################################
## Skip version commit for feature branches                   ##
## Feature versions are ephemeral (include commit hash) and   ##
## don't need to be persisted back to the repository          ##
################################################################
if [[ "$BRANCH_TYPE" == "feature" ]]; then
  echo "Skipping version commit for feature branch (ephemeral versions)"
  exit 0
fi

################################################################
## Check if pom.xml was modified and commit changes if needed ##
################################################################
if [[ -n "$(git status --porcelain pom.xml)" ]]; then
  NEW_VERSION=$(grep '<revision>' pom.xml | sed 's/.*<revision>//;s/<.*//')
  git add pom.xml
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
