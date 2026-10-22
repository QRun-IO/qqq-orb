"""Execute shared Voyage release commands against isolated service doubles."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = json.loads((ROOT / "src/scripts/templates/voyage.json").read_text())


def command(job):
    return next(step["run"]["command"] for step in TEMPLATE["jobs"][job]["steps"]
                if isinstance(step, dict) and "run" in step)


class VoyageRelease(unittest.TestCase):
    def run_job(self, job, failure=""):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "fake"
            fake.write_text("""#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys
name=pathlib.Path(sys.argv[0]).name
args=sys.argv[1:]
with open(os.environ['EVENTS'], 'a') as output:
    output.write(json.dumps([name, args])+'\\n')
if name=='docker':
    if args[0]=='login': sys.stdin.read()
    if args[0]=='manifest': print('{}')
elif name=='jq':
    sys.stdin.read(); print('sha256:'+'a'*64)
elif name=='git':
    if args[0]=='clone':
        assert args==['clone','--branch','main','https://github.com/QRun-IO/voyage-cd.git']
        assert os.environ['GIT_TERMINAL_PROMPT']=='0'
        askpass=os.environ['GIT_ASKPASS']
        assert subprocess.check_output([askpass, 'Username for https://github.com']).strip()==b'x-access-token'
        assert subprocess.check_output([askpass, 'Password for https://github.com']).strip()==b'fixture-token'
        if os.environ['FAILURE']=='clone': sys.exit(23)
        p=pathlib.Path('voyage-cd/overlays/production'); p.mkdir(parents=True)
        (p/'kustomization.yaml').write_text('digest: sha256:'+'b'*64+'\\n')
    elif args[0]=='diff': sys.exit(1)
    elif args[0]=='push' and os.environ['FAILURE']=='push': sys.exit(24)
elif name=='npx':
    assert '--target-branch=main' in args
    if os.environ['FAILURE']=='release' and 'github-release' in args: sys.exit(25)
""")
            fake.chmod(0o755)
            for name in ("docker", "jq", "git", "npx"):
                (bin_dir / name).symlink_to(fake)
            events = root / "events.jsonl"
            env = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
                   "EVENTS": str(events), "FAILURE": failure, "GITHUB_TOKEN": "fixture-token",
                   "GHCR_TOKEN": "fixture-ghcr", "GHCR_USERNAME": "fixture-user",
                   "CIRCLE_SHA1": "1" * 40, "CIRCLE_BRANCH": "main"}
            result = subprocess.run(["bash", "-eo", "pipefail", "-c", command(job)],
                                    cwd=root, env=env, capture_output=True, text=True)
            rows = [json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []
            content = root / "voyage-cd/overlays/production/kustomization.yaml"
            return result, rows, content.read_text() if content.exists() else None

    def test_cd_uses_canonical_authenticated_checkout_and_publishes_digest(self):
        result, rows, content = self.run_job("update-cd-repo")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(content, 'digest: sha256:' + 'a' * 64 + '\n')
        self.assertIn(['git', ['push', 'origin', 'main']], rows)
        self.assertNotIn('fixture-token', json.dumps(rows))
        self.assertNotIn('fixture-token', result.stdout + result.stderr)

    def test_cd_failure_stops_publication(self):
        for failure, code in (("clone", 23), ("push", 24)):
            result, rows, _ = self.run_job("update-cd-repo", failure)
            self.assertEqual(result.returncode, code, result.stderr)
            if failure == "clone":
                self.assertFalse(any(name == 'git' and args[0] == 'push' for name, args in rows))

    def test_release_targets_main_for_both_commands(self):
        result, rows, _ = self.run_job("release-please")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([args[1] for name, args in rows if name == 'npx'], ['github-release', 'release-pr'])

    def test_release_failure_is_not_hidden_by_second_command(self):
        result, rows, _ = self.run_job("release-please", 'release')
        self.assertEqual(result.returncode, 25, result.stderr)
        self.assertEqual(len(rows), 1)
