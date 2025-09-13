#!/bin/bash

############################################################################
## create_github_release.sh
## GitHub Release Creation Script
## 
## This script creates Git tags and GitHub releases for production releases.
## It extracts the version from pom.xml and creates both a Git tag and
## a corresponding GitHub release with automated notes.
##
## Process:
## 1. Extracts version from pom.xml revision field
## 2. Creates Git tag if it doesn't already exist
## 3. Pushes tag to remote repository
## 4. Authenticates with GitHub CLI
## 5. Creates GitHub release with automated notes
##
## Usage: Called by CircleCI orb commands publish_release and publish_hotfix
## Output: Creates Git tag and GitHub release for the version
############################################################################

set -e

##################################
## Extract version from pom.xml ##
##################################
VERSION=$(grep '<revision>' pom.xml | sed 's/.*<revision>//;s/<.*//')
echo "Creating tag for version: $VERSION"

##################################################
## Create and push tag (if not already created) ##
##################################################
if ! git tag --list | grep -q "v$VERSION"; then
  git tag "v$VERSION"
  git push origin "v$VERSION"
  echo "Tag v$VERSION created and pushed"
else
  echo "Tag v$VERSION already exists"
fi

###########################
## Create GitHub release ##
###########################
echo "Creating GitHub release for v$VERSION"
echo "$GITHUB_TOKEN" | gh auth login --with-token
gh release create "v$VERSION" \
  --title "Release v$VERSION" \
  --notes "Automated release from CircleCI" \
  --repo Kingsrook/qqq
