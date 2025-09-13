#!/bin/bash

############################################################################
## frontend_build_compile.sh
## Maven Compile Step for Frontend Build
## 
## This script runs the Maven compile step with optimized settings
## for frontend builds in CI/CD environments.
##
## Usage: Called by frontend_build command
## Output: Compiles the Maven project
############################################################################

set -e

echo "Running Maven Compile with optimized settings"
mvn -s /tmp/circleci/mvn-settings.xml -T4 --no-transfer-progress compile
