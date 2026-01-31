#!/bin/bash
set -e

echo "Running OWASP Dependency-Check..."

##################################
## Build Maven command           ##
##################################
MVN_CMD="mvn -s /tmp/circleci/mvn-settings.xml --no-transfer-progress"
MVN_CMD="${MVN_CMD} org.owasp:dependency-check-maven:12.1.0:aggregate"
MVN_CMD="${MVN_CMD} -DskipTests"
MVN_CMD="${MVN_CMD} -DfailBuildOnCVSS=${OWASP_CVSS_THRESHOLD}"
MVN_CMD="${MVN_CMD} -Dformats=JSON,HTML"

# Use NVD API key if available (speeds up NVD database updates)
if [ -n "${NVD_API_KEY}" ]; then
    MVN_CMD="${MVN_CMD} -DnvdApiKey=${NVD_API_KEY}"
    echo "  NVD API key detected -- using authenticated NVD access"
else
    echo "  No NVD API key -- using unauthenticated access (slower)"
fi

##################################
## Run with retry logic (3x)    ##
##################################
MAX_RETRIES=3
ATTEMPT=1
EXIT_CODE=0

while [ "${ATTEMPT}" -le "${MAX_RETRIES}" ]; do
    echo ""
    echo "OWASP Dependency-Check attempt ${ATTEMPT}/${MAX_RETRIES}..."

    EXIT_CODE=0
    eval "${MVN_CMD}" 2>&1 | tee /tmp/owasp-output.txt || EXIT_CODE=$?

    # Exit code 1 = vulnerabilities found (expected), anything else = tool error
    if [ "${EXIT_CODE}" -eq 0 ] || [ "${EXIT_CODE}" -eq 1 ]; then
        break
    fi

    echo "Attempt ${ATTEMPT} failed with exit code ${EXIT_CODE}"
    ATTEMPT=$((ATTEMPT + 1))

    if [ "${ATTEMPT}" -le "${MAX_RETRIES}" ]; then
        echo "Retrying in 30 seconds..."
        sleep 30
    fi
done

if [ "${ATTEMPT}" -gt "${MAX_RETRIES}" ] && [ "${EXIT_CODE}" -gt 1 ]; then
    echo "OWASP Dependency-Check failed after ${MAX_RETRIES} attempts"
    echo "This is typically caused by NVD database download issues"
    exit 1
fi

##################################
## Collect reports              ##
##################################
REPORT_FILE=$(find . -name "dependency-check-report.json" -path "*/target/*" | head -1)
if [ -n "${REPORT_FILE}" ]; then
    cp "${REPORT_FILE}" /tmp/owasp-dependency-check.json
fi

HTML_REPORT=$(find . -name "dependency-check-report.html" -path "*/target/*" | head -1)
if [ -n "${HTML_REPORT}" ]; then
    cp "${HTML_REPORT}" /tmp/owasp-dependency-check.html
fi

##################################
## Summarize results            ##
##################################
echo ""
echo "=== OWASP Dependency-Check Summary ==="
if [ -f /tmp/owasp-dependency-check.json ]; then
    VULN_COUNT=$(python3 -c "
import json
r = json.load(open('/tmp/owasp-dependency-check.json'))
deps = r.get('dependencies', [])
vulns = sum(len(d.get('vulnerabilities', [])) for d in deps)
print(vulns)
" 2>/dev/null || echo "unknown")
    echo "  Vulnerabilities: ${VULN_COUNT}"
    echo "  CVSS Threshold: ${OWASP_CVSS_THRESHOLD}"
else
    echo "  No report generated"
fi
echo "======================================="

##################################
## Handle fail_on flag          ##
##################################
if [ "${OWASP_FAIL_ON_CVSS}" = "true" ] && [ "${EXIT_CODE}" -ne 0 ]; then
    echo "OWASP found CVEs above threshold and fail_on_owasp is enabled. Failing build."
    exit 1
fi

echo "OWASP Dependency-Check complete"
