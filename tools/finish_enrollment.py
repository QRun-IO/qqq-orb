"""Qualify signed enrollment PRs and enforce only successful current branch heads."""
import json

import enforce_orb_checks as enforcement
import reconcile_enrollment as remote


def qualification(repo, head, profile='qbit'):
    """Require profile-specific app-bound gates and every advertised latest check/status."""
    checks, page = [], 1
    while True:
        batch = remote.api(f'repos/{repo}/commits/{head}/check-runs?filter=latest&per_page=100&page={page}')['check_runs']
        checks.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    reasons = []
    for gate in enforcement.gates(profile):
        name = gate['context']
        found = [check for check in checks if check['name'] == name and check['app']['id'] == gate['app_id']]
        if not found or max(found, key=lambda check: check['id'])['conclusion'] != 'success':
            reasons.append(name)
    for check in checks:
        if check['status'] != 'completed' or check['conclusion'] not in ('success', 'neutral', 'skipped'):
            reasons.append(check['name'])
    page = 1
    while True:
        batch = remote.api(f'repos/{repo}/commits/{head}/status?per_page=100&page={page}')['statuses']
        reasons.extend(status['context'] for status in batch if status['state'] != 'success')
        if len(batch) < 100:
            break
        page += 1
    return sorted(set(reasons))


def merge_ready(plan, result):
    """Normal exact-head squash merge only; no administrative or force bypass."""
    if plan['profile'] not in enforcement.PROFILES:
        return {'state': 'unsupported-gates', 'profile': plan['profile']}
    if result['state'] == 'unchanged':
        return {'state': 'unchanged'}
    repo, head = plan['repository'], result['head']
    remote.verify_submission(plan, head)
    pr = json.loads(remote.command(['gh', 'pr', 'view', result['url'], '--repo', repo,
        '--json', 'number,state,headRefOid,baseRefOid,baseRefName,mergeCommit']))
    if pr['headRefOid'] != head or pr['baseRefName'] != plan['branch']:
        raise ValueError('PR differs from enrollment target')
    if pr['state'] == 'CLOSED':
        return {'state': 'closed', 'url': result['url']}
    if pr['state'] != 'MERGED':
        if pr['baseRefOid'] != plan['head'] or remote.api(f'repos/{repo}/branches/{plan["branch"]}')['commit']['sha'] != plan['head']:
            return {'state': 'stale-base', 'url': result['url']}
        if plan['profile'] == 'native-gitops':
            enforcement.gitops.validate(repo, head, plan['branch'], remote.api, enforcement.standard.load_yaml)
        if plan['profile'] == 'frontend-next':
            enforcement.native.validate(repo, head, plan['branch'], remote.api, enforcement.standard.load_yaml)
        pending = qualification(repo, head, plan['profile'])
        if pending:
            return {'state': 'waiting-checks', 'checks': pending, 'url': result['url']}
        remote.command(['gh', 'pr', 'merge', str(pr['number']), '--repo', repo, '--squash', '--match-head-commit', head])
        pr = json.loads(remote.command(['gh', 'pr', 'view', result['url'], '--repo', repo,
                                                    '--json', 'state,mergeCommit']))
    if pr['state'] != 'MERGED':
        raise ValueError('PR merge was not confirmed')
    merged = pr['mergeCommit']['oid']
    expected = remote.api(f'repos/{repo}/commits/{head}')['commit']['tree']['sha']
    actual = remote.api(f'repos/{repo}/commits/{merged}')['commit']
    if not actual['verification']['verified'] or actual['tree']['sha'] != expected:
        raise ValueError('Merged signature or source tree differs from qualified source')
    return {'state': 'merged', 'url': result['url'], 'head': head, 'merge': merged}


def enforce_current(plan):
    """Use shared narrow enforcement after the actual branch head passes its gates."""
    if plan['profile'] not in enforcement.PROFILES:
        return {'state': 'unsupported-gates', 'profile': plan['profile']}
    try:
        current = enforcement.inspect(plan['repository'], plan['branch'], plan['version'])
    except ValueError as error:
        return {'state': 'waiting-enforcement', 'reason': str(error)}
    enforcement.enforce(current)
    return {'state': 'enforced', 'head': current['head'], 'changed': current['changed'],
            'protection_mode': current.get('protection_mode', 'classic')}
