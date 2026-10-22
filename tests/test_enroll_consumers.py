"""Batch enrollment preserves policy and rejects unsafe or unknown declarations."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import enroll_consumers as enrollment


class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def legacy(self, name):
        root = self.root / name
        (root / '.circleci').mkdir(parents=True)
        config = {'version': 2.1, 'orbs': {'qqq-orb': 'kingsrook/qqq-orb@0.5.0'},
                  'workflows': {'verify': {'jobs': [{'qqq-orb/mvn_test_only': {}}]}}}
        (root / '.circleci/config.yml').write_text(yaml.safe_dump(config), encoding='utf-8')
        return {'checkout': str(root), 'default_branch': 'main'}

    def canonical(self, profile):
        target = self.legacy(profile)
        root = Path(target['checkout'])
        data = {'profile': profile, 'orb_version': '0.7.4', 'default_branch': 'main'}
        if profile == 'node-artifact':
            data.update(context='registry', npm_scopes=['@example'], node_version='20.19',
                        artifact_path='dist/bundle.js', build_branches=['main'])
        if profile == 'homebrew-tap':
            data.update(tap='qrun-io/qctl', formula='qctl')
        (root / '.qqq-ci.yml').write_text(yaml.safe_dump(data), encoding='utf-8')
        (root / '.circleci/config.yml').write_text(yaml.safe_dump(
            enrollment.rollout.standard.canonical_caller(profile, '0.7.4')), encoding='utf-8')
        return target

    def test_mixed_fleet_preview_write_and_idempotence(self):
        legacy = self.legacy('legacy')
        targets = [legacy] + [self.canonical(p) for p in enrollment.rollout.standard.PROFILE_PARAMETERS]
        preview = enrollment.enroll(targets, '0.8')
        self.assertTrue(all(item['changed'] for item in preview))
        self.assertFalse((Path(legacy['checkout']) / '.qqq-ci.yml').exists())
        result = enrollment.enroll(targets, '0.8', write=True)
        self.assertEqual(1, sum(item['enrollment'] for item in result))
        data = yaml.safe_load((Path(legacy['checkout']) / '.qqq-ci.yml').read_text())
        self.assertFalse(any(data['publish'].values()))
        self.assertEqual('all', data['test_branch_policy'])
        self.assertTrue(all(not item['changed'] for item in enrollment.enroll(targets, '0.8', write=True)))

    def test_unknown_orchestration_rejects_entire_batch(self):
        good, bad = self.legacy('good'), self.legacy('bad')
        path = Path(bad['checkout']) / '.circleci/config.yml'
        path.write_text(path.read_text() + '\njobs: {custom: {steps: [checkout]}}\n')
        original = (Path(good['checkout']) / '.circleci/config.yml').read_bytes()
        with self.assertRaises(ValueError):
            enrollment.enroll([good, bad], '0.8', write=True)
        self.assertEqual(original, (Path(good['checkout']) / '.circleci/config.yml').read_bytes())
        self.assertFalse((Path(good['checkout']) / '.qqq-ci.yml').exists())

    def test_duplicate_targets_and_wrong_default_reject_before_write(self):
        target = self.canonical('core')
        for targets in ([target, target], [{**target, 'default_branch': 'develop'}]):
            with self.assertRaises(ValueError):
                enrollment.enroll(targets, '0.8', write=True)
        self.assertEqual('0.7.4', yaml.safe_load((Path(target['checkout']) / '.qqq-ci.yml').read_text())['orb_version'])

    def test_invalid_manifest_and_unstable_versions_rejected(self):
        target = self.canonical('qbit')
        path = Path(target['checkout']) / '.qqq-ci.yml'
        path.write_text(path.read_text() + '\nunknown_policy: true\n')
        for version in ('0.8', 'dev:snapshot', 'latest', 0.8):
            with self.assertRaises(ValueError):
                enrollment.enroll([target], version, write=True)

    def test_drift_after_preflight_is_not_overwritten(self):
        target = self.legacy('drift')
        path = Path(target['checkout']) / '.circleci/config.yml'
        original_plan = enrollment.plan

        def changed_plan(*args):
            result = original_plan(*args)
            path.write_bytes(b'concurrent edit\n')
            return result

        with mock.patch.object(enrollment, 'plan', side_effect=changed_plan):
            with self.assertRaises(ValueError):
                enrollment.enroll([target], '0.8', write=True)
        self.assertEqual(b'concurrent edit\n', path.read_bytes())
        self.assertFalse((Path(target['checkout']) / '.qqq-ci.yml').exists())

    def test_manifest_symlink_is_rejected(self):
        target = self.legacy('redirect')
        outside = self.root / 'outside.yml'
        outside.write_text('untouched\n')
        try:
            (Path(target['checkout']) / '.qqq-ci.yml').symlink_to(outside)
        except OSError as error:
            self.skipTest('Symlink creation unavailable: ' + str(error))
        with self.assertRaises(ValueError):
            enrollment.enroll([target], '0.8', write=True)
        self.assertEqual('untouched\n', outside.read_text())


if __name__ == '__main__':
    unittest.main()
