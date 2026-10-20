import copy
import importlib.util
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("validate_standard", ROOT / "src/scripts/validate_standard.py")
standard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(standard)
VERSION = "0.7.0"
CALLER = {
    "version": 2.1, "setup": True,
    "orbs": {"qqq-orb": "kingsrook/qqq-orb@0.7.0"},
    "workflows": {"setup": {"jobs": [{"qqq-orb/generate_pipeline": {
        "orb_version": "0.7.0",
        "filters": {"branches": {"ignore": "automation/qbit-rc-pending"}, "tags": {"only": "/.*/"}},
    }}]}},
}


class ValidateStandard(unittest.TestCase):
    def test_declarative_qbit_tag_filters_match_migration_and_manifest(self):
        spec = importlib.util.spec_from_file_location("migration_policy", ROOT / "tools/standardize_qbit.py")
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        for policy in ("stable", "v-prefix", "none"):
            caller = migration.canonical_caller(VERSION, policy)
            manifest = {"profile": "qbit", "orb_version": VERSION, "default_branch": "main",
                        "release_tag_policy": policy}
            standard.validate(yaml.safe_dump(caller), yaml.safe_dump(manifest), VERSION)
            caller["workflows"]["setup"]["jobs"][0]["qqq-orb/generate_pipeline"]["filters"]["tags"] = {"only": "/custom.*/"}
            with self.assertRaises(standard.StandardError):
                standard.validate(yaml.safe_dump(caller), yaml.safe_dump(manifest), VERSION)

    def check(self, config, profile="qbit", version=VERSION):
        standard.validate(yaml.safe_dump(config), yaml.safe_dump({"profile": profile, "orb_version": version, "default_branch": "develop"}), VERSION)

    def rejected(self, config, profile="qbit"):
        with self.assertRaises(standard.StandardError):
            self.check(config, profile)

    def test_standardizer_normal_caller_matches(self):
        self.check(CALLER)
        spec = importlib.util.spec_from_file_location("standardize_qbit", ROOT / "tools/standardize_qbit.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.canonical_caller(VERSION), CALLER)

    def test_all_profile_parameter_contracts(self):
        for profile in standard.PROFILE_PARAMETERS:
            with self.subTest(profile=profile):
                self.check(standard.canonical_caller(profile, VERSION), profile)

    def test_custom_jobs_and_commands_rejected(self):
        for key in ("jobs", "commands"):
            config = copy.deepcopy(CALLER)
            config[key] = {"custom": {"steps": ["checkout"]}}
            self.rejected(config)

    def test_extra_workflow_and_second_job_rejected(self):
        config = copy.deepcopy(CALLER)
        config["workflows"]["custom"] = {"jobs": []}
        self.rejected(config)
        config = copy.deepcopy(CALLER)
        config["workflows"]["setup"]["jobs"].append("custom")
        self.rejected(config)

    def test_import_job_and_manifest_version_mismatch(self):
        config = copy.deepcopy(CALLER)
        config["orbs"]["qqq-orb"] = "kingsrook/qqq-orb@0.6.9"
        self.rejected(config)
        config = copy.deepcopy(CALLER)
        config["workflows"]["setup"]["jobs"][0]["qqq-orb/generate_pipeline"]["orb_version"] = "0.6.9"
        self.rejected(config)
        with self.assertRaises(standard.StandardError):
            self.check(CALLER, version="0.6.9")

    def test_extra_orb_rejected(self):
        config = copy.deepcopy(CALLER)
        config["orbs"]["other"] = "circleci/node@1.0.0"
        self.rejected(config)

    def test_unknown_pipeline_and_job_parameters_rejected(self):
        config = copy.deepcopy(CALLER)
        config["parameters"] = {"custom": {"type": "string", "default": ""}}
        self.rejected(config)
        config = copy.deepcopy(CALLER)
        config["workflows"]["setup"]["jobs"][0]["qqq-orb/generate_pipeline"]["custom"] = True
        self.rejected(config)

    def test_profile_parameters_required_and_exactly_forwarded(self):
        self.rejected(CALLER, "core")
        config = standard.canonical_caller("core", VERSION)
        config["workflows"]["setup"]["jobs"][0]["qqq-orb/generate_pipeline"]["mongo_bind_diagnostics"] = False
        self.rejected(config, "core")
        config = standard.canonical_caller("frontend-material", VERSION)
        self.rejected(config, "frontend-core")

    def test_duplicate_yaml_keys_rejected(self):
        config = yaml.safe_dump(CALLER)
        manifest = "profile: qbit\norb_version: 0.7.0\n"
        for candidate, candidate_manifest in ((config + "setup: true\n", manifest), (config, manifest + "profile: cli\n"), (config.replace("orb_version: 0.7.0", "orb_version: 0.7.0\n        orb_version: 0.7.0"), manifest)):
            with self.subTest(candidate=candidate):
                with self.assertRaises(standard.StandardError):
                    standard.validate(candidate, candidate_manifest, VERSION)

    def test_wrong_boolean_type_rejected(self):
        config = copy.deepcopy(CALLER)
        config["setup"] = 1
        self.rejected(config)

    def test_exact_filters_required(self):
        config = copy.deepcopy(CALLER)
        config["workflows"]["setup"]["jobs"][0]["qqq-orb/generate_pipeline"]["filters"]["branches"]["ignore"] = "main"
        self.rejected(config)

    def test_only_standard_manifest_path_allowed(self):
        config = copy.deepcopy(CALLER)
        options = config["workflows"]["setup"]["jobs"][0]["qqq-orb/generate_pipeline"]
        options["manifest"] = ".qqq-ci.yml"
        self.check(config)
        options["manifest"] = "custom.yml"
        self.rejected(config)

    def test_setup_context_or_presteps_rejected(self):
        for key, value in (("context", "custom"), ("pre-steps", ["checkout"])):
            config = copy.deepcopy(CALLER)
            config["workflows"]["setup"]["jobs"][0]["qqq-orb/generate_pipeline"][key] = value
            self.rejected(config)


if __name__ == "__main__":
    unittest.main()
