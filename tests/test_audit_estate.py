import importlib.util
import json
import io
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


class InventoryTests(unittest.TestCase):
    def repo(self, name, archived=False):
        return {'name': name, 'full_name': 'QRun-IO/' + name,
                'archived': archived, 'default_branch': 'main'}

    def test_all_pages_include_new_private_and_archived_repositories(self):
        new = dict(self.repo('new-product'), private=True)
        pages = [[self.repo('qbit-existing')], [new, self.repo('retired', True)]]
        with patch.object(audit, 'command', return_value=json.dumps(pages)) as command:
            entries = audit.discover_inventory('QRun-IO')
        self.assertEqual([e['name'] for e in entries], ['new-product', 'qbit-existing', 'retired'])
        self.assertTrue(entries[-1]['isArchived'])
        self.assertEqual(command.call_args.args[0], ['gh', 'api', '--method', 'GET',
            '--paginate', '--slurp', 'orgs/QRun-IO/repos?type=all&per_page=100'])

    def test_empty_duplicate_foreign_and_malformed_inventories_fail_closed(self):
        repo = self.repo('qbit-example')
        for pages in ([], [[]], {}, [repo], [[repo], [repo]],
                      [[dict(repo, full_name='Other/qbit-example')]],
                      [[dict(repo, archived='false')]], [[dict(repo, default_branch=None)]]):
            with self.subTest(pages=pages), patch.object(audit, 'command', return_value=json.dumps(pages)):
                with self.assertRaises(audit.ReadError):
                    audit.discover_inventory('QRun-IO')
        with patch.object(audit, 'command') as command:
            with self.assertRaises(audit.ReadError):
                audit.discover_inventory('QRun-IO/../../other')
            command.assert_not_called()

    def test_live_cli_count_is_dynamic_but_explicit_expectation_is_enforced(self):
        for expected, status in ((None, 0), ('1', 0), ('68', 1)):
            args = ['audit', '--organization', 'QRun-IO', '--live', '--orb-version', '0.8']
            if expected:
                args += ['--expected-active', expected]
            report = {'active_count': 1, 'unique_repository_count': 1,
                      'inventory_count': 1, 'results': [{'status': 'pass'}]}
            output = io.StringIO()
            with patch.object(audit.sys, 'argv', args), patch.object(audit.sys, 'stdout', output), \
                    patch.object(audit, 'discover_inventory', return_value=[ENTRY]), \
                    patch.object(audit, 'run', return_value=report):
                self.assertEqual(audit.main(), status)
            self.assertEqual(json.loads(output.getvalue())['inventory_source'], 'organization-api')

    def test_discovery_api_failure_never_falls_back_to_old_inventory(self):
        with patch.object(audit, 'command', side_effect=audit.ReadError('unavailable')):
            with self.assertRaises(audit.ReadError):
                audit.discover_inventory('QRun-IO')


