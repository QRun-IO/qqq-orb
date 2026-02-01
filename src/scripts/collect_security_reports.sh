#!/bin/bash

# Collect security scan reports to a central location for artifacts
REPORT_DIR="/home/circleci/security-reports"
mkdir -p "$REPORT_DIR/gitleaks" "$REPORT_DIR/semgrep" "$REPORT_DIR/owasp" "$REPORT_DIR/sbom"

echo "Collecting security scan reports..."

# Collect Gitleaks reports
if [ -f /tmp/gitleaks-report.json ]; then
    cp /tmp/gitleaks-report.json "$REPORT_DIR/gitleaks/" 2>/dev/null || true
fi

# Collect Semgrep reports
if [ -f /tmp/semgrep-report.json ]; then
    cp /tmp/semgrep-report.json "$REPORT_DIR/semgrep/" 2>/dev/null || true
fi
if [ -f /tmp/semgrep-report.sarif ]; then
    cp /tmp/semgrep-report.sarif "$REPORT_DIR/semgrep/" 2>/dev/null || true
fi

# Collect OWASP Dependency-Check reports
if [ -f /tmp/owasp-dependency-check.json ]; then
    cp /tmp/owasp-dependency-check.json "$REPORT_DIR/owasp/" 2>/dev/null || true
fi
if [ -f /tmp/owasp-dependency-check.html ]; then
    cp /tmp/owasp-dependency-check.html "$REPORT_DIR/owasp/" 2>/dev/null || true
fi

# Collect CycloneDX SBOM
if [ -f /tmp/cyclonedx-sbom.json ]; then
    cp /tmp/cyclonedx-sbom.json "$REPORT_DIR/sbom/" 2>/dev/null || true
fi

# Generate combined summary
{
    echo "=== Security Scan Report Summary ==="
    echo "Generated: $(date)"
    echo ""

    echo "Gitleaks (Secret Detection):"
    if [ -f "$REPORT_DIR/gitleaks/gitleaks-report.json" ]; then
        COUNT=$(python3 -c "import json; print(len(json.load(open('$REPORT_DIR/gitleaks/gitleaks-report.json'))))" 2>/dev/null || echo "unknown")
        echo "  Findings: ${COUNT}"
    else
        echo "  Not run or no report"
    fi

    echo ""
    echo "Semgrep (SAST):"
    if [ -f "$REPORT_DIR/semgrep/semgrep-report.json" ]; then
        COUNT=$(python3 -c "import json; r=json.load(open('$REPORT_DIR/semgrep/semgrep-report.json')); print(len(r.get('results', [])))" 2>/dev/null || echo "unknown")
        echo "  Findings: ${COUNT}"
    else
        echo "  Not run or no report"
    fi

    echo ""
    echo "OWASP Dependency-Check (CVEs):"
    if [ -f "$REPORT_DIR/owasp/owasp-dependency-check.json" ]; then
        COUNT=$(python3 -c "
import json
r = json.load(open('$REPORT_DIR/owasp/owasp-dependency-check.json'))
deps = r.get('dependencies', [])
vulns = sum(len(d.get('vulnerabilities', [])) for d in deps)
print(vulns)
" 2>/dev/null || echo "unknown")
        echo "  Vulnerabilities: ${COUNT}"
    else
        echo "  Not run or no report"
    fi

    echo ""
    echo "CycloneDX SBOM:"
    if [ -f "$REPORT_DIR/sbom/cyclonedx-sbom.json" ]; then
        COUNT=$(python3 -c "import json; r=json.load(open('$REPORT_DIR/sbom/cyclonedx-sbom.json')); print(len(r.get('components', [])))" 2>/dev/null || echo "unknown")
        echo "  Components: ${COUNT}"
    else
        echo "  Not run or no report"
    fi

    echo ""
    echo "==================================="
} > "$REPORT_DIR/summary.txt"

cat "$REPORT_DIR/summary.txt"
echo ""
echo "Reports collected to: $REPORT_DIR"
