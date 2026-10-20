#!/usr/bin/env python3
"""Emit/check approved native maintenance bridges; orchestration lives in the orb."""
import argparse
import copy
import json
from pathlib import Path
import re
import sys
import yaml

BRIDGES = json.loads((Path(__file__).with_name('templates') / 'auxiliary-bridges.json').read_text(encoding='utf-8'))


def canonical(kind, worker_sha):
    if kind not in BRIDGES or not re.fullmatch(r'[0-9a-f]{40}', worker_sha or ''):
        raise ValueError('Choose an approved bridge and immutable orb commit SHA')
    result = copy.deepcopy(BRIDGES[kind]['caller'])
    for job in result['jobs'].values():
        job['uses'] = job['uses'].replace('WORKER_SHA', worker_sha)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=sorted(BRIDGES))
    parser.add_argument('--ref', required=True)
    parser.add_argument('--check', type=Path)
    args = parser.parse_args()
    expected = canonical(args.kind, args.ref)
    if args.check:
        # Compare exact canonical output: local custom keys or duplicate mappings cannot hide.
        if args.check.read_text(encoding='utf-8') != yaml.safe_dump(expected, sort_keys=False):
            raise ValueError('Native maintenance caller differs from canonical orb definition')
        print('Canonical native maintenance caller verified')
    else:
        print(yaml.safe_dump(expected, sort_keys=False), end='')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError):
        sys.exit('Invalid native maintenance bridge, pin, or caller')
