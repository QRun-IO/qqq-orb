#!/bin/bash
set -e

echo "Running Gitleaks secret detection..."

##################################
## Install Gitleaks binary      ##
##################################
GITLEAKS_VERSION="8.21.2"
curl -sSfL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" \
    | tar -xz -C /tmp
chmod +x /tmp/gitleaks

##################################
## Run Gitleaks scan            ##
##################################
EXIT_CODE=0
/tmp/gitleaks detect \
    --source=. \
    --report-format=json \
    --report-path=/tmp/gitleaks-report.json \
    --verbose \
    || EXIT_CODE=$?

##################################
## Summarize results            ##
##################################
echo ""
echo "=== Gitleaks Summary ==="
if [ -f /tmp/gitleaks-report.json ]; then
    COUNT=$(python3 -c "import json; print(len(json.load(open('/tmp/gitleaks-report.json'))))" 2>/dev/null || echo "unknown")
    echo "  Findings: ${COUNT}"
else
    echo "  Findings: 0"
fi
echo "========================="

##################################
## Handle fail_on flag          ##
##################################
if [ "${GITLEAKS_FAIL_ON_FINDINGS}" = "true" ] && [ "${EXIT_CODE}" -ne 0 ]; then
    echo "Gitleaks found secrets and fail_on_gitleaks is enabled. Failing build."
    exit 1
fi

echo "Gitleaks scan complete (exit code: ${EXIT_CODE})"
