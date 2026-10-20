#!/usr/bin/env python3
"""Replace audited standard QBit pipelines with the canonical orb caller.

Only modifies the two CI declarations in a supplied checkout. Git operations and
publication remain separate. Unknown jobs/options fail closed for human review.
"""
import argparse
from pathlib import Path
import re

import yaml


def canonical_caller(version):
    return {
        "version": 2.1,
        "setup": True,
        "orbs": {"qqq-orb": f"kingsrook/qqq-orb@{version}"},
        "workflows": {"setup": {"jobs": [{"qqq-orb/generate_pipeline": {
            "orb_version": version,
            "filters": {"branches": {"ignore": "automation/qbit-rc-pending"},
                        "tags": {"only": "/.*/"}},
        }}]}},
    }


def infer_manifest(config, version, default_branch):
    if not re.fullmatch(r"(?:\d+\.\d+\.\d+|dev:[A-Za-z0-9_-]+)", version):
        raise ValueError("An explicit published orb version is required")
    if default_branch not in ("main", "develop"):
        raise ValueError("Unsupported default branch")
    if set(config) - {"version", "orbs", "commands", "workflows"}:
        raise ValueError("Custom top-level CI configuration requires review")
    if set(config.get("commands", {})) - {"configure-package-install"}:
        raise ValueError("Custom commands require a central profile")
    if set(config.get("orbs", {})) != {"qqq-orb"}:
        raise ValueError("Unexpected orb dependencies")
    publications = set()
    job_count = 0
    for workflow in config.get("workflows", {}).values():
        if not isinstance(workflow, dict) or set(workflow) != {"jobs"}:
            raise ValueError("Custom workflow conditions require review")
        for invocation in workflow["jobs"]:
            if not isinstance(invocation, dict) or len(invocation) != 1:
                raise ValueError("Unexpected job invocation")
            job, options = next(iter(invocation.items()))
            options = options or {}
            if job not in ("qqq-orb/mvn_test_only", "qqq-orb/mvn_publish"):
                raise ValueError("Custom jobs require a central profile")
            if set(options) - {"context", "branch_type", "filters", "pre-steps"}:
                raise ValueError("Custom job options require review")
            if options.get("context", ["qqq-maven-registry-credentials"]) != ["qqq-maven-registry-credentials"]:
                raise ValueError("Unexpected credential contexts")
            if options.get("pre-steps", []) not in ([], ["configure-package-install"]):
                raise ValueError("Custom pre-steps require review")
            if job.endswith("/mvn_publish"):
                kind = options.get("branch_type")
                if kind not in ("snapshot", "release_candidate", "release"):
                    raise ValueError("Custom publication contract requires review")
                publications.add(kind)
            job_count += 1
    if not job_count:
        raise ValueError("No recognized QBit jobs")
    return {
        "profile": "qbit", "orb_version": version,
        "default_branch": default_branch, "java_version": "21",
        # Opt-outs require test inventory evidence, not heuristics.
        "browsers": True, "api_checks": False, "docs_only": False,
        "publish": {**{kind: kind in publications
                      for kind in ("snapshot", "release_candidate", "release")},
                    "asciidoc": False},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--orb-version", required=True)
    parser.add_argument("--default-branch", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    config_path = args.checkout / ".circleci/config.yml"
    manifest_path = args.checkout / ".qqq-ci.yml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if manifest_path.exists():
        raise ValueError("Already has a manifest; use the version rollout operation")
    manifest = infer_manifest(config, args.orb_version, args.default_branch)
    caller = canonical_caller(args.orb_version)
    if args.write:
        for path, data in ((config_path, caller), (manifest_path, manifest)):
            path.write_bytes(yaml.safe_dump(data, sort_keys=False).encode("utf-8"))
        print("Updated canonical caller and manifest")
    else:
        print(yaml.safe_dump(manifest, sort_keys=False), end="")


if __name__ == "__main__":
    main()
