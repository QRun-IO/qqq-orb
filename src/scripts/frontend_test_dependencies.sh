#!/bin/bash

############################################################################
## frontend_test_dependencies.sh
## Install Browser Dependencies
## 
## This script installs system libraries required for Chrome
## to run in headless CI environments.
##
## Usage: Called by frontend_test command
## Output: Installs required system libraries
############################################################################

set -e

echo "Installing browser dependencies"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  libnss3-dev libgdk-pixbuf2.0-dev libgtk-3-dev libxss-dev
