#!/bin/bash
set -e

mvn -s .circleci/mvn-settings.xml -T4 --no-transfer-progress install -DskipTests
mvn -s .circleci/mvn-settings.xml -T4 --no-transfer-progress -pl qqq-middleware-javalin package appassembler:assemble -DskipTests
qqq-middleware-javalin/target/appassembler/bin/ValidateApiVersions -r $(pwd)
