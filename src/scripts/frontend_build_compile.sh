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
## --update-snapshots: the ~/.m2 cache is keyed only on the pom checksum, so
## without it a SNAPSHOT dependency restored from cache is never re-checked
## (Maven's daily update policy) and builds run against stale snapshots.
mvn -s /tmp/circleci/mvn-settings.xml --update-snapshots -T4 --no-transfer-progress compile
