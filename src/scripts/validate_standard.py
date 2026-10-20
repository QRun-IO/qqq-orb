#!/usr/bin/env python3
"""Reject consumer-owned CI orchestration outside the canonical QQQ setup caller."""
import os
from pathlib import Path
import re
import sys

import yaml


class StandardError(ValueError):
    """The consumer does not satisfy the central pipeline contract."""


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise StandardError("YAML mapping keys must be unique strings")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)

PROFILE_PARAMETERS = {
    "qbit": {},
    "core": {
        "mongo_bind_diagnostics": {"type": "boolean", "default": False},
        "next_acceptance_bundle_url": {"type": "string", "default": ""},
        "next_acceptance_bundle_sha256": {"type": "string", "default": ""},
        "next_acceptance_receipt_sha256": {"type": "string", "default": ""},
    },
    "frontend-material": {"run_playwright": {"type": "boolean", "default": False}},
    "frontend-core": {},
    "cli": {},
    "voyage": {},
    "frontend-next": {},
    "all": {},
    "app-starter": {},
    "android": {},
    "mcp-policy": {},
}


def load_yaml(raw):
    if len(raw.encode("utf-8")) > 65536:
        raise StandardError("CI declaration exceeds 64 KiB")
    try:
        return yaml.load(raw, Loader=UniqueLoader)
    except yaml.YAMLError as error:
        raise StandardError("Invalid YAML declaration") from error


def canonical_caller(profile, version, explicit_manifest=False):
    if not isinstance(profile, str) or profile not in PROFILE_PARAMETERS:
        raise StandardError("Unsupported CI profile")
    options = {
        "orb_version": version,
        "filters": {"branches": {"ignore": "automation/qbit-rc-pending"}, "tags": {"only": "/.*/"}},
    }
    if profile == "frontend-next":
        options["filters"]["branches"] = {"ignore": "/.*/"}
    if explicit_manifest:
        options["manifest"] = ".qqq-ci.yml"
    parameters = PROFILE_PARAMETERS[profile]
    for name in parameters:
        options[name] = "<< pipeline.parameters." + name + " >>"
    caller = {
        "version": 2.1,
        "setup": True,
        "orbs": {"qqq-orb": "kingsrook/qqq-orb@" + version},
        "workflows": {"setup": {"jobs": [{"qqq-orb/generate_pipeline": options}]}},
    }
    if parameters:
        caller["parameters"] = parameters
    return caller


def exact(actual, expected):
    # Python equality considers 1 == True: CI parameter types must remain exact.
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(exact(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(exact(a, b) for a, b in zip(actual, expected))
    return actual == expected


def validate(config_raw, manifest_raw, setup_version):
    config = load_yaml(config_raw)
    manifest = load_yaml(manifest_raw)
    if not isinstance(manifest, dict):
        raise StandardError("Manifest must be a mapping")
    version = manifest.get("orb_version")
    if not isinstance(version, str) or not re.fullmatch(r"(?:\d+\.\d+\.\d+|dev:[A-Za-z0-9_-]+)", version):
        raise StandardError("Manifest must pin an explicit orb version")
    if version != setup_version:
        raise StandardError("Manifest and running setup orb versions differ")
    expected = canonical_caller(manifest.get("profile"), version)
    explicit = canonical_caller(manifest.get("profile"), version, explicit_manifest=True)
    if not exact(config, expected) and not exact(config, explicit):
        raise StandardError("Consumer config must be the canonical setup caller with only its profile's declared and forwarded parameters")


def main():
    manifest = os.environ.get("QQQ_CI_MANIFEST", ".qqq-ci.yml")
    if manifest != ".qqq-ci.yml":
        raise StandardError("The standard manifest path is .qqq-ci.yml")
    validate(Path(".circleci/config.yml").read_text(encoding="utf-8"),
             Path(manifest).read_text(encoding="utf-8"), os.environ.get("QQQ_CI_ORB_VERSION", ""))
    print("Canonical QQQ CI caller verified")


if __name__ == "__main__":
    try:
        main()
    except (StandardError, OSError) as error:
        print("CI standard validation failed: " + str(error), file=sys.stderr)
        sys.exit(1)
