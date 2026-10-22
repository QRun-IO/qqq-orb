#!/usr/bin/env bash
set -euo pipefail

# Ubuntu Jammy ships gh 2.4, which lacks API --slurp and modern merge guards.
# Pin the official amd64 release and its GitHub release asset SHA-256.
version=2.103.0
checksum=fdd768eb70f6409f80fcfa9f3a1c0adf0fc98d827ab3ce0bed2ac22762c5d786
archive=$(mktemp)
binary=$(mktemp)
trap 'rm -f "$archive" "$binary"' EXIT
curl --fail --silent --show-error --location --retry 3 \
  "https://github.com/cli/cli/releases/download/v${version}/gh_${version}_linux_amd64.tar.gz" -o "$archive"
printf '%s  %s\n' "$checksum" "$archive" | sha256sum --check --status
tar -xOzf "$archive" "gh_${version}_linux_amd64/bin/gh" > "$binary"
sudo install -m 0755 "$binary" /usr/local/bin/gh
gh --version
# Drain help output: grep -q can SIGPIPE gh under pipefail.
gh api --help | grep -- --slurp >/dev/null
gh pr merge --help | grep -- --match-head-commit >/dev/null
