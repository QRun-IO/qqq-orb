#!/bin/bash
# Verify unattended installation through executable stubs; never invokes sudo/apt/network.
set -euo pipefail
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../src/scripts" && pwd)
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
mkdir "$scratch/bin"
export INSTALL_LOG="$scratch/install.log"
export APT_CONFIG_CAPTURE="$scratch/apt.conf"
export BASH_ENV="$scratch/bash-env"
export QQQ_MAVEN_BIN_DIR="$scratch/maven-bin"
: > "$BASH_ENV"
cat > "$scratch/bin/sudo" <<'STUB'
#!/bin/bash
printf '%s\n' "$*" >> "$INSTALL_LOG"
if [[ "$*" == *apt-get* ]]; then
  [[ "$1" == env && "$2" == DEBIAN_FRONTEND=noninteractive && "$3" == NEEDRESTART_MODE=l ]] || exit 90
  [[ -f "$APT_CONFIG_CAPTURE" ]] && grep -qx 'Acquire::Retries "3";' "$APT_CONFIG_CAPTURE" || exit 91
  [[ ${APT_FAIL:-0} == 0 ]] || exit "$APT_FAIL"
  if [[ "$*" == *'apt-get update'* ]]; then
    updates=$(grep -c 'apt-get update' "$INSTALL_LOG")
    if [[ $updates -eq 2 ]]; then
      # Model a PPA outage after the initial base-package installation. Only
      # the new signed repository may be contacted; existing indexes survive.
      [[ "$*" == *'Dir::Etc::sourcelist=/etc/apt/sources.list.d/adoptium.list'* ]] || exit 100
      [[ "$*" == *'Dir::Etc::sourceparts=-'* ]] || exit 100
      [[ "$*" == *'APT::Get::List-Cleanup=0'* ]] || exit 92
      [[ ${TEMURIN_UPDATE_FAIL:-0} == 0 ]] || exit "$TEMURIN_UPDATE_FAIL"
    fi
  fi
fi
if [[ "$1" == tee && "$2" == /etc/apt/apt.conf.d/80-qqq-download-retries ]]; then
  cat > "$APT_CONFIG_CAPTURE"; exit 0
fi
if [[ "$1" == tee || "$1" == gpg || "$1" == -E ]]; then cat >/dev/null; fi
STUB
for tool in wget curl; do
  printf '#!/bin/bash\nprintf "placeholder\\n"\n' > "$scratch/bin/$tool"
done
for tool in java mvn docker node npm; do
  printf '#!/bin/bash\nexit 0\n' > "$scratch/bin/$tool"
done
printf '#!/bin/bash\necho jammy\n' > "$scratch/bin/lsb_release"
chmod +x "$scratch/bin/"*
export PATH="$scratch/bin:$PATH"
PARAM_INSTALL_NODE=false bash "$script_dir/install_java.sh" >/dev/null 2>&1
[[ $(grep -c 'apt-get' "$INSTALL_LOG") -eq 4 ]]
grep -q 'tee /etc/needrestart/conf.d/99-qqq-ci.conf' "$INSTALL_LOG"
grep -q 'export JAVA_HOME=' "$BASH_ENV"
: > "$INSTALL_LOG"
: > "$BASH_ENV"
rm "$APT_CONFIG_CAPTURE"
PARAM_INSTALL_NODE=true bash "$script_dir/install_java.sh" >/dev/null 2>&1
[[ $(grep -c 'apt-get' "$INSTALL_LOG") -eq 5 ]]
grep -q 'apt-get install -y -qq nodejs' "$INSTALL_LOG"
# An outage of the required repository must still stop before Java installation.
: > "$INSTALL_LOG"
if TEMURIN_UPDATE_FAIL=100 PARAM_INSTALL_NODE=false bash "$script_dir/install_java.sh" >/dev/null 2>&1; then
  echo 'required Temurin repository failure accepted' >&2; exit 1
else
  [[ $? -eq 100 ]]
fi
if grep -q 'apt-get install -y -qq temurin-' "$INSTALL_LOG"; then
  echo 'Java installation continued after repository failure' >&2; exit 1
fi
# Execute the actual generated selector. Arguments containing spaces stay intact.
export SELECTOR_LOG="$scratch/selector.log"
cat > "$scratch/bin/mvn" <<'NATIVE'
#!/bin/bash
printf 'native\n' >> "$SELECTOR_LOG"
printf '<%s>\n' "$@" >> "$SELECTOR_LOG"
NATIVE
chmod +x "$scratch/bin/mvn"
mkdir "$scratch/project"
cd "$scratch/project"
git init -q
"$QQQ_MAVEN_BIN_DIR/mvn" verify '-Dname=two words'
grep -qx native "$SELECTOR_LOG"
grep -qx '<-Dname=two words>' "$SELECTOR_LOG"
cat > mvnw <<'WRAPPER'
#!/bin/sh
printf 'wrapper\n' >> "$SELECTOR_LOG"
printf '<%s>\n' "$@" >> "$SELECTOR_LOG"
WRAPPER
: > "$SELECTOR_LOG"
"$QQQ_MAVEN_BIN_DIR/mvn" verify '-Dname=two words'
grep -qx wrapper "$SELECTOR_LOG"
grep -qx '<-Dname=two words>' "$SELECTOR_LOG"
chmod +x mvnw
: > "$SELECTOR_LOG"
"$QQQ_MAVEN_BIN_DIR/mvn" --update-snapshots verify
grep -qx wrapper "$SELECTOR_LOG"
grep -qx '<--update-snapshots>' "$SELECTOR_LOG"
mkdir module
cd module
: > "$SELECTOR_LOG"
"$QQQ_MAVEN_BIN_DIR/mvn" verify
grep -qx wrapper "$SELECTOR_LOG"
printf '#!/bin/sh\nexit 23\n' > ../mvnw
if "$QQQ_MAVEN_BIN_DIR/mvn" verify; then exit 1; else [[ $? -eq 23 ]]; fi
rm ../mvnw
printf '#!/bin/bash\nexit 24\n' > "$scratch/bin/mvn"
if "$QQQ_MAVEN_BIN_DIR/mvn" verify; then exit 1; else [[ $? -eq 24 ]]; fi
# A shell function is not a valid native fallback and must fail closed.
# Exported to child Bash to test rejecting a function as native Maven.
# shellcheck disable=SC2329,SC2317
mvn() { return 0; }
export -f mvn
if PARAM_INSTALL_NODE=false bash "$script_dir/install_java.sh" >/dev/null 2>&1; then
  echo 'invalid native Maven accepted' >&2; exit 1
fi
unset -f mvn
if APT_FAIL=100 PARAM_INSTALL_NODE=false bash "$script_dir/install_java.sh" >/dev/null 2>&1; then
  echo 'persistent apt failure accepted' >&2; exit 1
else
  [[ $? -eq 100 ]]
fi
printf 'PASS: unattended installation and native/executable/nonexecutable wrapper selection\n'
