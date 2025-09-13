#!/bin/bash

############################################################################
## frontend_test_collect_results.sh
## Collect JUnit XML Test Results
## 
## This script collects JUnit XML test results from the Maven
## surefire reports directory for CircleCI test reporting.
##
## Usage: Called by frontend_test command
## Output: Collects test results to ~/test-results/junit/
############################################################################

set -e

echo "Collecting JUnit XML test results"
mkdir -p ~/test-results/junit/
find . -type f -regex ".*/target/surefire-reports/.*xml" -exec cp {} ~/test-results/junit/ \; || true
