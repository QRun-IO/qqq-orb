#!/usr/bin/env python3
"""Upgrade canonical CircleCI callers in one batch; dry-run unless --write.

Only the orb pin changes. Repository publication policy and profile parameters
are preserved. Git commits, pushes and hosted verification remain separate.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'src/scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


standard = module('validate_standard')
pipeline = module('generate_pipeline')


def plan(checkout, version):
    root = Path(checkout).resolve(strict=True)
    paths = [root / '.circleci/config.yml', root / '.qqq-ci.yml']
    if any(not path.resolve(strict=True).is_relative_to(root) for path in paths):
        raise ValueError('CI declarations must remain inside their checkout')
    originals = [path.read_bytes() for path in paths]
    caller_raw, manifest_raw = [data.decode('utf-8') for data in originals]
    manifest = standard.load_yaml(manifest_raw)
    if not isinstance(manifest, dict):
        raise ValueError('Existing manifest must be a mapping')
    previous = manifest.get('orb_version')
    standard.validate(caller_raw, manifest_raw, previous)
    pipeline.load_manifest(paths[1], previous)
    caller = standard.load_yaml(caller_raw)
    if previous == version:
        replacements = originals
    else:
        manifest['orb_version'] = version
        caller['orbs']['qqq-orb'] = 'kingsrook/qqq-orb@' + version
        caller['workflows']['setup']['jobs'][0]['qqq-orb/generate_pipeline']['orb_version'] = version
        new_caller = yaml.safe_dump(caller, sort_keys=False)
        new_manifest = yaml.safe_dump(manifest, sort_keys=False)
        standard.validate(new_caller, new_manifest, version)
        replacements = [new_caller.encode('utf-8'), new_manifest.encode('utf-8')]
    return {'checkout': str(root), 'profile': manifest['profile'], 'from': previous, 'to': version,
            'files': list(zip(paths, originals, replacements))}


def rollout(checkouts, version, write=False):
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Fleet upgrades require an explicit stable orb version')
    # Validate the entire batch before writing any repository.
    plans = [plan(path, version) for path in checkouts]
    if len({item['checkout'] for item in plans}) != len(plans):
        raise ValueError('Each checkout may appear only once')
    if write:
        for item in plans:
            for path, original, replacement in item['files']:
                if path.read_bytes() != original:
                    raise ValueError('CI declaration changed after preflight; rerun the rollout')
        for item in plans:
            for path, original, replacement in item['files']:
                if replacement != original:
                    path.write_bytes(replacement)
    return [{**{key: value for key, value in item.items() if key != 'files'},
             'changed': any(old != new for _, old, new in item['files']), 'written': write}
            for item in plans]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkouts', nargs='+', type=Path)
    parser.add_argument('--orb-version', required=True)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    print(json.dumps(rollout(args.checkouts, args.orb_version, args.write), indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        sys.exit('Version rollout rejected: ' + str(error))
