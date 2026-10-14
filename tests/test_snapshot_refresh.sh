#!/bin/bash
# Asserts that every Maven build/test entry point refreshes SNAPSHOT dependencies.
# The ~/.m2 cache is keyed only on the pom checksum, so without --update-snapshots
# a cached SNAPSHOT is never re-checked within Maven's daily update window.
set -u
cd "$(dirname "$0")/.." || exit 1
fail=0
for f in src/scripts/mvn_build_compile.sh src/scripts/mvn_verify.sh src/scripts/frontend_build_compile.sh src/scripts/frontend_test_run.sh; do
  if grep -E '^mvn ' "$f" | grep -q -- '--update-snapshots'; then
    echo "PASS $f"
  else
    echo "FAIL $f: mvn invocation lacks --update-snapshots"; fail=1
  fi
done
exit $fail
