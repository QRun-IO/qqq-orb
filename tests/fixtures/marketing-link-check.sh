#!/usr/bin/env bash
set -euo pipefail
npm run start > /tmp/qqq-link-server.log 2>&1 &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true; wait "$server_pid" 2>/dev/null || true' EXIT
ready=false
for _attempt in {1..60}; do
  if ! kill -0 "$server_pid" 2>/dev/null; then
    cat /tmp/qqq-link-server.log
    exit 1
  fi
  if curl --fail --silent --output /dev/null --max-time 2 http://localhost:3005/; then
    ready=true
    break
  fi
  sleep 1
done
if [ "$ready" != true ]; then
  cat /tmp/qqq-link-server.log
  echo 'Marketing server did not become ready on port 3005' >&2
  exit 1
fi
npm run check-links
