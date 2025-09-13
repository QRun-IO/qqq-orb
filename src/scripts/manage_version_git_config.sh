#!/bin/bash

############################################################################
## manage_version_git_config.sh
## Git Configuration Setup Script
## 
## This script configures Git identity for automated version commits.
## It sets up the Git user email and name for CircleCI to make
## automated commits when versions are updated.
##
## Process:
## 1. Sets Git user email to CI address
## 2. Sets Git user name to CircleCI
##
## Usage: Called by CircleCI orb command manage_version
## Output: Configures Git identity for automated commits
############################################################################

set -e

##################################################
## Configure Git identity for automated commits ##
##################################################
git config user.email "ci@kingsrook.com"
git config user.name "CircleCI"
