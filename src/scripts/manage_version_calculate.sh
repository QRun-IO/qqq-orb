#!/bin/bash
set -e

chmod +x .circleci/calculate-version.sh
.circleci/calculate-version.sh
