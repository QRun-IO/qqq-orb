#!/bin/bash
set -e

echo "Running Semgrep SAST analysis..."

##################################
## Install Semgrep              ##
##################################
pip3 install --quiet semgrep

##################################
## Run Semgrep scan             ##
##################################
EXIT_CODE=0
semgrep scan \
    --config "${SEMGREP_RULESETS// / --config }" \
    --json --output /tmp/semgrep-report.json \
    --sarif --sarif-output /tmp/semgrep-report.sarif \
    --metrics=off \
    . \
    || EXIT_CODE=$?

##################################
## Summarize results            ##
##################################
echo ""
echo "=== Semgrep Summary ==="
if [ -f /tmp/semgrep-report.json ]; then
    COUNT=$(python3 -c "import json; r=json.load(open('/tmp/semgrep-report.json')); print(len(r.get('results', [])))" 2>/dev/null || echo "unknown")
    echo "  Findings: ${COUNT}"
else
    echo "  Findings: 0"
fi
echo "========================"

##################################
## Handle fail_on flag          ##
##################################
if [ "${SEMGREP_FAIL_ON_FINDINGS}" = "true" ] && [ "${EXIT_CODE}" -ne 0 ]; then
    echo "Semgrep found issues and fail_on_semgrep is enabled. Failing build."
    exit 1
fi

echo "Semgrep scan complete (exit code: ${EXIT_CODE})"