class AuditTests(unittest.TestCase):
    def test_all_scanner_and_release_requirements_follow_branch_profile(self):
        entry = dict(ENTRY, name='qqq-all', nameWithOwner='QRun-IO/qqq-all')
        scanner = '.github/workflows/codeql.yml'
        release = audit.auxiliary.BRIDGES['all-release']['path']
        for profile in ('all', 'repository-policy'):
            files = {'.qqq-ci.yml': audit.generator.yaml.safe_dump({'profile': profile, 'orb_version': VERSION, 'default_branch': 'develop'}),
                     '.circleci/config.yml': audit.generator.yaml.safe_dump(audit.standard.canonical_caller(profile, VERSION))}
            policy = dict(POLICY, profile=profile, codeql_worker_sha=SHA)
            report = audit.audit(entry, Snapshot(files), VERSION, SHA, policy)
            missing = {f.get('path') for f in report['findings'] if f['code'] == 'missing_native_maintenance_bridge'}
            self.assertIn(scanner, missing)
            self.assertEqual(profile == 'all', release in missing)
            files[scanner] = audit.generator.yaml.safe_dump(audit.auxiliary.canonical('qbit-codeql', SHA), sort_keys=False)
            if profile == 'all':
                files[release] = audit.generator.yaml.safe_dump(audit.auxiliary.canonical('all-release', SHA), sort_keys=False)
            self.assertEqual([], audit.audit(entry, Snapshot(files), VERSION, SHA, policy)['findings'])
            files[scanner] = files[scanner].replace(SHA, 'b' * 40)
            self.assertIn('native_maintenance_bridge_drift', [f['code'] for f in audit.audit(entry, Snapshot(files), VERSION, SHA, policy)['findings']])
            files[release] = 'jobs: {}'
            self.assertTrue(any(f['code'] == 'native_maintenance_bridge_drift' and f.get('path') == release for f in audit.audit(entry, Snapshot(files), VERSION, SHA, policy)['findings']))

    def test_schema_drift_bridge_tracks_branch_source_without_exempting_default(self):
        entry = dict(ENTRY, name='qbit-authentik', nameWithOwner='QRun-IO/qbit-authentik')
        path = '.github/workflows/schema-drift.yml'
        cases = [
            ('main', {}, False),
            ('main', {'src/test/java/example/SchemaDriftTest.java': 'class SchemaDriftTest {}'}, True),
            ('develop', {}, True),
        ]
        for branch, files, required in cases:
            with self.subTest(branch=branch, files=files):
                snapshot = Snapshot(files)
                snapshot.branch, snapshot.default_branch = branch, 'develop'
                report = audit.audit(entry, snapshot, VERSION, SHA, POLICY)
                missing = any(f['code'] == 'missing_native_maintenance_bridge' and f.get('path') == path for f in report['findings'])
                self.assertEqual(required, missing)
        snapshot = Snapshot({path: 'jobs: {}'})
        snapshot.branch, snapshot.default_branch = 'main', 'develop'
        report = audit.audit(entry, snapshot, VERSION, SHA, POLICY)
        self.assertIn('native_maintenance_bridge_drift', [f['code'] for f in report['findings']])

    def test_placeholder_can_retain_canonical_release_and_scanner_bridges(self):
        entry = dict(ENTRY, name='qbit-help', nameWithOwner='QRun-IO/qbit-help')
        files = {'.qqq-ci.yml': audit.generator.yaml.safe_dump({'profile': 'repository-policy', 'orb_version': VERSION, 'default_branch': 'develop'}),
                 '.circleci/config.yml': audit.generator.yaml.safe_dump(audit.standard.canonical_caller('repository-policy', VERSION)),
                 audit.rc_worker.CALLER_PATH: audit.rc_worker.generate(SHA),
                 '.github/workflows/codeql.yml': audit.generator.yaml.safe_dump(audit.auxiliary.canonical('qbit-codeql', SHA), sort_keys=False)}
        snapshot = Snapshot(files)
        snapshot.branch = 'main'
        snapshot.default_branch = 'develop'
        policy = dict(POLICY, branch_profiles={'main': 'repository-policy'}, rc_worker_sha=SHA, codeql_worker_sha=SHA)
        self.assertEqual([], audit.audit(entry, snapshot, VERSION, SHA, policy)['findings'])
        files['.github/workflows/codeql.yml'] = files['.github/workflows/codeql.yml'].replace(SHA, 'b' * 40)
        self.assertTrue(any(f['code'] == 'native_maintenance_bridge_drift' for f in audit.audit(entry, snapshot, VERSION, SHA, policy)['findings']))

    def test_placeholder_profile_is_scoped_to_selected_branch(self):
        entry = dict(ENTRY, name='qbit-help', nameWithOwner='QRun-IO/qbit-help')
        files = {'.qqq-ci.yml': audit.generator.yaml.safe_dump({'profile': 'repository-policy', 'orb_version': VERSION, 'default_branch': 'develop'}),
                 '.circleci/config.yml': audit.generator.yaml.safe_dump(audit.standard.canonical_caller('repository-policy', VERSION))}
        snapshot = Snapshot(files)
        snapshot.branch = 'main'
        snapshot.default_branch = 'develop'
        policy = dict(POLICY, branch_profiles={'main': 'repository-policy'})
        self.assertEqual([], audit.audit(entry, snapshot, VERSION, SHA, policy)['findings'])
        snapshot.branch = 'develop'
        report = audit.audit(entry, snapshot, VERSION, SHA, policy)
        self.assertEqual('qbit', report['profile'])
        self.assertTrue(any(f['code'] == 'profile_mismatch' for f in report['findings']))

    def test_qbit_scanner_policy_requires_exact_canonical_worker(self):
        entry = dict(ENTRY, name='qbit-help', nameWithOwner='QRun-IO/qbit-help')
        manifest = {'profile': 'qbit', 'orb_version': VERSION, 'default_branch': 'develop',
                    'publish': {'snapshot': False, 'release_candidate': False, 'release': False}}
        files = {'.qqq-ci.yml': audit.generator.yaml.safe_dump(manifest),
                 '.circleci/config.yml': audit.generator.yaml.safe_dump(audit.standard.canonical_caller('qbit', VERSION))}
        policy = dict(POLICY, codeql_worker_sha='b' * 40)
        report = audit.audit(entry, Snapshot(files), VERSION, SHA, policy)
        self.assertTrue(any(f['code'] == 'missing_native_maintenance_bridge' for f in report['findings']))
        files['.github/workflows/codeql.yml'] = audit.generator.yaml.safe_dump(audit.auxiliary.canonical('qbit-codeql', 'b' * 40), sort_keys=False)
        self.assertEqual([], audit.audit(entry, Snapshot(files), VERSION, SHA, policy)['findings'])
        files['.github/workflows/codeql.yml'] = files['.github/workflows/codeql.yml'].replace('b' * 40, 'a' * 40)
        report = audit.audit(entry, Snapshot(files), VERSION, SHA, policy)
        self.assertTrue(any(f['code'] == 'native_maintenance_bridge_drift' for f in report['findings']))

    def test_live_snapshot_reads_requested_branch_and_keeps_default_identity(self):
        entry = dict(ENTRY, sourceBranch='release/1.2')
        replies = [{'default_branch': 'develop', 'archived': False}, {'sha': SHA},
                   {'truncated': False, 'tree': []}]
        with patch.object(audit, 'gh', side_effect=replies) as gh:
            snapshot = audit.Snapshot(entry, live=True)
        self.assertEqual('develop', snapshot.default_branch)
        self.assertEqual('release/1.2', snapshot.branch)
        self.assertEqual('repos/QRun-IO/qctl/commits/release%2F1.2', gh.call_args_list[1].args[0])

    def test_other_source_branch_does_not_change_manifest_default_branch(self):
        entry = dict(ENTRY, name='qbit-help', nameWithOwner='QRun-IO/qbit-help')
        manifest = {'profile': 'qbit', 'orb_version': VERSION, 'default_branch': 'develop',
                    'publish': {'snapshot': False, 'release_candidate': False, 'release': False}}
        files = {'.qqq-ci.yml': audit.generator.yaml.safe_dump(manifest),
                 '.circleci/config.yml': audit.generator.yaml.safe_dump(audit.standard.canonical_caller('qbit', VERSION))}
        snapshot = Snapshot(files)
        snapshot.branch = 'main'
        snapshot.default_branch = 'develop'
        report = audit.audit(entry, snapshot, VERSION, SHA, POLICY)
        self.assertEqual([], report['findings'])
        self.assertEqual('main', report['source_branch'])
        self.assertEqual('develop', report['default_branch'])

    def test_selected_branch_read_failure_is_unknown_not_default_fallback(self):
        captured = []
        def factory(entry, live):
            captured.append(entry)
            raise audit.ReadError('branch unavailable')
        report = audit.run([ENTRY], VERSION, SHA, {}, live=True,
                           snapshot_factory=factory, source_branch='main')
        self.assertEqual('main', captured[0]['sourceBranch'])
        self.assertEqual('unknown', report['results'][0]['status'])
        self.assertEqual('main', report['results'][0]['source_branch'])
        self.assertNotIn('sourceBranch', ENTRY)

    def test_omitted_source_branch_still_reads_repository_default(self):
        replies = [{'default_branch': 'develop', 'archived': False}, {'sha': SHA},
                   {'truncated': False, 'tree': []}]
        with patch.object(audit, 'gh', side_effect=replies) as gh:
            snapshot = audit.Snapshot(ENTRY, live=True)
        self.assertEqual('develop', snapshot.branch)
        self.assertEqual('develop', snapshot.default_branch)
        self.assertEqual('repos/QRun-IO/qctl/commits/develop', gh.call_args_list[1].args[0])

    def test_explicit_source_branch_cannot_relabel_offline_snapshot(self):
        with self.assertRaises(ValueError):
            audit.run([ENTRY], VERSION, SHA, {}, source_branch='main')
        with self.assertRaises(audit.ReadError):
            audit.Snapshot(dict(ENTRY, sourceBranch='main'), live=False)

    def test_invalid_source_branch_is_rejected_before_api_calls(self):
        for branch in ('', 'main?ref=develop', 'main\n', 123):
            with self.subTest(branch=branch), patch.object(audit, 'gh') as gh:
                with self.assertRaises(audit.ReadError):
                    audit.Snapshot(dict(ENTRY, sourceBranch=branch), live=True)
                gh.assert_not_called()

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

    def test_rc_pin_policy_does_not_force_unchanged_auxiliary_worker_updates(self):
        entry = dict(ENTRY, name='qbit-authentik', nameWithOwner='QRun-IO/qbit-authentik')
        rc_sha = 'b' * 40
        definition = audit.auxiliary.BRIDGES['qbit-schema-drift']
        manifest = {'profile': 'qbit', 'orb_version': VERSION, 'default_branch': 'develop', 'release_completion': True}
        files = {audit.rc_worker.CALLER_PATH: audit.rc_worker.generate(rc_sha),
                 definition['path']: audit.generator.yaml.safe_dump(audit.auxiliary.canonical('qbit-schema-drift', SHA), sort_keys=False),
                 '.qqq-ci.yml': audit.generator.yaml.safe_dump(manifest),
                 '.circleci/config.yml': audit.generator.yaml.safe_dump(audit.standard.canonical_caller('qbit', VERSION))}
        policy = dict(POLICY, rc_worker_sha=rc_sha)
        self.assertEqual('pass', audit.audit(entry, Snapshot(files), VERSION, SHA, policy)['status'])
        for pin in (SHA, 'main', ''):
            with self.subTest(pin=pin):
                report = audit.audit(entry, Snapshot(files), VERSION, SHA, dict(POLICY, rc_worker_sha=pin))
                self.assertTrue(report['findings'])
        files[definition['path']] = files[definition['path']].replace(SHA, rc_sha)
        report = audit.audit(entry, Snapshot(files), VERSION, SHA, policy)
        self.assertIn('native_maintenance_bridge_drift', [f['code'] for f in report['findings']])

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
        self.assertEqual(7, len(audit.NO_CI))
        self.assertNotIn("QRun-IO/voyage-cd", audit.NO_CI)
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
        for name, kind in [('qqq-mcp-rag', 'mcp-rag'), ('qqq-business-platform', 'business-db'), ('.github', 'github-workflow-lint'), ('marketing-website-cd', 'gitops'), ('voyage-cd', 'gitops')]:
            entry = dict(ENTRY, name=name, nameWithOwner='QRun-IO/' + name)
            definition = audit.auxiliary.BRIDGES[kind]
            missing = audit.audit(entry, Snapshot({}), VERSION, SHA, {})
            self.assertIn('missing_native_maintenance_bridge', [f['code'] for f in missing['findings']])
            files = {item['path']: audit.generator.yaml.safe_dump(audit.auxiliary.canonical(key, SHA), sort_keys=False)
                     for key, item in audit.auxiliary.BRIDGES.items() if item['repository'] == entry['nameWithOwner'] or entry['nameWithOwner'] in item.get('additional_repositories', [])}
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
        for managed in [[], ['main', 'main'], ['feature'], 'main', None, [True],
                        ['release/*'], ['release/1.2/extra'], ['hotfix/1..2'],
                        ['release/1.2', 'release/1.2']]:
            with self.subTest(managed=managed), self.assertRaises(audit.ReadError):
                self.native(policy={'managed_branches': managed, 'required_checks': {}})

    def test_release_and_hotfix_enforcement_requires_actual_checks(self):
        files = {'.github/workflows/build.yml': audit.qctl.generate(SHA)}
        for branch in ['release/0.1', 'release/4.1.0', 'hotfix/4.0.1']:
            with self.subTest(branch=branch):
                snapshot = Snapshot(files)
                snapshot.branch = branch
                policy = {'managed_branches': [branch],
                          'required_checks': {branch: ['native / test']}}
                with patch.object(snapshot, 'checks', wraps=snapshot.checks) as read:
                    report = audit.audit(ENTRY, snapshot, VERSION, SHA, policy)
                    self.assertEqual('pass', report['status'])
                    read.assert_called_once_with(branch)
                snapshot.required = []
                report = audit.audit(ENTRY, snapshot, VERSION, SHA, policy)
                self.assertEqual('missing', report['required_checks'][branch]['state'])
                self.assertEqual('findings', report['status'])
                policy['required_checks'] = {}
                self.assertEqual('unknown', audit.audit(ENTRY, snapshot, VERSION, SHA, policy)['status'])

    def test_gh_is_explicit_get_and_never_changes_settings(self):
        with patch.object(audit, 'command', return_value='{}') as command:
            audit.gh('repos/QRun-IO/example')
            self.assertEqual(['gh', 'api', '--method', 'GET', 'repos/QRun-IO/example'], command.call_args.args[0])


if __name__ == '__main__': unittest.main()
