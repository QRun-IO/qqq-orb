"""Exercise actual shell handling of gh error JSON, including the observed 404."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest

SOURCE = Path(__file__).parents[1].joinpath('.github/workflows/qbit-release-rc.yml').read_text()
FUNCTION = textwrap.dedent(SOURCE.split('          # BEGIN RC REF LOOKUP\n')[1].split('          # END RC REF LOOKUP')[0])


@unittest.skipUnless(shutil.which('bash') and shutil.which('jq'), 'Bash and jq required')
class RefLookupTests(unittest.TestCase):
    def lookup(self, body, code):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, BODY=body, CODE=str(code), REPO='QRun-IO/qbit-alerts', workdir=directory)
            script = 'set -euo pipefail\ngh() { printf "%s" "$BODY"; return "$CODE"; }\n' + FUNCTION + '\nresult=$(read_ref tags/v0.1.0-RC.17)\nprintf "%s" "$result"\n'
            return subprocess.run(['bash', '-c', script], env=env, text=True, capture_output=True)

    def test_absent_tag_returns_empty_not_error_json(self):
        result = self.lookup('{"message":"Not Found","documentation_url":"https://docs.github.com/rest/git/refs#get-a-reference","status":"404"}', 1)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('', result.stdout)

    def test_existing_tag_returns_only_valid_object_sha(self):
        result = self.lookup('{"object":{"sha":"' + 'a' * 40 + '"}}', 0)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('a' * 40, result.stdout)

    def test_permission_network_and_server_errors_are_not_missing_refs(self):
        for body in ('{"status":"403"}', '{"status":"500"}', '', 'not json'):
            with self.subTest(body=body):
                self.assertNotEqual(0, self.lookup(body, 1).returncode)

    def test_malformed_success_response_is_rejected(self):
        for body in ('{}', '{"object":{"sha":null}}', '{"object":{"sha":"not-a-sha"}}'):
            with self.subTest(body=body):
                self.assertNotEqual(0, self.lookup(body, 0).returncode)


if __name__ == '__main__':
    unittest.main()
