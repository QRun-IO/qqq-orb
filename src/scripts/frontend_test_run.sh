#!/bin/bash

############################################################################
## frontend_test_run.sh
## Build App, Start Server, Run Tests
## 
## This script builds the React app, starts the development server,
## waits for it to become available, then runs Selenium tests.
##
## Usage: Called by frontend_test command
## Output: Runs complete frontend test suite
############################################################################

set -e

echo "Building app, starting server, running tests"
echo "HTTPS=true" >> ./.env
npm run build
export REACT_APP_PROXY_LOCALHOST_PORT=8001
export PORT=3001
npm run start &
dockerize -wait tcp://localhost:3001 -timeout 3m
export QQQ_SELENIUM_HEADLESS=true
## --update-snapshots: the ~/.m2 cache is keyed only on the pom checksum, so
## without it a SNAPSHOT dependency restored from cache is never re-checked
## (Maven's daily update policy) and builds run against stale snapshots.
mvn -s /tmp/circleci/mvn-settings.xml --update-snapshots --no-transfer-progress -B test
