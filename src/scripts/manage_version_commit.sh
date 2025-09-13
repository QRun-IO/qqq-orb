#!/bin/bash
set -e

if [[ -n "$(git status --porcelain pom.xml)" ]]; then
  NEW_VERSION=$(grep '<revision>' pom.xml | sed 's/.*<revision>//;s/<.*//')
  git add pom.xml
  git commit -m "Bump version to $NEW_VERSION [skip ci]"
  git push origin "HEAD:${CIRCLE_BRANCH}"
  echo "Version updated to: $NEW_VERSION and pushed"
else
  echo "No version change needed"
fi
