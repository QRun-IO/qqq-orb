#!/bin/bash

############################################################################
## frontend_package_jar.sh
## Package React App into Maven JAR
## 
## This script packages the React application build artifacts
## into the Maven JAR structure for deployment.
##
## Usage: Called by frontend_package command
## Output: Copies build artifacts to src/main/resources/material-dashboard
############################################################################

set -e

echo "Packaging React app into Maven JAR"
rm -rf src/main/resources/material-dashboard
mkdir -p src/main/resources/material-dashboard
cp -r build/* src/main/resources/material-dashboard
