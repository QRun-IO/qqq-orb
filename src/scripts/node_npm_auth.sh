#!/bin/bash

############################################################################
## node_npm_auth.sh
## NPM Authentication Setup Script
## 
## This script configures NPM authentication for publishing to the public registry.
## It sets up the authentication token and verifies the authentication.
##
## Process:
## 1. Configures NPM authentication for public registry
## 2. Verifies authentication by checking current user
##
## Usage: Called by node_publish command
## Output: Sets up NPM authentication and verifies it
############################################################################

set -e

echo "Configuring NPM authentication for public registry"
echo "//registry.npmjs.org/:_authToken=${NPM_TOKEN}" > ~/.npmrc

echo "Verifying authentication by checking current user"
npm whoami
