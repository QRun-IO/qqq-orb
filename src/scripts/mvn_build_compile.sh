#!/bin/bash

############################################################################
## mvn_build_compile.sh
## Maven Compilation Script
## 
## This script compiles the Maven project using optimized settings.
## It uses the CircleCI Maven settings file and enables parallel builds
## for faster compilation.
##
## Process:
## 1. Uses CircleCI Maven settings configuration
## 2. Enables parallel builds with 4 threads
## 3. Disables transfer progress for cleaner output
## 4. Compiles the project
##
## Usage: Called by CircleCI orb command mvn_build
## Output: Compiles the Maven project
############################################################################

set -e

###################################################
## Compile Maven project with optimized settings ##
###################################################
mvn -s .circleci/mvn-settings.xml -T4 --no-transfer-progress compile
