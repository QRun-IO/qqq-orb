#!/usr/bin/env bash
printf '%s\n' 'pipeline: node-webapp' 'node_version: 22' 'docker:' '  use_repo_dockerfile: true' > .munitor.yml
