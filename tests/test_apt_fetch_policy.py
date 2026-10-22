#!/usr/bin/env python3
"""Exercise actual APT downloads against a local fault-injecting HTTP mirror.

Run in a disposable Debian/Ubuntu container with Python and apt-helper installed.
No external network, package installation, or signature bypass is required.
"""
import hashlib
import http.server
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = b"qqq package download fixture\n"
POLICY = (
    'Acquire::Retries "3";',
    'Acquire::http::Timeout "30";',
    'Acquire::https::Timeout "30";',
    'APT::Update::Error-Mode "any";',
)


class AptFetchPolicyTests(unittest.TestCase):
    def test_runner_mirror_selection(self):
        # Execute the actual workflow command against the hosted runner's mirror format.
        original = ("http://azure.archive.ubuntu.com/ubuntu/\tpriority:1\n"
                    "https://archive.ubuntu.com/ubuntu/\tpriority:2\n"
                    "https://security.ubuntu.com/ubuntu/\tpriority:3\n")
        expected = original.split("\n", 1)[1]
        for name in ("next-ci.yml", "next-acceptance.yml"):
            workflow = (ROOT / ".github/workflows" / name).read_text()
            commands = [line.strip() for line in workflow.splitlines()
                        if line.strip().startswith("sudo sed -i ")]
            self.assertEqual(len(commands), 2)
            for command in commands:
                with tempfile.TemporaryDirectory() as scratch:
                    mirrors = Path(scratch) / "apt-mirrors.txt"
                    mirrors.write_text(original)
                    command = command.removeprefix("sudo ").replace(
                        "/etc/apt/apt-mirrors.txt", str(mirrors))
                    for _ in range(2):
                        subprocess.run(["bash", "-e", "-c", command], check=True)
                        self.assertEqual(mirrors.read_text(), expected)

    def test_real_download_failures(self):
        source = (ROOT / "src/scripts/install_java.sh").read_text()
        stanza = source.split("# Retry transient repository downloads", 1)[1].split("# Ubuntu archive", 1)[0]
        options = re.findall(r"'([^']+;)'", stanza)
        self.assertEqual(tuple(options), POLICY)
        for name in ("next-ci.yml", "next-acceptance.yml"):
            workflow = (ROOT / ".github/workflows" / name).read_text()
            blocks = workflow.split("      - name: Install browser system dependencies\n")[1:]
            self.assertEqual(len(blocks), 2)
            for block in blocks:
                block = block.split("      - ", 1)[0]
                self.assertIn("timeout-minutes: 10", block)
                self.assertEqual(tuple(re.findall(r"'([^']+;)'", block)), POLICY)

        requests = {}

        class Mirror(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                requests[self.path] = requests.get(self.path, 0) + 1
                status = 200
                if self.path == "/permanent" or (self.path == "/transient" and requests[self.path] <= 2):
                    status = 503
                elif self.path == "/missing":
                    status = 404
                self.send_response(status)
                self.send_header("Content-Length", str(len(PAYLOAD)))
                self.end_headers()
                self.wfile.write(PAYLOAD)

            def log_message(self, *_args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Mirror)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as scratch:
                config = Path(scratch) / "apt.conf"
                config.write_text("\n".join(options) + "\n")
                for case, expected, count in (("normal", 0, 1), ("transient", 0, 3),
                                               ("permanent", 100, 4), ("missing", 100, 1),
                                               ("bad-hash", 100, 1)):
                    with self.subTest(case=case):
                        digest = hashlib.sha256(PAYLOAD if case != "bad-hash" else b"different").hexdigest()
                        url = f"http://127.0.0.1:{server.server_port}/{case}"
                        started = time.monotonic()
                        result = subprocess.run([
                            "/usr/lib/apt/apt-helper", "-c", str(config), "download-file", url,
                            str(Path(scratch) / case), "SHA256:" + digest,
                        ], capture_output=True, text=True, timeout=25)
                        output = result.stdout + result.stderr
                        self.assertEqual(result.returncode, expected, output)
                        self.assertEqual(requests["/" + case], count, output)
                        self.assertLess(time.monotonic() - started, 25)
                        if expected == 0:
                            self.assertEqual((Path(scratch) / case).read_bytes(), PAYLOAD)
                        else:
                            self.assertIn("127.0.0.1", output)
                        if case == "permanent":
                            self.assertIn("503", output)
                        if case == "bad-hash":
                            self.assertIn("Hash Sum mismatch", output)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
