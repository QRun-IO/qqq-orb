#!/usr/bin/env python3
"""One bounded central reconciliation pass; no executor polling for PR checks."""
import json
import os
from pathlib import Path
import subprocess
import sys


def run(environment=None, execute=subprocess.run, root=None):
    env = dict(os.environ if environment is None else environment)
    if (env.get('CIRCLE_PROJECT_USERNAME') != 'QRun-IO'
            or env.get('CIRCLE_PROJECT_REPONAME') != 'qqq-orb'
            or env.get('CIRCLE_BRANCH') != 'main' or env.get('CIRCLE_TAG')):
        raise ValueError('Reconciliation requires the orb main branch')
    token = env.get('GH_TOKEN') or env.get('GITHUB_TOKEN')
    if not token:
        raise ValueError('Existing GitHub authentication is required')
    env['GH_TOKEN'] = token
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    output = root / 'artifacts/enrollment'
    output.mkdir(parents=True, exist_ok=True)
    args = [sys.executable, str(root / 'tools/reconcile_enrollment.py'),
            '--organization', 'QRun-IO', '--orb-version', '0.8',
            '--output', str(output / 'result.json'), '--apply', '--merge-ready', '--enforce']
    try:
        result = execute(args, cwd=root, env=env, timeout=1200, check=False)
        code = result.returncode
        state = 'completed' if code == 0 else 'failed'
    except subprocess.TimeoutExpired:
        code, state = 124, 'timed-out'
    (output / 'run.json').write_text(json.dumps({'state': state, 'exit_code': code,
        'report_available': (output / 'result.json').exists(),
        'note': 'Completion of a pass does not prove all repositories conform; inspect unresolved and waiting entries.'}, indent=2), encoding='utf-8')
    return code


if __name__ == '__main__':
    sys.exit(run())
