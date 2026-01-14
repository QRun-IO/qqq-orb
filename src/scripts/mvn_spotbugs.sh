#!/bin/bash
set -e

echo "Running SpotBugs static analysis..."

# Default to report-only mode unless SPOTBUGS_FAIL_ON_ERROR is set
FAIL_FLAG=""
if [ "${SPOTBUGS_FAIL_ON_ERROR}" = "true" ]; then
    FAIL_FLAG="-Dspotbugs.failOnError=true"
fi

# Run SpotBugs
mvn spotbugs:check -DskipTests ${FAIL_FLAG} 2>&1 | tee /tmp/spotbugs-output.txt

# Summarize results
echo ""
echo "=== SpotBugs Summary ==="
find . -name "spotbugsXml.xml" -exec sh -c '
    MODULE=$(dirname "{}" | sed "s|^\./||;s|/target.*||")
    COUNT=$(grep -c "<BugInstance" "{}" 2>/dev/null || echo "0")
    echo "  $MODULE: $COUNT bugs"
' \; 2>/dev/null | sort || true
echo "========================"
