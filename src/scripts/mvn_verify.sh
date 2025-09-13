#!/bin/bash

############################################################################
## mvn_verify_verify.sh
## Maven Verification Script
## 
## This script runs the complete Maven verification lifecycle including
## compilation, testing, packaging, and verification. It uses optimized
## settings for faster execution in CI environments.
##
## Process:
## 1. Uses CircleCI Maven settings configuration
## 2. Enables parallel builds with 4 threads
## 3. Disables transfer progress for cleaner output
## 4. Runs Maven verify lifecycle (compile, test, package, verify)
##
## Usage: Called by CircleCI orb command mvn_verify
## Output: Runs complete Maven verification lifecycle
############################################################################

set -e

########################################################
## Run Maven verify lifecycle with optimized settings ##
########################################################
mvn -s /tmp/circleci/mvn-settings.xml -T4 --no-transfer-progress verify
