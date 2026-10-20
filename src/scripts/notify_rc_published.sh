#!/bin/bash
set -euo pipefail

# Called only after deploy and git_operations succeeded. No credential in argv/logs.
python3 - <<'PYTHON'
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def require(condition, message):
    if not condition:
        raise SystemExit(message)


branch = os.environ.get("CIRCLE_BRANCH", "")
merge = os.environ.get("CIRCLE_SHA1", "")
owner = os.environ.get("CIRCLE_PROJECT_USERNAME", "")
repo = os.environ.get("CIRCLE_PROJECT_REPONAME", "")
require(re.fullmatch(r"release/[A-Za-z0-9._/-]+", branch), "RC completion requires a release branch")
require(re.fullmatch(r"[0-9a-f]{40}", merge), "RC completion requires the exact pipeline SHA")
require(re.fullmatch(r"[A-Za-z0-9_.-]+", owner) and re.fullmatch(r"[A-Za-z0-9_.-]+", repo), "Invalid repository identity")
bump = git("rev-parse", "HEAD")
marker = Path(os.environ.get("QQQ_PUSHED_VERSION_FILE", "/tmp/circleci/qqq-pushed-version"))
require(marker.is_file() and marker.read_text().strip() == bump, "No acknowledged push for this bump")
require(git("show", "-s", "--format=%P", "HEAD") == merge, "Bump must have exactly the pipeline SHA as its parent")
remote = git("ls-remote", "--exit-code", "origin", "refs/heads/" + branch).split()
require(len(remote) == 2 and remote == [bump, "refs/heads/" + branch], "Remote release head no longer matches the pushed bump")
root = ET.parse("pom.xml").getroot()
ns = {"m": "http://maven.apache.org/POM/4.0.0"}
revision = root.find("m:properties/m:revision", ns) if root.tag.startswith("{") else root.find("properties/revision")
version = revision.text.strip() if revision is not None and revision.text else ""
require(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-RC\.[0-9]+", version), "Published version must be an RC revision")
require(git("show", "-s", "--format=%s", "HEAD") == "Bump version to " + version + " [skip ci]", "Unexpected version commit")
require(not git("status", "--porcelain", "pom.xml"), "Published POM differs from the bump commit")
token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
require(token, "GitHub write credential is required for RC completion")
payload = {"event_type": "qbit-rc-published", "client_payload": {"merge_sha": merge, "bump_sha": bump, "branch": branch, "version": version}}
request = urllib.request.Request(
    "https://api.github.com/repos/" + owner + "/" + repo + "/dispatches",
    data=json.dumps(payload).encode(), method="POST",
    headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json", "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28"},
)
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        require(response.status == 204, "GitHub did not acknowledge RC completion")
except urllib.error.HTTPError as error:
    raise SystemExit("RC completion dispatch failed (HTTP " + str(error.code) + ")") from None
except urllib.error.URLError:
    raise SystemExit("RC completion dispatch failed (network error)") from None
print("Dispatched RC completion for " + version + " at " + bump)
PYTHON
