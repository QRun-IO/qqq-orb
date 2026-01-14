#!/bin/bash

# Collect SpotBugs and PMD reports to a central location for artifacts
REPORT_DIR="/home/circleci/static-analysis-reports"
mkdir -p "$REPORT_DIR/spotbugs" "$REPORT_DIR/pmd"

echo "Collecting static analysis reports..."

# Collect SpotBugs reports
find . -name "spotbugsXml.xml" -exec sh -c '
    MODULE=$(dirname "$1" | sed "s|^\./||;s|/target.*||" | tr "/" "_")
    cp "$1" "'"$REPORT_DIR/spotbugs"'/${MODULE}_spotbugs.xml" 2>/dev/null || true
' _ {} \;

# Collect PMD reports
find . -name "pmd.xml" -exec sh -c '
    MODULE=$(dirname "$1" | sed "s|^\./||;s|/target.*||" | tr "/" "_")
    cp "$1" "'"$REPORT_DIR/pmd"'/${MODULE}_pmd.xml" 2>/dev/null || true
' _ {} \;

# Generate combined summary
{
    echo "=== Static Analysis Report Summary ==="
    echo "Generated: $(date)"
    echo ""
    echo "SpotBugs:"
} > "$REPORT_DIR/summary.txt"

find "$REPORT_DIR/spotbugs" -name "*.xml" 2>/dev/null | while read -r f; do
    MODULE=$(basename "$f" _spotbugs.xml)
    COUNT=$(grep -c "<BugInstance" "$f" 2>/dev/null || echo "0")
    echo "  $MODULE: $COUNT bugs" >> "$REPORT_DIR/summary.txt"
done

echo "" >> "$REPORT_DIR/summary.txt"
echo "PMD:" >> "$REPORT_DIR/summary.txt"

find "$REPORT_DIR/pmd" -name "*.xml" 2>/dev/null | while read -r f; do
    MODULE=$(basename "$f" _pmd.xml)
    COUNT=$(grep -c "<violation" "$f" 2>/dev/null || echo "0")
    echo "  $MODULE: $COUNT violations" >> "$REPORT_DIR/summary.txt"
done

cat "$REPORT_DIR/summary.txt"
echo ""
echo "Reports collected to: $REPORT_DIR"
