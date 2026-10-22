#!/bin/bash

############################################################################
## mvn_jar_deploy_deploy.sh
## Maven Artifact Deployment Script
## 
## This script deploys signed Maven artifacts to Maven Central (Sonatype).
## It uses the release profile and GPG signing configuration to publish
## artifacts to the central repository.
##
## Process:
## 1. Uses CircleCI Maven settings configuration
## 2. Activates release profile for deployment
## 3. Runs in batch mode for automation
## 4. Skips tests (should be run separately)
## 5. Configures GPG signing with keyname and passphrase
## 6. Deploys artifacts to Maven Central
##
## Usage: Called by CircleCI orb command mvn_jar_deploy
## Output: Deploys signed artifacts to Maven Central
############################################################################

set -e

# The shared publish job already ran these checks in its verify lifecycle.
# Standalone command callers retain analysis unless explicitly opted in.
analysis_args=()
if [[ "${QQQ_SKIP_VERIFIED_ANALYSIS:-false}" == "true" || "${QQQ_SKIP_VERIFIED_ANALYSIS:-false}" == "1" ]]; then
  analysis_args=(-Dspotbugs.skip=true -Dpmd.skip=true)
fi

##############################################
## Deploy signed artifacts to Maven Central ##
##############################################
# Resolve CI-friendly coordinates without stripping parent/BOM configuration.
# Flatten must share this Maven process so deploy uses the resolved project POMs.
# Central 0.8.x: this completion flag overrides inherited literal waitUntil=uploaded.
# Do not report a release as successful until Central confirms publication.
mvn -s /tmp/circleci/mvn-settings.xml -P release -B -DskipTests \
  "${analysis_args[@]}" \
  -Dgpg.keyname="$GPG_KEYNAME" -Dgpg.passphrase="$GPG_PASSPHRASE" \
  -DwaitForPublishCompletion=true \
  -Dflatten.mode=resolveCiFriendliesOnly -DupdatePomFile=true \
  org.codehaus.mojo:flatten-maven-plugin:1.7.3:flatten deploy
