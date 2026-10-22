#!/usr/bin/env python3
"""Plan remote enrollment and submit signed, repeatable PRs with --apply."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

import enroll_consumers
import native_gitops_gates as gitops
import native_specialist_gates as specialists
import yaml

PATHS = ('.circleci/config.yml', '.qqq-ci.yml')


def command(args, cwd=None):
    """Use existing credentials and signing configuration without interactive prompts."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True,
                            text=True, encoding='utf-8', timeout=120)
    if result.returncode:
        raise ValueError('Command failed: ' + args[0])
    return result.stdout.strip()


def api(path, missing=False):
    """Only an explicit 404 is treated as absence; other API failures stop work."""
    result = subprocess.run(['gh', 'api', path], capture_output=True,
                            text=True, encoding='utf-8', timeout=60)
    try:
        data = json.loads(result.stdout)
    except ValueError:
        raise ValueError('Invalid GitHub response') from None
    if result.returncode:
        if missing and str(data.get('status')) == '404':
            return None
        raise ValueError('GitHub read unavailable: ' + path.split('?')[0])
    return data


def content(repo, path, head):
    """Read a regular declaration at an immutable commit, never at a moving branch."""
    item = api(f'repos/{repo}/contents/{path}?ref={head}', missing=True)
    if item is None:
        return None
    if item.get('type') != 'file' or item.get('encoding') != 'base64':
        raise ValueError('Declaration is not a regular file')
    return base64.b64decode(item['content'])


def mutation(path, payload):
    """Use the existing gh identity; never print credentials or response bodies."""
    result = subprocess.run(['gh', 'api', path, '--method', 'POST', '--input', '-'],
                            input=json.dumps(payload), capture_output=True,
                            text=True, encoding='utf-8', timeout=60)
    if result.returncode:
        raise ValueError('GitHub mutation failed; inspect remote state before retrying')
    try:
        data = json.loads(result.stdout)
    except ValueError:
        raise ValueError('Invalid GitHub mutation response') from None
    if not isinstance(data, dict) or data.get('errors'):
        raise ValueError('GitHub mutation did not succeed')
    return data


def signed_api_commit(plan, ref):
    """Resume a base-only branch; append atomically without local Git/SSH keys."""
    repo, branch, base = plan['repository'], plan['automation_branch'], plan['head']
    if ref is None:
        mutation(f'repos/{repo}/git/refs', {'ref': 'refs/heads/' + branch, 'sha': base})
    elif ref['object']['sha'] != base:
        return ref['object']['sha']
    if api(f'repos/{repo}/branches/{plan["branch"]}')['commit']['sha'] != base:
        raise ValueError('Target branch moved before submission')
    additions = [{'path': path, 'contents': base64.b64encode(plan['replacements'][path]).decode('ascii')}
                 for path in PATHS if plan['originals'][path] != plan['replacements'][path]]
    result = mutation('graphql', {
        'query': 'mutation($input: CreateCommitOnBranchInput!) { createCommitOnBranch(input: $input) { commit { oid } } }',
        'variables': {'input': {
            'branch': {'repositoryNameWithOwner': repo, 'branchName': branch},
            'expectedHeadOid': base,
            'message': {'headline': 'ci: enroll in the shared QQQ orb',
                        'body': 'Co-Authored-By: Codex <noreply@openai.com>'},
            'fileChanges': {'additions': additions}}}})
    try:
        head = result['data']['createCommitOnBranch']['commit']['oid']
    except (KeyError, TypeError):
        raise ValueError('GitHub commit response is incomplete') from None
    if not isinstance(head, str) or not re.fullmatch(r'[0-9a-f]{40}', head):
        raise ValueError('GitHub commit response has no valid SHA')
    return head


def inspect(target, version):
    """Resolve observed repository identity and reuse the shared enrollment planner."""
    if not isinstance(target, dict) or set(target) != {'repository', 'branch'}:
        raise ValueError('Each target requires repository and branch')
    repo, branch = target['repository'], target['branch']
    if not isinstance(repo, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('Invalid repository')
    if branch not in ('main', 'develop'):
        raise ValueError('Enrollment targets current main/develop only')
    info = api('repos/' + repo)
    if info['archived']:
        raise ValueError('Archived repository')
    head = api(f'repos/{repo}/branches/{branch}')['commit']['sha']
    if repo in specialists.DEFINITIONS:
        profile, pins = specialists.validate(repo, head, branch, api)
        return {**target, 'head': head, 'profile': profile, 'version': version,
                'changed': False, 'worker_pins': pins}
    if repo in gitops.REPOSITORIES:
        pin = gitops.validate(repo, head, branch, api, yaml.safe_load)
        return {**target, 'head': head, 'profile': 'native-gitops', 'version': version,
                'changed': False, 'worker_pin': pin}
    originals = {path: content(repo, path, head) for path in PATHS}
    if originals[PATHS[0]] is None:
        raise ValueError('No recognized CircleCI entrypoint')
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / '.circleci').mkdir()
        for path, data in originals.items():
            if data is not None:
                (root / path).write_bytes(data)
        plan = enroll_consumers.plan({'checkout': str(root), 'default_branch': info['default_branch']}, version)
        replacements = {str(path.relative_to(root)).replace('\\', '/'): new for path, _, new in plan['files']}
    digest = hashlib.sha256(head.encode() + b''.join(replacements[path] for path in PATHS)).hexdigest()[:20]
    return {**target, 'head': head, 'originals': originals, 'replacements': replacements,
            'profile': plan['profile'], 'version': version,
            'changed': any(originals[path] != replacements[path] for path in PATHS),
            'automation_branch': f'automation/qqq-enroll-{branch}-{digest}'}


