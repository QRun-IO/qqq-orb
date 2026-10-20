"""Fail-closed checks for the manual 4.1.0 GA / exact RC.1 release workflow."""

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from xml.etree import ElementTree


QBITS = (
    "quick-search", "user-role-permissions", "customizable-table-views",
    "standard-process-trace", "webhooks", "workflows", "geo-data",
    "sftp-data-integration",
)
RELEASE_VERSIONS = ("4.1.0", "4.1.0-RC.1")


def immutable_version(value):
    return re.fullmatch(r"[0-9]+(?:\.[0-9]+){2,3}(?:-RC\.[1-9][0-9]*)?", value) is not None


def validate_version(version):
    if version not in RELEASE_VERSIONS:
        raise GateError("This release workflow is limited to 4.1.0 and 4.1.0-RC.1")


class GateError(ValueError):
    pass


def properties(path):
    root = ElementTree.parse(path).getroot()
    namespace = xml_namespace(root)
    values = root.find(f"{namespace}properties")
    if values is None:
        raise GateError(f"Missing Maven properties in {path}")
    return {child.tag.removeprefix(namespace): (child.text or "").strip() for child in values}


def xml_namespace(root):
    return root.tag.partition("}")[0] + "}" if root.tag.startswith("{") else ""


def coordinates(path):
    root = ElementTree.parse(path).getroot()
    namespace = xml_namespace(root)
    parent = root.find(f"{namespace}parent")

    def value(name):
        direct = root.findtext(f"{namespace}{name}")
        inherited = parent.findtext(f"{namespace}{name}") if parent is not None else None
        return direct or inherited

    return value("groupId"), value("artifactId"), value("version")


def managed_dependencies(path):
    root = ElementTree.parse(path).getroot()
    namespace = xml_namespace(root)
    values = properties(path)
    if root.findall(f"{namespace}profiles/{namespace}profile/{namespace}dependencyManagement"):
        raise GateError(f"Profile-managed dependency override in {path}")
    dependencies = root.find(f"{namespace}dependencyManagement/{namespace}dependencies")
    if dependencies is None:
        raise GateError(f"Missing dependencyManagement in {path}")

    def field(dependency, name, default=""):
        return (dependency.findtext(f"{namespace}{name}") or default).strip()

    managed = []
    for dependency in dependencies.findall(f"{namespace}dependency"):
        version = field(dependency, "version")
        reference = re.fullmatch(r"\$\{([^}]+)\}", version)
        if reference:
            version = values.get(reference.group(1), "")
        if not immutable_version(version):
            raise GateError(f"Unreleased managed dependency in {path}: "
                            f"{field(dependency, 'artifactId')}")
        managed.append((field(dependency, "groupId"), field(dependency, "artifactId"),
                        version, field(dependency, "type", "jar"),
                        field(dependency, "scope", "compile"),
                        field(dependency, "classifier")))
    if not managed:
        raise GateError(f"No managed dependencies in {path}")
    return managed


def validate_managed_bom(path, version):
    managed = managed_dependencies(path)
    entries = {(group, artifact): (pin, kind, scope) for group, artifact, pin, kind, scope, _ in managed}
    if len(entries) != len(managed):
        raise GateError(f"Duplicate managed dependency in {path}")
    if entries.get(("com.kingsrook.qqq", "qqq-bom-pom")) != (version, "pom", "import"):
        raise GateError(f"QQQ BOM import differs from {version} in {path}")
    values = properties(path)
    if entries.get(("com.kingsrook.qqq", "qqq-frontend-next")) != (
            values.get("qqq-frontend-next.version"), "jar", "compile"):
        raise GateError(f"Managed Next differs from its release pin in {path}")
    for name in QBITS:
        artifact = f"qbit-{name}"
        if entries.get(("com.kingsrook.qbits", artifact)) != (
                values.get(f"{artifact}.version"), "jar", "compile"):
            raise GateError(f"Managed {artifact} differs from its release pin in {path}")
    return managed


def validate_published_poms(parent_path, bom_path, version, local_bom):
    expected = (
        (parent_path, "qqq-all-parent"),
        (bom_path, "qqq-all-bom"),
    )
    for path, artifact in expected:
        if coordinates(path) != ("com.kingsrook.qqq", artifact, version):
            raise GateError(f"Published {artifact} POM is not the {version} release")
    published = properties(bom_path)
    if published.get("qqq.version") != version:
        raise GateError(f"Published BOM does not import QQQ {version}")
    for name in QBITS:
        key = f"qbit-{name}.version"
        value = published.get(key, "")
        if not immutable_version(value):
            raise GateError(f"Published BOM {key} is not a release")
    local = properties(local_bom)
    for key in ("qqq.version", "qqq-frontend-next.version", *(f"qbit-{name}.version" for name in QBITS)):
        if published.get(key) != local.get(key):
            raise GateError(f"Published BOM {key} differs from release source")
    if validate_managed_bom(bom_path, version) != validate_managed_bom(local_bom, version):
        raise GateError("Published BOM dependencyManagement differs from release source")


