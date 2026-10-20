#!/usr/bin/env bash
set -euo pipefail
mvn -B -ntp --update-snapshots -pl qqq-all-app -am \
  dependency:build-classpath -DincludeGroupIds=com.kingsrook.qqq,com.kingsrook.qbits \
  -Dmdep.outputFile=target/smoke-classpath.txt
