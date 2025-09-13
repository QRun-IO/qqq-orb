#!/bin/bash

############################################################################
## frontend_test_dockerize.sh
## Install Dockerize Utility
## 
## This script installs dockerize utility for waiting
## for services to become available during testing.
##
## Usage: Called by frontend_test command
## Output: Installs dockerize binary
############################################################################

set -e

echo "Installing dockerize (wait-for utility)"
DOCKERIZE_VERSION=v0.3.0
wget -q https://github.com/jwilder/dockerize/releases/download/$DOCKERIZE_VERSION/dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz
sudo tar -C /usr/local/bin -xzvf dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz
rm dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz
