#!/bin/bash
# nvm is a shell function on macOS and not nounset-safe, so no -u here.
set -eo pipefail

# Install the exact Node.js version with the image's nvm (macOS login shell, nvm-windows in Git Bash).
nvm install "$PARAM_NODE_VERSION"
if [[ "$OSTYPE" == darwin* ]]; then
  # Later steps start new login shells: make the version their default.
  nvm alias default "$PARAM_NODE_VERSION"
else
  # nvm-windows switches the global symlink, which later steps inherit.
  nvm use "$PARAM_NODE_VERSION"
fi
node --version
npm --version
