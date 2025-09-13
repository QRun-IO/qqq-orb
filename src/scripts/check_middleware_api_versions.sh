#!/bin/bash

############################################################################
## check_middleware_api_versions.sh
## API Version Compatibility Validation Script
## 
## This script validates API version compatibility across middleware components
## by building the project and running the ValidateApiVersions tool.
##
## Process:
## 1. Builds the entire project without running tests
## 2. Assembles the Javalin middleware application
## 3. Runs ValidateApiVersions tool to check API compatibility
##
## Usage: Called by CircleCI orb command check_middleware_api_versions
## Output: Validates API versions and exits with error if incompatible
############################################################################

set -e

#################################
## Build project without tests ##
#################################
mvn -s /tmp/circleci/mvn-settings.xml -T4 --no-transfer-progress install -DskipTests

#####################################
## Assemble middleware application ##
#####################################
mvn -s /tmp/circleci/mvn-settings.xml -T4 --no-transfer-progress -pl qqq-middleware-javalin package appassembler:assemble -DskipTests

################################
## Run API version validation ##
################################
qqq-middleware-javalin/target/appassembler/bin/ValidateApiVersions -r "$(pwd)"
