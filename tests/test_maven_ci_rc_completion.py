"""Exercise actual dispatch program with isolated POM/marker and mocked Git/API."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

SOURCE = (Path(__file__).resolve().parents[1] / "src/scripts/notify_rc_published.sh").read_text(encoding="utf-8").split("<<'PYTHON'\n", 1)[1].rsplit("\nPYTHON", 1)[0]
MERGE = "a" * 40
BUMP = "b" * 40


class RcCompletion(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.previous = os.getcwd()
        os.chdir(self.temp.name)
        self.addCleanup(os.chdir, self.previous)
        Path("pom.xml").write_text("<project><properties><revision>0.1.0-RC.2</revision></properties></project>")
        Path("marker").write_text(BUMP)
        self.env = {"CIRCLE_BRANCH": "release/0.1", "CIRCLE_SHA1": MERGE, "CIRCLE_PROJECT_USERNAME": "QRun-IO", "CIRCLE_PROJECT_REPONAME": "fixture", "QQQ_PUSHED_VERSION_FILE": str(Path("marker").resolve()), "GH_TOKEN": "test-not-a-credential"}
        self.answers = {
            ("rev-parse", "HEAD"): BUMP,
            ("show", "-s", "--format=%P", "HEAD"): MERGE,
            ("ls-remote", "--exit-code", "origin", "refs/heads/release/0.1"): BUMP + "\trefs/heads/release/0.1",
            ("show", "-s", "--format=%s", "HEAD"): "Bump version to 0.1.0-RC.2 [skip ci]",
            ("status", "--porcelain", "pom.xml"): "",
        }

    def run_program(self, expected_error=False, http_error=False):
        response = MagicMock()
        response.__enter__.return_value.status = 204
        with patch.dict(os.environ, self.env, clear=True), patch("subprocess.check_output", side_effect=lambda args, **_: self.answers[tuple(args[1:])]), patch("urllib.request.urlopen", return_value=response) as send, contextlib.redirect_stdout(io.StringIO()):
            if http_error:
                send.side_effect = urllib.error.HTTPError("https://example.invalid", 403, "denied", {}, None)
            if expected_error:
                with self.assertRaises(SystemExit):
                    exec(compile(SOURCE, "notify_rc_published", "exec"), {})
                if not http_error:
                    send.assert_not_called()
            else:
                exec(compile(SOURCE, "notify_rc_published", "exec"), {})
                send.assert_called_once()
                request = send.call_args.args[0]
                self.assertEqual(request.full_url, "https://api.github.com/repos/QRun-IO/fixture/dispatches")
                self.assertEqual(json.loads(request.data), {"event_type": "qbit-rc-published", "client_payload": {"merge_sha": MERGE, "bump_sha": BUMP, "branch": "release/0.1", "version": "0.1.0-RC.2"}})

    def test_verified_push_dispatches_exact_identity(self):
        self.run_program()

    def test_local_commit_without_push_is_rejected(self):
        Path("marker").unlink()
        self.run_program(True)

    def test_stale_push_marker_is_rejected(self):
        Path("marker").write_text(MERGE)
        self.run_program(True)

    def test_concurrent_remote_change_is_rejected(self):
        self.answers[("ls-remote", "--exit-code", "origin", "refs/heads/release/0.1")] = MERGE + "\trefs/heads/release/0.1"
        self.run_program(True)

    def test_wrong_parent_is_rejected(self):
        self.answers[("show", "-s", "--format=%P", "HEAD")] = MERGE + " " + BUMP
        self.run_program(True)

    def test_modified_pom_is_rejected(self):
        self.answers[("status", "--porcelain", "pom.xml")] = " M pom.xml"
        self.run_program(True)

    def test_non_rc_is_rejected(self):
        Path("pom.xml").write_text("<project><properties><revision>0.1.0</revision></properties></project>")
        self.run_program(True)

    def test_missing_credential_is_rejected(self):
        self.env.pop("GH_TOKEN")
        self.run_program(True)

    def test_github_denial_fails(self):
        self.run_program(True, True)


if __name__ == "__main__":
    unittest.main()
