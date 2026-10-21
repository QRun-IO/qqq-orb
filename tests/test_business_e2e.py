import copy
import importlib.util
import json
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('aux', ROOT / 'src/scripts/generate_auxiliary_workflow.py')
aux = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aux)


class BusinessE2ETests(unittest.TestCase):
    def setUp(self):
        self.original = json.loads((ROOT / 'tests/fixtures/business-e2e-original.json').read_text())
        self.worker = yaml.safe_load((ROOT / '.github/workflows/business-e2e.yml').read_text())
        self.caller = aux.canonical('business-e2e', 'a' * 40)

    def test_jobs_exactly_preserve_audited_live_service_gate_and_cleanup(self):
        expected = copy.deepcopy(self.original['workflow']['jobs'])
        for job in expected.values():
            for step in job.get('steps', []):
                if 'run' in step:
                    step['run'] = step['run'].replace('for attempt in {1..90}', 'for _attempt in {1..90}')
        self.assertEqual(expected, self.worker['jobs'])
        self.assertEqual('e2e', self.worker['jobs']['deployment-gate']['needs'])
        self.assertEqual(30, self.worker['jobs']['e2e']['timeout-minutes'])
        self.assertEqual('always()', self.worker['jobs']['e2e']['steps'][-1]['if'])
        self.assertEqual('docker compose -f deploy/compose/docker-compose.yml down -v', self.worker['jobs']['e2e']['steps'][-1]['run'])

    def test_code_changes_and_manual_runs_keep_full_gate_without_nightly_duplicates(self):
        expected_events = copy.deepcopy(self.original['events'])
        del expected_events['schedule']
        self.assertEqual(expected_events, self.caller['on'])
        self.assertEqual(self.original['workflow']['permissions'], self.caller['permissions'])
        self.assertEqual(self.caller['permissions'], self.worker['permissions'])
        self.assertEqual(self.original['workflow']['concurrency']['group'], self.caller['concurrency']['group'])
        self.assertEqual("${{ github.event_name == 'pull_request' }}", self.caller['concurrency']['cancel-in-progress'])
        self.assertNotIn('concurrency', self.worker)
        self.assertEqual('.github/workflows/e2e.yml', aux.BRIDGES['business-e2e']['path'])
        self.assertEqual({'workflow_call': {'secrets': {'E2E_ALERT_WEBHOOK_URL': {'required': False}}}}, self.worker['on'])
        self.assertNotIn('schedule', self.worker['on'])

    def test_only_pinned_worker_and_explicit_existing_optional_secret(self):
        job = self.caller['jobs']['validate']
        self.assertEqual({'uses', 'secrets'}, set(job))
        self.assertEqual('QRun-IO/qqq-orb/.github/workflows/business-e2e.yml@' + 'a' * 40, job['uses'])
        self.assertEqual({'E2E_ALERT_WEBHOOK_URL': '${{ secrets.E2E_ALERT_WEBHOOK_URL }}'}, job['secrets'])
        with self.assertRaises(ValueError):
            aux.canonical('business-e2e', 'main')


if __name__ == '__main__':
    unittest.main()
