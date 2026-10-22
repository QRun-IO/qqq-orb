"""Manage native cost controls only for profiles with reviewed cancellation semantics."""
import json
import os
import re
from urllib.error import URLError
from urllib.request import Request, urlopen


AUTOCANCEL_PROFILES = {'repository-policy', 'homebrew-tap', 'application-template', 'marketing'}


def request(repository, payload=None):
    """Use existing central credentials; never expose authentication or error bodies."""
    if not re.fullmatch(r'QRun-IO/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Only QRun-IO projects can be managed')
    token = os.environ.get('CIRCLE_TOKEN')
    if not token:
        raise ValueError('Central CircleCI credential unavailable')
    headers = {'Circle-Token': token, 'Accept': 'application/json'}
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    operation = Request('https://circleci.com/api/v1.1/project/github/' + repository + '/settings',
                        headers=headers, method='GET' if payload is None else 'PUT',
                        data=None if payload is None else json.dumps(payload).encode())
    try:
        with urlopen(operation, timeout=30) as response:
            return json.load(response)
    except (URLError, ValueError):
        raise ValueError('CircleCI project settings unavailable') from None


def reconcile(plan, source_request, apply=False, settings_request=request):
    """Require a current canonical source and preserve every unrelated project flag."""
    if plan['profile'] not in AUTOCANCEL_PROFILES:
        return {'state': 'not-managed', 'reason': 'Profile cancellation policy not reviewed'}
    if plan['changed']:
        return {'state': 'waiting-source', 'reason': 'Canonical enrollment must land first'}
    repo = plan['repository']
    try:
        info = source_request(f'repos/{repo}')
        if info['archived'] or (plan['profile'] == 'marketing' and info['default_branch'] != 'main'):
            raise ValueError('Repository default branch or archive state differs from policy')
        before = settings_request(repo)['feature_flags']
        if not isinstance(before, dict) or type(before.get('autocancel-builds')) is not bool:
            raise ValueError('CircleCI cancellation flag is missing or invalid')
        changed = not before['autocancel-builds']
        if apply and changed:
            if source_request(f'repos/{repo}/branches/{plan["branch"]}')['commit']['sha'] != plan['head']:
                raise ValueError('Source changed after enrollment inspection')
            settings_request(repo, {'feature_flags': {'autocancel-builds': True}})
            after = settings_request(repo)['feature_flags']
            if after != {**before, 'autocancel-builds': True}:
                raise ValueError('CircleCI settings readback differs from the narrow update')
        return {'state': 'enforced' if apply else 'inspected', 'changed': changed}
    except (ValueError, KeyError, TypeError) as error:
        return {'state': 'unresolved', 'reason': str(error)}


def reconcile_repository(plans, findings, source_request, apply=False, settings_request=request):
    """A project-wide flag requires agreement across all discovered current branches."""
    repo = plans[0]['repository']
    if any(plan['repository'] != repo for plan in plans):
        raise ValueError('Expected one repository')
    if any(row['repository'] == repo and row.get('state') == 'unresolved' for row in findings):
        return {'state': 'waiting-source', 'reason': 'A current branch is unresolved'}
    if any(plan['profile'] not in AUTOCANCEL_PROFILES for plan in plans):
        return {'state': 'not-managed', 'reason': 'A current branch has an unreviewed cancellation policy'}
    if any(plan['changed'] for plan in plans):
        return {'state': 'waiting-source', 'reason': 'All current branches must have canonical enrollment'}
    try:
        for plan in plans:
            if source_request(f'repos/{repo}/branches/{plan["branch"]}')['commit']['sha'] != plan['head']:
                raise ValueError('Source changed after enrollment inspection')
    except (ValueError, KeyError, TypeError) as error:
        return {'state': 'unresolved', 'reason': str(error)}
    # Preserve the marketing default-branch guard even in mixed eligible profiles.
    plan = next((p for p in plans if p['profile'] == 'marketing'), plans[0])
    return reconcile(plan, source_request, apply, settings_request)
