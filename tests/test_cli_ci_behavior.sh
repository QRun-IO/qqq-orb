#!/bin/bash
# Stub package commands and HTTP: no package publication or external network.
set -euo pipefail
scripts=$(cd "$(dirname "${BASH_SOURCE[0]}")/../src/scripts" && pwd)
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
cd "$scratch"
mkdir -p bin node_modules/.bin packages/{ui-api-client,core,conformance,cli}/src
export CLI_LOG="$scratch/commands" PRISM_PID_FILE="$scratch/prism-pid" CONFIG_PATH_FILE="$scratch/npm-config-path"
cat > bin/npm <<'STUB'
#!/bin/bash
printf '%s\n' "$*" >> "$CLI_LOG"
if [[ "$1" == whoami ]]; then
  [[ "${FAIL_AUTH:-false}" != true ]] || exit 42
  grep -Fq '${NODE_AUTH_TOKEN}' "$NPM_CONFIG_USERCONFIG" || exit 43
  printf '%s' "$NPM_CONFIG_USERCONFIG" > "$CONFIG_PATH_FILE"
fi
if [[ "$1" == test && "${FAIL_TEST:-false}" == true ]]; then exit 44; fi
STUB
cat > bin/git <<'STUB'
#!/bin/bash
[[ "${FAIL_DRIFT:-false}" != true ]]
STUB
cat > bin/curl <<'STUB'
#!/bin/bash
if [[ "$*" == *authentication* && "${FAIL_SMOKE:-false}" == true ]]; then exit 45; fi
exit 0
STUB
cat > node_modules/.bin/prism <<'STUB'
#!/bin/bash
printf '%s' "$$" > "$PRISM_PID_FILE"
exec sleep 60
STUB
chmod +x bin/* node_modules/.bin/prism
export PATH="$scratch/bin:$PATH"
: > "$CLI_LOG"
bash "$scripts/cli_verify.sh"
[[ "$(cat "$CLI_LOG")" == $'run generate\nrun build\ntest\nrun lint' ]]
if [[ -e "$PRISM_PID_FILE" ]] && kill -0 "$(cat "$PRISM_PID_FILE")" 2>/dev/null; then
  echo 'Prism process survived cleanup' >&2
  exit 1
fi
: > "$CLI_LOG"
if FAIL_DRIFT=true bash "$scripts/cli_verify.sh"; then exit 1; fi
[[ "$(cat "$CLI_LOG")" == 'run generate' ]]
: > "$CLI_LOG"
if FAIL_TEST=true bash "$scripts/cli_verify.sh"; then exit 1; fi
[[ "$(grep -c '^test$' "$CLI_LOG")" -eq 1 ]]
if FAIL_SMOKE=true bash "$scripts/cli_verify.sh"; then exit 1; fi
if [[ -e "$PRISM_PID_FILE" ]] && kill -0 "$(cat "$PRISM_PID_FILE")" 2>/dev/null; then
  echo 'Prism process survived cleanup' >&2
  exit 1
fi
write_packages() {
  local core_version=$1 core_dependency=$2 item dir name version
  for item in 'ui-api-client qqq-ui-api-client 1.6.0-rc.1' "core qqq-core $core_version" 'conformance qqq-ui-api-conformance 1.6.0-rc.1' 'cli qqq-cli 0.1.0-rc.1'; do
    read -r dir name version <<< "$item"
    printf '{"name":"@qrun-io/%s","version":"%s","publishConfig":{"registry":"https://npm.pkg.github.com"},"dependencies":{"@qrun-io/qqq-core":"%s"}}\n' "$name" "$version" "$core_dependency" > "packages/$dir/package.json"
  done
}
write_packages 0.1.0-rc.1 0.1.0-rc.1
export CIRCLE_TAG=v1.6.0-rc.1 GITHUB_TOKEN=test-not-a-credential
: > "$CLI_LOG"
bash "$scripts/cli_publish.sh"
[[ "$(grep '^publish ' "$CLI_LOG" | cut -d' ' -f3)" == $'@qrun-io/qqq-ui-api-client\n@qrun-io/qqq-core\n@qrun-io/qqq-ui-api-conformance\n@qrun-io/qqq-cli' ]]
[[ $(grep -c -- '--tag rc$' "$CLI_LOG") -eq 4 ]]
[[ $(grep -c '^test$' "$CLI_LOG" || true) -eq 0 ]]
[[ ! -e "$(cat "$CONFIG_PATH_FILE")" ]]
for condition in wrong-tag missing-token denied-auth core-version core-dependency; do
  : > "$CLI_LOG"
  write_packages 0.1.0-rc.1 0.1.0-rc.1
  case "$condition" in
    core-version) write_packages 0.1.0-rc.2 0.1.0-rc.2; if bash "$scripts/cli_publish.sh" >/dev/null 2>&1; then exit 1; fi ;;
    core-dependency) write_packages 0.1.0-rc.1 0.1.0-rc.0; if bash "$scripts/cli_publish.sh" >/dev/null 2>&1; then exit 1; fi ;;
    wrong-tag) if CIRCLE_TAG=v0.1.0 bash "$scripts/cli_publish.sh" >/dev/null 2>&1; then exit 1; fi ;;
    missing-token) if GITHUB_TOKEN='' bash "$scripts/cli_publish.sh" >/dev/null 2>&1; then exit 1; fi ;;
    denied-auth) if FAIL_AUTH=true bash "$scripts/cli_publish.sh" >/dev/null 2>&1; then exit 1; fi ;;
  esac
  if grep -q '^publish ' "$CLI_LOG"; then
    echo "Publication occurred despite $condition" >&2
    exit 1
  fi
done
printf 'PASS: CLI validation once, drift/test/smoke failures, cleanup, tag/core-version/auth checks and four rc publishes (stubbed)\n'
