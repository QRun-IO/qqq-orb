import base64
import importlib.util
import io
import json
import pathlib
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('sweep', pathlib.Path(__file__).parents[1] / 'src/scripts/rc_finalize_sweep.py')
sweep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep)
SHA, BUMP, OTHER = 'a' * 40, 'b' * 40, 'c' * 40
REPO = 'QRun-IO/qbit-test'
POM = '<project xmlns="http://maven.apache.org/POM/4.0.0"><artifactId>qbit-test</artifactId><version>1.2.3-RC.4</version></project>'


class FixtureAPI:
    def __init__(self):
        self.lock = SHA
        self.intent = {'repo': REPO, 'merge_sha': SHA, 'branch': 'release/1.2', 'run_id': '7', 'attempt': '1', 'merged_at': '2026-10-20T12:00:00Z'}
        self.run = {'id': 7, 'status': 'completed', 'conclusion': 'success', 'path': '.github/workflows/release-rc.yml', 'event': 'workflow_dispatch', 'run_attempt': 1, 'repository': {'full_name': REPO}, 'head_repository': {'full_name': REPO}}
        self.status = {'check_runs': [{'id': 9, 'name': 'publish_release_candidate', 'app': {'id': 18001}, 'head_sha': SHA, 'status': 'completed', 'conclusion': 'success'}]}
        self.commit = {'sha': BUMP, 'parents': [{'sha': SHA}], 'commit': {'message': 'Bump version to 1.2.3-RC.4 [skip ci]'}}
        self.published = (POM.encode(), 'Tue, 20 Oct 2026 12:00:01 GMT')
        self.sent = []
        self.reads = 0
        self.change_lock = False

    def request(self, path, payload=None, raw=False):
        self.reads += 1
        if path.endswith('git/ref/heads/' + sweep.LOCK):
            if self.change_lock and self.reads > 1:
                return {'object': {'sha': OTHER}}
            return {'object': {'sha': self.lock}} if self.lock else None
        if 'actions/artifacts?name=' in path:
            return {'artifacts': [{'id': 11, 'name': 'qbit-rc-intent-' + SHA, 'expired': False, 'workflow_run': {'id': 7}}]}
        if path.endswith('actions/runs/7'):
            return self.run
        if path.endswith('/11/zip'):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w') as z:
                z.writestr('rc-intent.json', json.dumps(self.intent))
            return stream.getvalue()
        if '/check-runs?' in path:
            return self.status
        if '/commits/' in path:
            return self.commit
        if 'contents/pom.xml' in path:
            return {'content': base64.b64encode(POM.encode()).decode()}
        if path.endswith('/dispatches'):
            self.sent.append(payload)
            return None
        raise AssertionError(path)

    def central(self, artifact, version):
        return self.published


