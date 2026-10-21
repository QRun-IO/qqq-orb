#!/bin/bash
set -euo pipefail

# Machine executors are Ubuntu amd64. Preserve an existing browser for Maven
# consumers; frontend_test deliberately removes its stale browser beforehand.
if command -v google-chrome >/dev/null 2>&1; then
  google-chrome --version
  exit 0
fi
architecture=$(dpkg --print-architecture)
if [[ "$architecture" != amd64 ]]; then
  echo "Google Chrome requires an amd64 machine executor" >&2
  exit 1
fi
curl --fail --silent --show-error --location https://dl.google.com/linux/linux_signing_key.pub \
  | sudo gpg --batch --yes --dearmor -o /usr/share/keyrings/qqq-google-chrome.gpg
printf '%s\n' 'deb [arch=amd64 signed-by=/usr/share/keyrings/qqq-google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main' \
  | sudo tee /etc/apt/sources.list.d/qqq-google-chrome.list >/dev/null
# Ubuntu dependency indexes were refreshed by install_java. Only the newly added
# signed Google repository needs refreshing; image PPAs are unrelated to Chrome.
sudo env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get update \
  -o Dir::Etc::sourcelist=/etc/apt/sources.list.d/qqq-google-chrome.list \
  -o Dir::Etc::sourceparts=- -o APT::Get::List-Cleanup=0
sudo env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get install -y google-chrome-stable
google-chrome --version
