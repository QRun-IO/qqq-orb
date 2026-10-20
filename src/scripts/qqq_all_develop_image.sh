#!/bin/bash
set -euo pipefail
[[ "${CIRCLE_BRANCH:-}" == develop && -z "${CIRCLE_TAG:-}" ]] || { echo "Develop image requires develop branch" >&2; exit 1; }
# Retain the original public-package gate: no implicit package visibility changes.
: "${GITHUB_TOKEN:?GitHub Packages credential required}"
if ! registry_user=$(python3 - <<'PYTHON'
import json
import os
import urllib.error
import urllib.request

def get(path):
    request = urllib.request.Request("https://api.github.com/" + path,
        headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"], "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

try:
    if get("orgs/QRun-IO/packages/container/qqq-all").get("visibility") != "public":
        raise SystemExit(1)
    user = get("user").get("login")
    if not isinstance(user, str) or not user:
        raise SystemExit(1)
    print(user)
except (urllib.error.URLError, ValueError):
    raise SystemExit(1) from None
PYTHON
); then
  echo "Skipped image publication: qqq-all package is not publicly readable by this credential"
  exit 0
fi
printf '%s' "$GITHUB_TOKEN" | docker login ghcr.io -u "$registry_user" --password-stdin
docker build --label org.opencontainers.image.source=https://github.com/QRun-IO/qqq-all --tag ghcr.io/qrun-io/qqq-all:develop .
docker push ghcr.io/qrun-io/qqq-all:develop
