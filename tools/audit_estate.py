#!/usr/bin/env python3
"""Read-only CI conformity inventory. Never changes repository files or GitHub settings.

Example: python tools/audit_estate.py --inventory inventory.json --orb-version 0.7.0
 --worker-sha <40hex> --policy observed-checks.json --live --output audit.json
Policy: {"profiles":{"qbit":{"required_checks":{"main":["observed context"],
"develop":["observed context"]}}},"repositories":{"QRun-IO/example":{...}}}.
Only use contexts verified on hosted canaries. Absent policy is unknown, not pass.
"""
import argparse
import base64
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'src/scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


standard = module('validate_standard')
generator = module('generate_pipeline')
qctl = module('generate_qctl_workflow')
next_worker = module('generate_next_workflow')
auxiliary = module('generate_auxiliary_workflow')
rc_worker = module('generate_rc_workflow')
PROFILES = {'qqq': 'core', 'qqq-frontend-material-dashboard': 'frontend-material',
            'qqq-frontend-core': 'frontend-core', 'qqq-cli': 'cli', 'Voyage': 'voyage',
            'qqq-frontend-next': 'frontend-next', 'qqq-all': 'all',
            'qqq-app-starter': 'app-starter', 'qctl': 'qctl',
            'qqq-app-developer-intellij-plugin': 'intellij-plugin',
            'qqq-android': 'android', 'qqq-mcp-rag-standard-policies': 'mcp-policy',
            'marketing-website': 'marketing', 'qqq-mcp-rag': 'native-mcp',
            'qqq-business-platform': 'native-business', '.github': 'native-workflow-lint',
            'qqq-orb': 'owner-bootstrap'}
NO_CI = json.loads((ROOT / 'tools/no-ci-policy.json').read_text(encoding='utf-8'))


class ReadError(RuntimeError):
    pass


def command(args):
    result = subprocess.run(args, capture_output=True, timeout=60)
    if result.returncode:
        # stderr may contain response bodies or configuration; never echo it.
        raise ReadError('read command failed: ' + args[0])
    return result.stdout.decode('utf-8')


def gh(path):
    return json.loads(command(['gh', 'api', '--method', 'GET', path]))


class Snapshot:
    def __init__(self, entry, live=False):
        self.repo = entry['nameWithOwner']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', self.repo):
            raise ReadError('invalid repository name')
        self.live = live
        self.path = entry.get('localPath', '')
        self.branch = (entry.get('defaultBranchRef') or {}).get('name')
        self.sha = entry.get('sha', '')
        if live:
            info = gh('repos/' + self.repo)
            self.branch = info['default_branch']
            if info['archived']:
                raise ReadError('repository is now archived; refresh inventory')
            self.sha = gh('repos/' + self.repo + '/commits/' + quote(self.branch, safe=''))['sha']
        if not re.fullmatch(r'[0-9a-f]{40}', self.sha):
            raise ReadError('missing immutable source SHA')
        if live:
            tree = gh('repos/' + self.repo + '/git/trees/' + self.sha + '?recursive=1')
            if tree.get('truncated'):
                raise ReadError('truncated repository tree')
            self.paths = {row['path'] for row in tree['tree'] if row['type'] == 'blob'}
        else:
            self.paths = set(command(['git', '-C', self.path, 'ls-tree', '-r', '--name-only', self.sha]).splitlines())

    def read(self, path):
        if path not in self.paths:
            return None
        if self.live:
            item = gh('repos/' + self.repo + '/contents/' + quote(path, safe='/') + '?ref=' + self.sha)
            if item.get('encoding') != 'base64':
                raise ReadError('unsupported content encoding')
            return base64.b64decode(item['content']).decode('utf-8')
        return command(['git', '-C', self.path, 'show', self.sha + ':' + path])

    def checks(self, branch):
        if not self.live:
            raise ReadError('required checks need --live')
        prefix = 'repos/' + self.repo + '/branches/' + quote(branch, safe='')
        branch_info = gh(prefix)
        rules = gh('repos/' + self.repo + '/rules/branches/' + quote(branch, safe=''))
        contexts = {check['context'] for rule in rules if rule['type'] == 'required_status_checks'
                    for check in rule['parameters']['required_status_checks']}
        # The branch response includes classic required contexts. A protection_url can
        # exist without classic protection, so following it would turn a legitimate
        # 404 into an unknown result for ruleset-only repositories.
        classic = (branch_info.get('protection') or {}).get('required_status_checks') or {}
        contexts.update(classic.get('contexts', []))
        contexts.update(check['context'] for check in classic.get('checks', []))
        return sorted(contexts)


