#!/usr/bin/env python3
"""Emit/check the small pinned native bridge; all worker policy belongs to the orb."""
import argparse
import os
from pathlib import Path
import re
import sys

import yaml


def canonical_next(shared_ref):
    if not re.fullmatch(r"[0-9a-f]{40}", shared_ref or ""):
        raise ValueError("Next workers require an immutable orb repository commit")
    worker = "QRun-IO/qqq-orb/.github/workflows/"
    non_label = "!contains(fromJSON('[\"labeled\",\"unlabeled\"]'), github.event.action)"
    return {
        "name": "Next centralized CI",
        "on": {
            "pull_request": {"types": ["opened", "synchronize", "reopened", "labeled", "unlabeled"]},
            "push": {"branches": ["main"], "tags": ["v*"]},
            "workflow_dispatch": {"inputs": {"qqq_ref": {"description": "QQQ source ref for acceptance", "type": "string", "required": False}}},
        },
        "permissions": {"contents": "read"},
        "jobs": {
            "ci": {
                "if": "(github.event_name == 'pull_request' && " + non_label + ") || (github.event_name == 'push' && github.ref == 'refs/heads/main')",
                "uses": worker + "next-ci.yml@" + shared_ref,
            },
            "acceptance": {
                "if": "github.event_name != 'pull_request' || " + non_label + " || github.event.label.name == 'full-acceptance'",
                "uses": worker + "next-acceptance.yml@" + shared_ref,
                "with": {"qqq_ref": "${{ inputs.qqq_ref || '' }}"},
            },
            "dashboard-image": {
                "if": "(github.event_name == 'pull_request' && " + non_label + ") || (github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v'))",
                "permissions": {"contents": "read", "packages": "write"},
                "uses": worker + "next-dashboard-image.yml@" + shared_ref,
            },
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ref", default=os.environ.get("QQQ_NEXT_SHARED_REF"))
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    try:
        expected = canonical_next(args.ref)
        if args.check:
            if yaml.safe_load(args.check.read_text(encoding="utf-8")) != expected:
                raise ValueError("Next native caller differs from the canonical bridge")
        else:
            print(yaml.safe_dump(expected, sort_keys=False), end="")
    except (ValueError, OSError, yaml.YAMLError):
        sys.exit("Next caller requires a valid immutable worker pin and canonical configuration")


if __name__ == "__main__":
    main()
