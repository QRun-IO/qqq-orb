#!/bin/bash
set -e

mvn -s .circleci/mvn-settings.xml -P release -B -DskipTests -Dgpg.keyname=$GPG_KEYNAME -Dgpg.passphrase=$GPG_PASSPHRASE deploy
