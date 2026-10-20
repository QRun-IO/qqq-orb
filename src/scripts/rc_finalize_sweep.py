"""Bounded RC reconciliation. Dispatch only; tagging remains in the trusted reusable workflow."""
import datetime
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from email.utils import parsedate_to_datetime

SHA = re.compile(r'[0-9a-f]{40}')
BRANCH = re.compile(r'release/\d+\.\d+(?:\.\d+)?')
VERSION = re.compile(r'Bump version to (\d+\.\d+\.\d+-RC\.\d+) \[skip ci\]')
LOCK = 'automation/qbit-rc-pending'


class InvalidIntent(ValueError):
    pass


class NoAuthRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if not newurl.startswith('https://'):
            raise InvalidIntent('Non-HTTPS artifact redirect')
        redirected = super().redirect_request(request, fp, code, msg, headers, newurl)
        redirected.remove_header('Authorization')
        return redirected


class API:
    def __init__(self, token):
        self.token = token
        self.deadline = time.monotonic() + 480
        self.calls = 0
        self.opener = urllib.request.build_opener(NoAuthRedirect())

    def request(self, path, payload=None, raw=False):
        self.calls += 1
        if self.calls > 500 or time.monotonic() >= self.deadline:
            raise InvalidIntent('Sweep API/time budget exhausted')
        req = urllib.request.Request('https://api.github.com/' + path,
            headers={'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json',
                     'X-GitHub-Api-Version': '2022-11-28'},
            data=None if payload is None else json.dumps(payload).encode())
        try:
            with self.opener.open(req, timeout=20) as response:
                body = response.read(2_000_001)
                if len(body) > 2_000_000:
                    raise InvalidIntent('Oversized API response')
                return body if raw else (json.loads(body) if body else None)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise InvalidIntent('GitHub HTTP ' + str(error.code)) from None

    def central(self, artifact, version):
        if time.monotonic() >= self.deadline:
            raise InvalidIntent('Sweep time budget exhausted')
        url = f'https://repo1.maven.org/maven2/com/kingsrook/qbits/{artifact}/{version}/{artifact}-{version}.pom'
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                return response.read(1_000_000), response.headers.get('Last-Modified')
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise InvalidIntent('Central HTTP ' + str(error.code)) from None


def validate_run(run, intent, repo, merge, run_id):
    if not run or run.get('status') != 'completed' or run.get('conclusion') != 'success':
        raise InvalidIntent('Cut run not successfully completed')
    if run.get('path') != '.github/workflows/release-rc.yml' or run.get('event') not in ('workflow_dispatch', 'pull_request'):
        raise InvalidIntent('Untrusted cut workflow/event')
    if any(run.get(key, {}).get('full_name') != repo for key in ('repository', 'head_repository')):
        raise InvalidIntent('Wrong cut repository')
    if str(run.get('id')) != str(run_id) or str(run.get('run_attempt')) != intent.get('attempt'):
        raise InvalidIntent('Wrong cut run/attempt')
    if (intent.get('repo'), intent.get('merge_sha'), intent.get('run_id')) != (repo, merge, str(run_id)):
        raise InvalidIntent('Intent/source mismatch')
    if not BRANCH.fullmatch(intent.get('branch', '')):
        raise InvalidIntent('Invalid release branch')


