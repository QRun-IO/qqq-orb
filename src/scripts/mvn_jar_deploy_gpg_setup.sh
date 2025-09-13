#!/bin/bash
set -e

mkdir -p ~/.gnupg
echo 'pinentry-mode loopback' > ~/.gnupg/gpg.conf
chmod 600 ~/.gnupg/gpg.conf
echo $GPG_PRIVATE_KEY_B64| tr -d ' \r\n\t' | base64 -d | gpg --batch --import
