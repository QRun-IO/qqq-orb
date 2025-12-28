#!/bin/bash
set -euo pipefail

# Install Java and Maven on Ubuntu machine executor
# Uses Eclipse Temurin (AdoptOpenJDK successor) for reliable JDK installation
# Optionally installs Node.js via NodeSource repository

JAVA_VERSION="${PARAM_JAVA_VERSION:-21}"
INSTALL_NODE="${PARAM_INSTALL_NODE:-false}"
NODE_VERSION="${PARAM_NODE_VERSION:-20}"

echo "Installing Java ${JAVA_VERSION} and Maven..."

# Add Eclipse Temurin repository
sudo apt-get update -qq
sudo apt-get install -y -qq wget apt-transport-https gpg maven curl

# Add Temurin GPG key
wget -qO - https://packages.adoptium.net/artifactory/api/gpg/key/public | sudo gpg --dearmor -o /usr/share/keyrings/adoptium.gpg

# Add repository
echo "deb [signed-by=/usr/share/keyrings/adoptium.gpg] https://packages.adoptium.net/artifactory/deb $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/adoptium.list

# Install Java
sudo apt-get update -qq
sudo apt-get install -y -qq "temurin-${JAVA_VERSION}-jdk"

# Set JAVA_HOME
JAVA_HOME="/usr/lib/jvm/temurin-${JAVA_VERSION}-jdk-amd64"
echo "export JAVA_HOME=${JAVA_HOME}" >> "${BASH_ENV}"
echo "export PATH=${JAVA_HOME}/bin:\$PATH" >> "${BASH_ENV}"

# Install Node.js if requested
if [ "${INSTALL_NODE}" = "true" ]; then
  echo ""
  echo "Installing Node.js ${NODE_VERSION}..."
  curl -fsSL "https://deb.nodesource.com/setup_${NODE_VERSION}.x" | sudo -E bash -
  sudo apt-get install -y -qq nodejs
  echo ""
  echo "Node.js version:"
  node --version
  echo "npm version:"
  npm --version
fi

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
