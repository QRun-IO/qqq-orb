#!/bin/bash

############################################################################
## frontend_test_diagnostics.sh
## Chrome Diagnostics
## 
## This script runs diagnostics to confirm Chrome installation
## and verify no chromedriver conflicts exist.
##
## Usage: Called by frontend_test command
## Output: Displays Chrome installation status
############################################################################

set -e

echo "Running Chrome diagnostics"
which google-chrome || true
google-chrome --version || /opt/google/chrome/chrome --version || true
which chromedriver || echo "chromedriver not present (expected)"
env | grep -i -E 'chrome|driver|selenium' || true
