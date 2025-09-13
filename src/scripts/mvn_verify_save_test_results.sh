#!/bin/bash
set -e

mkdir -p ~/test-results/junit/
find . -type f -regex ".*/target/surefire-reports/.*xml" -exec cp {} ~/test-results/junit/ \;
