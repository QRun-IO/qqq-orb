#!/bin/bash

# Collect SpotBugs and PMD reports to a central location for artifacts
REPORT_DIR="/home/circleci/static-analysis-reports"
mkdir -p "$REPORT_DIR/spotbugs" "$REPORT_DIR/pmd"

echo "Collecting static analysis reports..."

# Collect SpotBugs reports
find . -name "spotbugsXml.xml" -exec sh -c '
    MODULE=$(dirname "{}" | sed "s|^\./||;s|/target.*||" | tr "/" "_")
    cp "{}" "'"$REPORT_DIR/spotbugs"'/${MODULE}_spotbugs.xml" 2>/dev/null || true
' \;

# Collect PMD reports
find . -name "pmd.xml" -exec sh -c '
    MODULE=$(dirname "{}" | sed "s|^\./||;s|/target.*||" | tr "/" "_")
    cp "{}" "'"$REPORT_DIR/pmd"'/${MODULE}_pmd.xml" 2>/dev/null || true
' \;

# Generate combined summary
echo "=== Static Analysis Report Summary ===" > "$REPORT_DIR/summary.txt"
echo "Generated: $(date)" >> "$REPORT_DIR/summary.txt"
echo "" >> "$REPORT_DIR/summary.txt"

echo "SpotBugs:" >> "$REPORT_DIR/summary.txt"
ls -1 "$REPORT_DIR/spotbugs"/*.xml 2>/dev/null | while read f; do
    MODULE=$(basename "$f" _spotbugs.xml)
    COUNT=$(grep -c "<BugInstance" "$f" 2>/dev/null || echo "0")
    echo "  $MODULE: $COUNT bugs" >> "$REPORT_DIR/summary.txt"
done

echo "" >> "$REPORT_DIR/summary.txt"
echo "PMD:" >> "$REPORT_DIR/summary.txt"
ls -1 "$REPORT_DIR/pmd"/*.xml 2>/dev/null | while read f; do
    MODULE=$(basename "$f" _pmd.xml)
    COUNT=$(grep -c "<violation" "$f" 2>/dev/null || echo "0")
    echo "  $MODULE: $COUNT violations" >> "$REPORT_DIR/summary.txt"
done

cat "$REPORT_DIR/summary.txt"
echo ""
echo "Reports collected to: $REPORT_DIR"
