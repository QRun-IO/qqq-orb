"""Version rollouts preserve policy and reject drift before changing any repo."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

import yaml

spec = importlib.util.spec_from_file_location('rollout', Path(__file__).resolve().parents[1] / 'tools/rollout_version.py')
rollout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rollout)


class RolloutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def checkout(self, name, profile='qbit', explicit=False, **policy):
        root = self.root / name
        (root / '.circleci').mkdir(parents=True)
        if profile == 'node-artifact':
            policy = {'context': 'registry', 'npm_scopes': ['@example'], 'node_version': '20.19',
                      'artifact_path': 'dist/bundle.js', 'build_branches': ['main'], **policy}
        if profile == 'homebrew-tap':
            policy = {'tap': 'qrun-io/qctl', 'formula': 'qctl', **policy}
        manifest = {'profile': profile, 'orb_version': '0.7.4', 'default_branch': 'develop', **policy}
        caller = rollout.standard.canonical_caller(profile, '0.7.4', explicit_manifest=explicit,
                                                   release_tag_policy=manifest.get('release_tag_policy'))
        (root / '.qqq-ci.yml').write_text(yaml.safe_dump(manifest), encoding='utf-8')
        (root / '.circleci/config.yml').write_text(yaml.safe_dump(caller), encoding='utf-8')
        return root

    def contents(self, root):
        return [(root / path).read_bytes() for path in ('.circleci/config.yml', '.qqq-ci.yml')]

    def test_batch_preserves_opt_outs_filters_contexts_and_forwarded_parameters(self):
        qbit = self.checkout('qbit', release_tag_policy='none', release_on_main=False,
                             test_branch_policy='feature', browsers=False,
                             publish={'snapshot': False, 'release_candidate': False, 'release': False})
        core = self.checkout('core', profile='core', explicit=True)
        cli = self.checkout('cli', profile='cli', publish={'release': True}, publish_context='npm-publisher')
        roots = [qbit, core, cli]
        originals = [yaml.safe_load((root / '.qqq-ci.yml').read_text()) for root in roots]
        results = rollout.rollout(roots, '0.7.11', write=True)
        self.assertTrue(all(result['changed'] for result in results))
        for root, original in zip(roots, originals):
            expected = {**original, 'orb_version': '0.7.11'}
            self.assertEqual(expected, yaml.safe_load((root / '.qqq-ci.yml').read_text()))
            rollout.standard.validate(*(data.decode() for data in self.contents(root)), '0.7.11')
            rollout.pipeline.load_manifest(root / '.qqq-ci.yml', '0.7.11')
        core_caller = yaml.safe_load((core / '.circleci/config.yml').read_text())
        options = core_caller['workflows']['setup']['jobs'][0]['qqq-orb/generate_pipeline']
        self.assertEqual('.qqq-ci.yml', options['manifest'])
        self.assertEqual('<< pipeline.parameters.mongo_bind_diagnostics >>', options['mongo_bind_diagnostics'])

    def test_all_supported_profiles_remain_valid_after_the_same_batch_upgrade(self):
        roots = [self.checkout(profile, profile=profile, default_branch='main') for profile in rollout.standard.PROFILE_PARAMETERS]
        results = rollout.rollout(roots, '0.7.11', write=True)
        self.assertEqual(set(rollout.standard.PROFILE_PARAMETERS), {item['profile'] for item in results})
        for root in roots:
            rollout.pipeline.load_manifest(root / '.qqq-ci.yml', '0.7.11')
            rollout.standard.validate(*(data.decode() for data in self.contents(root)), '0.7.11')

    def test_dry_run_and_repeated_application_do_not_rewrite_files(self):
        root = self.checkout('qbit')
        before = self.contents(root)
        self.assertTrue(rollout.rollout([root], '0.7.11')[0]['changed'])
        self.assertEqual(before, self.contents(root))
        rollout.rollout([root], '0.7.11', write=True)
        applied = self.contents(root)
        self.assertFalse(rollout.rollout([root], '0.7.11', write=True)[0]['changed'])
        self.assertEqual(applied, self.contents(root))

    def test_managed_patch_track_and_exact_pin_rollback_preserve_every_profile(self):
        roots = [self.checkout(profile, profile=profile, default_branch='main')
                 for profile in rollout.standard.PROFILE_PARAMETERS]
        originals = [yaml.safe_load((root / '.qqq-ci.yml').read_text()) for root in roots]
        rollout.rollout(roots, '0.7', write=True)
        for root, original in zip(roots, originals):
            self.assertEqual({**original, 'orb_version': '0.7'},
                             yaml.safe_load((root / '.qqq-ci.yml').read_text()))
            rollout.standard.validate(*(data.decode() for data in self.contents(root)), '0.7')
            rollout.pipeline.load_manifest(root / '.qqq-ci.yml', '0.7')
            with self.assertRaises(ValueError):
                rollout.pipeline.load_manifest(root / '.qqq-ci.yml', '0.8')
        self.assertTrue(all(not r['changed'] for r in rollout.rollout(roots, '0.7', write=True)))
        rollout.rollout(roots, '0.7.4', write=True)
        for root, original in zip(roots, originals):
            self.assertEqual(original, yaml.safe_load((root / '.qqq-ci.yml').read_text()))

    def test_unquoted_track_is_rejected_as_numeric_yaml(self):
        root = self.checkout('numeric')
        manifest = root / '.qqq-ci.yml'
        manifest.write_text(manifest.read_text().replace('0.7.4', '0.7'))
        with self.assertRaises(ValueError):
            rollout.pipeline.load_manifest(manifest, '0.7')

    def test_one_custom_caller_rejects_entire_batch_before_any_write(self):
        good = self.checkout('good')
        bad = self.checkout('bad')
        before = self.contents(good)
        with (bad / '.circleci/config.yml').open('a') as stream:
            stream.write('\njobs: {custom: {steps: [checkout]}}\n')
        with self.assertRaises(ValueError):
            rollout.rollout([good, bad], '0.7.11', write=True)
        self.assertEqual(before, self.contents(good))

    def test_duplicate_manifest_keys_unknown_settings_and_mismatched_pins_are_rejected(self):
        for suffix in ['orb_version: 0.7.4\n', 'unknown_setting: true\n', 'publish: {release: maybe}\n']:
            with self.subTest(suffix=suffix):
                root = self.checkout(str(len(list(self.root.iterdir()))))
                with (root / '.qqq-ci.yml').open('a') as stream:
                    stream.write(suffix)
                before = self.contents(root)
                with self.assertRaises(ValueError):
                    rollout.rollout([root], '0.7.11', write=True)
                self.assertEqual(before, self.contents(root))
        root = self.checkout('mismatch')
        path = root / '.circleci/config.yml'
        path.write_text(path.read_text().replace('0.7.4', '0.7.3'))
        with self.assertRaises(ValueError):
            rollout.rollout([root], '0.7.11', write=True)

    def test_invalid_target_and_duplicate_checkout_are_rejected(self):
        root = self.checkout('qbit')
        before = self.contents(root)
        for version in ['latest', 'volatile', 'dev:test', '0', '0.7.*', '0.7.11\n']:
            with self.assertRaises(ValueError):
                rollout.rollout([root], version, write=True)
        with self.assertRaises(ValueError):
            rollout.rollout([root, root], '0.7.11', write=True)
        self.assertEqual(before, self.contents(root))


if __name__ == '__main__':
    unittest.main()
