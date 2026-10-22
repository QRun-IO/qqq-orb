"""Execute the generated CI staging command against representative Maven output."""
import base64
import importlib.util
import re
import shutil
import zlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pipeline", ROOT / "src/scripts/generate_pipeline.py")
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


class EsbJunitStagingTests(unittest.TestCase):
    def test_only_junit_suites_are_uploaded_without_changing_source_evidence(self):
        rendered = pipeline.core_template({"orb_version": "0.7.12", "docs_only": False, "java_version": "21", "browsers": True, "api_checks": False}, "feature/report-test", "")
        steps = rendered["jobs"]["esb_broker_conformance"]["steps"]
        stage = next(step["run"] for step in steps if isinstance(step, dict)
                     and step.get("run", {}).get("name") == "Stage broker JUnit reports")
        upload = next(step["store_test_results"] for step in steps
                      if isinstance(step, dict) and "store_test_results" in step)
        self.assertEqual(stage["when"], "always")
        script = "\n".join(stage["command"].splitlines()[1:-1])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "qqq-esb/target/failsafe-reports"
            source.mkdir(parents=True)
            reports = {
                "TEST-ArtemisConformanceIT.xml": "<testsuite tests='1'/>",
                "TEST-RabbitMQConformanceIT.xml": "<testsuite tests='2'/>",
                "TEST-PublishingPoolIT.xml": "<testsuite tests='3'/>",
                "failsafe-summary.xml": "<failsafe-summary/>",
                "broker.dumpstream": "diagnostic",
            }
            for name, content in reports.items():
                (source / name).write_text(content, encoding="utf-8")
            subprocess.run([sys.executable, "-c", script], cwd=root, check=True)
            destination = root / upload["path"]
            self.assertEqual({p.name for p in destination.iterdir()},
                             {name for name in reports if name.startswith("TEST-")})
            for name, content in reports.items():
                self.assertEqual((source / name).read_text(encoding="utf-8"), content)
                if name.startswith("TEST-"):
                    self.assertEqual((destination / name).read_text(encoding="utf-8"), content)


class PackedResourcePortabilityTests(unittest.TestCase):
    def test_compression_variants_pass_but_changed_resource_or_code_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            shutil.copyfile(ROOT / "scripts/pack_pipeline.py", root / "scripts/pack_pipeline.py")
            shutil.copytree(ROOT / "src/scripts", root / "src/scripts")
            command = [sys.executable, "scripts/pack_pipeline.py"]
            subprocess.run(command, cwd=root, check=True)
            output = root / "src/scripts/packed_generate_pipeline.py"
            packed = output.read_text(encoding="utf-8")
            pattern = r'base64\.b64decode\("([A-Za-z0-9+/=]+)"\)'
            variant = re.sub(pattern, lambda match: 'base64.b64decode("' + base64.b64encode(
                zlib.compress(zlib.decompress(base64.b64decode(match[1])), level=0)).decode("ascii") + '")', packed)
            self.assertNotEqual(variant, packed)
            output.write_text(variant, encoding="utf-8")
            subprocess.run(command + ["--check"], cwd=root, check=True)

            template = root / "src/scripts/templates/core.json"
            template.write_text(template.read_text(encoding="utf-8") + " ", encoding="utf-8")
            self.assertNotEqual(subprocess.run(command + ["--check"], cwd=root, capture_output=True).returncode, 0)
            template.write_text(template.read_text(encoding="utf-8")[:-1], encoding="utf-8")
            output.write_text(variant + "\n# stale code\n", encoding="utf-8")
            self.assertNotEqual(subprocess.run(command + ["--check"], cwd=root, capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()
