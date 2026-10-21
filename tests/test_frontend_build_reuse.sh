#!/bin/bash
# Exercise the actual test runner with no server, browser, network or Maven work.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
mkdir "$scratch/bin"
export RUN_LOG="$scratch/calls"
cat > "$scratch/bin/npm" <<'STUB'
#!/bin/bash
printf 'npm %s\n' "$*" >> "$RUN_LOG"
if [[ "$*" == 'run build' && ${BUILD_FAIL:-0} == 1 ]]; then exit 12; fi
STUB
for tool in mvn dockerize; do
  # shellcheck disable=SC2016
  printf '#!/bin/bash\nprintf "%s %%s\\n" "$*" >> "$RUN_LOG"\n' "$tool" > "$scratch/bin/$tool"
done
chmod +x "$scratch/bin/"*
export PATH="$scratch/bin:$PATH"
cd "$scratch"
PARAM_BUILD_BEFORE_TEST=false bash "$root/src/scripts/frontend_test_run.sh" >/dev/null
if grep -qx 'npm run build' "$RUN_LOG"; then
  echo 'FAIL: combined job rebuilt the already-built React app' >&2; exit 1
fi
grep -q '^mvn .* -B test$' "$RUN_LOG"
echo 'PASS: combined job retains tests without a duplicate build'

: > "$RUN_LOG"
bash "$root/src/scripts/frontend_test_run.sh" >/dev/null
grep -qx 'npm run build' "$RUN_LOG"
grep -q '^mvn .* -B test$' "$RUN_LOG"
: > "$RUN_LOG"
if BUILD_FAIL=1 bash "$root/src/scripts/frontend_test_run.sh" >/dev/null 2>&1; then
  echo 'FAIL: required standalone build failure ignored' >&2; exit 1
fi
if grep -q '^mvn ' "$RUN_LOG"; then exit 1; fi
echo 'PASS: standalone command still builds and fails before tests when its build fails'
