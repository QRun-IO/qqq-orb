#!/bin/bash

############################################################################
## create_github_release.sh
## GitHub Release Creation Script
## 
## This script creates GitHub releases for production releases.
## The Git tag should already exist from the version management process.
## This script creates the corresponding GitHub release using the GitHub API.
##
## Process:
## 1. Extracts version from pom.xml revision field
## 2. Verifies the Git tag exists (should be created by version management)
## 3. Creates GitHub release using GitHub API (no gh CLI required)
## 4. Generates release notes from recent commits
##
## Usage: Called by CircleCI orb commands publish_release and publish_hotfix
## Output: Creates GitHub release for the existing tag
############################################################################

set -e

##################################
## Extract version from pom.xml ##
##################################
VERSION=$(grep '<revision>' pom.xml | sed 's/.*<revision>//;s/<.*//')
TAG_NAME="v$VERSION"
echo "Creating GitHub release for tag: $TAG_NAME"

##########################################
## Verify the tag exists (should be created by version management) ##
##########################################
if ! git tag --list | grep -q "^$TAG_NAME$"; then
  echo "ERROR: Tag $TAG_NAME does not exist"
  echo "The tag should have been created by the version management process"
  exit 1
fi

echo "Tag $TAG_NAME exists, proceeding with GitHub release creation"

##########################################
## Generate release notes from commits ##
##########################################
echo "Generating release notes..."

# Get the previous tag for comparison
PREVIOUS_TAG=$(git describe --tags --abbrev=0 --match="v*" HEAD~1 2>/dev/null || echo "")

if [[ -n "$PREVIOUS_TAG" ]]; then
  echo "Comparing with previous release: $PREVIOUS_TAG"
  RELEASE_NOTES=$(git log --pretty=format:"- %s" "$PREVIOUS_TAG"..HEAD | head -20)
else
  echo "No previous tag found, using recent commits"
  RELEASE_NOTES=$(git log --pretty=format:"- %s" -10)
fi

# Create a more detailed release notes
FULL_NOTES="## Release $VERSION

### Changes
$RELEASE_NOTES

### Artifacts
This release includes Maven artifacts published to Maven Central.

---
*Automated release from CircleCI*"

###########################
## Create GitHub release ##
###########################
echo "Creating GitHub release for $TAG_NAME"

# Create the release using GitHub API
curl -X POST \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"tag_name\": \"$TAG_NAME\",
    \"name\": \"Release $VERSION\",
    \"body\": $(echo "$FULL_NOTES" | jq -Rs .),
    \"draft\": false,
    \"prerelease\": false
  }" \
  "https://api.github.com/repos/Kingsrook/qqq/releases"

echo "✅ GitHub release created successfully for $TAG_NAME"
