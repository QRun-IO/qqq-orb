#!/bin/bash
# Exercise the actual collector with colliding suites, spaces and non-JUnit XML.
set -euo pipefail
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../src/scripts" && pwd)
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
export HOME="$scratch/home"
mkdir -p "$scratch/repo"
cd "$scratch/repo"

# A repository with no tests is valid.
bash "$script_dir/mvn_verify_save_test_results.sh"
[[ -d "$HOME/test-results/junit" ]]
[[ -z "$(find "$HOME/test-results/junit" -type f -print)" ]]

for module in 'module one' 'module two'; do
   for runner in surefire failsafe; do
      report="$module/target/$runner-reports/TEST-shared.xml"
      mkdir -p "$(dirname "$report")"
      printf '<testsuite name="%s %s"/>\n' "$module" "$runner" > "$report"
   done
done
printf '<failsafe-summary/>\n' > 'module one/target/failsafe-reports/failsafe-summary.xml'
printf '<configuration/>\n' > 'module one/target/surefire-reports/configuration.xml'
mkdir -p unrelated
printf '<testsuite/>\n' > unrelated/TEST-ignore.xml
bash "$script_dir/mvn_verify_save_test_results.sh"
[[ "$(find "$HOME/test-results/junit" -type f | wc -l)" -eq 4 ]]
for module in 'module one' 'module two'; do
   for runner in surefire failsafe; do
      report="$module/target/$runner-reports/TEST-shared.xml"
      cmp "$report" "$HOME/test-results/junit/$report"
   done
done
printf 'PASS: unit/integration reports, module collisions, spaces, exclusions and no tests\n'
