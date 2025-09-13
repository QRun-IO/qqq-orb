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

##############################################
## Deploy signed artifacts to Maven Central ##
##############################################
cat /tmp/circleci/mvn-settings.xml
mvn -s /tmp/circleci/mvn-settings.xml -P release -B -DskipTests -Dgpg.keyname="$GPG_KEYNAME" -Dgpg.passphrase="$GPG_PASSPHRASE" deploy
