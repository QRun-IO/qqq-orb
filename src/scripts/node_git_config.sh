#!/bin/bash

############################################################################
## node_git_config.sh
## Git Configuration Setup for Node.js Projects
## 
## This script sets up Git identity for version commits in Node.js projects.
## It configures the Git user email and name for CircleCI operations.
##
## Usage: Called by node_manage_version command
## Output: Configures Git identity for CI operations
############################################################################

set -e

echo "Setting up Git identity for version commits"
git config user.email "ci@kingsrook.com"
git config user.name "CircleCI"
