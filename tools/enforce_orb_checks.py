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
PROFILE_GATES = {profile: 'verify' for profile in (
    'qbit', 'core', 'frontend-core', 'frontend-material', 'repository-policy', 'node-artifact', 'homebrew-tap', 'application-template', 'marketing', 'voyage')}
PROFILE_GATES.update({'all': 'verify-and-smoke', 'cli': 'test_only',
                      'app-starter': 'test_only', 'android': 'test-and-build',
                      'mcp-policy': 'validate'})
PROFILES = set(PROFILE_GATES) | {'frontend-next', 'native-gitops'}
_native_spec = importlib.util.spec_from_file_location('native_next_gates', ROOT / 'tools/native_next_gates.py')
native = importlib.util.module_from_spec(_native_spec)
_native_spec.loader.exec_module(native)
_gitops_spec = importlib.util.spec_from_file_location('native_gitops_gates', ROOT / 'tools/native_gitops_gates.py')
gitops = importlib.util.module_from_spec(_gitops_spec)
_gitops_spec.loader.exec_module(gitops)

_specialist_spec = importlib.util.spec_from_file_location('native_specialist_gates', ROOT / 'tools/native_specialist_gates.py')
specialists = importlib.util.module_from_spec(_specialist_spec)
_specialist_spec.loader.exec_module(specialists)
PROFILES |= specialists.PROFILES


def gates(profile):
    if profile in specialists.PROFILES:
        return specialists.gates(profile)
    if profile == 'native-gitops':
        return gitops.gates()
    if profile == 'frontend-next':
        return native.gates(pull_request=True)
    return [{'context': name, 'app_id': 18001}
            for name in ('setup', PROFILE_GATES[profile])]


def same_checks(left, right):
    """GitHub may reorder checks; retain exact bindings and duplicate counts."""
    return sorted(json.dumps(check, sort_keys=True) for check in left) == sorted(
        json.dumps(check, sort_keys=True) for check in right)


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


def required_checks(before, runs, desired_gates=DESIRED, observed_gates=None):
    """Require successful event-appropriate gates and preserve every PR requirement."""
    for desired in (desired_gates if observed_gates is None else observed_gates):
        matches = [run for run in runs if run['name'] == desired['context'] and run['app']['id'] == desired['app_id']]
        if not matches or max(matches, key=lambda run: run['id'])['conclusion'] != 'success':
            raise ValueError('Current branch head has no successful app-bound gate: ' + desired['context'])
    prior = (before or {}).get('required_status_checks') or {}
    checks = [dict(check) for check in prior.get('checks', [])]
    represented = {check['context'] for check in checks}
    checks += [{'context': name, 'app_id': -1} for name in prior.get('contexts', []) if name not in represented]
    for desired in desired_gates:
        matches = [check for check in checks if check['context'] == desired['context']]
        if any(check.get('app_id') not in (None, -1, desired['app_id']) for check in matches):
            raise ValueError('Existing gate uses a different app: ' + desired['context'])
        checks = [check for check in checks if check['context'] != desired['context']]
        checks.append(dict(desired))
    return {'strict': True, 'checks': checks}


