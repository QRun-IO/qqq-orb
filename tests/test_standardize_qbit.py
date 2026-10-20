"""Migration must preserve publication opt-outs and reject unknown work."""
import importlib.util
import json
from pathlib import Path
import re
import unittest
from unittest import mock

import yaml

spec = importlib.util.spec_from_file_location(
    "migration", Path(__file__).resolve().parents[1] / "tools/standardize_qbit.py")
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class MigrationTests(unittest.TestCase):
    def test_630_original_filter_intersections_equal_generated_publications(self):
        spec = importlib.util.spec_from_file_location(
            "publication_pipeline", Path(__file__).resolve().parents[1] / "src/scripts/generate_pipeline.py")
        pipeline = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pipeline)
        fixtures = json.loads((Path(__file__).parent / "fixtures/qbit-publication-policies.json").read_text(encoding="utf-8"))

        def matches(value, patterns):
            if not isinstance(patterns, list):
                patterns = [patterns]
            return any(re.fullmatch(pattern[1:-1], value) is not None
                       if pattern.startswith("/") and pattern.endswith("/") else pattern == value
                       for pattern in patterns)

        def original_selects(filters, branch, tag):
            # Circle tags are opt-in; branch filters govern branch events only.
            selection = filters.get("tags" if tag else "branches", {})
            if tag and not selection:
                return False
            value = tag or branch
            return (("only" not in selection or matches(value, selection["only"])) and
                    ("ignore" not in selection or not matches(value, selection["ignore"])))

        cases = [(branch, "") for branch in (
            "main", "develop", "release/1", "feature/a", "hotfix/a",
            "integration-test", "staging", "arbitrary")]
        cases += [("", tag) for tag in (
            "v1.2.3", "v1.2.3-RC.1", "vanything", "v", "publish1", "1.2.3", "invalid")]
        checked = 0
        for fixture in fixtures:
            manifest = migration.infer_manifest(fixture["config"], "0.7.0", fixture["default_branch"])
            with mock.patch.object(Path, "read_text", return_value=yaml.safe_dump(manifest)):
                config = pipeline.load_manifest("unused", "0.7.0")
            for branch, tag in cases:
                with self.subTest(repository=fixture["name"], branch=branch, tag=tag):
                    expected = [
                        options["branch_type"]
                        for workflow in fixture["config"]["workflows"].values()
                        for entry in workflow["jobs"] for job, options in entry.items()
                        if job == "qqq-orb/mvn_publish" and original_selects(options["filters"], branch, tag)
                    ]
                    with mock.patch.object(pipeline, "git", return_value=b"verified-head\n"):
                        generated = pipeline.qbit_template(config, branch, tag)
                    actual = [
                        options["branch_type"]
                        for workflow in generated["workflows"].values()
                        for entry in workflow["jobs"] for job, options in entry.items()
                        if job == "qqq-orb/mvn_publish"
                    ]
                    self.assertEqual(actual, expected)
                    checked += 1
        self.assertEqual(checked, 630)

    def config(self, job="qqq-orb/mvn_test_only", **options):
        return {"version": 2.1, "orbs": {"qqq-orb": "kingsrook/qqq-orb@0.5.0"},
                "workflows": {"build": {"jobs": [{job: options}]}}}

    def test_test_only_stays_non_publishing(self):
        manifest = migration.infer_manifest(self.config(), "0.7.0", "main")
        self.assertFalse(any(manifest["publish"].values()))

    def test_snapshot_does_not_enable_rc_or_release(self):
        manifest = migration.infer_manifest(
            self.config("qqq-orb/mvn_publish", branch_type="snapshot",
                        filters={"branches": {"only": ["develop"]}}),
            "0.7.0", "develop")
        self.assertTrue(manifest["publish"]["snapshot"])
        self.assertFalse(manifest["publish"]["release_candidate"])
        self.assertFalse(manifest["publish"]["release"])

    def test_reject_custom_work(self):
        for config in (self.config("custom"),
                       self.config(requires=["security"]),
                       self.config("qqq-orb/mvn_publish", branch_type="hotfix"),
                       self.config(context=["different-secret"]),
                       self.config(**{"pre-steps": ["custom-test"]})):
            with self.subTest(config=config), self.assertRaises(ValueError):
                migration.infer_manifest(config, "0.7.0", "develop")

    def test_caller_filters_tags_and_lock(self):
        caller = migration.canonical_caller("0.7.0")
        self.assertTrue(caller["setup"])
        options = caller["workflows"]["setup"]["jobs"][0]["qqq-orb/generate_pipeline"]
        self.assertEqual(options["filters"]["tags"]["only"], "/.*/")
        self.assertEqual(options["filters"]["branches"]["ignore"],
                         "automation/qbit-rc-pending")

    def test_all_42_audited_repositories_preserve_publication_policies(self):
        fixtures = json.loads((Path(__file__).parent / "fixtures/qbit-publication-policies.json").read_text(encoding="utf-8"))
        self.assertEqual(len(fixtures), 42)
        mains, broad, no_tags = set(), set(), set()
        for fixture in fixtures:
            with self.subTest(repository=fixture["name"]):
                manifest = migration.infer_manifest(fixture["config"], "0.7.0", fixture["default_branch"])
                if manifest["release_on_main"]:
                    mains.add(fixture["name"])
                if manifest["release_tag_policy"] == "v-prefix":
                    broad.add(fixture["name"])
                if manifest["release_tag_policy"] == "none":
                    no_tags.add(fixture["name"])
                    caller = migration.canonical_caller("0.7.0", "none")
                    self.assertEqual(caller["workflows"]["setup"]["jobs"][0]["qqq-orb/generate_pipeline"]["filters"]["tags"], {"ignore": "/.*/"})
        self.assertEqual(mains, {"qbit-middleware-mcp", "qbit-geo-data", "qbit-customizable-table-views",
                                "qbit-sftp-data-integration", "qbit-wms", "qbit-standard-process-trace",
                                "qbit-user-role-permissions", "qbit-session-store"})
        self.assertEqual(broad, {"qbit-middleware-mcp", "qbit-geo-data", "qbit-custom-apps", "qbit-workflows"})
        self.assertEqual(no_tags, {"qbit-help", "qbit-template-application", "qbit-template-extension", "qbit-template-data"})

    def test_unknown_filters_fail_closed(self):
        good = {"branches": {"only": ["main"]}, "tags": {"only": [r"/^v\d+\.\d+\.\d+$/"]}}
        for filters in ({}, {"branches": {"only": ["staging"]}}, {"branches": {"ignore": "/.*/"}, "tags": {"only": ["/publish.*/"]}},
                        {**good, "other": "ignored"}, {**good, "tags": {"only": ["v1", "v2"]}}):
            with self.subTest(filters=filters), self.assertRaises(ValueError):
                migration.infer_manifest(self.config("qqq-orb/mvn_publish", branch_type="release", filters=filters), "0.7.0", "main")
        with self.assertRaises(ValueError):
            migration.infer_manifest(self.config(filters={"branches": {"ignore": "/custom.*/"}}), "0.7.0", "main")


if __name__ == "__main__":
    unittest.main()
