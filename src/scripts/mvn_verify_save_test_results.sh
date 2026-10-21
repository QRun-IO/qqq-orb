#!/bin/bash
# Collect unit and integration JUnit reports without losing same-named module suites.
set -euo pipefail

mkdir -p "$HOME/test-results/junit"
while IFS= read -r -d '' report; do
   destination="$HOME/test-results/junit/${report#./}"
   mkdir -p "$(dirname "$destination")"
   cp "$report" "$destination"
done < <(find . -type f \( -path '*/target/surefire-reports/TEST-*.xml' -o -path '*/target/failsafe-reports/TEST-*.xml' \) -print0)
