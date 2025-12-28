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
## 1. Extracts version from pom.xml or package.json
## 2. Verifies the Git tag exists
## 3. Creates GitHub release using GitHub API with auto-generated notes
## 4. Adds artifact links to Maven Central and/or npmjs
##
## Environment Variables:
##   GITHUB_TOKEN      - Required: GitHub token with repo scope
##   PROJECT_TYPE      - Optional: maven, node, or both (default: auto-detect)
##   DRY_RUN           - Optional: Set to "true" to skip API calls
##   CIRCLE_PROJECT_USERNAME - CircleCI: GitHub org/user
##   CIRCLE_PROJECT_REPONAME - CircleCI: Repository name
##
## Usage: Called by CircleCI orb command publish_github_release
## Output: Creates GitHub release for the existing tag
############################################################################

set -e

###################
## Configuration ##
###################
DRY_RUN="${DRY_RUN:-false}"
REPO_OWNER="${CIRCLE_PROJECT_USERNAME:-}"
REPO_NAME="${CIRCLE_PROJECT_REPONAME:-}"
API_URL="https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases"

############################
## Validate configuration ##
############################
if [[ -z "$GITHUB_TOKEN" ]]; then
  echo "ERROR: GITHUB_TOKEN environment variable is not set"
  exit 1
fi

if [[ -z "$REPO_OWNER" ]] || [[ -z "$REPO_NAME" ]]; then
  echo "ERROR: CIRCLE_PROJECT_USERNAME and CIRCLE_PROJECT_REPONAME must be set"
  exit 1
fi

echo "Repository: ${REPO_OWNER}/${REPO_NAME}"

###############################
## Extract version from file ##
###############################
VERSION=""
PROJECT_TYPE="${PROJECT_TYPE:-auto}"

# Auto-detect project type if not specified
if [[ "$PROJECT_TYPE" == "auto" ]]; then
  if [[ -f "pom.xml" ]]; then
    PROJECT_TYPE="maven"
  elif [[ -f "package.json" ]]; then
    PROJECT_TYPE="node"
  else
    echo "ERROR: Cannot detect project type. No pom.xml or package.json found."
    exit 1
  fi
fi

echo "Project type: $PROJECT_TYPE"

# Extract version based on project type
if [[ "$PROJECT_TYPE" == "maven" ]] || [[ "$PROJECT_TYPE" == "both" ]]; then
  if [[ -f "pom.xml" ]]; then
    VERSION=$(grep '<revision>' pom.xml | sed 's/.*<revision>//;s/<.*//' | head -1)
    if [[ -z "$VERSION" ]]; then
      # Fallback to version tag if revision not found
      VERSION=$(grep -m1 '<version>' pom.xml | sed 's/.*<version>//;s/<.*//')
    fi
  fi
fi

if [[ -z "$VERSION" ]] && { [[ "$PROJECT_TYPE" == "node" ]] || [[ "$PROJECT_TYPE" == "both" ]]; }; then
  if [[ -f "package.json" ]]; then
    VERSION=$(jq -r '.version' package.json)
  fi
fi

if [[ -z "$VERSION" ]]; then
  echo "ERROR: Could not extract version from project files"
  exit 1
fi

TAG_NAME="v$VERSION"
echo "Version: $VERSION"
echo "Tag: $TAG_NAME"

#######################################
## Determine if this is a prerelease ##
#######################################
PRERELEASE="false"
if [[ "$VERSION" =~ -RC\.[0-9]+$ ]] || [[ "$VERSION" =~ -SNAPSHOT$ ]] || [[ "$VERSION" =~ -alpha ]] || [[ "$VERSION" =~ -beta ]]; then
  PRERELEASE="true"
  echo "This is a prerelease version"
fi

##########################################
## Verify the tag exists ##
##########################################
if ! git tag --list | grep -q "^$TAG_NAME$"; then
  # Also check for version- prefix format
  ALT_TAG="version-$VERSION"
  if git tag --list | grep -q "^$ALT_TAG$"; then
    TAG_NAME="$ALT_TAG"
    echo "Using alternate tag format: $TAG_NAME"
  else
    echo "ERROR: Tag $TAG_NAME does not exist"
    echo "The tag should have been created by the version management process"
    exit 1
  fi
fi

echo "Tag $TAG_NAME exists, proceeding with GitHub release creation"

################################
## Build artifact links ##
################################
ARTIFACT_SECTION=""

