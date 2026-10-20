#!/bin/bash
set -euo pipefail

# Hash every tracked Maven descriptor, including modules and wrapper/config inputs.
# Read working-tree contents so CI version changes are represented. Never print them.
# No artifact filtering: repository caches retain snapshots, classifiers and metadata.
python3 - <<'PYTHON'
import hashlib
import os
from pathlib import Path
import subprocess

root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).split(b"\0")
inputs = []
for raw in tracked:
    if not raw:
        continue
    name = os.fsdecode(raw)
    path = Path(name)
    if path.name == "pom.xml" or ".mvn" in path.parts or path.name in ("mvnw", "mvnw.cmd"):
        inputs.append((raw, root / path))
if not any(path.name == "pom.xml" for _, path in inputs):
    raise SystemExit("No tracked Maven POM found; refusing an empty dependency fingerprint")
digest = hashlib.sha256()
for raw, path in sorted(inputs):
    content = path.read_bytes()
    # Length framing prevents ambiguous concatenations of paths and contents.
    for value in (raw, content):
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)
output = Path(os.environ.get("MAVEN_CACHE_FINGERPRINT_FILE", "/tmp/circleci/maven-cache-fingerprint"))
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(digest.hexdigest() + "\n", encoding="ascii")
PYTHON
