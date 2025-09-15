#!/bin/bash

############################################################################
## manage_version_commit.sh
## Version Commit Management Script
## 
## This script handles committing version changes to Git. It checks if
## the pom.xml and/or package.json files have been modified and commits
## the changes if needed. It also pushes the changes back to the current branch.
##
## Process:
## 1. Checks if pom.xml and/or package.json have been modified
## 2. Extracts the new version from the modified files
## 3. Commits the changes with skip ci flag
## 4. Pushes changes to the current branch
##
## Usage: Called by CircleCI orb command manage_version
## Output: Commits and pushes version changes if files were modified
############################################################################

set -e

#############################################################
## Check for modified files and commit changes if needed ##
#############################################################
MODIFIED_FILES=()
NEW_VERSION=""

# Check if pom.xml was modified
if [[ -n "$(git status --porcelain pom.xml)" ]]; then
  MODIFIED_FILES+=("pom.xml")
  NEW_VERSION=$(grep '<revision>' pom.xml | sed 's/.*<revision>//;s/<.*//')
fi

# Check if package.json was modified
if [[ -n "$(git status --porcelain package.json)" ]]; then
  MODIFIED_FILES+=("package.json")
  # Extract version from package.json (handles both "version": "1.0.0" and "version": "1.0.0-SNAPSHOT")
  PKG_VERSION=$(grep '"version"' package.json | sed 's/.*"version": *"//;s/".*//')
  if [[ -n "$NEW_VERSION" ]]; then
    # If we already have a version from pom.xml, use that for consistency
    echo "Using version from pom.xml: $NEW_VERSION"
  else
    NEW_VERSION="$PKG_VERSION"
  fi
fi

# Commit changes if any files were modified
if [[ ${#MODIFIED_FILES[@]} -gt 0 ]]; then
  echo "Modified files: ${MODIFIED_FILES[*]}"
  echo "New version: $NEW_VERSION"
  
  # Add all modified files
  for file in "${MODIFIED_FILES[@]}"; do
    git add "$file"
  done
  
  # Commit with skip ci flag
  git commit -m "Bump version to $NEW_VERSION [skip ci]"
  git push origin "HEAD:${CIRCLE_BRANCH}"
  echo "Version updated to: $NEW_VERSION and pushed"
else
  echo "No version change needed"
fi