def reconcile(api, repo):
    prefix = 'repos/' + repo + '/'
    lock = api.request(prefix + 'git/ref/heads/' + LOCK)
    if lock is None:
        return 'idle'
    merge = lock['object']['sha']
    if not SHA.fullmatch(merge):
        raise InvalidIntent('Invalid lock source')
    name = 'qbit-rc-intent-' + merge
    result = api.request(prefix + 'actions/artifacts?name=' + name + '&per_page=100')
    artifacts = [a for a in result['artifacts'] if a['name'] == name and not a['expired']]
    if not result['artifacts']:
        return 'intent-pending'
    if len(artifacts) != 1:
        raise InvalidIntent('Pending lock lacks unique unexpired cut intent; inspect cut run')
    artifact = artifacts[0]
    run_id = artifact['workflow_run']['id']
    run = api.request(prefix + 'actions/runs/' + str(run_id))
    # A callback/sweep can race the short upload-and-exit window. Leave the lock untouched.
    if run and run.get('status') != 'completed':
        return 'cut-running'
    archive = api.request(prefix + 'actions/artifacts/' + str(artifact['id']) + '/zip', raw=True)
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        info = zipped.getinfo('rc-intent.json')
        if info.file_size > 10000:
            raise InvalidIntent('Oversized intent')
        intent = json.loads(zipped.read(info))
    validate_run(run, intent, repo, merge, run_id)
    checks = api.request(prefix + 'commits/' + merge + '/check-runs?filter=latest&per_page=100')
    publishers = [c for c in checks.get('check_runs', [])
                  if c.get('name') == 'publish_release_candidate' and c.get('app', {}).get('id') == 18001]
    if not publishers:
        return 'publisher-running'
    publisher = max(publishers, key=lambda c: c['id'])
    if publisher.get('head_sha') != merge:
        raise InvalidIntent('Wrong Circle publisher source')
    if publisher.get('status') != 'completed':
        return 'publisher-running'
    if publisher.get('conclusion') != 'success':
        raise InvalidIntent('Upstream CircleCI terminal failure on exact release merge')
    branch = intent['branch']
    commit = api.request(prefix + 'commits/' + urllib.parse.quote(branch, safe=''))
    match = VERSION.fullmatch(commit['commit']['message'].split('\n')[0])
    if not match or [p['sha'] for p in commit['parents']] != [merge]:
        raise InvalidIntent('Bump is not the exact published merge child')
    version = match.group(1)
    if not SHA.fullmatch(commit['sha']):
        raise InvalidIntent('Invalid bump SHA')
    # Resolve coordinates from original source, never from dispatch data.
    contents = api.request(prefix + 'contents/pom.xml?ref=' + merge)
    import base64
    pom = ET.fromstring(base64.b64decode(contents['content']))
    ns = {'m': 'http://maven.apache.org/POM/4.0.0'}
    artifact_name = pom.findtext('m:artifactId', namespaces=ns)
    if not artifact_name or not re.fullmatch(r'qbit-[a-z0-9-]+', artifact_name):
        raise InvalidIntent('Invalid artifact coordinate')
    central = api.central(artifact_name, version)
    if central is None:
        return 'central-pending'
    xml, modified = central
    published = ET.fromstring(xml)
    if (published.findtext('m:artifactId', namespaces=ns), published.findtext('m:version', namespaces=ns)) != (artifact_name, version):
        raise InvalidIntent('Central artifact/version mismatch')
    if not modified or parsedate_to_datetime(modified).timestamp() <= datetime.datetime.fromisoformat(intent['merged_at'].replace('Z', '+00:00')).timestamp():
        raise InvalidIntent('Central provenance predates cut')
    # Re-read ownership immediately before dispatch; finalizer checks it again under concurrency.
    current = api.request(prefix + 'git/ref/heads/' + LOCK)
    if not current or current['object']['sha'] != merge:
        raise InvalidIntent('Pending lock changed')
    api.request(prefix + 'dispatches', {'event_type': 'qbit-rc-published', 'client_payload': {
        'merge_sha': merge, 'bump_sha': commit['sha'], 'branch': branch, 'version': version}})
    return 'dispatched'


def main():
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        raise InvalidIntent('Existing GH_TOKEN/GITHUB_TOKEN required; no cross-repo fallback token')
    repos = json.loads(os.environ['RC_REPOSITORIES_JSON'])
    if not isinstance(repos, list) or not 1 <= len(repos) <= 64 or len(set(repos)) != len(repos):
        raise InvalidIntent('Explicit unique allowlist of 1..64 repositories required')
    if any(not isinstance(repo, str) or not re.fullmatch(r'QRun-IO/qbit-[a-z0-9-]+', repo) for repo in repos):
        raise InvalidIntent('Invalid allowlisted repository')
    api = API(token)
    failures = []
    for repo in repos:
        try:
            print(repo + ': ' + reconcile(api, repo))
        except Exception as error:
            # No HTTP bodies, URLs, credentials or artifact content in logs.
            reason = str(error) if isinstance(error, InvalidIntent) else type(error).__name__
            print(repo + ': ERROR ' + reason, file=sys.stderr)
            failures.append(repo)
        if time.monotonic() >= api.deadline or api.calls >= 500:
            raise InvalidIntent('Sweep bounded budget exhausted; remaining repos await next scheduled run')
    if failures:
        raise InvalidIntent('Sweep failures: ' + ', '.join(failures))


if __name__ == '__main__':
    try:
        main()
    except InvalidIntent as error:
        sys.exit(str(error))
