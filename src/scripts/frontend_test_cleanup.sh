#!/bin/bash

############################################################################
## frontend_test_cleanup.sh
## Remove Preinstalled Chrome/ChromeDriver
## 
## This script removes any preinstalled Chrome/ChromeDriver
## to ensure clean browser testing environment.
##
## Usage: Called by frontend_test command
## Output: Removes stale Chrome installations
############################################################################

set -e

echo "Removing any preinstalled Chrome/ChromeDriver"
sudo apt-get remove -y google-chrome-stable || true
sudo rm -f /usr/bin/google-chrome /opt/google/chrome/chrome || true
sudo rm -f /usr/local/bin/chromedriver /usr/bin/chromedriver || true
