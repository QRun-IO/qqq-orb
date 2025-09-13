#!/bin/bash

############################################################################
## mvn_verify_save_test_results.sh
## Test Results Collection Script
## 
## This script collects JUnit test results from Maven Surefire reports
## and saves them to the CircleCI test results directory for reporting.
## It finds all XML test result files and copies them to the standard location.
##
## Process:
## 1. Creates test results directory structure
## 2. Finds all Surefire XML report files
## 3. Copies test results to CircleCI test results directory
##
## Usage: Called by CircleCI orb command mvn_verify
## Output: Collects and saves JUnit test results for CircleCI reporting
############################################################################

set -e

#############################################################
## Create test results directory and collect JUnit reports ##
#############################################################
mkdir -p ~/test-results/junit/
find . -type f -regex ".*/target/surefire-reports/.*xml" -exec cp {} ~/test-results/junit/ \;
