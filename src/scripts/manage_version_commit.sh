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
## Check if pom.xml was modified and commit changes if needed ##
################################################################
if [[ -n "$(git status --porcelain pom.xml)" ]]; then
  NEW_VERSION=$(grep '<revision>' pom.xml | sed 's/.*<revision>//;s/<.*//')
  git add pom.xml
  git commit -m "Bump version to $NEW_VERSION [skip ci]"
  git push origin "HEAD:${CIRCLE_BRANCH}"
  echo "Version updated to: $NEW_VERSION and pushed"
else
  echo "No version change needed"
fi
