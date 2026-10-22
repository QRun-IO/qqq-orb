"""Recognize approved GitOps repositories through their shared immutable worker."""
import base64
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gitops_bridge', ROOT / 'src/scripts/generate_auxiliary_workflow.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
DEFINITION = bridge.BRIDGES['gitops']
REPOSITORIES = {DEFINITION['repository'], *DEFINITION.get('additional_repositories', [])}


def gates():
    return [{'context': 'gitops / validate', 'app_id': 15368}]


def validate(repo, head, branch, request, load_yaml):
    if repo not in REPOSITORIES or branch != 'main':
        raise ValueError('GitOps recognition requires an approved repository on main only')

    def content(owner, path, ref):
        item = request(f'repos/{owner}/contents/{path}?ref={ref}')
        if item.get('type') != 'file' or item.get('encoding') != 'base64':
            raise ValueError('GitOps workflow must be a regular file')
        return base64.b64decode(item['content']).decode('utf-8').replace('\r\n', '\n')

    path = DEFINITION['path']
    caller = load_yaml(content(repo, path, head))
    try:
        pin = caller['jobs']['gitops']['uses'].rsplit('@', 1)[1]
        expected = bridge.canonical('gitops', pin)
    except (KeyError, TypeError, IndexError, ValueError, AttributeError):
        raise ValueError('GitOps caller has no immutable shared worker pin') from None
    if caller != expected:
        raise ValueError('GitOps caller differs from the canonical shared bridge')
    tree = request(f'repos/{repo}/git/trees/{head}?recursive=1')
    if tree.get('truncated') is not False or not isinstance(tree.get('tree'), list):
        raise ValueError('GitOps recognition requires the complete source tree')
    for entry in tree['tree']:
        name = entry['path']
        if name == '.circleci/config.yml' or (name.startswith('.github/workflows/')
                and name.endswith(('.yml', '.yaml')) and name != path):
            raise ValueError('GitOps repository has additional orchestration: ' + name)
    commit = request('repos/QRun-IO/qqq-orb/commits/' + pin)
    if not commit['commit']['verification']['verified']:
        raise ValueError('GitOps worker commit is not verified')
    worker = '.github/workflows/gitops.yml'
    if content('QRun-IO/qqq-orb', worker, pin) != (ROOT / worker).read_text(encoding='utf-8'):
        raise ValueError('Pinned GitOps worker differs from the supported contract')
    return pin
