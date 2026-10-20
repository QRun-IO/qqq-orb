"""Migration must preserve publication opt-outs and reject unknown work."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "migration", Path(__file__).resolve().parents[1] / "tools/standardize_qbit.py")
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class MigrationTests(unittest.TestCase):
    def config(self, job="qqq-orb/mvn_test_only", **options):
        return {"version": 2.1, "orbs": {"qqq-orb": "kingsrook/qqq-orb@0.5.0"},
                "workflows": {"build": {"jobs": [{job: options}]}}}

    def test_test_only_stays_non_publishing(self):
        manifest = migration.infer_manifest(self.config(), "0.7.0", "main")
        self.assertFalse(any(manifest["publish"].values()))

    def test_snapshot_does_not_enable_rc_or_release(self):
        manifest = migration.infer_manifest(
            self.config("qqq-orb/mvn_publish", branch_type="snapshot"),
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


if __name__ == "__main__":
    unittest.main()
