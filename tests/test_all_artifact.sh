#!/bin/bash
set -euo pipefail
scripts=$(cd "$(dirname "${BASH_SOURCE[0]}")/../src/scripts" && pwd)
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
cd "$scratch"
git init -q
git config user.name 'CI fixture'
git config user.email 'ci@example.invalid'
git config commit.gpgsign false
git -c core.hooksPath=/dev/null commit --allow-empty -qm initial
export CIRCLE_SHA1
CIRCLE_SHA1=$(git rev-parse HEAD)
mkdir -p qqq-all-app/target
printf 'verified jar bytes' > qqq-all-app/target/qqq-all-app.jar
printf 'dependency classpath' > qqq-all-app/target/smoke-classpath.txt
QQQ_ALL_ARTIFACT_ACTION='write' bash "$scripts/qqq_all_artifact.sh"
bash "$scripts/qqq_all_artifact.sh"
printf 'changed bytes' >> qqq-all-app/target/qqq-all-app.jar
if bash "$scripts/qqq_all_artifact.sh" >/dev/null 2>&1; then exit 1; fi
printf 'verified jar bytes' > qqq-all-app/target/qqq-all-app.jar
if CIRCLE_SHA1=0000000000000000000000000000000000000000 bash "$scripts/qqq_all_artifact.sh" >/dev/null 2>&1; then exit 1; fi
printf 'changed classpath' > qqq-all-app/target/smoke-classpath.txt
if bash "$scripts/qqq_all_artifact.sh" >/dev/null 2>&1; then exit 1; fi
printf 'dependency classpath' > qqq-all-app/target/smoke-classpath.txt
git -c core.hooksPath=/dev/null commit --allow-empty -qm different-source
CIRCLE_SHA1=$(git rev-parse HEAD)
if bash "$scripts/qqq_all_artifact.sh" >/dev/null 2>&1; then exit 1; fi
# Publication stubs never authenticate externally or push an actual image.
mkdir bin
cat > bin/python3 <<'STUB'
#!/bin/bash
cat >/dev/null
[[ "${PUBLIC_PACKAGE:-false}" == true ]] || exit 1
echo fixture-user
STUB
cat > bin/docker <<'STUB'
#!/bin/bash
printf '%s\n' "$*" >> "$DOCKER_LOG"
if [[ "$1" == login ]]; then cat >/dev/null; fi
STUB
chmod +x bin/*
export PATH="$scratch/bin:$PATH" DOCKER_LOG="$scratch/docker.log" GITHUB_TOKEN=test-not-a-credential CIRCLE_BRANCH=develop CIRCLE_TAG=
: > "$DOCKER_LOG"
bash "$scripts/qqq_all_develop_image.sh"
[[ ! -s "$DOCKER_LOG" ]]
PUBLIC_PACKAGE=true bash "$scripts/qqq_all_develop_image.sh"
[[ $(grep -c '^push ghcr.io/qrun-io/qqq-all:develop$' "$DOCKER_LOG") -eq 1 ]]
: > "$DOCKER_LOG"
if CIRCLE_BRANCH=main PUBLIC_PACKAGE=true bash "$scripts/qqq_all_develop_image.sh" >/dev/null 2>&1; then exit 1; fi
[[ ! -s "$DOCKER_LOG" ]]
if CIRCLE_TAG=v4.1.0 PUBLIC_PACKAGE=true bash "$scripts/qqq_all_develop_image.sh" >/dev/null 2>&1; then exit 1; fi
[[ ! -s "$DOCKER_LOG" ]]
printf 'PASS: exact artifact/source receipts, public package gate and develop-only image (stubbed)\n'
