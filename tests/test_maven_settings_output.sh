#!/bin/bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_dir="$(dirname "$script_dir")/src/scripts"
test_dir="$(mktemp -d)"
trap 'rm -rf "$test_dir"' EXIT
mkdir -p "$test_dir/bin"

# Keep the production scripts' fixed CircleCI path away from any shared /tmp file.
sed "s|/tmp/circleci|$test_dir/circleci|g" \
    "$source_dir/setup_maven_settings.sh" > "$test_dir/setup.sh"
sed "s|/tmp/circleci|$test_dir/circleci|g" \
    "$source_dir/mvn_jar_deploy.sh" > "$test_dir/deploy.sh"

bash "$test_dir/setup.sh" > "$test_dir/setup-output" 2>&1
settings="$test_dir/circleci/mvn-settings.xml"
test -f "$settings"
grep -Fq "\${env.CENTRAL_USERNAME}" "$settings"
grep -Fq "\${env.CENTRAL_PASSWORD}" "$settings"
if grep -Fq '<settings' "$test_dir/setup-output" ||
    grep -Fq "\${env.CENTRAL_USERNAME}" "$test_dir/setup-output"; then
    echo 'Setup printed Maven settings content' >&2
    exit 1
fi

# A distinctive future secret must never be echoed by the deploy wrapper.
printf '\n<!-- settings-output-sentinel -->\n' >> "$settings"
cat > "$test_dir/bin/mvn" <<'EOF'
#!/bin/bash
printf '%s\n' "$@" > "$TEST_MVN_ARGS"
EOF
chmod +x "$test_dir/bin/mvn"
PATH="$test_dir/bin:$PATH" TEST_MVN_ARGS="$test_dir/mvn-args" \
    GPG_KEYNAME=test-key GPG_PASSPHRASE=test-passphrase \
    bash "$test_dir/deploy.sh" > "$test_dir/deploy-output" 2>&1
if grep -Fq 'settings-output-sentinel' "$test_dir/deploy-output"; then
    echo 'Deploy printed Maven settings content' >&2
    exit 1
fi

cat > "$test_dir/expected-args" <<EOF
-s
$settings
-P
release
-B
-DskipTests
-Dgpg.keyname=test-key
-Dgpg.passphrase=test-passphrase
deploy
EOF
diff -u "$test_dir/expected-args" "$test_dir/mvn-args"
echo 'Maven settings setup and deploy output are safe; deploy arguments preserved'
