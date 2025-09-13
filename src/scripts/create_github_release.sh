#!/bin/bash
set -e

VERSION=$(grep '<revision>' pom.xml | sed 's/.*<revision>//;s/<.*//')
echo "Creating tag for version: $VERSION

# Create and push tag (if not already created)
if ! git tag --list | grep -q "v$VERSION"; then
  git tag "v$VERSION"
  git push origin "v$VERSION"
  echo "Tag v$VERSION created and pushed"
else
  echo "Tag v$VERSION already exists"
fi

echo "Creating GitHub release for v$VERSION"
echo "$GITHUB_TOKEN" | gh auth login --with-token
gh release create "v$VERSION" \
  --title "Release v$VERSION" \
  --notes "Automated release from CircleCI" \
  --repo Kingsrook/qqq