def owner_gate_errors(snapshot):
    """Check the owner's two-stage lint/test/publication graph, not a self-consuming manifest."""
    try:
        setup = standard.load_yaml(snapshot.read('.circleci/config.yml') or '')
        deploy = standard.load_yaml(snapshot.read('.circleci/test-deploy.yml') or '')
        if not isinstance(setup, dict) or not isinstance(deploy, dict):
            return ['missing owner setup or test-deploy mapping']
        def invocations(config, workflow):
            result = {}
            for item in config['workflows'][workflow]['jobs']:
                if isinstance(item, str):
                    result[item] = {}
                else:
                    name, options = next(iter(item.items()))
                    result[name] = options or {}
            return result
        errors = []
        lint = invocations(setup, 'lint-pack')
        gates = {'orb-tools/lint', 'orb-tools/pack', 'orb-tools/review', 'shellcheck/check'}
        if setup.get('setup') is not True or not gates.issubset(lint):
            errors.append('lint/pack/review/shellcheck setup gates')
        if not gates.issubset(set(lint.get('orb-tools/continue', {}).get('requires', []))):
            errors.append('continuation must depend on every lint/pack/review/shellcheck gate')
        tests = invocations(deploy, 'test-deploy')
        required = {'command-test', 'pipeline-contract-test'}
        for test in required:
            definition = deploy.get('jobs', {}).get(test, {})
            if test not in tests or not definition.get('steps') or not any(isinstance(step, dict) and 'run' in step for step in definition['steps']):
                errors.append('executable test gate ' + test)
        for name, branch in [('publish-dev-snapshot', 'develop'), ('publish-production', 'main')]:
            invocation = tests.get(name, {})
            if not required.issubset(set(invocation.get('requires', []))):
                errors.append(name + ' must require both test gates')
            if invocation.get('filters', {}).get('branches', {}).get('only') != [branch]:
                errors.append(name + ' branch filter')
            commands = []
            for step in deploy.get('jobs', {}).get(name, {}).get('steps', []):
                if isinstance(step, dict) and 'run' in step:
                    run = step['run']
                    commands.append(run if isinstance(run, str) else run.get('command', ''))
            command = '\n'.join(commands)
            for operation in ('circleci orb pack ', 'circleci orb validate ', 'circleci orb publish '):
                if operation not in command:
                    errors.append(name + ' missing ' + operation.strip())
        return errors
    except (ValueError, TypeError, KeyError, AttributeError):
        return ['invalid owner bootstrap configuration']


