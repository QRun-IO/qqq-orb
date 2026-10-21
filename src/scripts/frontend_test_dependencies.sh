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

set -euo pipefail

echo "Installing browser dependencies"
export DEBIAN_FRONTEND=noninteractive
ubuntu_sources=/etc/apt/sources.list
if [[ ! -s "$ubuntu_sources" ]]; then
  ubuntu_sources=/etc/apt/sources.list.d/ubuntu.sources
fi
if [[ ! -s "$ubuntu_sources" ]]; then
  echo 'Cannot locate Ubuntu package sources' >&2
  exit 1
fi
sudo env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get update \
  -o "Dir::Etc::sourcelist=$ubuntu_sources" \
  -o Dir::Etc::sourceparts=- -o APT::Get::List-Cleanup=0
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  libnss3-dev libgdk-pixbuf2.0-dev libgtk-3-dev libxss-dev
