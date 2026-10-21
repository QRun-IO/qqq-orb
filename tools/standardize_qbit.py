#!/usr/bin/env python3
"""Replace audited standard QBit pipelines with the canonical orb caller.

Only modifies the two CI declarations in a supplied checkout. Git operations and
publication remain separate. Unknown jobs/options fail closed for central profile resolution.
"""
import argparse
from pathlib import Path
import re

import yaml


def canonical_caller(version, release_tag_policy=None, publish_feature=False):
    caller = {
        "version": 2.1,
        "setup": True,
        "orbs": {"qqq-orb": f"kingsrook/qqq-orb@{version}"},
        "workflows": {"setup": {"jobs": [{"qqq-orb/generate_pipeline": {
            "orb_version": version,
            "filters": {"branches": {"ignore": "automation/qbit-rc-pending"},
                        "tags": {"only": "/.*/"}},
        }}]}},
    }
    if release_tag_policy is not None:
        filters = {"stable": {"only": r"/^v\d+\.\d+\.\d+$/"},
                   "v-prefix": {"only": "/v.*/"}, "none": {"ignore": "/.*/"}}
        if release_tag_policy not in filters:
            raise ValueError("Unknown tag policy")
        caller["workflows"]["setup"]["jobs"][0]["qqq-orb/generate_pipeline"]["filters"]["tags"] = filters[release_tag_policy]
        if publish_feature:
            caller["workflows"]["setup"]["jobs"][0]["qqq-orb/generate_pipeline"]["filters"]["tags"] = {
                "only": ([filters[release_tag_policy]["only"]] if release_tag_policy != "none" else []) + ["/publish.*/"]}
    return caller


def single_filter(value):
    """Circle accepts a scalar or one-item list; never accept arbitrary regex."""
    if isinstance(value, list) and len(value) == 1:
        return value[0]
    return value


def publication_filters(kind, filters):
    if not isinstance(filters, dict) or set(filters) - {"branches", "tags"}:
        raise ValueError("Unknown publication filters")
    branches = filters.get("branches")
    tags = filters.get("tags")
    if kind == "feature":
        # Preserve the audited literal branch selector; it is not a regex and
        # contains a character Git forbids, so only publish* tags can select it.
        if branches != {"only": ["feature/.*"]} or tags != {"only": ["/publish.*/"]}:
            raise ValueError("Unknown feature publication filters")
        return False, "none"
    if kind in ("snapshot", "release_candidate", "hotfix"):
        expected = {"snapshot": "develop", "release_candidate": r"/release\/.*/", "hotfix": r"/hotfix\/.*/"}[kind]
        if not isinstance(branches, dict) or set(branches) != {"only"} or single_filter(branches["only"]) != expected or tags not in (None, {"only": []}):
            raise ValueError("Unknown snapshot/RC filters")
        return False, "none"
    if not isinstance(branches, dict):
        raise ValueError("Release branch filters are required")
    main = set(branches) == {"only"} and single_filter(branches["only"]) == "main"
    if not main and branches != {"ignore": "/.*/"}:
        raise ValueError("Unknown release branch filter")
    if not isinstance(tags, dict) or set(tags) != {"only"}:
        raise ValueError("Release tag filters are required")
    tag_filter = single_filter(tags["only"])
    if not isinstance(tag_filter, str):
        raise ValueError("Unknown release tag filter")
    policy = {r"/^v\d+\.\d+\.\d+$/": "stable", r"/^v[0-9]+\.[0-9]+\.[0-9]+$/": "stable",
              "/v.*/": "v-prefix"}.get(tag_filter)
    if policy is None:
        raise ValueError("Unknown release tag filter")
    return main, policy


def test_filters(filters):
    if filters is None or filters == {}:
        return "all"
    if not isinstance(filters, dict) or set(filters) - {"branches", "tags"} or filters.get("tags") not in (None, {"only": []}):
        raise ValueError("Unknown test tag filters")
    branches = filters.get("branches")
    if not isinstance(branches, dict) or set(branches) != {"ignore"}:
        raise ValueError("Unknown test branch filters")
    pattern = single_filter(branches["ignore"])
    if not isinstance(pattern, str):
        raise ValueError("Unknown test branch filters")
    policy = {
        "/(develop|release/.*)/": "non-release",
        "/(develop|release/.*|integration.*)/": "non-release-no-integration",
        "/(develop|main|release/.*|integration.*)/": "feature",
        "/(develop|main|release/.*)/": "non-release-no-main",
        "/(develop|release/.*|hotfix/.*)/": "non-release-no-hotfix",
        "/(develop|main|release/.*|hotfix/.*)/": "non-release-no-main-hotfix",
        "/(develop|main|release/.*|hotfix/.*|integration.*)/": "feature-no-hotfix",
    }.get(pattern.replace(r"\/", "/"))
    if policy is None:
        raise ValueError("Unknown test branch filters")
    return policy


def infer_manifest(config, version, default_branch):
    if not isinstance(version, str) or not re.fullmatch(r"(?:\d+\.\d+(?:\.\d+)?|dev:[A-Za-z0-9_-]+)", version):
        raise ValueError("A minor track, exact patch or explicit development orb version is required")
    if default_branch not in ("main", "develop"):
        raise ValueError("Unsupported default branch")
    if set(config) - {"version", "orbs", "commands", "workflows"}:
        raise ValueError("Custom top-level CI configuration requires review")
    if set(config.get("commands", {})) - {"configure-package-install"}:
        raise ValueError("Custom commands require a central profile")
    if set(config.get("orbs", {})) != {"qqq-orb"}:
        raise ValueError("Unexpected orb dependencies")
    publications = set()
    release_on_main, release_tag_policy = False, "none"
    test_policy = None
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
                if kind not in ("snapshot", "release_candidate", "release", "hotfix", "feature"):
                    raise ValueError("Custom publication contract requires review")
                if kind in publications:
                    raise ValueError("Duplicate publication jobs require review")
                main, tags = publication_filters(kind, options.get("filters"))
                if kind == "release":
                    release_on_main, release_tag_policy = main, tags
                publications.add(kind)
            else:
                if test_policy is not None:
                    raise ValueError("Duplicate test jobs require review")
                test_policy = test_filters(options.get("filters"))
            job_count += 1
    if not job_count:
        raise ValueError("No recognized QBit jobs")
    return {
        "profile": "qbit", "orb_version": version,
        "default_branch": default_branch, "java_version": "21",
        # Opt-outs require test inventory evidence, not heuristics.
        "browsers": True, "api_checks": False, "docs_only": False,
        "release_on_main": release_on_main, "release_tag_policy": release_tag_policy,
        "test_branch_policy": test_policy or "all",
        "publish": {**{kind: kind in publications
                      for kind in ("snapshot", "release_candidate", "release")},
                    **({"hotfix": True} if "hotfix" in publications else {}),
                    **({"feature": True} if "feature" in publications else {}),
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
        raise ValueError("Already has a manifest; use tools/rollout_version.py")
    manifest = infer_manifest(config, args.orb_version, args.default_branch)
    caller = canonical_caller(args.orb_version, manifest["release_tag_policy"], manifest["publish"].get("feature", False))
    if args.write:
        for path, data in ((config_path, caller), (manifest_path, manifest)):
            path.write_bytes(yaml.safe_dump(data, sort_keys=False).encode("utf-8"))
        print("Updated canonical caller and manifest")
    else:
        print(yaml.safe_dump(manifest, sort_keys=False), end="")


if __name__ == "__main__":
    main()
