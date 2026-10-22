"""Voyage delegates live GitOps updates to the existing shared updater."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

TEMPLATE = json.loads((Path(__file__).resolve().parents[1] / "src/scripts/templates/voyage.json").read_text())


class VoyageGitOps(unittest.TestCase):
    def test_live_target_uses_shared_updater_only_after_main_image_publication(self):
        self.assertNotIn('update-cd-repo', TEMPLATE['jobs'])
        self.assertEqual(TEMPLATE['orbs']['munitor'], 'kof22/munitor@0.3.11')
        invocations = [(workflow, entry['munitor/update_cd_repo'])
                       for workflow, body in TEMPLATE['workflows'].items() for entry in body['jobs']
                       if 'munitor/update_cd_repo' in entry]
        self.assertEqual(len(invocations), 1)
        workflow, options = invocations[0]
        self.assertEqual(workflow, 'release')
        self.assertEqual(options['cd_repo'], 'KofTwentyTwo/cluster-gitops')
        self.assertEqual(options['cd_path'], 'tenants/voyage/kustomization.yaml')
        self.assertEqual(options['cd_image_name'], 'ghcr.io/qrun-io/voyage')
        self.assertEqual(options['cd_format'], 'kustomize')
        self.assertEqual(options['requires'], ['docker-build'])
        self.assertEqual(options['context'], ['github'])
        self.assertEqual(options['filters'], {'branches': {'only': 'main'}})

    def test_updater_receives_published_commit_tag_and_rejects_invalid_revision(self):
        options = next(entry['munitor/update_cd_repo'] for entry in TEMPLATE['workflows']['release']['jobs']
                       if 'munitor/update_cd_repo' in entry)
        command = options['pre-steps'][0]['run']['command']
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / 'bash-env'
            for revision in ('a' * 40, '', 'main', 'a' * 39):
                env_file.write_text('')
                env = {**os.environ, 'BASH_ENV': str(env_file), 'CIRCLE_SHA1': revision}
                result = subprocess.run(['bash', '-c', command], env=env, capture_output=True)
                if revision == 'a' * 40:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(env_file.read_text(), "export PROJECT_VERSION='aaaaaaa'\n")
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(env_file.read_text(), '')
