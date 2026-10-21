import copy
import importlib.util
import io
import os
from pathlib import Path
import unittest
from unittest import mock
import urllib.error
import yaml

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('verify', ROOT / 'src/scripts/verify_all_circle_smoke.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
SHA = 'a'*40
W = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
P = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'


def fixture():
    workflow = {'id': W, 'project_slug': v.PROJECT, 'name': 'verify-and-smoke', 'status': 'success', 'pipeline_id': P}
    pipeline = {'id': P, 'project_slug': v.PROJECT,
                'vcs': {'revision': SHA, 'branch': 'develop', 'origin_repository_url': 'https://github.com/' + v.REPO},
                'trigger': {'type': 'webhook', 'received_at': '2026-10-20T00:00:00Z', 'actor': {'login': 'builder'}}}
    jobs = [{'id': str(i), 'job_number': i, 'name': name, 'status': 'success', 'type': 'build'} for i, name in enumerate(['build-and-test', 'core', 'full'], 1)]
    checks = [{'id': 1, 'name': 'verify-and-smoke', 'app': {'id': 18001}, 'head_sha': SHA,
               'status': 'completed', 'conclusion': 'success', 'details_url': 'https://app.circleci.com/workflow/' + W}]
    return [workflow, pipeline, jobs, checks, [workflow.copy()]]


class EvidenceTests(unittest.TestCase):
    def test_public_evidence_needs_no_credential_and_optional_token_stays_on_circle(self):
        for token in ('', 'fixture-token'):
            opener = mock.Mock()
            opener.open.return_value = io.BytesIO(b'{"status":"success"}')
            with mock.patch.dict(os.environ, {'CIRCLECI_TOKEN': token}), \
                    mock.patch.object(v.urllib.request, 'build_opener', return_value=opener):
                self.assertEqual(v.circle('workflow/' + W), {'status': 'success'})
            request = opener.open.call_args.args[0]
            self.assertEqual(request.full_url, 'https://circleci.com/api/v2/workflow/' + W)
            self.assertEqual(request.get_header('Circle-token'), token or None)

    def test_unavailable_public_evidence_is_not_a_success(self):
        opener = mock.Mock()
        opener.open.side_effect = urllib.error.HTTPError('https://circleci.com', 403, 'Forbidden', {}, None)
        with mock.patch.dict(os.environ, {'CIRCLECI_TOKEN': ''}), \
                mock.patch.object(v.urllib.request, 'build_opener', return_value=opener), \
                self.assertRaises(OSError):
            v.circle('workflow/' + W)
        with self.assertRaises(v.EvidenceError):
            v.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.example/')

    def test_success_returns_real_circle_evidence_not_fake_github_run(self):
        evidence = v.validate(SHA, W, *fixture())
        self.assertEqual('qqq-all-circle-smoke/v1', evidence['schema'])
        self.assertEqual(W, evidence['workflow_id'])
        self.assertNotIn('smoke_run', evidence)

    def test_missing_skipped_failed_and_duplicate_required_jobs_rejected(self):
        for kind in ['missing', 'skipped', 'failure', 'duplicate']:
            data = fixture()
            if kind == 'missing': data[2].pop()
            elif kind == 'duplicate': data[2].append(data[2][0].copy())
            else: data[2][2]['status'] = kind
            with self.subTest(kind=kind), self.assertRaises(v.EvidenceError): v.validate(SHA, W, *data)

    def test_forged_app_wrong_sha_repo_and_manual_trigger_rejected(self):
        for kind in ['app', 'sha', 'repo', 'trigger', 'branch', 'url']:
            data = fixture()
            if kind == 'app': data[3][0]['app']['id'] = 1
            if kind == 'sha': data[1]['vcs']['revision'] = 'b'*40
            if kind == 'repo': data[1]['project_slug'] = 'gh/attacker/repo'
            if kind == 'trigger': data[1]['trigger']['type'] = 'api'
            if kind == 'branch': data[1]['vcs']['branch'] = 'feature/test'
            if kind == 'url': data[3][0]['details_url'] = 'https://evil.example/workflow/' + W
            with self.subTest(kind=kind), self.assertRaises(v.EvidenceError): v.validate(SHA, W, *data)

    def test_latest_failure_or_different_workflow_cannot_be_cherry_picked(self):
        for change in [{'conclusion': 'failure'}, {'details_url': 'https://app.circleci.com/workflow/' + P}]:
            data = fixture()
            data[3].append(dict(data[3][0], id=2, **change))
            with self.assertRaises(v.EvidenceError): v.validate(SHA, W, *data)

    def test_rerun_ancestry_rejected_even_when_subset_passed(self):
        for kind in ['flag', 'siblings']:
            data = fixture()
            if kind == 'flag': data[0]['rerun_of'] = P
            else: data[4].append(dict(data[0], id=P))
            with self.assertRaises(v.EvidenceError): v.validate(SHA, W, *data)

    def test_worker_embeds_exact_verifier_and_preserves_legacy_gate(self):
        worker = yaml.safe_load((ROOT / '.github/workflows/qqq-all-release.yml').read_text())
        steps = worker['jobs']['release']['steps']
        script = next(s['run'] for s in steps if s.get('name') == 'Materialize reviewed central release gates')
        source = (ROOT / 'src/scripts/verify_all_circle_smoke.py').read_text()
        self.assertIn(source, script)
        triggers = worker.get('on', worker.get(True))
        self.assertEqual('github', triggers['workflow_call']['inputs']['smoke_evidence']['default'])
        self.assertEqual('qqq-all-release', worker['jobs']['release']['environment'])
        all_runs = '\n'.join(s.get('run', '') for s in steps)
        self.assertIn('--circle-smoke', all_runs)
        self.assertIn('--smoke-run', all_runs)
        self.assertIn('requireReleaseDeps', all_runs)
        self.assertIn('--tag-object', all_runs)


if __name__ == '__main__': unittest.main()
