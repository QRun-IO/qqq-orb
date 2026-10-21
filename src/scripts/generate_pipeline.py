#!/usr/bin/env python3
"""Strict QQQ pipeline manifest and native CircleCI continuation entry point."""
import json
import copy
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.request

import yaml


# BEGIN PROFILE RESOURCES
_TEMPLATE_DIR = Path(__file__).with_name("templates")
CORE_TEMPLATE = json.loads((_TEMPLATE_DIR / "core.json").read_text(encoding="utf-8"))
MATERIAL_TEMPLATE = json.loads((_TEMPLATE_DIR / "frontend-material.json").read_text(encoding="utf-8"))
VOYAGE_TEMPLATE = json.loads((_TEMPLATE_DIR / "voyage.json").read_text(encoding="utf-8"))
NEXT_TEMPLATE = json.loads((_TEMPLATE_DIR / "frontend-next.json").read_text(encoding="utf-8"))
ALL_TEMPLATE = json.loads((_TEMPLATE_DIR / "all.json").read_text(encoding="utf-8"))
STARTER_TEMPLATE = json.loads((_TEMPLATE_DIR / "app-starter.json").read_text(encoding="utf-8"))
ANDROID_TEMPLATE = json.loads((_TEMPLATE_DIR / "android.json").read_text(encoding="utf-8"))
POLICY_TEMPLATE = json.loads((_TEMPLATE_DIR / "mcp-policy.json").read_text(encoding="utf-8"))
REPOSITORY_POLICY_TEMPLATE = json.loads((_TEMPLATE_DIR / "repository-policy.json").read_text(encoding="utf-8"))
MARKETING_TEMPLATE = json.loads((_TEMPLATE_DIR / "marketing.json").read_text(encoding="utf-8"))
# END PROFILE RESOURCES


