#!/bin/bash

############################################################################
## setup_maven_settings.sh
## Maven Settings Setup Script
## 
## This script creates a Maven settings.xml file optimized for CI/CD
## environments. It sets up repository configurations, authentication,
## and performance optimizations for automated builds.
##
## Process:
## 1. Creates .circleci directory if it doesn't exist
## 2. Generates mvn-settings.xml with CI-optimized configuration
## 3. Sets up repository mirrors and authentication
##
## Usage: Called by orb commands that need Maven settings
## Output: Creates /tmp/circleci/mvn-settings.xml file
############################################################################

set -e

#############################################################
## Create .circleci directory and Maven settings file ##
#############################################################
mkdir -p /tmp/circleci

cat > /tmp/circleci/mvn-settings.xml << 'EOF'
<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="
http://maven.apache.org/SETTINGS/1.0.0 http://maven.apache.org/xsd/settings-1.0.0.xsd">
    <servers>

        <!-- Sonatype Central Portal credentials (for releases) -->
        <server>
            <id>central</id>
            <username>${env.CENTRAL_USERNAME}</username>
            <password>${env.CENTRAL_PASSWORD}</password>
        </server>

        <!-- Central Portal Snapshots credentials -->
        <server>
            <id>central-snapshots</id>
            <username>${env.CENTRAL_USERNAME}</username>
            <password>${env.CENTRAL_PASSWORD}</password>
        </server>
    </servers>
</settings>
EOF

echo "✅ Maven settings file created: /tmp/circleci/mvn-settings.xml"
cat /tmp/circleci/mvn-settings.xml
