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

############################################################################
## Strip rerunFailure elements that CircleCI's JUnit parser doesn't support
## These are added by Maven Surefire when rerunFailingTestsCount > 0
############################################################################
echo "Cleaning JUnit XML files for CircleCI compatibility"
for xml_file in ~/test-results/junit/*.xml; do
  if [ -f "$xml_file" ]; then
    sed -i.bak '/<rerunFailure/,/<\/rerunFailure>/d' "$xml_file" 2>/dev/null || \
    sed -i '' '/<rerunFailure/,/<\/rerunFailure>/d' "$xml_file" 2>/dev/null || true
    rm -f "${xml_file}.bak" 2>/dev/null || true
  fi
done
