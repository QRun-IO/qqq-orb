"""Guard full CLI validation before optional publication."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class CliContract(unittest.TestCase):
    def test_single_full_validation_and_opt_in_publication(self):
        config = yaml.safe_load((ROOT / "src/jobs/cli_verify_publish.yml").read_text())
        self.assertIs(config["parameters"]["publish"]["default"], False)
        self.assertEqual(config["docker"], [{"image": "cimg/node:22.23"}])
        steps = config["steps"]
        ci = [i for i, s in enumerate(steps) if isinstance(s, dict) and s.get("run", {}).get("command") == "npm ci"]
        verify = [i for i, s in enumerate(steps) if "scripts/cli_verify.sh" in str(s)]
        publish = [i for i, s in enumerate(steps) if "scripts/cli_publish.sh" in str(s)]
        self.assertEqual(len(ci), 1)
        self.assertEqual(len(verify), 1)
        self.assertEqual(len(publish), 1)
        self.assertLess(ci[0], verify[0])
        self.assertLess(verify[0], publish[0])
        self.assertEqual(steps[publish[0]]["when"]["condition"], "<< parameters.publish >>")
        cache = next(s["save_cache"] for s in steps if isinstance(s, dict) and "save_cache" in s)
        self.assertEqual(cache["paths"], ["~/.npm"])

    def test_platform_lane_runs_install_build_test_and_lint(self):
        config = yaml.safe_load((ROOT / "src/jobs/cli_platform.yml").read_text())
        self.assertEqual(config["executor"], "<< parameters.executor >>")
        self.assertEqual(config["parameters"]["executor"]["type"], "executor")
        commands = [s["run"]["command"] if isinstance(s["run"], dict) else s["run"]
                    for s in config["steps"] if isinstance(s, dict) and "run" in s]
        self.assertIn("npm ci", commands)
        self.assertEqual(commands[-1], "npm run build && npm test && npm run lint")
        self.assertNotIn("publish", str(config))
        for name in ("cli_macos_arm64", "cli_windows_x64"):
            self.assertTrue((ROOT / "src/executors" / (name + ".yml")).exists())


if __name__ == "__main__":
    unittest.main()
