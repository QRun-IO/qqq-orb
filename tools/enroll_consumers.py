#!/usr/bin/env python3
"""Enroll a batch of audited consumers; preview by default, write with --write.

Existing canonical profiles retain their manifests. Legacy QBits use the shared
policy inference. Unknown orchestration is rejected before any checkout changes.
"""
import argparse
import json
from pathlib import Path
import re
import tempfile

import yaml

import rollout_version as rollout
import standardize_qbit as qbit


def declaration(root, relative):
    """Reject redirected declarations, including symlinked parent directories."""
    path = root / relative
    current = path
    while current != root:
        if current.is_symlink():
            raise ValueError('CI declarations must not use symlinks')
        current = current.parent
    if not path.resolve().is_relative_to(root):
        raise ValueError('CI declarations must remain inside the checkout')
    return path


def plan(target, version):
    """Preserve explicit publication policy and validate generated declarations."""
    if not isinstance(target, dict) or set(target) != {'checkout', 'default_branch'}:
        raise ValueError('Each target requires checkout and observed default_branch')
    if target['default_branch'] not in ('main', 'develop'):
        raise ValueError('Unsupported default branch')
    root = Path(target['checkout']).resolve(strict=True)
    config = declaration(root, '.circleci/config.yml')
    manifest = declaration(root, '.qqq-ci.yml')
    if manifest.exists():
        data = rollout.standard.load_yaml(manifest.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('default_branch') != target['default_branch']:
            raise ValueError('Observed default branch differs from manifest')
        return {**rollout.plan(root, version), 'enrollment': False}
    original = config.read_bytes()
    data = qbit.infer_manifest(rollout.standard.load_yaml(original.decode('utf-8')),
                               version, target['default_branch'])
    caller = rollout.standard.canonical_caller(data['profile'], version,
        release_tag_policy=data['release_tag_policy'], publish_feature=data['publish'].get('feature', False))
    config_raw = yaml.safe_dump(caller, sort_keys=False)
    manifest_raw = yaml.safe_dump(data, sort_keys=False)
    rollout.standard.validate(config_raw, manifest_raw, version)
    with tempfile.TemporaryDirectory() as directory:
        temporary_manifest = Path(directory) / 'manifest.yml'
        temporary_manifest.write_text(manifest_raw, encoding='utf-8')
        rollout.pipeline.load_manifest(temporary_manifest, version)
    return {'checkout': str(root), 'profile': data['profile'], 'from': None,
            'to': version, 'enrollment': True,
            'files': [(config, original, config_raw.encode('utf-8')),
                      (manifest, None, manifest_raw.encode('utf-8'))]}


def enroll(targets, version, write=False):
    """Validate the whole batch before writing; repeat applications are no-ops."""
    if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+(?:\.\d+)?', version):
        raise ValueError('Enrollment requires a stable minor track or exact patch')
    if not isinstance(targets, list) or not targets:
        raise ValueError('A nonempty target list is required')
    plans = [plan(target, version) for target in targets]
    if len({item['checkout'] for item in plans}) != len(plans):
        raise ValueError('Each checkout may appear only once')
    if write:
        for item in plans:
            for path, original, replacement in item['files']:
                declaration(Path(item['checkout']), path.relative_to(item['checkout']))
                current = path.read_bytes() if path.exists() else None
                if current != original:
                    raise ValueError('Declaration changed after preflight')
        for item in plans:
            for path, original, replacement in item['files']:
                if replacement != original:
                    path.write_bytes(replacement)
    return [{**{key: value for key, value in item.items() if key != 'files'},
             'changed': any(old != new for _, old, new in item['files']),
             'written': write} for item in plans]


def main():
    """Read one fleet target file and emit an auditable result."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('targets', type=Path)
    parser.add_argument('--orb-version', required=True)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    print(json.dumps(enroll(json.loads(args.targets.read_text(encoding='utf-8')),
                            args.orb_version, args.write), indent=2))


if __name__ == '__main__':
    main()
