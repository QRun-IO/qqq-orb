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

    def test_new_circle_profile_mappings_require_actual_configuration(self):
        for name, profile in [('qqq-android', 'android'), ('qqq-mcp-rag-standard-policies', 'mcp-policy'), ('marketing-website', 'marketing')]:
            entry = dict(ENTRY, name=name, nameWithOwner='QRun-IO/' + name)
            report = audit.audit(entry, Snapshot({}), VERSION, SHA, {})
            self.assertEqual(profile, report['profile'])
            self.assertIn('missing_manifest', [f['code'] for f in report['findings']])
            self.assertIn('missing_canonical_caller', [f['code'] for f in report['findings']])

    def test_intellij_is_native_product_not_no_ci_exception(self):
        repository = 'QRun-IO/qqq-app-developer-intellij-plugin'
        self.assertNotIn(repository, audit.NO_CI)
        entry = dict(ENTRY, name='qqq-app-developer-intellij-plugin', nameWithOwner=repository)
        report = audit.audit(entry, Snapshot({}), VERSION, SHA, POLICY)
        self.assertEqual('intellij-plugin', report['profile'])
        self.assertIn('missing_native_maintenance_bridge', [f['code'] for f in report['findings']])

    def test_approved_no_ci_is_exact_allowlist_with_evidence_not_check_pass(self):
        self.assertEqual(8, len(audit.NO_CI))
        for repository, policy in audit.NO_CI.items():
            entry = dict(ENTRY, name=repository.split('/')[-1], nameWithOwner=repository)
            files = {path: 'identity fixture' for path in policy['required_paths']}
            report = audit.audit(entry, Snapshot(files), VERSION, SHA, {})
            self.assertEqual('approved-no-ci', report['classification'])
            self.assertEqual([], report['findings'])
            self.assertEqual('unknown', report['status'])
            self.assertEqual('unknown', report['required_checks']['main']['state'])
            for new_path in ['.github/workflows/new.yml', '.circleci/config.yml', '.qqq-ci.yml', 'Jenkinsfile']:
                changed = dict(files, **{new_path: 'new CI'})
                drift = audit.audit(entry, Snapshot(changed), VERSION, SHA, {})
                self.assertIn('no_ci_configuration_drift', [f['code'] for f in drift['findings']])
            missing = audit.audit(entry, Snapshot({}), VERSION, SHA, {})
            self.assertIn('no_ci_identity_path_missing', [f['code'] for f in missing['findings']])

    def test_unknown_no_ci_repo_is_not_silently_approved(self):
        entry = dict(ENTRY, name='new-unknown-repo', nameWithOwner='QRun-IO/new-unknown-repo')
        report = audit.audit(entry, Snapshot({}), VERSION, SHA, {})
        self.assertIn('profile_not_assigned', [f['code'] for f in report['findings']])

    def test_native_specialists_require_bridges_and_report_remaining_workflows(self):
        for name, kind in [('qqq-mcp-rag', 'mcp-rag'), ('qqq-business-platform', 'business-db'), ('.github', 'github-workflow-lint')]:
            entry = dict(ENTRY, name=name, nameWithOwner='QRun-IO/' + name)
            definition = audit.auxiliary.BRIDGES[kind]
            missing = audit.audit(entry, Snapshot({}), VERSION, SHA, {})
            self.assertIn('missing_native_maintenance_bridge', [f['code'] for f in missing['findings']])
            files = {item['path']: audit.generator.yaml.safe_dump(audit.auxiliary.canonical(key, SHA), sort_keys=False)
                     for key, item in audit.auxiliary.BRIDGES.items() if item['repository'] == entry['nameWithOwner']}
            report = audit.audit(entry, Snapshot(files), VERSION, SHA, {})
            self.assertEqual([], report['findings'])
            self.assertEqual('unknown', report['status'])
            files['.circleci/config.yml'] = 'old pipeline'
            files['.github/workflows/unconverted.yml'] = 'name: unconverted'
            report = audit.audit(entry, Snapshot(files), VERSION, SHA, {})
            self.assertIn('legacy_circle_pipeline', [f['code'] for f in report['findings']])
            self.assertIn('unapproved_native_workflow', [f['code'] for f in report['findings']])

    def test_owner_bootstrap_requires_real_gates_and_dependencies(self):
        root = pathlib.Path(__file__).parents[1]
        files = {path: (root / path).read_text(encoding='utf-8') for path in ['.circleci/config.yml', '.circleci/test-deploy.yml']}
        entry = dict(ENTRY, name='qqq-orb', nameWithOwner='QRun-IO/qqq-orb')
        report = audit.audit(entry, Snapshot(files), VERSION, SHA, {})
        self.assertEqual('owner-bootstrap', report['classification'])
        self.assertEqual([], report['findings'])
        self.assertEqual('unknown', report['status'])
        self.assertNotIn('missing_manifest', [f['code'] for f in report['findings']])
        for path, old, new in [('.circleci/config.yml', 'orb-tools/pack', 'disabled-pack'),
                               ('.circleci/test-deploy.yml', 'requires: [command-test, pipeline-contract-test, maven-publication-contract]', 'requires: [command-test, pipeline-contract-test]'),
                               ('.circleci/test-deploy.yml', 'circleci orb validate ', 'echo skipped ')]:
            self.assertIn(old, files[path])
            changed = dict(files, **{path: files[path].replace(old, new)})
            report = audit.audit(entry, Snapshot(changed), VERSION, SHA, {})
            self.assertIn('owner_bootstrap_gate_missing', [f['code'] for f in report['findings']])
        report = audit.audit(entry, Snapshot({}), VERSION, SHA, {})
        self.assertIn('owner_bootstrap_gate_missing', [f['code'] for f in report['findings']])

    def test_managed_branches_explicit_main_only_and_actual_readback(self):
        files = {'.github/workflows/build.yml': audit.qctl.generate(SHA)}
        snapshot = Snapshot(files)
        policy = {'managed_branches': ['main'], 'required_checks': {'main': ['native / test']}}
        with patch.object(snapshot, 'checks', wraps=snapshot.checks) as read:
            report = audit.audit(ENTRY, snapshot, VERSION, SHA, policy)
            self.assertEqual('pass', report['status'])
            self.assertEqual({'main'}, set(report['required_checks']))
            read.assert_called_once_with('main')
        with patch.object(snapshot, 'checks', side_effect=audit.ReadError('403 or missing branch')):
            report = audit.audit(ENTRY, snapshot, VERSION, SHA, policy)
            self.assertEqual('unknown', report['status'])
        policy.pop('required_checks')
        report = audit.audit(ENTRY, snapshot, VERSION, SHA, policy)
        self.assertEqual('unknown', report['status'])

    def test_empty_check_policy_only_for_exact_no_ci_and_actual_empty(self):
        repository, definition = next(iter(audit.NO_CI.items()))
        entry = dict(ENTRY, name=repository.split('/')[-1], nameWithOwner=repository)
        files = {path: 'identity' for path in definition['required_paths']}
        policy = {'managed_branches': ['main'], 'required_checks': {'main': []}}
        snapshot = Snapshot(files, checks=[])
        with patch.object(snapshot, 'checks', wraps=snapshot.checks) as read:
            report = audit.audit(entry, snapshot, VERSION, SHA, policy)
            self.assertEqual('pass', report['status'])
            read.assert_called_once_with('main')
        report = audit.audit(entry, Snapshot(files, checks=['removed CI context']), VERSION, SHA, policy)
        self.assertEqual('stale', report['required_checks']['main']['state'])
        self.assertIn('stale_required_merge_check', [f['code'] for f in report['findings']])
        with patch.object(snapshot, 'checks', side_effect=audit.ReadError('404')):
            report = audit.audit(entry, snapshot, VERSION, SHA, policy)
            self.assertEqual('unknown', report['status'])
        report = audit.audit(entry, snapshot, VERSION, SHA, {'managed_branches': ['main']})
        self.assertEqual('unknown', report['status'])
        for name in ['qctl', 'qqq-orb', 'qqq-mcp-rag', 'qbit-example', 'unknown']:
            other = dict(ENTRY, name=name, nameWithOwner='QRun-IO/' + name)
            with self.subTest(name=name), self.assertRaises(audit.ReadError):
                audit.audit(other, Snapshot({}, checks=[]), VERSION, SHA, policy)

    def test_invalid_managed_branches_cannot_bypass_policy(self):
        for managed in [[], ['main', 'main'], ['feature'], 'main', None, [True]]:
            with self.subTest(managed=managed), self.assertRaises(audit.ReadError):
                self.native(policy={'managed_branches': managed, 'required_checks': {}})

    def test_gh_is_explicit_get_and_never_changes_settings(self):
        with patch.object(audit, 'command', return_value='{}') as command:
            audit.gh('repos/QRun-IO/example')
            self.assertEqual(['gh', 'api', '--method', 'GET', 'repos/QRun-IO/example'], command.call_args.args[0])


if __name__ == '__main__': unittest.main()
