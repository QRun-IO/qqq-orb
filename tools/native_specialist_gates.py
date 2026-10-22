"""Recognize reviewed native consumers and their shared immutable orb workers."""
import base64
import importlib.util
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'src/scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


auxiliary = module('generate_auxiliary_workflow')
qctl = module('generate_qctl_workflow')
standard = module('validate_standard')


class WorkflowLoader(standard.UniqueLoader):
    # GitHub uses YAML 1.2: unquoted "on" is an event key, not a boolean.
    yaml_implicit_resolvers = {
        key: [(tag, pattern) for tag, pattern in values if tag != 'tag:yaml.org,2002:bool']
        for key, values in standard.UniqueLoader.yaml_implicit_resolvers.items()
    }


WorkflowLoader.add_implicit_resolver('tag:yaml.org,2002:bool', re.compile(r'^(true|false)$', re.I), list('tTfF'))


def load_workflow(raw):
    try:
        return yaml.load(raw, Loader=WorkflowLoader)
    except yaml.YAMLError as error:
        raise ValueError('Invalid native workflow YAML') from error


# Only observed, mandatory verification gates; release-only jobs are not PR gates.
DEFINITIONS = {
    'QRun-IO/qctl': ('qctl', ('main', 'develop'), ('qctl',),
        ('native / test',)),
    'QRun-IO/.github': ('native-workflow-lint', ('main',), ('github-workflow-lint',),
        ('actionlint / actionlint',)),
    'QRun-IO/qqq-business-platform': ('native-business', ('main',), ('business-db', 'business-e2e'),
        ('validate / empty-database-migration', 'validate / Deployment gate / E2E passed')),
    'QRun-IO/qqq-mcp-rag': ('native-mcp', ('main',), ('mcp-rag',),
        ('validate / Build and Test',)),
    'QRun-IO/qqq-app-developer-intellij-plugin': ('intellij-plugin', ('main',), ('intellij-plugin',),
        ('plugin / build',)),
}
PROFILES = {definition[0] for definition in DEFINITIONS.values()}


def gates(profile):
    names = next(definition[3] for definition in DEFINITIONS.values() if definition[0] == profile)
    return [{'context': name, 'app_id': 15368} for name in names]


def caller(kind, pin):
    if kind == 'qctl':
        return '.github/workflows/build.yml', load_workflow(qctl.generate(pin))
    return auxiliary.BRIDGES[kind]['path'], auxiliary.canonical(kind, pin)


def validate(repo, head, branch, request):
    if repo not in DEFINITIONS or branch not in DEFINITIONS[repo][1]:
        raise ValueError('Native recognition requires an approved repository and branch')
    profile, _, kinds, _ = DEFINITIONS[repo]

    def content(owner, path, ref):
        item = request(f'repos/{owner}/contents/{path}?ref={ref}')
        if item.get('type') != 'file' or item.get('encoding') != 'base64':
            raise ValueError('Native workflow must be a regular file')
        return base64.b64decode(item['content']).decode('utf-8').replace('\r\n', '\n')

    paths, pins, verified = set(), {}, set()
    for kind in kinds:
        path, _ = caller(kind, '0' * 40)
        actual = load_workflow(content(repo, path, head))
        try:
            pin = next(iter(actual['jobs'].values()))['uses'].rsplit('@', 1)[1]
            _, expected = caller(kind, pin)
        except (KeyError, TypeError, IndexError, ValueError, AttributeError, StopIteration):
            raise ValueError('Native caller has no immutable orb pin') from None
        if actual != expected:
            raise ValueError('Native caller differs from the canonical shared bridge')
        if pin not in verified:
            commit = request('repos/QRun-IO/qqq-orb/commits/' + pin)
            if not commit['commit']['verification']['verified']:
                raise ValueError('Native worker commit is not verified')
            verified.add(pin)
        for job in expected['jobs'].values():
            worker = job['uses'].split('@')[0].removeprefix('QRun-IO/qqq-orb/')
            if content('QRun-IO/qqq-orb', worker, pin) != (ROOT / worker).read_text(encoding='utf-8'):
                raise ValueError('Pinned native worker differs from the supported contract')
        paths.add(path)
        pins[path] = pin
    tree = request(f'repos/{repo}/git/trees/{head}?recursive=1')
    if tree.get('truncated') is not False or not isinstance(tree.get('tree'), list):
        raise ValueError('Native recognition requires the complete source tree')
    entries = {entry['path']: entry for entry in tree['tree']}
    for path in paths:
        entry = entries.get(path, {})
        if entry.get('type') != 'blob' or entry.get('mode') not in ('100644', '100755'):
            raise ValueError('Native caller is missing or is not a regular source file')
    for entry in tree['tree']:
        path = entry['path']
        if path == '.circleci/config.yml' or (path.startswith('.github/workflows/')
                and path.endswith(('.yml', '.yaml')) and path not in paths):
            raise ValueError('Native repository has additional orchestration: ' + path)
    return profile, pins
