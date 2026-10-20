#!/bin/bash
set -euo pipefail

npm run generate
git diff --exit-code -- packages/ui-api-client/src/schema.ts
npm run build
npm test

# Use the locked local executable; never download an unpinned npx fallback.
./node_modules/.bin/prism mock --port 4010 packages/ui-api-client/openapi/qqq-v1.json > prism.log 2>&1 &
prism_pid=$!
cleanup() {
  kill "$prism_pid" 2>/dev/null || true
  wait "$prism_pid" 2>/dev/null || true
}
trap cleanup EXIT
ready=false
for ((attempt = 0; attempt < 30; attempt++)); do
  if ! kill -0 "$prism_pid" 2>/dev/null; then
    echo "Prism exited before readiness; see prism.log" >&2
    exit 1
  fi
  if curl --connect-timeout 2 --max-time 3 -fsS http://127.0.0.1:4010/qqq/v1/version >/dev/null; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "$ready" != true ]]; then
  echo "Prism readiness timed out; see prism.log" >&2
  exit 1
fi
curl --connect-timeout 2 --max-time 3 -fsS http://127.0.0.1:4010/qqq/v1/metaData/authentication >/dev/null
