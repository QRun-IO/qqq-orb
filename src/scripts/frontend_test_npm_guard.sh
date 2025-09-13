#!/bin/bash

############################################################################
## frontend_test_npm_guard.sh
## Ensure Node Dependencies Exist
## 
## This script ensures Node.js dependencies are available
## for frontend testing, installing them if missing.
##
## Usage: Called by frontend_test command
## Output: Ensures node_modules exists
############################################################################

set -e

echo "Ensuring Node dependencies exist (optional guard)"
if [ ! -d node_modules ]; then
  echo "//registry.npmjs.org/:_authToken=${NPM_TOKEN}" >> ~/.npmrc || true
  npm ci --legacy-peer-deps
fi
