#!/bin/bash
set -e

echo "Running PMD static analysis..."

# Default to report-only mode unless PMD_FAIL_ON_VIOLATION is set
FAIL_FLAG=""
if [ "${PMD_FAIL_ON_VIOLATION}" = "true" ]; then
    FAIL_FLAG="-Dpmd.failOnViolation=true"
fi

# Run PMD
mvn pmd:check -DskipTests ${FAIL_FLAG} 2>&1 | tee /tmp/pmd-output.txt

# Summarize results
echo ""
echo "=== PMD Summary ==="
find . -name "pmd.xml" -exec sh -c '
    MODULE=$(dirname "$1" | sed "s|^\./||;s|/target.*||")
    COUNT=$(grep -c "<violation" "$1" 2>/dev/null || echo "0")
    echo "  $MODULE: $COUNT violations"
' _ {} \; 2>/dev/null | sort || true
echo "==================="