def validate_poms(root, version):
    validate_version(version)
    parent = properties(root / "pom.xml")
    bom = properties(root / "qqq-all-bom/pom.xml")
    if parent.get("revision") != version or bom.get("qqq.version") != version:
        raise GateError(f"Parent revision and QQQ BOM pin must both equal {version}")
    for name in QBITS:
        key = f"qbit-{name}.version"
        value = bom.get(key, "")
        if not immutable_version(value):
            raise GateError(f"{key} must be a published non-snapshot version")
    for key, value in bom.items():
        if key.endswith(".version") and not immutable_version(value):
            raise GateError(f"{key} must be an immutable release version")
    validate_managed_bom(root / "qqq-all-bom/pom.xml", version)


def validate_smoke(run, jobs, sha):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise GateError("Release SHA must be a full lowercase Git commit ID")
    expected = {
        "name": "Smoke", "path": ".github/workflows/smoke.yml",
        "head_sha": sha, "head_branch": "develop", "event": "push",
        "conclusion": "success",
    }
    for key, value in expected.items():
        if run.get(key) != value:
            raise GateError(f"Smoke run {key} must equal {value}")
    observed = {"core": False, "full": False}
    for job in jobs.get("jobs", []):
        name = job.get("name")
        if name in observed:
            if job.get("conclusion") != "success":
                raise GateError(f"Smoke job {name} did not pass")
            observed[name] = True
    if not all(observed.values()):
        raise GateError("Smoke run must include successful core and full jobs")


def validate_upstream_release(release, version):
    if (not immutable_version(version) or release.get("tag_name") != "v" + version
            or release.get("draft") is not False
            or release.get("prerelease") is not ("-RC." in version)):
        raise GateError(f"Upstream release must be public v{version} with matching prerelease state")


def validate_tag(tag, version, sha, tag_sha):
    validate_version(version)
    if not all(re.fullmatch(r"[0-9a-f]{40}", value) for value in (sha, tag_sha)):
        raise GateError("Tag and commit IDs must be full Git SHAs")
    if (tag.get("sha") != tag_sha or tag.get("tag") != version
            or tag.get("object", {}).get("type") != "commit"
            or tag.get("object", {}).get("sha") != sha
            or tag.get("verification", {}).get("verified") is not True
            or tag.get("verification", {}).get("reason") != "valid"):
        raise GateError("Release tag must be signed, verified, annotated and point to the exact release commit")