def audit(entry, snapshot, version, worker_sha, policy):
    name = entry['name']
    profile = policy.get('profile') or ('qbit' if name.startswith('qbit-') else PROFILES.get(name))
    result = {'repository': entry['nameWithOwner'], 'sha': snapshot.sha,
              'default_branch': snapshot.branch, 'profile': profile, 'findings': [], 'required_checks': {}}
    findings = result['findings']
    def finding(code, path=None, detail=None):
        findings.append({k: v for k, v in {'code': code, 'path': path, 'detail': detail}.items() if v is not None})
    native = profile in ('qctl', 'frontend-next')
    rc_enabled = policy.get('rc_release') is True
    if profile in standard.PROFILE_PARAMETERS:
        raw = snapshot.read('.qqq-ci.yml')
        caller = snapshot.read('.circleci/config.yml')
        if raw is None:
            finding('missing_manifest', '.qqq-ci.yml')
        if caller is None:
            finding('missing_canonical_caller', '.circleci/config.yml')
        if raw is not None:
            try:
                data = standard.load_yaml(raw)
                if not isinstance(data, dict):
                    raise standard.StandardError('Manifest must be a mapping')
                if data.get('profile') != profile:
                    finding('profile_mismatch', '.qqq-ci.yml')
                rc_enabled = rc_enabled or data.get('release_completion') is True
                pin = data.get('orb_version')
                result['orb_version'] = pin
                if pin != version:
                    finding('orb_pin_drift', '.qqq-ci.yml', {'expected': version, 'actual': pin})
                with tempfile.TemporaryDirectory() as directory:
                    manifest = Path(directory) / 'manifest.yml'
                    manifest.write_text(raw, encoding='utf-8')
                    generator.load_manifest(manifest, pin)
                if data.get('default_branch') != snapshot.branch:
                    finding('default_branch_drift', '.qqq-ci.yml')
                if caller is not None:
                    standard.validate(caller, raw, pin)
            except (ValueError, TypeError):
                finding('invalid_manifest_or_caller', '.circleci/config.yml')
    workflows = sorted(path for path in snapshot.paths if path.startswith('.github/workflows/') and path.endswith(('.yml', '.yaml')))
    native_paths = set()
    rc_source = snapshot.read(rc_worker.CALLER_PATH)
    existing_rc = rc_source is not None and 'qbit-release-rc.yml@' in rc_source
    if profile == 'qbit' and (rc_enabled or existing_rc):
        path = rc_worker.CALLER_PATH
        raw = rc_source
        if raw is None:
            finding('missing_rc_bridge', path)
        elif not re.fullmatch(r'[0-9a-f]{40}', worker_sha or ''):
            finding('native_pin_policy_missing', path)
        elif raw != rc_worker.generate(worker_sha):
            finding('rc_bridge_drift', path)
        else:
            native_paths.add(path)
        for other in workflows:
            if other != path and 'qbit-release-rc.yml@' in snapshot.read(other):
                finding('duplicate_rc_bridge', other)
    for kind, definition in auxiliary.BRIDGES.items():
        if definition['repository'] != entry['nameWithOwner']:
            continue
        path = definition['path']
        raw = snapshot.read(path)
        if raw is None:
            finding('missing_native_maintenance_bridge', path)
            continue
        if not re.fullmatch(r'[0-9a-f]{40}', worker_sha or ''):
            finding('native_pin_policy_missing', path)
            continue
        expected = generator.yaml.safe_dump(auxiliary.canonical(kind, worker_sha), sort_keys=False)
        if raw != expected:
            finding('native_maintenance_bridge_drift', path)
        else:
            native_paths.add(path)
    if native:
        if not re.fullmatch(r'[0-9a-f]{40}', worker_sha or ''):
            finding('native_pin_policy_missing')
        else:
            expected = (qctl.generate(worker_sha) if profile == 'qctl' else next_worker.canonical_next(worker_sha))
            primary_native_paths = set()
            for path in workflows:
                if path in native_paths:
                    continue
                raw = snapshot.read(path)
                if 'QRun-IO/qqq-orb/.github/workflows/' not in raw:
                    continue
                native_paths.add(path)
                primary_native_paths.add(path)
                try:
                    actual = raw if profile == 'qctl' else generator.yaml.safe_load(raw)
                    target = expected
                    if not standard.exact(actual, target):
                        finding('native_bridge_drift', path)
                except (ValueError, generator.yaml.YAMLError):
                    finding('invalid_native_bridge', path)
            if len(primary_native_paths) != 1:
                finding('native_bridge_missing_or_duplicate', detail={'candidates': sorted(primary_native_paths)})
    no_ci = NO_CI.get(entry['nameWithOwner'])
    if no_ci is not None:
        result['classification'] = 'approved-no-ci'
        result['no_ci_policy'] = no_ci
        for path in no_ci['required_paths']:
            if path not in snapshot.paths:
                finding('no_ci_identity_path_missing', path)
        for path in sorted(snapshot.paths):
            if path in no_ci['forbidden_paths'] or any(path.startswith(prefix) for prefix in no_ci['forbidden_prefixes']):
                finding('no_ci_configuration_drift', path)
    elif not profile:
        finding('profile_not_assigned')
    elif profile == 'owner-bootstrap':
        result['classification'] = 'owner-bootstrap'
        for detail in owner_gate_errors(snapshot):
            finding('owner_bootstrap_gate_missing', detail=detail)
    elif profile.startswith('native-'):
        result['classification'] = 'approved-native-bridges'
        if snapshot.read('.circleci/config.yml') is not None:
            finding('legacy_circle_pipeline', '.circleci/config.yml', 'Retire only after hosted equivalent native checks pass')
        for path in workflows:
            if path not in native_paths:
                finding('unapproved_native_workflow', path)

    for path in workflows:
        if path in native_paths or profile == 'owner-bootstrap':
            continue
        raw = snapshot.read(path)
        # Candidate detection only: security/release maintenance workflows are not automatically removed.
        if re.search(r'(?m)\b(?:mvnw?|npm|pnpm|yarn|gradlew?|cargo)\s+(?:clean|verify|test|build|run|package)\b', raw):
            finding('possible_duplicate_legacy_build', path)
    branches = policy.get('required_checks', {})
    managed = policy.get('managed_branches', ['main', 'develop'])
    if (not isinstance(managed, list) or not managed
            or any(branch not in ('main', 'develop') for branch in managed)
            or len(set(managed)) != len(managed)):
        raise ReadError('managed_branches must be a nonempty unique main/develop list')
    result['managed_branches'] = managed
    for branch in managed:
        if branch not in branches:
            result['required_checks'][branch] = {'state': 'unknown', 'reason': 'observed context policy missing'}
            continue
        expected = branches[branch]
        if (not isinstance(expected, list) or not all(isinstance(x, str) and x for x in expected)
                or (not expected and no_ci is None)):
            raise ReadError('required check policy must contain nonempty observed contexts except approved no-CI repositories')
        try:
            actual = snapshot.checks(branch)
            missing = sorted(set(expected) - set(actual))
            stale = sorted(actual) if no_ci is not None and not expected else []
            state = 'stale' if stale else 'missing' if missing else 'pass'
            result['required_checks'][branch] = {'state': state, 'actual': actual, 'expected': expected, 'missing': missing}
            if stale:
                finding('stale_required_merge_check', detail={'branch': branch, 'contexts': stale})
            if missing:
                finding('missing_required_merge_check', detail={'branch': branch, 'contexts': missing})
        except ReadError:
            result['required_checks'][branch] = {'state': 'unknown', 'reason': 'branch settings unavailable or offline'}
    result['status'] = 'findings' if findings else ('unknown' if any(v['state'] == 'unknown' for v in result['required_checks'].values()) else 'pass')
    return result


