#!/bin/bash

############################################################################
## mvn_jar_deploy_gpg_setup.sh
## GPG Signing Setup Script
## 
## This script sets up GPG signing for Maven artifact deployment.
## It configures the GPG environment and imports the private key
## needed for signing artifacts before deployment to Maven Central.
##
## Process:
## 1. Creates GPG directory structure
## 2. Configures GPG with loopback pinentry mode
## 3. Sets proper permissions on GPG configuration
## 4. Imports the base64-encoded private key
##
## Usage: Called by CircleCI orb command mvn_jar_deploy
## Output: Sets up GPG signing for artifact deployment
############################################################################

set -e

#################################################
## Set up GPG environment for artifact signing ##
#################################################
mkdir -p ~/.gnupg
echo 'pinentry-mode loopback' > ~/.gnupg/gpg.conf
chmod 600 ~/.gnupg/gpg.conf
echo "$GPG_PRIVATE_KEY_B64"| tr -d ' \r\n\t' | base64 -d | gpg --batch --import