# Maven Central links
if [[ "$PROJECT_TYPE" == "maven" ]] || [[ "$PROJECT_TYPE" == "both" ]]; then
  if [[ -f "pom.xml" ]]; then
    GROUP_ID=$(grep -m1 '<groupId>' pom.xml | sed 's/.*<groupId>//;s/<.*//')
    ARTIFACT_ID=$(grep -m1 '<artifactId>' pom.xml | sed 's/.*<artifactId>//;s/<.*//')

    if [[ -n "$GROUP_ID" ]] && [[ -n "$ARTIFACT_ID" ]]; then
      MAVEN_URL="https://central.sonatype.com/artifact/${GROUP_ID}/${ARTIFACT_ID}/${VERSION}"
      ARTIFACT_SECTION="### Artifacts

**Maven Central:**
- [${GROUP_ID}:${ARTIFACT_ID}:${VERSION}](${MAVEN_URL})"
      echo "Maven artifact: ${GROUP_ID}:${ARTIFACT_ID}"
    fi
  fi
fi

# NPM links
if [[ "$PROJECT_TYPE" == "node" ]] || [[ "$PROJECT_TYPE" == "both" ]]; then
  if [[ -f "package.json" ]]; then
    NPM_PACKAGE=$(jq -r '.name' package.json)

    if [[ -n "$NPM_PACKAGE" ]] && [[ "$NPM_PACKAGE" != "null" ]]; then
      NPM_URL="https://www.npmjs.com/package/${NPM_PACKAGE}/v/${VERSION}"
      if [[ -n "$ARTIFACT_SECTION" ]]; then
        ARTIFACT_SECTION="${ARTIFACT_SECTION}

**NPM:**
- [${NPM_PACKAGE}@${VERSION}](${NPM_URL})"
      else
        ARTIFACT_SECTION="### Artifacts

**NPM:**
- [${NPM_PACKAGE}@${VERSION}](${NPM_URL})"
      fi
      echo "NPM package: ${NPM_PACKAGE}"
    fi
  fi
fi

# Add footer
if [[ -n "$ARTIFACT_SECTION" ]]; then
  ARTIFACT_SECTION="${ARTIFACT_SECTION}

---
_Automated release via CircleCI_"
fi

###########################
## Create GitHub release ##
###########################
echo "Creating GitHub release for $TAG_NAME"

if [[ "$DRY_RUN" == "true" ]]; then
  echo "DRY RUN: Would create release with:"
  echo "  Tag: $TAG_NAME"
  echo "  Name: Release $VERSION"
  echo "  Prerelease: $PRERELEASE"
  echo "  Artifact section:"
  echo "$ARTIFACT_SECTION"
  echo "DRY RUN: Skipping API call"
  exit 0
fi

# Build the request body
# Using generate_release_notes to auto-generate from PRs (respects .github/release.yml)
REQUEST_BODY=$(jq -n \
  --arg tag "$TAG_NAME" \
  --arg name "Release $VERSION" \
  --arg body "$ARTIFACT_SECTION" \
  --argjson prerelease "$PRERELEASE" \
  '{
    tag_name: $tag,
    name: $name,
    body: $body,
    draft: false,
    prerelease: $prerelease,
    generate_release_notes: true
  }')

# Create the release with retry logic
MAX_RETRIES=2
RETRY_COUNT=0

while [[ $RETRY_COUNT -lt $MAX_RETRIES ]]; do
  HTTP_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
    -H "Accept: application/vnd.github.v3+json" \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$REQUEST_BODY" \
    "$API_URL")

  HTTP_BODY=$(echo "$HTTP_RESPONSE" | sed '$d')
  HTTP_CODE=$(echo "$HTTP_RESPONSE" | tail -n1)

  if [[ "$HTTP_CODE" -ge 200 ]] && [[ "$HTTP_CODE" -lt 300 ]]; then
    RELEASE_URL=$(echo "$HTTP_BODY" | jq -r '.html_url')
    echo "GitHub release created successfully: $RELEASE_URL"
    exit 0
  elif [[ "$HTTP_CODE" -ge 500 ]]; then
    echo "Server error (HTTP $HTTP_CODE), retrying..."
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 2
  elif [[ "$HTTP_CODE" == "422" ]]; then
    # Check if release already exists
    if echo "$HTTP_BODY" | grep -q "already_exists"; then
      echo "Release for $TAG_NAME already exists, skipping"
      exit 0
    else
      echo "ERROR: GitHub API returned HTTP $HTTP_CODE"
      echo "$HTTP_BODY"
      # Don't fail the build - artifacts are already published
      echo "WARNING: GitHub release creation failed, but artifacts are published"
      exit 0
    fi
  else
    echo "ERROR: GitHub API returned HTTP $HTTP_CODE"
    echo "$HTTP_BODY"
    # Don't fail the build - artifacts are already published
    echo "WARNING: GitHub release creation failed, but artifacts are published"
    exit 0
  fi
done

echo "WARNING: GitHub release creation failed after $MAX_RETRIES retries"
echo "Artifacts are published, continuing..."
exit 0
