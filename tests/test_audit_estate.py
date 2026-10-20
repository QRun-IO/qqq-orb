import importlib.util
import pathlib
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('audit', pathlib.Path(__file__).parents[1] / 'tools/audit_estate.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
SHA = 'a' * 40
VERSION = '0.7.0'
ENTRY = {'name': 'qctl', 'nameWithOwner': 'QRun-IO/qctl', 'isArchived': False}
POLICY = {'required_checks': {'main': ['native / test'], 'develop': ['native / test']}}


class Snapshot:
    sha = SHA
    branch = 'develop'
    def __init__(self, files, checks=None):
        self.files = files
        self.paths = set(files)
        self.required = checks if checks is not None else ['native / test']
    def read(self, path):
        return self.files.get(path)
    def checks(self, branch):
        return self.required


class AuditTests(unittest.TestCase):
    def native(self, files=None, checks=None, policy=POLICY):
        files = files if files is not None else {'.github/workflows/build.yml': audit.qctl.generate(SHA)}
        return audit.audit(ENTRY, Snapshot(files, checks), VERSION, SHA, policy)

    def test_native_canonical_and_checks_pass(self):
        self.assertEqual('pass', self.native()['status'])

    def test_native_mutable_pin_or_local_job_detected(self):
        for source in (audit.qctl.generate(SHA).replace(SHA, 'main'), audit.qctl.generate(SHA) + '  local: {}\n'):
            report = self.native({'.github/workflows/build.yml': source})
            self.assertIn('native_bridge_drift', [f['code'] for f in report['findings']])

    def test_missing_observed_check_and_unknown_policy_not_pass(self):
        self.assertEqual('missing', self.native(checks=[])['required_checks']['main']['state'])
        self.assertEqual('unknown', self.native(policy={})['status'])

    def test_duplicate_legacy_build_reported_without_removing_it(self):
        report = self.native({'.github/workflows/build.yml': audit.qctl.generate(SHA), '.github/workflows/legacy.yml': 'run: mvn clean verify'})
        self.assertIn('possible_duplicate_legacy_build', [f['code'] for f in report['findings']])

    def test_qbit_missing_declarations(self):
        entry = dict(ENTRY, name='qbit-test', nameWithOwner='QRun-IO/qbit-test')
        report = audit.audit(entry, Snapshot({}), VERSION, SHA, POLICY)
        self.assertIn('missing_manifest', [f['code'] for f in report['findings']])
        self.assertIn('missing_canonical_caller', [f['code'] for f in report['findings']])

    def test_qbit_reuses_manifest_and_caller_validators(self):
        entry = dict(ENTRY, name='qbit-test', nameWithOwner='QRun-IO/qbit-test')
        manifest = {'profile': 'qbit', 'orb_version': VERSION, 'default_branch': 'develop'}
        files = {audit.rc_worker.CALLER_PATH: audit.rc_worker.generate(SHA),
                 '.qqq-ci.yml': audit.generator.yaml.safe_dump(manifest),
                 '.circleci/config.yml': audit.generator.yaml.safe_dump(audit.standard.canonical_caller('qbit', VERSION))}
        with patch.object(audit.generator, 'load_manifest', wraps=audit.generator.load_manifest) as load:
            report = audit.audit(entry, Snapshot(files), VERSION, SHA, POLICY)
            self.assertEqual('pass', report['status'])
            load.assert_called_once()
        files['.circleci/config.yml'] += 'jobs: {}\n'
        report = audit.audit(entry, Snapshot(files), VERSION, SHA, POLICY)
        self.assertIn('invalid_manifest_or_caller', [f['code'] for f in report['findings']])

    def test_test_only_qbit_does_not_require_rc_bridge(self):
        entry = dict(ENTRY, name='qbit-help', nameWithOwner='QRun-IO/qbit-help')
        report = audit.audit(entry, Snapshot({}), VERSION, SHA, POLICY)
        self.assertNotIn('missing_rc_bridge', [f['code'] for f in report['findings']])
        manifest = {'profile': 'qbit', 'orb_version': VERSION, 'default_branch': 'develop', 'release_completion': True}
        report = audit.audit(entry, Snapshot({'.qqq-ci.yml': audit.generator.yaml.safe_dump(manifest)}), VERSION, SHA, POLICY)
        self.assertIn('missing_rc_bridge', [f['code'] for f in report['findings']])

    def test_qbit_rc_bridge_missing_drift_pin_and_duplicate(self):
        entry = dict(ENTRY, name='qbit-test', nameWithOwner='QRun-IO/qbit-test')
        path = audit.rc_worker.CALLER_PATH
        source = audit.rc_worker.generate(SHA)
        cases = [({}, SHA, 'missing_rc_bridge'),
                 ({path: source.replace(SHA, 'main')}, SHA, 'rc_bridge_drift'),
                 ({path: source + 'permissions: {}\n'}, SHA, 'rc_bridge_drift'),
                 ({path: source}, None, 'native_pin_policy_missing'),
                 ({path: source, '.github/workflows/other.yml': source}, SHA, 'duplicate_rc_bridge')]
        for files, pin, code in cases:
            with self.subTest(code=code):
                report = audit.audit(entry, Snapshot(files), VERSION, pin, dict(POLICY, rc_release=True))
                self.assertIn(code, [f['code'] for f in report['findings']])

    def test_all_68_active_and_archived_coverage_failures_do_not_abort(self):
        entries = [dict(ENTRY, nameWithOwner='QRun-IO/repo' + str(i)) for i in range(68)]
        entries += [dict(ENTRY, isArchived=True, nameWithOwner='QRun-IO/archived')]
        def factory(entry, live):
            if entry['nameWithOwner'].endswith('0'):
                raise audit.ReadError('inaccessible')
            return Snapshot({'.github/workflows/build.yml': audit.qctl.generate(SHA)})
        report = audit.run(entries, VERSION, SHA, {'profiles': {'qctl': POLICY}}, snapshot_factory=factory)
        self.assertEqual(68, report['active_count'])
        self.assertEqual(69, report['covered_count'])
        self.assertEqual('unknown', report['results'][0]['status'])
        self.assertEqual('archived_skip', report['results'][-1]['status'])
        self.assertEqual('pass', report['results'][1]['status'])

    def test_approved_auxiliary_bridge_recognized_and_drift_rejected(self):
        entry = dict(ENTRY, name='qbit-authentik', nameWithOwner='QRun-IO/qbit-authentik')
        path = '.github/workflows/schema-drift.yml'
        raw = audit.generator.yaml.safe_dump(audit.auxiliary.canonical('qbit-schema-drift', SHA), sort_keys=False)
        report = audit.audit(entry, Snapshot({path: raw}), VERSION, SHA, POLICY)
        self.assertNotIn('native_maintenance_bridge_drift', [f['code'] for f in report['findings']])
        self.assertNotIn('possible_duplicate_legacy_build', [f['code'] for f in report['findings']])
        report = audit.audit(entry, Snapshot({path: raw.replace(SHA, 'main')}), VERSION, SHA, POLICY)
        self.assertIn('native_maintenance_bridge_drift', [f['code'] for f in report['findings']])

    def test_gh_is_explicit_get_and_never_changes_settings(self):
        with patch.object(audit, 'command', return_value='{}') as command:
            audit.gh('repos/QRun-IO/example')
            self.assertEqual(['gh', 'api', '--method', 'GET', 'repos/QRun-IO/example'], command.call_args.args[0])


if __name__ == '__main__': unittest.main()
