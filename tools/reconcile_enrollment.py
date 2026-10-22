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
    if ref is None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'checkout'
            command(['git', 'clone', '-c', 'core.autocrlf=false', '--depth', '1', '--single-branch', '--branch', plan['branch'],
                     f'git@github.com:{repo}.git', str(root)])
            if command(['git', 'rev-parse', 'HEAD'], root) != plan['head']:
                raise ValueError('Target branch moved before checkout')
            for path in PATHS:
                target = enroll_consumers.declaration(root, path)
                current = target.read_bytes() if target.exists() else None
                if current != plan['originals'][path]:
                    raise ValueError('Checkout differs from immutable preflight')
                target.write_bytes(plan['replacements'][path])
            command(['git', 'add', '--', *PATHS], root)
            command(['git', 'diff', '--cached', '--check'], root)
            command(['git', 'commit', '-S', '-m', 'ci: enroll in the shared QQQ orb', '-m',
                     'Co-Authored-By: Codex <noreply@openai.com>'], root)
            head = command(['git', 'rev-parse', 'HEAD'], root)
            if api(f'repos/{repo}/branches/{plan["branch"]}')['commit']['sha'] != plan['head']:
                raise ValueError('Target branch moved before submission')
            command(['git', 'push', 'origin', f'HEAD:refs/heads/{branch}'], root)
    else:
        head = ref['object']['sha']
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
    parser.add_argument('--targets', type=Path, required=True)
    parser.add_argument('--orb-version', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+(?:\.\d+)?', args.orb_version):
        raise ValueError('A stable minor track or exact patch is required')
    targets = json.loads(args.targets.read_text(encoding='utf-8'))
    if not isinstance(targets, list) or not targets:
        raise ValueError('A nonempty target list is required')
    plans = [inspect(target, args.orb_version) for target in targets]
    if len({(p['repository'].lower(), p['branch']) for p in plans}) != len(plans):
        raise ValueError('Duplicate target')
    report = [{key: value for key, value in p.items() if key not in ('originals', 'replacements')} for p in plans]
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    if args.apply:
        for plan, row in zip(plans, report):
            row['result'] = apply(plan)
            args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'targets': len(plans), 'changed': sum(p['changed'] for p in plans), 'applied': args.apply}))


if __name__ == '__main__':
    main()
