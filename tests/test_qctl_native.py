"""Contract tests against the actual native worker, using only the standard library."""
import json
import pathlib
import re
import unittest

WORKFLOW = (pathlib.Path(__file__).parents[1] / '.github/workflows/qctl-native.yml').read_text()
JOBS = dict(re.findall(r'^  ([a-z][a-z-]+):\n(.*?)(?=^  [a-z][a-z-]+:|\Z)', WORKFLOW.split('jobs:\n', 1)[1], re.M | re.S))


class NativeWorkerTests(unittest.TestCase):
    def test_source_tests_unconditional_and_native_gated_after_them(self):
        self.assertNotIn('    if:', JOBS['test'])
        self.assertIn('run: mvn clean verify -q', JOBS['test'])
        self.assertIn('needs: test', JOBS['build-native'])
        self.assertIn("if: github.event_name == 'push' || (github.event_name == 'workflow_dispatch' && inputs.full_native)", JOBS['build-native'])

    def test_branch_linux_and_full_five_platform_matrix(self):
        full, branch = [json.loads(value) for value in re.findall(r"'(\[.*?\])'", JOBS['build-native'])]
        self.assertEqual([{'os': 'ubuntu-latest', 'artifact': 'qctl-linux-amd64'}], branch)
        self.assertEqual({'qctl-linux-amd64', 'qctl-linux-arm64', 'qctl-macos-amd64', 'qctl-macos-arm64', 'qctl-windows-amd64.exe'}, {row['artifact'] for row in full})
        self.assertEqual(5, len(full))
        self.assertEqual('macos-15-intel', next(row['os'] for row in full if row['artifact'] == 'qctl-macos-amd64'))
        self.assertIn("startsWith(github.ref, 'refs/tags/v') || inputs.full_native", JOBS['build-native'])
        self.assertIn('Verify artifact architecture', JOBS['build-native'])

    def test_publishers_are_only_tag_pushes_and_reuse_built_binaries(self):
        for name in ['release', 'docker', 'update-homebrew', 'update-scoop', 'update-aur']:
            with self.subTest(job=name):
                job = JOBS[name]
                self.assertIn("if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')", job)
                self.assertIn('needs: ' + ('build-native' if name == 'release' else 'release'), job)
                self.assertIn('actions/download-artifact@v4', job)
                self.assertNotIn('mvn ', job)
        self.assertIn('name: qctl-linux-amd64', JOBS['docker'])
        self.assertIn('name: qctl-linux-arm64', JOBS['docker'])
        self.assertIn('platforms: linux/amd64,linux/arm64', JOBS['docker'])
        self.assertIn('name: qctl-windows-amd64.exe', JOBS['update-scoop'])

    def test_fork_code_has_read_only_token_and_no_secret_publisher(self):
        self.assertIn('permissions:\n  contents: read', WORKFLOW.split('jobs:', 1)[0])
        for name in ['test', 'build-native']:
            self.assertNotIn('HOMEBREW_TAP_TOKEN', JOBS[name])
            self.assertNotIn('contents: write', JOBS[name])
        self.assertNotIn('pull_request_target', WORKFLOW)
        self.assertIn("github.event_name == 'push' && !startsWith(github.ref, 'refs/tags/')", WORKFLOW)


if __name__ == '__main__':
    unittest.main()
