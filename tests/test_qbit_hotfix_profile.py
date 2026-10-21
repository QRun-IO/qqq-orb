"""Preserve the audited main-branch hotfix contracts in the shared profile."""
import importlib.util
import json
from pathlib import Path
import re
import unittest
from unittest import mock
import yaml

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

migration = load('migration', 'tools/standardize_qbit.py')
pipeline = load('pipeline', 'src/scripts/generate_pipeline.py')

def selects(filters, branch, tag):
    selector = filters.get('tags' if tag else 'branches', {})
    if tag and not selector:
        return False
    def matches(patterns):
        patterns = patterns if isinstance(patterns, list) else [patterns]
        return any(re.fullmatch(p[1:-1], tag or branch, flags=re.ASCII) is not None if p.startswith('/') and p.endswith('/') else p == (tag or branch) for p in patterns)
    return ('only' not in selector or matches(selector['only'])) and ('ignore' not in selector or not matches(selector['ignore']))

class HotfixMigrationTests(unittest.TestCase):
    def test_audited_main_job_selection_is_preserved(self):
        fixtures = json.loads((ROOT/'tests/fixtures/qbit-main-hotfix-policies.json').read_text())
        for fixture in fixtures:
            manifest = migration.infer_manifest(fixture['config'], '0.7.13', 'develop')
            with mock.patch.object(Path, 'read_text', return_value=yaml.safe_dump(manifest)):
                config = pipeline.load_manifest('unused', '0.7.13')
            cases = [(branch, '') for branch in ('main','develop','feature/a','release/1','hotfix/1.2.3','integration-test','staging')]
            cases += [('', tag) for tag in ('v1.2.3','v1.2.3-RC.1','vanything','publish1','invalid','v\u0661.\u0662.\u0663')]
            for branch, tag in cases:
                with self.subTest(repository=fixture['repository'], branch=branch, tag=tag):
                    expected = sorted((job, options.get('branch_type')) for workflow in fixture['config']['workflows'].values() for entry in workflow['jobs'] for job, options in entry.items() if selects(options.get('filters', {}), branch, tag))
                    with mock.patch.object(pipeline, 'git', return_value=b'verified-head\n'):
                        generated = pipeline.qbit_template(config, branch, tag)
                    actual = sorted((job, options.get('branch_type')) for workflow in generated['workflows'].values() for entry in workflow['jobs'] for job, options in entry.items() if selects(options.get('filters', {}), branch, tag))
                    # The canonical setup's tag filter prevents non-release tag runs.
                    caller = migration.canonical_caller('0.7.13', manifest['release_tag_policy'])
                    setup = caller['workflows']['setup']['jobs'][0]['qqq-orb/generate_pipeline']
                    if not selects(setup['filters'], branch, tag): actual = []
                    self.assertEqual(actual, expected)

    def test_cms_repair_only_quotes_the_existing_tag_pattern(self):
        fixtures = json.loads((ROOT/'tests/fixtures/qbit-main-hotfix-policies.json').read_text())
        fixture = next(row for row in fixtures if row['repository'] == 'QRun-IO/qbit-cms')
        with self.assertRaises(yaml.YAMLError):
            yaml.safe_load(fixture['original_yaml'])
        repaired = fixture['original_yaml'].replace(r'only: [/^v[0-9]+\.[0-9]+\.[0-9]+$/]',
                                                  r"only: ['/^v[0-9]+\.[0-9]+\.[0-9]+$/']")
        self.assertEqual(yaml.safe_load(repaired), fixture['config'])

    def test_stable_tag_selection_uses_ascii_digits(self):
        with mock.patch.object(pipeline, 'git', return_value=b'verified-head\n'):
            self.assertEqual(pipeline.event_kind('', 'v\u0661.\u0662.\u0663'), 'test')
            self.assertEqual(pipeline.event_kind('', 'v1.2.3'), 'release')

    def test_existing_manifest_does_not_enable_hotfix_publication(self):
        raw = 'profile: qbit\norb_version: 0.7.13\ndefault_branch: develop\n'
        with mock.patch.object(Path, 'read_text', return_value=raw):
            config = pipeline.load_manifest('unused','0.7.13')
        self.assertFalse(config['publish'].get('hotfix', False))
        result = pipeline.qbit_template(config, 'hotfix/1.2.3', '')
        self.assertIn('qqq-orb/mvn_test_only', result['workflows']['test_only']['jobs'][0])

if __name__ == '__main__': unittest.main()
