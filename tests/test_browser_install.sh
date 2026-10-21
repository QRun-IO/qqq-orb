#!/bin/bash
# Exercise real browser scripts without sudo, package installation or network.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
mkdir "$scratch/bin"
export INSTALL_LOG="$scratch/install.log"
cat > "$scratch/bin/sudo" <<'STUB'
#!/bin/bash
printf '%s\n' "$*" >> "$INSTALL_LOG"
if [[ "$*" == *'apt-get update'* ]]; then
  [[ "$*" == *'Dir::Etc::sourceparts=-'* ]] || { echo 'unrelated image PPA: 503' >&2; exit 100; }
  [[ "$*" == *'APT::Get::List-Cleanup=0'* ]] || exit 91
  [[ ${REQUIRED_REPO_FAIL:-0} == 0 ]] || exit 100
fi
if [[ "$1" == tee ]]; then cat >> "$INSTALL_LOG"; fi
if [[ "$1" == gpg ]]; then cat >/dev/null; fi
STUB
chmod +x "$scratch/bin/sudo"
export PATH="$scratch/bin:$PATH"
bash "$root/src/scripts/frontend_test_dependencies.sh"
echo 'PASS: browser dependencies ignore unavailable image PPAs'
# Model Chrome presence without depending on the host's installed browsers.
export CHROME_MARKER="$scratch/chrome-installed"
export BASH_ENV="$scratch/shell-env"
cat > "$BASH_ENV" <<'STUB'
command() {
  if [[ "$*" == '-v google-chrome' ]]; then [[ -f "$CHROME_MARKER" ]]; else builtin command "$@"; fi
}
google-chrome() { [[ -f "$CHROME_MARKER" ]] && echo 'Google Chrome test'; }
STUB
cat > "$scratch/bin/curl" <<'STUB'
#!/bin/bash
printf '%s\n' "$*" >> "$INSTALL_LOG"
[[ ${KEY_FAIL:-0} == 0 ]] || exit 22
printf 'signing-key\n'
STUB
cat > "$scratch/bin/dpkg" <<'STUB'
#!/bin/bash
echo amd64
STUB
# Successful installation makes Chrome available to the final version check.
# shellcheck disable=SC2016
sed -i '/if \[\[ "$1" == tee/i if [[ "$*" == *"apt-get install -y google-chrome-stable"* ]]; then touch "$CHROME_MARKER"; fi' "$scratch/bin/sudo"
chmod +x "$scratch/bin/"*
: > "$INSTALL_LOG"
bash "$root/src/scripts/install_chrome.sh" >/dev/null
grep -q 'Dir::Etc::sourcelist=/etc/apt/sources.list.d/qqq-google-chrome.list' "$INSTALL_LOG"
grep -q 'gpg --batch --yes --dearmor -o /usr/share/keyrings/qqq-google-chrome.gpg' "$INSTALL_LOG"
grep -q 'signed-by=/usr/share/keyrings/qqq-google-chrome.gpg] https://dl.google.com/linux/chrome/deb/' "$INSTALL_LOG"
grep -q 'apt-get install -y google-chrome-stable' "$INSTALL_LOG"
: > "$INSTALL_LOG"
bash "$root/src/scripts/install_chrome.sh" >/dev/null
[[ ! -s "$INSTALL_LOG" ]] # Existing Chrome needs no network/package work.
rm "$CHROME_MARKER"
for script in install_chrome frontend_test_dependencies; do
  : > "$INSTALL_LOG"
  if REQUIRED_REPO_FAIL=1 bash "$root/src/scripts/$script.sh" >/dev/null 2>&1; then
    echo "Required repository outage accepted: $script" >&2; exit 1
  fi
  if grep -q 'apt-get install' "$INSTALL_LOG"; then exit 1; fi
done
: > "$INSTALL_LOG"
if KEY_FAIL=1 bash "$root/src/scripts/install_chrome.sh" >/dev/null 2>&1; then
  echo 'Signing key failure accepted' >&2; exit 1
fi
if grep -q 'apt-get' "$INSTALL_LOG"; then exit 1; fi
echo 'PASS: Chrome ignores unrelated PPAs; required repositories and signing key fail closed; existing browser reused'
