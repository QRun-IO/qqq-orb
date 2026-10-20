#!/usr/bin/env bash
# Execute the real release script with offline curl/git fixtures.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/bin" "$scratch/work"
cat > "$scratch/work/pom.xml" <<'EOF'
<project>
<groupId>example.fixture</groupId>
<artifactId>release-test</artifactId>
<revision>1.2.3</revision>
</project>
EOF
cat > "$scratch/bin/git" <<'EOF'
#!/usr/bin/env bash
[[ "$*" == "tag --list" ]] || exit 92
printf 'v1.2.3\n'
EOF
cat > "$scratch/bin/sleep" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat > "$scratch/bin/curl" <<'EOF'
#!/usr/bin/env bash
set -eu
count=$(cat "$MOCK_COUNT")
count=$((count + 1))
printf '%s' "$count" > "$MOCK_COUNT"
method=POST
while (($#)); do
  if [[ "$1" == "-X" ]]; then method=$2; shift; fi
  shift
done
existing='{"errors":[{"resource":"Release","field":"tag_name","code":"already_exists"}]}'
valid='{"tag_name":"v1.2.3","draft":false,"html_url":"https://github.com/example/fixture/releases/tag/v1.2.3"}'
case "$MOCK_CASE" in
  created) printf '%s\n201' "$valid" ;;
  unauthorized) printf '{"message":"BODY_MUST_NOT_LEAK"}\n401' ;;
  forbidden) printf '{"message":"BODY_MUST_NOT_LEAK"}\n403' ;;
  invalid) printf '{"message":"BODY_MUST_NOT_LEAK","errors":[{"code":"invalid"}]}\n422' ;;
  misleading) printf '{"message":"already_exists BODY_MUST_NOT_LEAK"}\n422' ;;
  server) printf '{"message":"BODY_MUST_NOT_LEAK"}\n503' ;;
  recover)
    if [[ "$count" == 1 ]]; then printf '{}\n503'; else printf '%s\n201' "$valid"; fi ;;
  transport) exit 7 ;;
  malformed) printf 'BODY_MUST_NOT_LEAK\nnot-http' ;;
  existing|wrong-tag|draft|lookup-unauthorized)
    if [[ "$method" == POST ]]; then
      printf '%s\n422' "$existing"
    elif [[ "$MOCK_CASE" == wrong-tag ]]; then
      printf '{"tag_name":"v9.9.9","draft":false}\n200'
    elif [[ "$MOCK_CASE" == draft ]]; then
      printf '{"tag_name":"v1.2.3","draft":true}\n200'
    elif [[ "$MOCK_CASE" == lookup-unauthorized ]]; then
      printf '{"message":"BODY_MUST_NOT_LEAK"}\n401'
    else
      printf '%s\n200' "$valid"
    fi ;;
  *) exit 93 ;;
esac
EOF
chmod +x "$scratch/bin/"*
export PATH="$scratch/bin:$PATH" PROJECT_TYPE=maven
export GITHUB_TOKEN=fixture-token-must-not-leak
export CIRCLE_PROJECT_USERNAME=example CIRCLE_PROJECT_REPONAME=fixture
export MOCK_COUNT="$scratch/count"
cd "$scratch/work"
check() {
  export MOCK_CASE=$1
  local expected=$2 calls=$3 status=0
  printf 0 > "$MOCK_COUNT"
  bash "$root/src/scripts/create_github_release.sh" > "$scratch/output" 2>&1 || status=$?
  if [[ "$expected" == pass && "$status" != 0 ]] || [[ "$expected" == fail && "$status" == 0 ]]; then
    printf 'FAIL: %s returned %s (expected %s)\n' "$MOCK_CASE" "$status" "$expected" >&2
    exit 1
  fi
  [[ "$(cat "$MOCK_COUNT")" == "$calls" ]]
  if grep -Eq 'BODY_MUST_NOT_LEAK|fixture-token-must-not-leak|artifacts are published|Artifacts are published' "$scratch/output"; then
    printf 'FAIL: unsafe or unverified output in %s\n' "$MOCK_CASE" >&2
    exit 1
  fi
  printf 'PASS: %s\n' "$MOCK_CASE"
}
# First assertion reproduces the hosted HTTP401 false success before the fix.
check unauthorized fail 1
check forbidden fail 1
check invalid fail 1
check misleading fail 1
check server fail 2
check transport fail 1
check malformed fail 1
check created pass 1
check recover pass 2
check existing pass 2
check wrong-tag fail 2
check draft fail 2
check lookup-unauthorized fail 2
export DRY_RUN=true
check created pass 0