def verified_rulesets(repo, effective, request=api, desired_gates=DESIRED):
    """Recognize active repository rulesets with bound gates and no bypass actors."""
    selected = [rule for rule in effective if rule['type'] == 'required_status_checks']
    if not selected or any(rule.get('ruleset_source_type') != 'Repository'
                           or rule.get('ruleset_source') != repo for rule in selected):
        raise ValueError('Required rulesets need unsupported source reconciliation')
    records = []
    for identifier in sorted({rule['ruleset_id'] for rule in selected}):
        record = request(f'repos/{repo}/rulesets/{identifier}')
        if (record.get('enforcement') != 'active' or record.get('target') != 'branch'
                or record.get('source_type') != 'Repository' or record.get('source') != repo
                or record.get('bypass_actors') != []):
            raise ValueError('Ruleset must be active with no bypass actors')
        records.append(record)
    requirements = [rule['parameters'] for record in records for rule in record['rules']
                    if rule['type'] == 'required_status_checks']
    for desired in desired_gates:
        if not any(check['context'] == desired['context'] and check.get('integration_id') == desired['app_id']
                   for parameters in requirements for check in parameters['required_status_checks']):
            raise ValueError('Ruleset is missing app-bound gate: ' + desired['context'])
    # Retain the existing freshness policy: recognition does not add rebuilds or
    # weaken any existing scanner, merge, or bypass requirement.
    return records, any(parameters.get('strict_required_status_checks_policy', False) for parameters in requirements)


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
    if repo in specialists.DEFINITIONS:
        profile, _ = specialists.validate(repo, head, branch, request)
    elif repo in gitops.REPOSITORIES:
        gitops.validate(repo, head, branch, request, standard.load_yaml)
        profile = 'native-gitops'
    else:
        source = []
        for path in ('.circleci/config.yml', '.qqq-ci.yml'):
            item = request(root + '/contents/' + quote(path, safe='/') + '?ref=' + head)
            if item.get('encoding') != 'base64' or item.get('type') != 'file':
                raise ValueError('Canonical declarations must be regular files')
            source.append(base64.b64decode(item['content'], validate=False).decode('utf-8'))
        standard.validate(*source, version)
        profile = standard.load_yaml(source[1])['profile']
    if profile not in PROFILES:
        raise ValueError('Profile has no supported shared branch gates')
    desired_gates = gates(profile)
    observed_gates = desired_gates
    if profile == 'frontend-next':
        native.validate(repo, head, branch, request, standard.load_yaml)
        observed_gates = native.gates()
    rules = request(root + '/rules/branches/' + branch)
    rulesets, ruleset_strict = verified_rulesets(repo, rules, request, desired_gates) if rules else ([], False)
    before = request(prefix + '/protection')
    restrictions = (before or {}).get('restrictions')
    missing_status_section = before is not None and before.get('required_status_checks') is None
    empty_push_allowlist = (restrictions is not None
            and not any(restrictions.get(kind) for kind in ('users', 'teams', 'apps'))
            and not (before or {}).get('enforce_admins', {}).get('enabled'))
    # GitHub cannot PATCH a missing status-check subresource. An additive ruleset
    # preserves the existing signing, review, history and access policies.
    use_ruleset = not rulesets and (missing_status_section or empty_push_allowlist)
    runs = []
    page = 1
    while True:
        batch = request(root + '/commits/' + head + '/check-runs?filter=latest&per_page=100&page=' + str(page))['check_runs']
        runs += batch
        if len(batch) < 100:
            break
        page += 1
    desired = required_checks(before, runs, desired_gates, observed_gates)
    if use_ruleset:
        return {'repository': repo, 'branch': branch, 'head': head, 'before': before, 'gates': desired_gates,
                'required_status_checks': {'strict': False, 'checks': desired_gates},
                'changed': True, 'protection_mode': 'create-ruleset'}
    if rulesets:
        desired['strict'] = ruleset_strict or bool(((before or {}).get('required_status_checks') or {}).get('strict'))
        return {'repository': repo, 'branch': branch, 'head': head, 'before': before, 'gates': desired_gates,
                'required_status_checks': desired, 'changed': False, 'protection_mode': 'rulesets',
                'effective_rules': rules, 'rulesets': rulesets}
    current = (before or {}).get('required_status_checks') or {}
    ready = (current.get('strict') is True and same_checks(current.get('checks', []), desired['checks'])
             and (before or {}).get('enforce_admins', {}).get('enabled') is True)
    return {'repository': repo, 'branch': branch, 'head': head, 'before': before, 'gates': desired_gates,
            'required_status_checks': desired, 'changed': not ready}


def enforce(plan, request=api):
    """Recheck drift, use narrow updates, and verify preservation of other settings."""
    desired_gates = plan.get('gates', DESIRED)
    root = 'repos/' + plan['repository']
    prefix = root + '/branches/' + plan['branch']
    if request(prefix)['commit']['sha'] != plan['head'] or request(prefix + '/protection') != plan['before']:
        raise ValueError('Branch or protection changed after preflight')
    rules = request(root + '/rules/branches/' + plan['branch'])
    if plan.get('protection_mode') == 'rulesets':
        if rules != plan['effective_rules'] or verified_rulesets(plan['repository'], rules, request, desired_gates)[0] != plan['rulesets']:
            raise ValueError('Ruleset changed after preflight')
        return
    if rules:
        raise ValueError('Ruleset changed after preflight')
    if plan.get('protection_mode') == 'create-ruleset':
        name = 'QQQ automated verification: ' + plan['branch']
        page = 1
        while True:
            existing = request(root + '/rulesets?per_page=100&page=' + str(page))
            if any(record['name'] == name for record in existing):
                raise ValueError('Named ruleset already exists; reconcile its scope explicitly')
            if len(existing) < 100:
                break
            page += 1
        request(root + '/rulesets', 'POST', {
            'name': name, 'target': 'branch', 'enforcement': 'active', 'bypass_actors': [],
            'conditions': {'ref_name': {'include': ['refs/heads/' + plan['branch']], 'exclude': []}},
            'rules': [{'type': 'required_status_checks', 'parameters': {
                'strict_required_status_checks_policy': False, 'do_not_enforce_on_create': False,
                'required_status_checks': [{'context': gate['context'], 'integration_id': gate['app_id']}
                                           for gate in desired_gates]}}]})
        effective = request(root + '/rules/branches/' + plan['branch'])
        verified_rulesets(plan['repository'], effective, request, desired_gates)
        if request(prefix + '/protection') != plan['before']:
            raise ValueError('Classic access policy changed during ruleset creation')
        return
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
    if not actual['strict'] or not same_checks(actual['checks'], plan['required_status_checks']['checks']) or not after['enforce_admins']['enabled']:
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
