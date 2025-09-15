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
## 1. Checks if package.json has been modified
## 2. Extracts the new version from package.json
## 3. Commits the changes with skip ci flag
## 4. Pushes changes to the current branch
##
## Usage: Called by node_manage_version command
## Output: Commits and pushes version changes if package.json was modified
############################################################################

set -e

echo "Checking for package.json version changes"
if [[ -n "$(git status --porcelain package.json)" ]]; then
  NEW_VERSION=$(grep '"version"' package.json | sed 's/.*"version": "//;s/".*//')
  git add package.json
  git commit -m "Bump version to $NEW_VERSION [skip ci]"
  git push origin "HEAD:${CIRCLE_BRANCH}"
  echo "Version updated to: $NEW_VERSION and pushed"
else
  echo "No version change needed"
fi
