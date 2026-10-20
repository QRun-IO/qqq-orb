"""Guard compatibility and ordering of orb Maven commands (requires PyYAML)."""
import pathlib
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def read(relative):
    return yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))


class MavenCiContract(unittest.TestCase):
    def test_legacy_defaults_and_job_forwarding(self):
        for name in ("commands/mvn_build", "jobs/mvn_test_only", "jobs/mvn_publish"):
            config = read("src/" + name + ".yml")
            for param in ("install_browsers", "compile_before_verify"):
                self.assertEqual(config["parameters"][param]["type"], "boolean")
                self.assertIs(config["parameters"][param]["default"], True)
            if name.startswith("jobs/"):
                build = next(s["mvn_build"] for s in config["steps"] if isinstance(s, dict) and "mvn_build" in s)
                for param in ("install_browsers", "compile_before_verify"):
                    self.assertEqual(build[param], "<< parameters." + param + " >>")

    def test_no_premature_cache_and_full_repository_after_verify(self):
        build = read("src/commands/mvn_build.yml")["steps"]
        self.assertFalse(any("save_cache" in step for step in build))
        self.assertIn("mvn_cache_restore", build)
        restore = next(s["restore_cache"] for s in read("src/commands/mvn_cache_restore.yml")["steps"] if "restore_cache" in s)
        self.assertIn("maven-cache-fingerprint", restore["keys"][0])
        verify = read("src/commands/mvn_verify.yml")["steps"]
        invocation = next(i for i, s in enumerate(verify) if "mvn_verify.sh" in str(s))
        saved = verify.index("mvn_cache_save")
        save = next(s["save_cache"] for s in read("src/commands/mvn_cache_save.yml")["steps"] if "save_cache" in s)
        self.assertGreater(saved, invocation)
        self.assertEqual(save["paths"], ["~/.m2/repository"])
        self.assertNotIn("when", save)
        self.assertEqual(save["key"], restore["keys"][0])

    def test_completion_is_opt_in_and_after_deploy_and_push(self):
        job = read("src/jobs/mvn_publish.yml")
        self.assertIs(job["parameters"]["notify_rc_published"]["default"], False)
        self.assertIs(read("src/commands/git_operations.yml")["parameters"]["require_pushed_version"]["default"], False)
        steps = job["steps"]
        deploy = steps.index("mvn_jar_deploy")
        pushed = next(i for i, s in enumerate(steps) if "git_operations" in str(s))
        dispatch = next(i for i, s in enumerate(steps) if "notify_rc_published.sh" in str(s))
        self.assertLess(deploy, pushed)
        self.assertLess(pushed, dispatch)
        self.assertIn("release_candidate", str(steps[dispatch]["when"]["condition"]))
        self.assertIn("parameters.notify_rc_published", str(steps[dispatch]["when"]["condition"]))

    def test_publish_still_versions_verifies_checks_and_deploys(self):
        steps = read("src/jobs/mvn_publish.yml")["steps"]
        def position(name):
            return next(i for i, s in enumerate(steps) if s == name or isinstance(s, dict) and name in s)
        self.assertLess(position("mvn_manage_version"), position("mvn_verify"))
        self.assertLess(position("mvn_verify"), position("mvn_jar_deploy"))
        self.assertTrue(any("check_middleware_api_versions" in str(s) for s in steps[position("mvn_verify") + 1:position("mvn_jar_deploy")]))
        deploy = (ROOT / "src/scripts/mvn_jar_deploy.sh").read_text()
        self.assertIn("-P release", deploy)
        self.assertIn("-Dgpg.keyname=", deploy)
        self.assertIn("-DskipTests", deploy)


if __name__ == "__main__":
    unittest.main()