class ManifestError(ValueError):
    """A manifest must fail closed rather than silently ignore configuration."""


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate mapping keys, including YAML merge overrides."""


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise ManifestError("Manifest keys must be unique strings")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def mapping(value, allowed, name):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ManifestError(f"Invalid keys or mapping in {name}")
    return value


def boolean(data, key, default):
    value = data.get(key, default)
    if type(value) is not bool:
        raise ManifestError(f"{key} must be a boolean")
    return value


def load_manifest(path, setup_version):
    raw = Path(path).read_text(encoding="utf-8")
    if len(raw) > 65536:
        raise ManifestError("Manifest exceeds 64 KiB")
    data = yaml.load(raw, Loader=UniqueLoader)
    if not isinstance(data, dict):
        raise ManifestError("Manifest must be a mapping")
    profile = data.get("profile")
    if profile not in ("qbit", "core", "frontend-material", "frontend-core", "cli", "voyage", "frontend-next", "all", "app-starter", "android", "mcp-policy", "repository-policy", "marketing"):
        raise ManifestError("Unsupported profile")
    allowed = ("profile", "orb_version", "default_branch", "docs_only", "publish")
    if profile in ("qbit", "core"):
        allowed += ("java_version", "browsers", "api_checks")
        if profile == "qbit":
            allowed += ("release_completion", "release_on_main", "release_tag_policy", "test_branch_policy")
    elif profile == "cli":
        allowed += ("publish_context",)
    elif profile in ("voyage", "frontend-next", "app-starter", "android", "mcp-policy", "repository-policy", "marketing"):
        allowed = ("profile", "orb_version", "default_branch")
    elif profile == "all":
        allowed = ("profile", "orb_version", "default_branch", "publish", "publish_context")
    else:
        allowed += ("node_version",)
        if profile == "frontend-material":
            allowed += ("java_version",)
    mapping(data, allowed, "manifest")
    version = data.get("orb_version")
    if not isinstance(version, str) or not re.fullmatch(r"(?:\d+\.\d+\.\d+|dev:[A-Za-z0-9_-]+)", version):
        raise ManifestError("orb_version must be an explicit stable or development version")
    if version != setup_version:
        raise ManifestError("Manifest orb_version must match the setup job orb_version")
    default_branch = data.get("default_branch")
    if default_branch not in ("main", "develop"):
        raise ManifestError("default_branch must be main or develop")
    if profile == "marketing" and default_branch != "main":
        raise ManifestError("Marketing requires the audited main production branch")
    java = data.get("java_version", "21")
    if java not in ("17", "21"):
        raise ManifestError("java_version must be the string 17 or 21")
    node = data.get("node_version", "24.21" if profile == "frontend-core" else "20")
    if not isinstance(node, str) or not re.fullmatch(r"\d+(?:\.\d+){0,2}", node):
        raise ManifestError("node_version must be an explicit numeric version string")
    publish_keys = ("snapshot", "release_candidate", "release")
    if profile == "all":
        publish_keys = ("snapshot",)
    if profile == "cli":
        publish_keys = ("release",)
    if profile in ("qbit", "core"):
        publish_keys += ("asciidoc",)
    if profile == "qbit":
        publish_keys += ("hotfix",)
    if profile not in ("qbit", "cli", "all", "app-starter", "voyage", "frontend-next"):
        publish_keys += ("feature", "hotfix")
    publishing = mapping(data.get("publish", {}), publish_keys, "publish")
    publish_context = data.get("publish_context", "")
    if not isinstance(publish_context, str) or (publish_context and not re.fullmatch(r"[A-Za-z0-9_-]+", publish_context)):
        raise ManifestError("publish_context must be a CircleCI context name")
    if profile == "all" and boolean(publishing, "snapshot", False) and not publish_context:
        raise ManifestError("All image publication requires an explicitly verified context")
    if profile == "cli" and boolean(publishing, "release", False) and not publish_context:
        raise ManifestError("CLI publication requires an explicitly verified context")
    if profile == "cli" and boolean(data, "docs_only", False):
        raise ManifestError("CLI currently requires full generated-client verification")
    tag_policy = data.get("release_tag_policy", "stable")
    if tag_policy not in ("stable", "v-prefix", "none"):
        raise ManifestError("Unsupported QBit release tag policy")
    test_policy = data.get("test_branch_policy", "all")
    if test_policy not in ("all", "non-release", "non-release-no-integration", "feature", "non-release-no-main",
                           "non-release-no-hotfix", "non-release-no-main-hotfix", "feature-no-hotfix"):
        raise ManifestError("Unsupported QBit test branch policy")
    return {"profile": profile, "orb_version": version, "default_branch": default_branch,
            "java_version": java, "node_version": node, "browsers": boolean(data, "browsers", True),
            "api_checks": boolean(data, "api_checks", False),
            "release_completion": boolean(data, "release_completion", False),
            "release_on_main": boolean(data, "release_on_main", False),
            "release_tag_policy": tag_policy, "test_branch_policy": test_policy,
            "docs_only": boolean(data, "docs_only", False),
            "publish_context": publish_context,
            "publish": {key: boolean(publishing, key, key != "asciidoc" and profile not in ("cli", "all", "repository-policy")
                                      and not (profile == "qbit" and key == "hotfix"))
                        for key in publish_keys}}


def git(*args):
    try:
        return subprocess.run(["git", *args], check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=60).stdout
    except (subprocess.SubprocessError, OSError):
        return None


def proven_docs_only(config, branch, tag):
    if not config["docs_only"] or tag or not (branch == "main" or branch.startswith(("feature/", "hotfix/"))):
        return False
    if git("rev-parse", "--is-shallow-repository") != b"false\n":
        return False
    if branch == "main":
        base = git("rev-parse", "--verify", "HEAD^1")
    else:
        default = config["default_branch"]
        if git("fetch", "--no-tags", "origin", f"+refs/heads/{default}:refs/remotes/origin/{default}") is None:
            return False
        base = git("merge-base", "HEAD", f"refs/remotes/origin/{default}")
    if not base:
        return False
    changed = git("diff", "--no-ext-diff", "--no-renames", "--name-only", "-z", base.decode().strip(), "HEAD")
    if not changed:
        return False
    paths = changed.rstrip(b"\0").split(b"\0")
    eligible = all(path in (b"README.md", b"CHANGELOG.md", b"CONTRIBUTING.md") or
                   (path.startswith(b"docs/") and path.endswith(b".md")) for path in paths)
    return base.decode().strip() if eligible else False


def proven_ci_maintenance(branch, tag):
    """Keep application tests, but do not publish for isolated CI declarations."""
    if tag or not (branch == "main" or branch == "develop" or branch.startswith(("release/", "hotfix/"))):
        return False
    subject = git("log", "-1", "--format=%s")
    if not subject or not re.match(rb"ci(?:\([^\r\n()]+\))?: ", subject):
        return False
    parents = git("rev-list", "--parents", "-n", "1", "HEAD")
    if not parents or not re.fullmatch(rb"[0-9a-f]{40} [0-9a-f]{40}\n", parents):
        return False
    base = parents.split()[1].decode("ascii")
    changed = git("diff", "--no-ext-diff", "--no-renames", "--name-only", "-z", base, "HEAD")
    if not changed:
        return False
    allowed = {b".qqq-ci.yml", b".circleci/config.yml", b".github/workflows/codeql.yml",
               b".github/workflows/release-rc.yml"}
    return all(path in allowed for path in changed.rstrip(b"\0").split(b"\0"))


def event_kind(branch, tag, release_on_main=False, release_tag_policy="stable"):
    if tag:
        if release_tag_policy == "none" or not re.fullmatch(r"v.*" if release_tag_policy == "v-prefix" else r"v\d+\.\d+\.\d+", tag, flags=re.ASCII):
            return "test"
        tagged = git("rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
        if not tagged and git("fetch", "--no-tags", "origin", f"refs/tags/{tag}:refs/tags/{tag}") is not None:
            tagged = git("rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
        return "release" if tagged and tagged == git("rev-parse", "HEAD") else "test"
    if branch == "main" and release_on_main:
        return "release"
    if branch == "develop":
        return "snapshot"
    if re.fullmatch(r"release/.+", branch):
        return "release_candidate"
    return "test"


def qbit_template(config, branch, tag):
    """Profile-owned template; add future profiles as reviewed renderers, not raw YAML."""
    kind = event_kind(branch, tag, config.get("release_on_main", False), config.get("release_tag_policy", "stable"))
    if not tag and re.fullmatch(r"hotfix/.+", branch) and config["publish"].get("hotfix", False):
        kind = "hotfix"
    if kind != "test" and not config["publish"][kind]:
        kind = "test"
    maintenance = kind != "test" and proven_ci_maintenance(branch, tag)
    if maintenance:
        kind = "test"
    workflow = "test_only" if kind == "test" else "publish_" + kind
    result = {"version": 2.1, "orbs": {"qqq-orb": "kingsrook/qqq-orb@" + config["orb_version"]}}
    filters = ({"branches": {"ignore": "/.*/"}, "tags": {"only": "/.*/"}} if tag else
               {"branches": {"ignore": "automation/qbit-rc-pending"}, "tags": {"ignore": "/.*/"}})
    if kind == "test" and not tag and not maintenance:
        ignores = {"all": None, "non-release": "/(develop|release/.*)/",
                   "non-release-no-integration": "/(develop|release/.*|integration.*)/",
                   "feature": "/(develop|main|release/.*|integration.*)/",
                   "non-release-no-main": "/(develop|main|release/.*)/",
                   "non-release-no-hotfix": "/(develop|release/.*|hotfix/.*)/",
                   "non-release-no-main-hotfix": "/(develop|main|release/.*|hotfix/.*)/",
                   "feature-no-hotfix": "/(develop|main|release/.*|hotfix/.*|integration.*)/"}
        ignored = ignores[config.get("test_branch_policy", "all")]
        if ignored:
            filters["branches"]["ignore"] = ["automation/qbit-rc-pending", ignored]
    docs_base = proven_docs_only(config, branch, tag) if kind == "test" and not maintenance else False
    if docs_base:
        # Keep the existing workflow/result identity even when Maven is not needed.
        result["jobs"] = {"docs_only": {"resource_class": "small", "docker": [{"image": "cimg/base:2026.03"}],
                                         "steps": ["checkout", {"run": {"name": "Check documentation whitespace",
                                                            "command": f"git fetch --no-tags origin {docs_base}\ngit diff --check {docs_base} HEAD"}}]}}
        invocation = {"docs_only": {"name": "qqq-orb/mvn_test_only", "filters": filters}}
    else:
        options = {"java_version": config["java_version"], "install_browsers": config["browsers"],
                   "compile_before_verify": False, "check_middleware_api_versions": config["api_checks"],
                   "context": ["qqq-maven-registry-credentials"], "filters": filters}
        job = "qqq-orb/mvn_test_only"
        if kind != "test":
            job = "qqq-orb/mvn_publish"
            options.update(branch_type=kind, publish_asciidoc=config["publish"]["asciidoc"])
            if kind == "release_candidate":
                options["notify_rc_published"] = config["release_completion"]
        invocation = {job: options}
    result["workflows"] = {workflow: {"jobs": [invocation]}}
    return result


def core_template(config, branch, tag):
    """Keep the core acceptance/release graph in the orb; scripts stay with core."""
    result = copy.deepcopy(CORE_TEMPLATE)
    result["orbs"]["qqq-orb"] = "kingsrook/qqq-orb@" + config["orb_version"]
    kind = event_kind(branch, tag)
    if tag.startswith("publish"):
        tagged = git("rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
        if not tagged and git("fetch", "--no-tags", "origin", f"refs/tags/{tag}:refs/tags/{tag}") is not None:
            tagged = git("rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
        if tagged and tagged == git("rev-parse", "HEAD"):
            kind = "feature"
    elif not tag and branch.startswith("hotfix/"):
        kind = "hotfix"
    if kind != "test" and not config["publish"][kind]:
        kind = "test"
    if kind == "test" and proven_docs_only(config, branch, tag):
        return qbit_template(config, branch, tag)
    workflow = {"test": "test_only", "hotfix": "publish_hotfix_release"}.get(kind, "publish_" + kind)
    result["workflows"] = {workflow: result["workflows"][workflow]}
    # Shared install_java owns unattended installation and the signed archive mirror.
    del result["commands"]["configure-package-install"]
    def remove_package_steps(value):
        if isinstance(value, list):
            return [remove_package_steps(item) for item in value if item != "configure-package-install"]
        if isinstance(value, dict):
            return {key: remove_package_steps(item) for key, item in value.items()}
        return value
    result = remove_package_steps(result)
    for name, job in result["jobs"].items():
        steps = job["steps"]
        for index, step in enumerate(steps):
            if step == "qqq-orb/mvn_build":
                steps[index] = {"qqq-orb/mvn_build": {"install_browsers": config["browsers"], "compile_before_verify": False}}
            elif step == "qqq-orb/install_java":
                steps[index] = {"qqq-orb/install_java": {"java_version": config["java_version"]}}
            elif isinstance(step, dict) and "qqq-orb/install_java" in step:
                step["qqq-orb/install_java"]["java_version"] = config["java_version"]
        if name in ("esb_broker_conformance", "sample_acceptance", "sample_multinode_acceptance", "sample_consumer_acceptance"):
            # Only save after the last successful executable verification step.
            last_run = max(i for i, step in enumerate(steps) if isinstance(step, dict) and "run" in step)
            steps.insert(last_run + 1, "qqq-orb/mvn_cache_save")
    # Keep the copied Lambda reports for the coverage workspace, but do not upload
    # them twice: their original directories are already uploaded by sample_acceptance.
    collect = result["commands"]["store-sample-results"]["steps"][0]["run"]
    collect["command"] = collect["command"].replace(
        '  if [ -f "$report" ]; then',
        '  case "${report##*/}" in\n'
        '    TEST-com.kingsrook.sampleapp.SampleLambdaDispatchAcceptanceTest.xml|TEST-com.kingsrook.sampleapp.SampleSqsUtilityAcceptanceTest.xml) continue ;;\n'
        '  esac\n  if [ -f "$report" ]; then')
    filters = ({"branches": {"ignore": "/.*/"}, "tags": {"only": "/.*/"}} if tag else
               {"branches": {"ignore": "automation/qbit-rc-pending"}, "tags": {"ignore": "/.*/"}})
    for invocation in result["workflows"][workflow]["jobs"]:
        job, options = next(iter(invocation.items()))
        options["filters"] = copy.deepcopy(filters)
        if job in ("qqq-orb/mvn_test_only", "qqq-orb/mvn_publish"):
            options.update(java_version=config["java_version"], install_browsers=config["browsers"],
                           compile_before_verify=False, check_middleware_api_versions=config["api_checks"])
            if job == "qqq-orb/mvn_publish":
                options["publish_asciidoc"] = config["publish"]["asciidoc"]
    return result


def frontend_template(config, branch, tag):
    material = config["profile"] == "frontend-material"
    kind = event_kind(branch, tag)
    if tag.startswith("publish") or (not material and tag.startswith("v")):
        tagged = git("rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
        if not tagged and git("fetch", "--no-tags", "origin", f"refs/tags/{tag}:refs/tags/{tag}") is not None:
            tagged = git("rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
        if tagged and tagged == git("rev-parse", "HEAD"):
            kind = "feature" if tag.startswith("publish") else "release"
    elif not tag and branch.startswith("hotfix/"):
        kind = "hotfix"
    elif not tag and branch == "main" and not material:
        kind = "release"
    if kind != "test" and not config["publish"][kind]:
        kind = "test"
    if kind == "test" and proven_docs_only(config, branch, tag):
        result = qbit_template(config, branch, tag)
        result["workflows"]["test_only"]["jobs"][0]["docs_only"]["name"] = (
            "qqq-orb/mvn_frontend_test_only" if material else "qqq-orb/node_test_only")
        return result
    workflow = {"test": "test_only", "hotfix": "publish_hotfix_release"}.get(kind, "publish_" + kind)
    playwright = material and runtime_boolean("QQQ_CI_RUN_PLAYWRIGHT") and kind in ("test", "snapshot")
    if playwright:
        workflow += "_with_playwright"
    result = {"version": 2.1, "orbs": {"qqq-orb": "kingsrook/qqq-orb@" + config["orb_version"]}}
    filters = ({"branches": {"ignore": "/.*/"}, "tags": {"only": "/.*/"}} if tag else
               {"branches": {"ignore": "automation/qbit-rc-pending"}, "tags": {"ignore": "/.*/"}})
    job = "qqq-orb/" + ("mvn_frontend_" if material else "node_") + ("test_only" if kind == "test" else "publish")
    options = {"node_version": config["node_version"], "context": ["qqq-maven-registry-credentials"], "filters": filters}
    if material:
        options["java_version"] = config["java_version"]
        result["parameters"] = {"run_playwright": {"type": "boolean", "default": playwright}}
    else:
        options["context"].append("build-qqq-sample-app")
    if kind != "test":
        options["branch_type"] = kind
        if not material:
            options["npm_trusted_publishing"] = True
    jobs = []
    if playwright:
        result.update(copy.deepcopy(MATERIAL_TEMPLATE))
        steps = result["jobs"]["playwright_tests"]["steps"]
        for step in steps:
            if not isinstance(step, dict):
                continue
            if "restore_cache" in step:
                step["restore_cache"]["keys"] = ['material-npm-downloads-v1-{{ checksum "package-lock.json" }}', 'material-npm-downloads-v1-']
            if "save_cache" in step:
                step["save_cache"].update(key='material-npm-downloads-v1-{{ checksum "package-lock.json" }}', paths=["~/.npm"])
            if "run" in step and step["run"]["name"] == "Install dependencies":
                step["run"]["command"] = "npm ci --legacy-peer-deps --prefer-offline --cache ~/.npm"
        jobs.append({"playwright_tests": {"filters": copy.deepcopy(filters)}})
        options["requires"] = ["playwright_tests"]
    jobs.append({job: options})
    result["workflows"] = {workflow: {"jobs": jobs}}
    return result


def cli_template(config, branch, tag):
    publish = False
    if tag.startswith("v") and config["publish"]["release"]:
        tagged = git("rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
        if not tagged and git("fetch", "--no-tags", "origin", f"refs/tags/{tag}:refs/tags/{tag}") is not None:
            tagged = git("rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
        publish = bool(tagged and tagged == git("rev-parse", "HEAD"))
    filters = ({"branches": {"ignore": "/.*/"}, "tags": {"only": "/.*/"}} if tag else
               {"branches": {"ignore": "automation/qbit-rc-pending"}, "tags": {"ignore": "/.*/"}})
    options = {"publish": publish, "filters": filters}
    if publish:
        options["context"] = [config["publish_context"]]
    # CLI docs are still verified until its generated-client inputs get a dedicated policy.
    return {"version": 2.1, "orbs": {"qqq-orb": "kingsrook/qqq-orb@" + config["orb_version"]},
            "workflows": {"publish_release" if publish else "test_only": {"jobs": [{"qqq-orb/cli_verify_publish": options}]}}}


def marketing_template(config, branch, tag):
    del config, branch, tag
    # One final continuation; Munitor supplies jobs, never another setup pipeline.
    return copy.deepcopy(MARKETING_TEMPLATE)


def android_template(config, branch, tag):
    del config, branch, tag
    return copy.deepcopy(ANDROID_TEMPLATE)


def policy_template(config, branch, tag):
    del config, branch, tag
    return copy.deepcopy(POLICY_TEMPLATE)


def all_template(config, branch, tag):
    result = json.loads(json.dumps(ALL_TEMPLATE).replace("__ORB_VERSION__", config["orb_version"]))
    jobs = result["workflows"]["verify-and-smoke"]["jobs"]
    for entry in jobs:
        next(iter(entry.values()))["filters"] = {"branches": {"ignore": "automation/qbit-rc-pending"}, "tags": {"ignore": "/.*/"}}
    if branch == "develop" and not tag and config["publish"]["snapshot"]:
        jobs.append({"qqq-orb/all_develop_image": {"context": [config["publish_context"]], "requires": ["build-and-test", "core", "full"], "filters": {"branches": {"only": "develop"}, "tags": {"ignore": "/.*/"}}}})
    return result


def starter_template(config, branch, tag):
    del branch, tag
    result = json.loads(json.dumps(STARTER_TEMPLATE).replace("__ORB_VERSION__", config["orb_version"]))
    result["workflows"]["test_only"]["jobs"][0]["qqq-orb/mvn_test_only"]["filters"]["branches"] = {"ignore": "automation/qbit-rc-pending"}
    return result


def next_template(config, branch, tag):
    del branch, tag  # Tag-only filters preserve the existing release validation.
    return json.loads(json.dumps(NEXT_TEMPLATE).replace("__ORB_VERSION__", config["orb_version"]))


def voyage_template(config, branch, tag):
    del branch, tag  # This profile's reviewed static filters own its three workflows.
    return json.loads(json.dumps(VOYAGE_TEMPLATE).replace("__ORB_VERSION__", config["orb_version"]))


def repository_policy_template(config, branch, tag):
    del config, branch, tag
    return copy.deepcopy(REPOSITORY_POLICY_TEMPLATE)


PROFILE_TEMPLATES = {"qbit": qbit_template, "core": core_template,
                     "repository-policy": repository_policy_template,
                     "frontend-material": frontend_template, "frontend-core": frontend_template,
                     "cli": cli_template, "voyage": voyage_template, "frontend-next": next_template, "all": all_template, "app-starter": starter_template, "android": android_template, "mcp-policy": policy_template, "marketing": marketing_template}


def runtime_boolean(name):
    value = os.environ.get(name, "false").lower()
    if value in ("true", "1"):
        return True
    if value in ("false", "0"):
        return False
    raise ManifestError("Runtime boolean parameter has an unsupported representation")


def continuation_parameters(profile):
    runtime_boolean("QQQ_CI_RUN_PLAYWRIGHT")
    if profile != "frontend-material" and runtime_boolean("QQQ_CI_RUN_PLAYWRIGHT"):
        raise ManifestError("run_playwright requires frontend-material")
    values = {"mongo_bind_diagnostics": runtime_boolean("QQQ_CI_MONGO_DIAGNOSTICS")}
    for key in ("next_acceptance_bundle_url", "next_acceptance_bundle_sha256", "next_acceptance_receipt_sha256"):
        values[key] = os.environ.get("QQQ_CI_" + key.upper(), "")
    if profile != "core":
        if any(values.values()):
            raise ManifestError("Core pipeline parameters require the core profile")
        return {}
    return values


def main():
    config = load_manifest(os.environ.get("QQQ_CI_MANIFEST", ".qqq-ci.yml"), os.environ.get("QQQ_CI_ORB_VERSION", ""))
    expected = os.environ.get("CIRCLE_SHA1")
    if expected and (not re.fullmatch(r"[0-9a-fA-F]{40}", expected) or git("rev-parse", "HEAD") != (expected + "\n").encode()):
        raise ManifestError("Checkout does not match the pipeline commit")
    output = PROFILE_TEMPLATES[config["profile"]](config, os.environ.get("CIRCLE_BRANCH", ""), os.environ.get("CIRCLE_TAG", ""))
    if config["profile"] in ("qbit", "core", "frontend-core", "frontend-material"):
        # One whole-workflow check follows the same commit from feature to release.
        # Keep every selected job, dependency and filter; add no runner or duplicate build.
        if len(output["workflows"]) != 1:
            raise ManifestError("Stable verification requires exactly one selected workflow")
        output["workflows"] = {"verify": next(iter(output["workflows"].values()))}
    parameters = continuation_parameters(config["profile"])
    if config["profile"] == "core":
        output["parameters"] = copy.deepcopy(CORE_TEMPLATE["parameters"])
        for name, value in parameters.items():
            output["parameters"][name]["default"] = value
    elif config["profile"] == "frontend-material":
        output["parameters"] = {"run_playwright": {"type": "boolean", "default": runtime_boolean("QQQ_CI_RUN_PLAYWRIGHT")}}
    encoded = json.dumps(output, indent=2) + "\n"
    Path(os.environ.get("QQQ_CI_OUTPUT", "/tmp/qqq-generated-config.json")).write_text(encoded, encoding="utf-8")
    if os.environ.get("QQQ_CI_CONTINUE") == "true":
        key = os.environ.get("CIRCLE_CONTINUATION_KEY")
        if not key:
            raise ManifestError("CircleCI continuation key is unavailable")
        # Values are in the continued declarations, avoiding setup/API parameter conflicts.
        payload = json.dumps({"continuation-key": key, "configuration": encoded}).encode()
        request = urllib.request.Request("https://circleci.com/api/v2/pipeline/continue", data=payload,
                                         headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                if response.status != 200:
                    raise ManifestError("CircleCI continuation failed")
        except urllib.error.HTTPError as error:
            raise ManifestError(f"CircleCI continuation failed (HTTP {error.code})") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise ManifestError("CircleCI continuation failed; inspect pipeline status") from error


if __name__ == "__main__":
    try:
        main()
    except ManifestError as error:
        # ManifestError messages are authored above; never include raw input or HTTP bodies.
        print(f"Pipeline generation failed: {error}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError:
        print("Pipeline generation failed: invalid manifest YAML.", file=sys.stderr)
        sys.exit(1)
    except OSError:
        print("Pipeline generation failed: manifest input or generated output is inaccessible.", file=sys.stderr)
        sys.exit(1)
