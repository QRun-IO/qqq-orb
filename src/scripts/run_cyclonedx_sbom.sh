#!/bin/bash
set -e

echo "Generating CycloneDX SBOM..."

##################################
## Run CycloneDX Maven plugin   ##
##################################
mvn -s /tmp/circleci/mvn-settings.xml \
    --no-transfer-progress \
    org.cyclonedx:cyclonedx-maven-plugin:2.9.1:makeAggregateBom \
    -DskipTests \
    -DoutputFormat=json \
    -DoutputName=bom

##################################
## Collect SBOM output          ##
##################################
echo ""
echo "=== CycloneDX SBOM Summary ==="
if [ -f target/bom.json ]; then
    COMPONENTS=$(python3 -c "import json; r=json.load(open('target/bom.json')); print(len(r.get('components', [])))" 2>/dev/null || echo "unknown")
    echo "  Components: ${COMPONENTS}"
    cp target/bom.json /tmp/cyclonedx-sbom.json
else
    # Multi-module projects may output to different location
    BOM_FILE=$(find . -name "bom.json" -path "*/target/*" | head -1)
    if [ -n "${BOM_FILE}" ]; then
        COMPONENTS=$(python3 -c "import json; r=json.load(open('${BOM_FILE}')); print(len(r.get('components', [])))" 2>/dev/null || echo "unknown")
        echo "  Components: ${COMPONENTS}"
        cp "${BOM_FILE}" /tmp/cyclonedx-sbom.json
    else
        echo "  No SBOM generated"
    fi
fi
echo "==============================="

echo "CycloneDX SBOM generation complete"
