import copy
import os
import subprocess
import tempfile
import importlib.util
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
import yaml

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('auxiliary', ROOT / 'src/scripts/generate_auxiliary_workflow.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
ORIGINALS = json.loads((ROOT / 'tests/fixtures/auxiliary-original-workflows.json').read_text())
SHA = 'a' * 40


class GitOpsTests(unittest.TestCase):
    def test_render_all_directories_and_fail_on_invalid_or_missing_configuration(self):
        worker = yaml.safe_load((ROOT / '.github/workflows/gitops.yml').read_text())
        command = worker['jobs']['validate']['steps'][-1]['run']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'bin'
            binary.mkdir()
            tool = binary / 'kustomize'
            tool.write_text("#!/bin/bash\n[[ $1 == build ]] || exit 2\n[[ ! -f \"$2/invalid\" ]] || exit 1\necho sensitive-rendered-fixture\n")
            tool.chmod(0o755)
            env = {**os.environ, 'PATH': str(binary) + os.pathsep + os.environ['PATH']}
            def run():
                return subprocess.run(['bash', '-c', command], cwd=root, env=env, text=True, capture_output=True)
            self.assertNotEqual(0, run().returncode)
            for name in ('base', 'overlays/dev', 'overlays/with space', 'proxy'):
                folder = root / name
                folder.mkdir(parents=True)
                (folder / 'kustomization.yaml').write_text('resources: []')
            result = run()
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(4, result.stdout.count('Validated '))
            self.assertNotIn('sensitive-rendered-fixture', result.stdout)
            (root / 'proxy/invalid').touch()
            self.assertNotEqual(0, run().returncode)

    def test_gitops_caller_is_read_only_and_has_no_duplicate_feature_push_build(self):
        caller = bridge.canonical('gitops', SHA)
        self.assertEqual({'contents': 'read'}, caller['permissions'])
        self.assertEqual(['main'], caller['on']['push']['branches'])
        self.assertNotIn('paths', caller['on']['pull_request'])
        self.assertNotIn('secrets', caller['jobs']['gitops'])


class SpecialistNativeTests(unittest.TestCase):
    def setUp(self):
        self.originals = json.loads((ROOT / 'tests/fixtures/specialist-native-originals.json').read_text(encoding='utf-8'))

    def worker(self, kind):
        return yaml.safe_load((ROOT / '.github/workflows' / (kind + '.yml')).read_text(encoding='utf-8'))

    def test_business_database_job_and_path_filters_are_unchanged(self):
        original = self.originals['business-db']
        worker = self.worker('business-db')
        self.assertEqual(worker['jobs'], original['workflow']['jobs'])
        caller = bridge.canonical('business-db', SHA)
        self.assertEqual(caller['on'], original['events'])
        self.assertEqual(set(worker['jobs']), {'empty-database-migration'})
        self.assertNotIn('secrets', caller['jobs']['validate'])
        self.assertNotIn('schedule', caller['on'])

    def test_mcp_preserves_publication_and_secret_with_one_verification(self):
        worker = self.worker('mcp-rag')
        original = self.originals['mcp-rag']['workflow']
        expected_publish = copy.deepcopy(original['jobs']['publish'])
        for step in expected_publish['steps']:
            if step.get('name') == 'Set image name':
                step['run'] = 'printf \'IMAGE_NAME=%s\\n\' "${GITHUB_REPOSITORY,,}" >> "$GITHUB_ENV"'
        self.assertEqual(worker['jobs']['publish'], expected_publish)
        self.assertEqual(worker['env'], original['env'])
        self.assertEqual(set(worker['jobs']), {'build-and-test', 'publish'})
        steps = worker['jobs']['build-and-test']['steps']
        commands = [step['run'] for step in steps if 'run' in step]
        self.assertEqual(commands, ['mvn -B -ntp clean verify'])
        verify = next(step for step in steps if 'run' in step)
        old_verify = next(step for step in original['jobs']['build-and-test']['steps'] if 'run' in step)
        self.assertEqual(verify['env'], old_verify['env'])
        self.assertEqual(steps[:2], original['jobs']['build-and-test']['steps'][:2])
        self.assertEqual(steps[3], original['jobs']['build-and-test']['steps'][3])
        self.assertEqual(steps[4]['if'], 'always()')
        caller = bridge.canonical('mcp-rag', SHA)
        # Feature branches run once through the PR event, not also on push.
        self.assertEqual(caller['on']['push'], {'branches': ['main']})
        self.assertEqual(caller['on']['pull_request'], {'branches': ['main']})
        self.assertEqual(caller['jobs']['validate']['secrets'], {
            'QQQ_MCP_VOYAGE_API_KEY': '${{ secrets.QQQ_MCP_VOYAGE_API_KEY }}'})
        self.assertEqual(worker['on']['workflow_call']['secrets'], {
            'QQQ_MCP_VOYAGE_API_KEY': {'required': False}})

    def test_mcp_verify_really_contains_separate_lint_compile_and_integration_gates(self):
        pom = ET.parse(ROOT / 'tests/fixtures/mcp-rag-pom.xml')
        ns = {'m': 'http://maven.apache.org/POM/4.0.0'}
        plugins = {p.findtext('m:artifactId', namespaces=ns): p
                   for p in pom.findall('./m:build/m:plugins/m:plugin', ns)}
        style = plugins['maven-checkstyle-plugin']
        self.assertEqual(style.findtext('m:executions/m:execution/m:phase', namespaces=ns), 'validate')
        self.assertIn('check', [g.text for g in style.findall('.//m:goal', ns)])
        compiler = ET.tostring(plugins['maven-compiler-plugin'], encoding='unicode')
        self.assertIn('error_prone_core', compiler)
        self.assertIn('ErrorProne', compiler)
        failsafe = plugins['maven-failsafe-plugin']
        self.assertEqual({g.text for g in failsafe.findall('.//m:goal', ns)}, {'integration-test', 'verify'})


class AuxiliaryTests(unittest.TestCase):
    def test_all_worker_jobs_exactly_preserve_audited_source(self):
        for kind, original in ORIGINALS.items():
            with self.subTest(kind=kind):
                worker = yaml.safe_load((ROOT / '.github/workflows' / (kind + '.yml')).read_text())
                expected = copy.deepcopy(original['jobs'])
                if kind == 'core-codeql':
                    # Cover the additional languages observed in active default setup.
                    expected['analyze']['strategy']['matrix']['include'].extend([
                        {'language': 'actions', 'build-mode': 'none'},
                        {'language': 'python', 'build-mode': 'none'},
                    ])
                if kind == 'core-quickstart-lifecycle':
                    for job in expected.values():
                        for step in job.get('steps', []):
                            if 'run' in step:
                                # Existing umask 077 gives mkdir the required private permissions.
                                step['run'] = step['run'].replace('mkdir -m 700 -p', 'mkdir -p')
                self.assertEqual(expected, worker['jobs'])
                self.assertEqual(original['permissions'], worker.get('permissions'))
                self.assertEqual({'workflow_call'}, set(worker['on']))

    def test_codeql_union_keeps_original_languages_and_default_queries(self):
        worker = yaml.safe_load((ROOT / '.github/workflows/core-codeql.yml').read_text())
        job = worker['jobs']['analyze']
        matrix = job['strategy']['matrix']['include']
        original = ORIGINALS['core-codeql']['jobs']['analyze']['strategy']['matrix']['include']
        self.assertEqual(matrix[:2], original)
        self.assertEqual(matrix[2:], [
            {'language': 'actions', 'build-mode': 'none'},
            {'language': 'python', 'build-mode': 'none'},
        ])
        self.assertEqual({cell['language'] for cell in matrix},
                         {'actions', 'java-kotlin', 'javascript-typescript', 'python'})
        init = next(step for step in job['steps'] if step.get('uses', '').startswith('github/codeql-action/init@'))
        self.assertNotIn('queries', init['with'])
        self.assertNotIn('config-file', init['with'])
        self.assertNotIn('config', init['with'])
        self.assertNotIn('packs', init['with'])

    def test_callers_preserve_events_and_have_no_local_steps(self):
        for kind, original in ORIGINALS.items():
            with self.subTest(kind=kind):
                caller = bridge.canonical(kind, SHA)
                self.assertEqual(original['events'], caller['on'])
                self.assertEqual(1, len(caller['jobs']))
                job = next(iter(caller['jobs'].values()))
                self.assertEqual('QRun-IO/qqq-orb/.github/workflows/' + kind + '.yml@' + SHA, job['uses'])
                self.assertNotIn('steps', job)
                self.assertNotIn('secrets', job)
                self.assertEqual(original['permissions'] or original['jobs']['analyze']['permissions'], caller['permissions'])

    def test_native_dispatch_inputs_forwarded_with_correct_types(self):
        for kind, original in ORIGINALS.items():
            worker = yaml.safe_load((ROOT / '.github/workflows' / (kind + '.yml')).read_text())
            inputs = worker['on']['workflow_call'].get('inputs', {})
            source = (original['events'].get('workflow_dispatch') or {}).get('inputs', {})
            self.assertEqual(set(source), set(inputs))
            job = next(iter(bridge.canonical(kind, SHA)['jobs'].values()))
            self.assertEqual(set(source), set(job.get('with', {})))
            for name, value in inputs.items():
                self.assertIn(value['type'], ['string', 'boolean'])
                self.assertIn('inputs.' + name, job['with'][name])
        quickstart = yaml.safe_load((ROOT / '.github/workflows/core-quickstart-lifecycle.yml').read_text())
        self.assertFalse(quickstart['on']['workflow_call']['inputs']['source_sha']['required'])
        self.assertFalse(quickstart['on']['workflow_call']['inputs']['boundary_capture']['default'])

    def test_ref_must_be_immutable_and_calls_are_independent(self):
        for ref in ['main', 'v1.0.0', 'a'*39, 'a'*40 + '\n']:
            with self.assertRaises(ValueError):
                bridge.canonical('core-codeql', ref)
        caller = bridge.canonical('core-codeql', SHA)
        caller['jobs'].clear()
        self.assertTrue(bridge.canonical('core-codeql', SHA)['jobs'])


if __name__ == '__main__': unittest.main()
