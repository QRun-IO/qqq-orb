#!/bin/bash

############################################################################
## manage_version_calculate.sh
## Version Calculation Execution Script
## 
## This script executes the version calculation process by running
## the calculate-version.sh script. It ensures the script is executable
## and then runs it to determine and set the appropriate version.
##
## Process:
## 1. Makes calculate-version.sh executable
## 2. Executes the version calculation script
##
## Usage: Called by CircleCI orb command manage_version
## Output: Calculates and sets version in pom.xml
############################################################################

set -e

###########################################################
## Make version calculation script executable and run it ##
###########################################################
chmod +x .circleci/calculate-version.sh
.circleci/calculate-version.sh