def run(entries, version, worker_sha, policies, live=False, snapshot_factory=Snapshot):
    results = []
    for entry in entries:
        if entry.get('isArchived'):
            results.append({'repository': entry['nameWithOwner'], 'status': 'archived_skip'})
            continue
        name = entry['name']
        profile = 'qbit' if name.startswith('qbit-') else PROFILES.get(name)
        policy = dict(policies.get('profiles', {}).get(profile, {}))
        policy.update(policies.get('repositories', {}).get(entry['nameWithOwner'], {}))
        try:
            results.append(audit(entry, snapshot_factory(entry, live), version, worker_sha, policy))
        except (ReadError, OSError, ValueError, KeyError, subprocess.TimeoutExpired):
            results.append({'repository': entry['nameWithOwner'], 'status': 'unknown', 'reason': 'source/API/policy read failed'})
    return {'inventory_count': len(entries), 'active_count': sum(not e.get('isArchived', False) for e in entries),
            'covered_count': len(results), 'unique_repository_count': len({e['nameWithOwner'] for e in entries}),
            'live': live, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--orb-version', required=True)
    parser.add_argument('--worker-sha')
    parser.add_argument('--policy', type=Path)
    parser.add_argument('--live', action='store_true', help='Read current source and branch rules using existing gh authentication')
    parser.add_argument('--expected-active', type=int, default=68)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    entries = json.loads(args.inventory.read_text(encoding='utf-8'))
    policies = json.loads(args.policy.read_text(encoding='utf-8')) if args.policy else {}
    report = run(entries, args.orb_version, args.worker_sha, policies, args.live)
    report['expected_active_count'] = args.expected_active
    report['coverage_matches_expected'] = (report['active_count'] == args.expected_active
                                           and report['unique_repository_count'] == report['inventory_count'])
    text = json.dumps(report, indent=2) + '\n'
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    else:
        print(text, end='')
    return 0 if report['coverage_matches_expected'] and all(r['status'] in ('pass', 'archived_skip') for r in report['results']) else 1


if __name__ == '__main__':
    sys.exit(main())
