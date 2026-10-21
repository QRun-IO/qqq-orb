#!/usr/bin/env python3
"""Emit/check the canonical QBit RC bridge; release authority stays in the pinned worker."""
import argparse
from pathlib import Path
import re
import sys

import yaml

CALLER_PATH = ".github/workflows/release-rc.yml"


def canonical(worker_sha):
    if not re.fullmatch(r"[0-9a-f]{40}", worker_sha or ""):
        raise ValueError("RC worker requires an immutable 40-character orb commit SHA")
    inputs = {
        "dry_run": {"description": "Plan a cut without changing release state", "type": "boolean", "default": False},
        "finalize": {"description": "Retry finalization of an existing cut; do not cut another RC", "type": "boolean", "default": False},
    }
    inputs['recover'] = {'description': 'Recover the same published RC after a deployment timeout; never reupload', 'type': 'boolean', 'default': False}
    inputs['circle_build'] = {'description': 'Original Circle publisher build number (recovery only)', 'type': 'string', 'default': ''}
    for field in ("merge_sha", "bump_sha", "branch", "version"):
        inputs[field] = {"description": "Existing cut " + field + " (finalize retry only)", "type": "string", "default": ""}
    forwarded = {
        "dry_run": "${{ github.event_name == 'workflow_dispatch' && inputs.dry_run || false }}",
        "finalize": "${{ github.event_name == 'repository_dispatch' || (github.event_name == 'workflow_dispatch' && inputs.finalize) }}",
    }
    forwarded['recover'] = "${{ github.event_name == 'workflow_dispatch' && inputs.recover || false }}"
    forwarded['circle_build'] = "${{ github.event_name == 'workflow_dispatch' && inputs.circle_build || '' }}"
    for field in ("merge_sha", "bump_sha", "branch", "version"):
        forwarded[field] = "${{ github.event_name == 'repository_dispatch' && github.event.client_payload." + field + " || inputs." + field + " || '' }}"
    return {
        "name": "Release candidate",
        "on": {
            "workflow_dispatch": {"inputs": inputs},
            "pull_request": {"types": ["closed"], "branches": ["develop"]},
            "repository_dispatch": {"types": ["qbit-rc-published"]},
        },
        "permissions": {"contents": "write", "actions": "read", "checks": "read"},
        "jobs": {
            "release-rc": {
                "if": "github.event_name == 'workflow_dispatch' || github.event_name == 'repository_dispatch' || (github.event_name == 'pull_request' && github.event.pull_request.merged == true && github.event.pull_request.base.ref == 'develop' && contains(github.event.pull_request.labels.*.name, 'release:rc'))",
                "uses": "QRun-IO/qqq-orb/.github/workflows/qbit-release-rc.yml@" + worker_sha,
                "with": forwarded,
                "secrets": "inherit",
            }
        },
    }


def generate(worker_sha):
    return yaml.safe_dump(canonical(worker_sha), sort_keys=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    expected = generate(args.ref)
    if args.check:
        # Exact canonical text rejects added steps, permissions and duplicate YAML keys.
        if args.check.read_text(encoding="utf-8") != expected:
            raise ValueError("RC caller differs from canonical bridge")
        print("Canonical RC caller verified")
    else:
        print(expected, end="")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError):
        sys.exit("Invalid RC worker pin or noncanonical caller")
