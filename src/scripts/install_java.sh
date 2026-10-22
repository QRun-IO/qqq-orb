#!/bin/bash
set -euo pipefail

# Install Java and Maven on Ubuntu machine executor
# Uses Eclipse Temurin (AdoptOpenJDK successor) for reliable JDK installation
# Optionally installs Node.js via NodeSource repository

JAVA_VERSION="${PARAM_JAVA_VERSION:-21}"
INSTALL_NODE="${PARAM_INSTALL_NODE:-false}"
NODE_VERSION="${PARAM_NODE_VERSION:-20}"

echo "Installing Java ${JAVA_VERSION} and Maven..."

# Keep package installation unattended on disposable build machines.
# Set this before either apt invocation, including NodeSource's child process.
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=l
sudo install -d /etc/needrestart/conf.d
# Keep Perl's variable literal in the needrestart configuration.
# shellcheck disable=SC2016
printf '%s\n' '$nrconf{restart} = "l";' | sudo tee /etc/needrestart/conf.d/99-qqq-ci.conf >/dev/null

# Retry transient repository downloads within APT, including NodeSource's child process.
# Exhausted downloads retain APT's nonzero exit status and fail this build step.
printf '%s\n' 'Acquire::Retries "3";' 'Acquire::http::Timeout "30";' \
  'Acquire::https::Timeout "30";' 'APT::Update::Error-Mode "any";' \
  | sudo tee /etc/apt/apt.conf.d/80-qqq-download-retries >/dev/null

# Ubuntu archive carries the same signed security suite; avoid the flaky HTTP mirror.
if [[ -f /etc/apt/sources.list ]]; then
  sudo sed -i 's|http://security.ubuntu.com/ubuntu|https://archive.ubuntu.com/ubuntu|g' /etc/apt/sources.list
fi

# Base tools come from Ubuntu, not the unrelated PPAs bundled in machine images.
# Support both the 22.04 list and the newer deb822 Ubuntu source file. Preserve
# other indexes for later jobs without contacting their repositories here.
ubuntu_sources=/etc/apt/sources.list
if [[ ! -s "$ubuntu_sources" ]]; then
  ubuntu_sources=/etc/apt/sources.list.d/ubuntu.sources
fi
if [[ ! -s "$ubuntu_sources" ]]; then
  echo 'Cannot locate Ubuntu package sources' >&2
  exit 1
fi
sudo env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get update -qq \
  -o "Dir::Etc::sourcelist=$ubuntu_sources" \
  -o Dir::Etc::sourceparts=- \
  -o APT::Get::List-Cleanup=0
sudo env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get install -y -qq wget apt-transport-https gpg maven curl

# Add Temurin GPG key
wget -qO - https://packages.adoptium.net/artifactory/api/gpg/key/public | sudo gpg --dearmor -o /usr/share/keyrings/adoptium.gpg

# Add repository
echo "deb [signed-by=/usr/share/keyrings/adoptium.gpg] https://packages.adoptium.net/artifactory/deb $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/adoptium.list

# Refresh only the repository just added. Re-fetching unrelated image PPAs here
# caused otherwise successful setup to fail on Launchpad 503 responses. Keep
# Ubuntu indexes from the first refresh so Java dependencies remain resolvable.
sudo env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get update -qq \
  -o Dir::Etc::sourcelist=/etc/apt/sources.list.d/adoptium.list \
  -o Dir::Etc::sourceparts=- \
  -o APT::Get::List-Cleanup=0
sudo env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get install -y -qq "temurin-${JAVA_VERSION}-jdk"

# Set JAVA_HOME
JAVA_HOME="/usr/lib/jvm/temurin-${JAVA_VERSION}-jdk-amd64"
echo "export JAVA_HOME=${JAVA_HOME}" >> "${BASH_ENV}"
echo "export PATH=${JAVA_HOME}/bin:\$PATH" >> "${BASH_ENV}"

# Install Node.js if requested
if [ "${INSTALL_NODE}" = "true" ]; then
  echo ""
  echo "Installing Node.js ${NODE_VERSION}..."
  curl -fsSL "https://deb.nodesource.com/setup_${NODE_VERSION}.x" | sudo -E bash -
  sudo env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get install -y -qq nodejs
  echo ""
  echo "Node.js version:"
  node --version
  echo "npm version:"
  npm --version
fi

# Select the checked-out project's Maven wrapper at invocation time (checkout is later).
# Keep the installed executable as fallback; all callers, including subprocesses,
# see the same selector without changing lifecycle arguments.
MAVEN_BIN_DIR="${QQQ_MAVEN_BIN_DIR:-/tmp/circleci/maven-bin}"
mkdir -p "$MAVEN_BIN_DIR"
NATIVE_MAVEN=$(command -v mvn)
if [[ "$NATIVE_MAVEN" == "$MAVEN_BIN_DIR/mvn" ]]; then
  NATIVE_MAVEN="$MAVEN_BIN_DIR/mvn-native"
fi
if [[ "$NATIVE_MAVEN" != /* ]]; then
  echo "Native Maven must resolve to an absolute executable path" >&2
  exit 1
fi
NATIVE_MAVEN=$(readlink -f "$NATIVE_MAVEN")
if [[ "$NATIVE_MAVEN" != /* || ! -f "$NATIVE_MAVEN" || ! -x "$NATIVE_MAVEN" || "$NATIVE_MAVEN" == "$MAVEN_BIN_DIR/mvn" ]]; then
  echo "Cannot locate a valid native Maven executable" >&2
  exit 1
fi
ln -sfn "$NATIVE_MAVEN" "$MAVEN_BIN_DIR/mvn-native"
cat > "$MAVEN_BIN_DIR/mvn" <<'MAVEN_SELECTOR'
#!/bin/bash
set -euo pipefail
wrapper=./mvnw
if [[ ! -f "$wrapper" ]]; then
  # A module invocation still uses its checkout's root wrapper. Never search
  # outside the repository into a user's unrelated home-directory scripts.
  root=$(git rev-parse --show-toplevel 2>/dev/null || true)
  if [[ -n "$root" ]]; then wrapper="$root/mvnw"; fi
fi
if [[ -f "$wrapper" ]]; then
  if [[ -x "$wrapper" ]]; then exec "$wrapper" "$@"; fi
  exec sh "$wrapper" "$@"
fi
exec "$(dirname "$0")/mvn-native" "$@"
MAVEN_SELECTOR
chmod +x "$MAVEN_BIN_DIR/mvn"
# Expand PATH when the next Circle step sources BASH_ENV, not during installation.
# shellcheck disable=SC2016
printf 'export PATH=%q:$PATH\n' "$MAVEN_BIN_DIR" >> "${BASH_ENV}"

# Verify installation
echo ""
echo "Java version:"
java -version
echo ""
echo "Maven version:"
mvn --version
echo ""
echo "Docker version:"
docker --version
echo ""
echo "Installation completed successfully"
