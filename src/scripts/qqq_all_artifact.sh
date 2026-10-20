#!/bin/bash
set -euo pipefail
python3 - <<'PYTHON'
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
if not re.fullmatch(r"[0-9a-f]{40}", sha) or sha != os.environ.get("CIRCLE_SHA1"):
    raise SystemExit("Artifact checkout does not match the pipeline SHA")
paths = ["qqq-all-app/target/qqq-all-app.jar", "qqq-all-app/target/smoke-classpath.txt"]
actual = {"sha": sha, "artifacts": {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}}
receipt = Path(".qqq-ci-artifact.json")
action = os.environ.get("QQQ_ALL_ARTIFACT_ACTION", "check")
if action == "write":
    receipt.write_text(json.dumps(actual, sort_keys=True) + "\n", encoding="utf-8")
elif action == "check":
    if json.loads(receipt.read_text(encoding="utf-8")) != actual:
        raise SystemExit("Artifact or source identity differs from the verified build")
else:
    raise SystemExit("Unknown artifact receipt action")
print("Verified qqq-all artifact identity for " + sha)
PYTHON
