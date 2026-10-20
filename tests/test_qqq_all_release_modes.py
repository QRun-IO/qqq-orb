import sys
from pathlib import Path
import unittest
import yaml
sys.path.insert(0, str(Path(__file__).parents[1] / 'src/scripts'))
import qqq_all_release_gate as gate
import verify_all_circle_smoke as circle
from test_verify_all_circle_smoke import fixture, SHA, W


class ModeTests(unittest.TestCase):
    def test_real_circle_evidence_validated_and_legacy_remains(self):
        evidence = circle.validate(SHA, W, *fixture())
        gate.validate_evidence(SHA, circle_smoke=evidence)
        run = {'name': 'Smoke', 'path': '.github/workflows/smoke.yml', 'head_sha': SHA,
               'head_branch': 'develop', 'event': 'push', 'conclusion': 'success'}
        jobs = {'jobs': [{'name': name, 'conclusion': 'success'} for name in ['core', 'full']]}
        gate.validate_evidence(SHA, run, jobs)
        with self.assertRaises(gate.GateError): gate.validate_evidence(SHA, run, jobs, evidence)
        with self.assertRaises(gate.GateError): gate.validate_evidence(SHA)
        with self.assertRaises(gate.GateError): gate.validate_evidence(SHA, run)

    def test_schema_sha_and_failed_job_cannot_be_boolean_receipt(self):
        for kind in ['schema', 'sha', 'job', 'receipt']:
            evidence = circle.validate(SHA, W, *fixture())
            if kind == 'schema': evidence['schema'] = 'other'
            if kind == 'sha': evidence['sha'] = 'b'*40
            if kind == 'job': evidence['jobs'][2]['status'] = 'failure'
            if kind == 'receipt': evidence = {'success': True}
            with self.subTest(kind=kind), self.assertRaises(gate.GateError):
                gate.validate_evidence(SHA, circle_smoke=evidence)

    def test_worker_embeds_both_exact_central_scripts_and_uses_consumer_root(self):
        root = Path(__file__).parents[1]
        worker = yaml.safe_load((root / '.github/workflows/qqq-all-release.yml').read_text())
        steps = worker['jobs']['release']['steps']
        materialize = next(s['run'] for s in steps if s.get('name') == 'Materialize reviewed central release gates')
        for name in ['qqq_all_release_gate.py', 'verify_all_circle_smoke.py']:
            self.assertIn((root / 'src/scripts' / name).read_text(), materialize)
        scripts = '\n'.join(s.get('run', '') for s in steps)
        self.assertNotIn('python3 scripts/release_gate.py', scripts)
        self.assertIn('central-release/qqq_all_release_gate.py" --root .', scripts)
        self.assertIn('scripts/release_bundle.py', scripts)


if __name__ == '__main__': unittest.main()