def download_public_inputs(bom, version, destination, central="https://repo.maven.apache.org/maven2"):
    """Fetch the declared first-party inputs and their parents without credentials."""
    validate_version(version)
    destination.mkdir(parents=True, exist_ok=True)
    receipts = []
    visited = set()

    def fetch(group, artifact, pin, kind):
        coordinate = (group, artifact, pin, kind)
        if coordinate in visited:
            return
        if (not re.fullmatch(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*", group)
                or not re.fullmatch(r"[A-Za-z0-9_-]+", artifact) or not immutable_version(pin)):
            raise GateError(f"Invalid or mutable public coordinate: {coordinate}")
        visited.add(coordinate)
        relative = f"{group.replace('.', '/')}/{artifact}/{pin}/{artifact}-{pin}.{kind}"
        url = central + "/" + relative
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                data = response.read()
        except (urllib.error.URLError, OSError) as error:
            if isinstance(error, urllib.error.HTTPError):
                error.close()
            raise GateError(f"Public input unavailable: {relative}") from error
        if not data:
            raise GateError(f"Empty public input: {relative}")
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        if kind == "pom":
            if coordinates(path) != (group, artifact, pin):
                raise GateError(f"Public POM coordinates differ: {relative}")
            root = ElementTree.fromstring(data)
            ns = xml_namespace(root)
            parent = root.find(f"{ns}parent")
            if parent is not None:
                parent_group = parent.findtext(f"{ns}groupId", "")
                parent_pin = parent.findtext(f"{ns}version", "")
                if not immutable_version(parent_pin):
                    raise GateError(f"Mutable parent in {relative}")
                if parent_group.startswith("com.kingsrook"):
                    fetch(parent_group, parent.findtext(f"{ns}artifactId", ""), parent_pin, "pom")
            if artifact == "qbit-build-parent":
                imports = root.findall(f"{ns}dependencyManagement/{ns}dependencies/{ns}dependency")
                props = root.find(f"{ns}properties")
                values = {child.tag.removeprefix(ns): child.text for child in props} if props is not None else {}
                qqq_imports = [dep for dep in imports if dep.findtext(f"{ns}groupId") == "com.kingsrook.qqq"
                               and dep.findtext(f"{ns}artifactId") == "qqq-bom-pom"]
                if len(qqq_imports) != 1:
                    raise GateError("Public qbit-build-parent must import the candidate QQQ BOM")
                dep = qqq_imports[0]
                actual = dep.findtext(f"{ns}version", "")
                actual = values.get(actual[2:-1], "") if actual.startswith("${") else actual
                if (actual != version or dep.findtext(f"{ns}type") != "pom"
                        or dep.findtext(f"{ns}scope") != "import"):
                    raise GateError("Public qbit-build-parent QQQ import differs from the candidate")
        receipts.append({"url": url, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})

    for group, artifact, pin, kind, _, classifier in validate_managed_bom(bom, version):
        if group.startswith("com.kingsrook"):
            if classifier or kind not in ("jar", "pom"):
                raise GateError(f"Unsupported first-party release input: {artifact}")
            fetch(group, artifact, pin, "pom")
            if kind == "jar":
                fetch(group, artifact, pin, "jar")
    (destination / "receipts.json").write_text(json.dumps(receipts, indent=2) + "\n")
    return receipts


def validate_evidence(sha, smoke_run=None, smoke_jobs=None, circle_smoke=None):
    if circle_smoke is not None:
        if smoke_run is not None or smoke_jobs is not None:
            raise GateError("Select exactly one complete smoke evidence mode")
        from verify_all_circle_smoke import validate, EvidenceError
        try:
            if (circle_smoke.get("schema") != "qqq-all-circle-smoke/v1"
                    or circle_smoke.get("repository") != "QRun-IO/qqq-all"
                    or circle_smoke.get("sha") != sha):
                raise GateError("Circle evidence schema, repository or SHA differs")
            validate(sha, circle_smoke["workflow_id"], circle_smoke["workflow"],
                     circle_smoke["pipeline"], circle_smoke["jobs"],
                     circle_smoke["check_runs"], circle_smoke["pipeline_workflows"])
        except (EvidenceError, KeyError, TypeError) as error:
            raise GateError("Circle smoke evidence rejected") from error
    else:
        if smoke_run is None or smoke_jobs is None:
            raise GateError("Select exactly one complete smoke evidence mode")
        validate_smoke(smoke_run, smoke_jobs, sha)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--smoke-run", type=Path)
    parser.add_argument("--smoke-jobs", type=Path)
    parser.add_argument("--circle-smoke", type=Path)
    parser.add_argument("--published-parent", type=Path, required=True)
    parser.add_argument("--published-bom", type=Path, required=True)
    parser.add_argument("--upstream-release", type=Path, required=True)
    parser.add_argument("--next-release", type=Path, required=True)
    parser.add_argument("--tag-object", type=Path, required=True)
    parser.add_argument("--tag-sha", required=True)
    parser.add_argument("--public-inputs", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate_poms(args.root, args.version)
        validate_upstream_release(json.loads(args.upstream_release.read_text()), args.version)
        validate_upstream_release(json.loads(args.next_release.read_text()),
                                  properties(args.root / "qqq-all-bom/pom.xml")["qqq-frontend-next.version"])
        validate_tag(json.loads(args.tag_object.read_text()), args.version, args.sha, args.tag_sha)
        validate_evidence(args.sha,
                          json.loads(args.smoke_run.read_text()) if args.smoke_run else None,
                          json.loads(args.smoke_jobs.read_text()) if args.smoke_jobs else None,
                          json.loads(args.circle_smoke.read_text()) if args.circle_smoke else None)
        validate_published_poms(args.published_parent, args.published_bom, args.version,
                                args.root / "qqq-all-bom/pom.xml")
        download_public_inputs(args.root / "qqq-all-bom/pom.xml", args.version, args.public_inputs)
    except (GateError, OSError, ElementTree.ParseError, json.JSONDecodeError) as error:
        print(f"Release gate failed: {error}", file=sys.stderr)
        return 1
    print("Local POM and exact-commit smoke gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