class SweepTests(unittest.TestCase):
    def test_stable_gate_and_mixed_name_latest_failure(self):
        api = FixtureAPI()
        api.status['check_runs'][0]['name'] = 'verify'
        self.assertEqual('dispatched', sweep.reconcile(api, REPO))
        api.sent.clear()
        api.status['check_runs'].append(dict(api.status['check_runs'][0],
                                            id=10, name='publish_release_candidate', conclusion='failure'))
        with self.assertRaises(sweep.InvalidIntent):
            sweep.reconcile(api, REPO)
        self.assertEqual([], api.sent)

    def test_idle_never_dispatches_or_reads_artifacts(self):
        api = FixtureAPI(); api.lock = None
        self.assertEqual('idle', sweep.reconcile(api, REPO))
        self.assertEqual(1, api.reads)
        self.assertEqual([], api.sent)

    def test_success_exact_payload_and_duplicate_dispatch_is_same_candidate(self):
        api = FixtureAPI()
        self.assertEqual('dispatched', sweep.reconcile(api, REPO))
        self.assertEqual('dispatched', sweep.reconcile(api, REPO))
        self.assertEqual(api.sent[0], api.sent[1])
        self.assertEqual({'merge_sha': SHA, 'bump_sha': BUMP, 'branch': 'release/1.2', 'version': '1.2.3-RC.4'}, api.sent[0]['client_payload'])

    def test_central_delay_then_later_success_without_sleep(self):
        api = FixtureAPI(); api.published = None
        self.assertEqual('central-pending', sweep.reconcile(api, REPO))
        self.assertEqual([], api.sent)
        api.published = (POM.encode(), 'Tue, 20 Oct 2026 12:01:00 GMT')
        self.assertEqual('dispatched', sweep.reconcile(api, REPO))

    def test_failed_publisher_does_not_dispatch(self):
        api = FixtureAPI(); api.status['check_runs'][0]['conclusion'] = 'failure'
        with self.assertRaisesRegex(sweep.InvalidIntent, 'terminal failure'):
            sweep.reconcile(api, REPO)
        self.assertEqual([], api.sent)

    def test_pending_publisher_and_cut_race_wait_for_next_sweep(self):
        api = FixtureAPI(); api.status['check_runs'][0]['status'] = 'in_progress'
        self.assertEqual('publisher-running', sweep.reconcile(api, REPO))
        api.run['status'] = 'in_progress'
        self.assertEqual('cut-running', sweep.reconcile(api, REPO))
        self.assertEqual([], api.sent)

    def test_old_bump_wrong_status_sha_and_lock_replacement_rejected(self):
        for kind in ('bump', 'status', 'lock'):
            api = FixtureAPI()
            if kind == 'bump': api.commit['parents'] = [{'sha': OTHER}]
            if kind == 'status': api.status['check_runs'][0]['head_sha'] = OTHER
            if kind == 'lock': api.change_lock = True
            with self.subTest(kind=kind), self.assertRaises(sweep.InvalidIntent):
                sweep.reconcile(api, REPO)
            self.assertEqual([], api.sent)

    def test_untrusted_artifact_run_rejected(self):
        for field, value in [('event', 'repository_dispatch'), ('run_attempt', 2), ('conclusion', 'failure'), ('path', '.github/workflows/evil.yml')]:
            api = FixtureAPI(); api.run[field] = value
            with self.subTest(field=field), self.assertRaises(sweep.InvalidIntent):
                sweep.reconcile(api, REPO)
            self.assertEqual([], api.sent)

    def test_central_old_or_wrong_version_rejected(self):
        for xml, modified in [(POM.encode(), 'Tue, 20 Oct 2026 11:00:00 GMT'), (POM.replace('RC.4', 'RC.3').encode(), 'Tue, 20 Oct 2026 12:01:00 GMT')]:
            api = FixtureAPI(); api.published = (xml, modified)
            with self.assertRaises(sweep.InvalidIntent): sweep.reconcile(api, REPO)
            self.assertEqual([], api.sent)

    def test_other_circle_success_cannot_authorize_release(self):
        api = FixtureAPI(); api.status['check_runs'][0]['name'] = 'test_only'
        self.assertEqual('publisher-running', sweep.reconcile(api, REPO))
        self.assertEqual([], api.sent)

    def test_missing_artifact_is_deferred_not_dispatched(self):
        api = FixtureAPI()
        original = api.request
        def request(path, payload=None, raw=False):
            if 'actions/artifacts?name=' in path: return {'artifacts': []}
            return original(path, payload, raw)
        api.request = request
        self.assertEqual('intent-pending', sweep.reconcile(api, REPO))
        self.assertEqual([], api.sent)

    def test_one_repository_failure_does_not_starve_other_repositories(self):
        api = FixtureAPI(); api.deadline = float('inf'); api.calls = 0
        repos = [REPO, 'QRun-IO/qbit-other']
        with patch.dict(sweep.os.environ, {'GH_TOKEN': 'fixture', 'RC_REPOSITORIES_JSON': json.dumps(repos)}), \
             patch.object(sweep, 'API', return_value=api), \
             patch.object(sweep, 'reconcile', side_effect=[sweep.InvalidIntent('fixture failure'), 'idle']) as reconcile, \
             patch('sys.stdout', new_callable=io.StringIO), patch('sys.stderr', new_callable=io.StringIO):
            with self.assertRaisesRegex(sweep.InvalidIntent, 'Sweep failures'):
                sweep.main()
            self.assertEqual(repos, [call.args[1] for call in reconcile.call_args_list])

    def test_redirect_does_not_forward_github_credential(self):
        request = sweep.urllib.request.Request('https://api.github.com/test', headers={'Authorization': 'Bearer fixture'})
        redirected = sweep.NoAuthRedirect().redirect_request(request, None, 302, '', {}, 'https://artifact.example/file')
        self.assertIsNone(redirected.get_header('Authorization'))


if __name__ == '__main__':
    unittest.main()
