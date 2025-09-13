#!/bin/bash
set -e

mvn -s .circleci/mvn-settings.xml -T4 --no-transfer-progress compile