def verify_submission(plan, head):
    """Accept only a signed, one-parent commit with exactly the planned changes."""
    repo = plan['repository']
    commit = api(f'repos/{repo}/commits/{head}')
    expected = {path for path in PATHS if plan['originals'][path] != plan['replacements'][path]}
    if (not commit['commit']['verification']['verified']
            or [parent['sha'] for parent in commit['parents']] != [plan['head']]
            or {item['filename'] for item in commit['files']} != expected):
        raise ValueError('Existing automation branch differs from the signed plan')
    for path in PATHS:
        if content(repo, path, head) != plan['replacements'][path]:
            raise ValueError('Submitted declaration differs from plan')


def apply(plan):
    """Never force push; reuse matching submissions after interrupted executions."""
    if not plan['changed']:
        return {'state': 'unchanged'}
    repo, branch = plan['repository'], plan['automation_branch']
    if api(f'repos/{repo}/branches/{plan["branch"]}')['commit']['sha'] != plan['head']:
        raise ValueError('Target branch changed after preflight')
    ref = api(f'repos/{repo}/git/ref/heads/{branch}', missing=True)
    head = signed_api_commit(plan, ref)
    verify_submission(plan, head)
    pulls = api(f'repos/{repo}/pulls?state=all&head={repo.split("/")[0]}:{branch}&base={plan["branch"]}')
    if pulls:
        if len(pulls) != 1 or pulls[0]['head']['sha'] != head:
            raise ValueError('Ambiguous existing enrollment PR')
        return {'state': 'existing-pr', 'head': head, 'url': pulls[0]['html_url']}
    body = ('Uses the shared orb enrollment converter and preserves existing publication policy. '
            'Only the canonical caller and manifest change. Exact-head hosted checks must pass '
            'before merge; branch enforcement follows successful qualification.\n\n'
            'Source base: ' + plan['head'])
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'body.md'
        path.write_text(body, encoding='utf-8')
        url = command(['gh', 'pr', 'create', '--repo', repo, '--base', plan['branch'], '--head', branch,
                       '--title', 'ci: enroll in the shared QQQ orb', '--body-file', str(path)])
    return {'state': 'submitted', 'head': head, 'url': url}


def main():
    """Preflight every explicit target before mutations and save resumable results."""
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--targets', type=Path)
    source.add_argument('--organization')
    parser.add_argument('--orb-version', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--merge-ready', action='store_true')
    parser.add_argument('--enforce', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if (args.merge_ready or args.enforce) and not args.apply:
        parser.error('--merge-ready and --enforce require --apply')
    if not re.fullmatch(r'\d+\.\d+(?:\.\d+)?', args.orb_version):
        raise ValueError('A stable minor track or exact patch is required')
    findings = []
    if args.organization:
        from discover_enrollment import discover
        plans, findings = discover(args.organization, args.orb_version, inspect, api)
    else:
        targets = json.loads(args.targets.read_text(encoding='utf-8'))
        if not isinstance(targets, list) or not targets:
            raise ValueError('A nonempty target list is required')
        plans = [inspect(target, args.orb_version) for target in targets]
    if len({(p['repository'].lower(), p['branch']) for p in plans}) != len(plans):
        raise ValueError('Duplicate target')
    rows = [{key: value for key, value in p.items() if key not in ('originals', 'replacements')} for p in plans]
    report = findings + rows
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    if args.apply:
        for plan, row in zip(plans, rows):
            row['result'] = apply(plan)
            args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
            if args.merge_ready or args.enforce:
                import finish_enrollment
                if args.merge_ready:
                    row['qualification'] = finish_enrollment.merge_ready(plan, row['result'])
                    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
                if args.enforce:
                    row['enforcement'] = finish_enrollment.enforce_current(plan)
                    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'targets': len(plans), 'changed': sum(p['changed'] for p in plans),
                      'unresolved': sum(row['state'] == 'unresolved' for row in findings),
                      'applied': args.apply}))


if __name__ == '__main__':
    main()
