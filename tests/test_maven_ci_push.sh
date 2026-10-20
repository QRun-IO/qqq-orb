#!/bin/bash
# Proves opt-in completion never accepts a failed push; no external remotes.
set -euo pipefail
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../src/scripts" && pwd)
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
git init -q --bare "$scratch/remote.git"
git init -q "$scratch/work"
cd "$scratch/work"
git config user.name 'CI fixture'
git config user.email 'ci@example.invalid'
git config commit.gpgsign false
git switch -q -c release/0.1
printf '<revision>0.1.0-RC.1</revision>\n' > pom.xml
git add pom.xml
git commit -qm initial
git remote add origin "$scratch/remote.git"
git push -q origin HEAD
export BRANCH_TYPE=release_candidate CIRCLE_BRANCH=release/0.1
export QQQ_PUSHED_VERSION_FILE="$scratch/pushed"
export REQUIRE_PUSHED_VERSION=true
printf '<revision>0.1.0-RC.2</revision>\n' > pom.xml
bash "$script_dir/manage_version_commit.sh" >/dev/null
[[ "$(cat "$QQQ_PUSHED_VERSION_FILE")" == "$(git rev-parse HEAD)" ]]
[[ "$(git ls-remote origin refs/heads/release/0.1 | cut -f1)" == "$(git rev-parse HEAD)" ]]
# Local server rejects the next publication. A stale prior marker must disappear.
printf '#!/bin/bash\nexit 1\n' > "$scratch/remote.git/hooks/pre-receive"
chmod +x "$scratch/remote.git/hooks/pre-receive"
printf '<revision>0.1.0-RC.3</revision>\n' > pom.xml
if bash "$script_dir/manage_version_commit.sh" >/dev/null 2>&1; then
  echo 'failed push reported success in completion mode' >&2; exit 1
fi
[[ ! -e "$QQQ_PUSHED_VERSION_FILE" ]]
# Existing callers retain their historical warning-only failed-push behavior.
export REQUIRE_PUSHED_VERSION=false
printf '<revision>0.1.0-RC.4</revision>\n' > pom.xml
bash "$script_dir/manage_version_commit.sh" >/dev/null 2>&1
printf 'PASS: acknowledged push marker, failed-push rejection and legacy compatibility\n'
