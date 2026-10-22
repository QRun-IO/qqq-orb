"""Validate the canonical native bridge and its immutable shared worker contract."""
import base64
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('next_bridge', ROOT / 'src/scripts/generate_next_workflow.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
MAIN_GATES = [
    'ci / Typecheck, lint, unit tests and coverage',
    'ci / Mocked e2e (Playwright, chromium)',
    'ci / Collaboration e2e (MSW; chromium, firefox, webkit, mobile, tablet)',
    'ci / Bundle budget (static export)', 'ci / Storybook build',
    'acceptance / acceptance gate',
]
PR_GATES = MAIN_GATES + ['dashboard-image / build (amd64, ubuntu-24.04)',
                        'dashboard-image / build (arm64, ubuntu-24.04-arm)']


def gates(pull_request=False):
    return [{'context': name, 'app_id': 15368} for name in (PR_GATES if pull_request else MAIN_GATES)]


def validate(repo, head, branch, request, load_yaml):
    """Only main has a push trigger; require exact caller and reviewed worker bytes."""
    if branch != 'main':
        raise ValueError('Next native branch verification supports main only')

    def content(owner, path, ref):
        item = request(f'repos/{owner}/contents/{path}?ref={ref}')
        if item.get('type') != 'file' or item.get('encoding') != 'base64':
            raise ValueError('Native workflow must be a regular file')
        return base64.b64decode(item['content']).decode('utf-8').replace('\r\n', '\n')

    caller = load_yaml(content(repo, '.github/workflows/ci.yml', head))
    try:
        pin = caller['jobs']['ci']['uses'].rsplit('@', 1)[1]
        expected = bridge.canonical_next(pin)
    except (KeyError, TypeError, IndexError, ValueError):
        raise ValueError('Native caller has no valid immutable worker pin') from None
    if caller != expected:
        raise ValueError('Native caller differs from the canonical shared bridge')
    commit = request('repos/QRun-IO/qqq-orb/commits/' + pin)
    if not commit['commit']['verification']['verified']:
        raise ValueError('Shared native worker commit is not verified')
    for name in ('next-ci.yml', 'next-acceptance.yml', 'next-dashboard-image.yml'):
        path = '.github/workflows/' + name
        if content('QRun-IO/qqq-orb', path, pin) != (ROOT / path).read_text(encoding='utf-8'):
            raise ValueError('Pinned native worker differs from the supported contract: ' + name)
    return pin
