"""Capability probes must drain help output while still rejecting missing options."""
from pathlib import Path
import shlex
import subprocess
import unittest


class InstallerTests(unittest.TestCase):
    def probe(self, flags):
        installer = Path(__file__).resolve().parents[1] / 'tools/install_reconcile_gh.sh'
        checks = '\n'.join(line for line in installer.read_text().splitlines()
                           if line.startswith(('gh api --help', 'gh pr merge --help')))
        self.assertEqual(2, len(checks.splitlines()))
        producer = ("import signal,sys; signal.signal(signal.SIGPIPE,signal.SIG_DFL); "
                    f"print({flags!r},flush=True); sys.stdout.write('x'*1048576)")
        script = 'set -euo pipefail\ngh() { python3 -c ' + shlex.quote(producer) + '; }\n' + checks
        return subprocess.run(['bash', '-c', script], capture_output=True, timeout=10).returncode

    def test_large_help_output_does_not_kill_producer(self):
        self.assertEqual(0, self.probe('--slurp --match-head-commit'))

    def test_missing_required_option_fails(self):
        self.assertNotEqual(0, self.probe('--slurp'))
        self.assertNotEqual(0, self.probe('--match-head-commit'))


if __name__ == '__main__':
    unittest.main()
