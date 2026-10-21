#!/usr/bin/env python3
"""Batch-enforce observed orb checks; dry-run unless --apply. Never changes source."""
import argparse
import base64
import importlib.util
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('standard', ROOT / 'src/scripts/validate_standard.py')
standard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(standard)
DESIRED = [{'context': name, 'app_id': 18001} for name in ('setup', 'verify')]
PROFILES = {'qbit', 'core', 'frontend-core', 'frontend-material'}


def api(path, method='GET', payload=None):
    """Use existing gh authentication; never expose response bodies on failure."""
    args = ['gh', 'api', '--method', method, path]
    if payload is not None:
        args += ['--input', '-']
    result = subprocess.run(args, input=None if payload is None else json.dumps(payload),
                            text=True, encoding='utf-8', capture_output=True, timeout=60)
    if result.returncode:
        try:
            error = json.loads(result.stdout)
        except ValueError:
            error = {}
        if method == 'GET' and path.endswith('/protection') and error.get('status') == '404' and error.get('message') == 'Branch not protected':
            return None
        raise ValueError('GitHub operation unavailable: ' + method + ' ' + path.split('?')[0])
    return json.loads(result.stdout) if result.stdout.strip() else None


def required_checks(before, runs):
    """Append app-bound gates only after both succeeded; preserve all other gates."""
    for desired in DESIRED:
        matches = [run for run in runs if run['name'] == desired['context'] and run['app']['id'] == desired['app_id']]
        if not matches or max(matches, key=lambda run: run['id'])['conclusion'] != 'success':
            raise ValueError('Current branch head has no successful CircleCI ' + desired['context'])
    prior = (before or {}).get('required_status_checks') or {}
    checks = [dict(check) for check in prior.get('checks', [])]
    represented = {check['context'] for check in checks}
    checks += [{'context': name, 'app_id': -1} for name in prior.get('contexts', []) if name not in represented]
    for desired in DESIRED:
        matches = [check for check in checks if check['context'] == desired['context']]
        if any(check.get('app_id') not in (None, -1, desired['app_id']) for check in matches):
            raise ValueError('Existing gate uses a different app: ' + desired['context'])
        checks = [check for check in checks if check['context'] != desired['context']]
        checks.append(dict(desired))
    return {'strict': True, 'checks': checks}


def inspect(repo, branch, version, request=api):
    """Read immutable canonical source, latest check runs, and current protections."""
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo) or branch not in ('main', 'develop'):
        raise ValueError('Targets must name an exact repository and main/develop branch')
    root = 'repos/' + repo
    info = request(root)
    if info['archived']:
        raise ValueError('Archived repository')
    prefix = root + '/branches/' + branch
    head = request(prefix)['commit']['sha']
    source = []
    for path in ('.circleci/config.yml', '.qqq-ci.yml'):
        item = request(root + '/contents/' + quote(path, safe='/') + '?ref=' + head)
        if item.get('encoding') != 'base64' or item.get('type') != 'file':
            raise ValueError('Canonical declarations must be regular files')
        source.append(base64.b64decode(item['content'], validate=False).decode('utf-8'))
    standard.validate(*source, version)
    if standard.load_yaml(source[1])['profile'] not in PROFILES:
        raise ValueError('Profile does not use the shared setup/verify gate pair')
    rules = request(root + '/rules/branches/' + branch)
    if rules:
        raise ValueError('Ruleset-managed branch requires ruleset reconciliation')
    before = request(prefix + '/protection')
    runs = []
    page = 1
    while True:
        batch = request(root + '/commits/' + head + '/check-runs?filter=latest&per_page=100&page=' + str(page))['check_runs']
        runs += batch
        if len(batch) < 100:
            break
        page += 1
    desired = required_checks(before, runs)
    current = (before or {}).get('required_status_checks') or {}
    ready = (current.get('strict') is True and current.get('checks') == desired['checks']
             and (before or {}).get('enforce_admins', {}).get('enabled') is True)
    return {'repository': repo, 'branch': branch, 'head': head, 'before': before,
            'required_status_checks': desired, 'changed': not ready}


def enforce(plan, request=api):
    """Recheck drift, use narrow updates, and verify preservation of other settings."""
    root = 'repos/' + plan['repository']
    prefix = root + '/branches/' + plan['branch']
    if request(prefix)['commit']['sha'] != plan['head'] or request(prefix + '/protection') != plan['before']:
        raise ValueError('Branch or protection changed after preflight')
    if request(root + '/rules/branches/' + plan['branch']):
        raise ValueError('Ruleset changed after preflight')
    if not plan['changed']:
        return
    before = plan['before']
    if before is None:
        request(prefix + '/protection', 'PUT', {
            'required_status_checks': plan['required_status_checks'], 'enforce_admins': True,
            'required_pull_request_reviews': None, 'restrictions': None})
    else:
        request(prefix + '/protection/required_status_checks', 'PATCH', plan['required_status_checks'])
        if not before['enforce_admins']['enabled']:
            request(prefix + '/protection/enforce_admins', 'POST')
    after = request(prefix + '/protection')
    actual = after['required_status_checks']
    if not actual['strict'] or actual['checks'] != plan['required_status_checks']['checks'] or not after['enforce_admins']['enabled']:
        raise ValueError('Protection readback did not match requested gates')
    if before:
        for key, value in before.items():
            if key not in ('required_status_checks', 'enforce_admins') and after.get(key) != value:
                raise ValueError('Unrelated protection changed: ' + key)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--targets', type=Path, required=True, help='JSON list of {repository, branch}')
    parser.add_argument('--orb-version', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    targets = json.loads(args.targets.read_text(encoding='utf-8'))
    if not isinstance(targets, list) or not targets:
        raise ValueError('A nonempty explicit target list is required')
    if len({(row['repository'], row['branch']) for row in targets}) != len(targets):
        raise ValueError('Duplicate branch target')
    # Resolve the entire batch before any mutations. Failures never trigger rollback
    # that would remove successful protections; rerunning converges idempotently.
    plans = [inspect(row['repository'], row['branch'], args.orb_version) for row in targets]
    args.output.write_text(json.dumps({'state': 'planned', 'plans': plans}, indent=2), encoding='utf-8')
    if args.apply:
        for plan in plans:
            enforce(plan)
            plan['verified'] = True
            args.output.write_text(json.dumps({'state': 'applying', 'plans': plans}, indent=2), encoding='utf-8')
        args.output.write_text(json.dumps({'state': 'verified', 'plans': plans}, indent=2), encoding='utf-8')
    print(json.dumps({'targets': len(plans), 'changed': sum(plan['changed'] for plan in plans), 'applied': args.apply}))


if __name__ == '__main__':
    main()
