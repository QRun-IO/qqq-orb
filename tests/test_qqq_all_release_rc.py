import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src/scripts"))
"""RC publication must retain the GA boundary and fail before any upload."""

import functools
import http.server
import tempfile
import threading
import unittest
from pathlib import Path

import qqq_all_release_gate as release_gate
from qqq_all_release_gate import GateError
import test_qqq_all_release_gate as test_release_gate


RC = "4.1.0-RC.1"
TAG_SHA = "b" * 40
RELEASE_SHA = "a" * 40


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


class ReleaseCandidateTest(unittest.TestCase):
    def setUp(self):
        self.fixture = test_release_gate.ReleaseGateTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root

    def test_exact_rc_and_ga_are_allowed_but_other_candidates_are_not(self):
        for version in ("4.1.0", RC):
            self.fixture.write_poms(version, version, "1.2.3-RC.1")
            release_gate.validate_poms(self.root, version)
        for version in ("4.1.0-RC.2", "4.1.0-SNAPSHOT", "4.1.1", "LATEST", ""):
            with self.subTest(version=version), self.assertRaises(GateError):
                self.fixture.write_poms(version, version, "1.2.3")
                release_gate.validate_poms(self.root, version)

    def test_rc_rejects_wrong_framework_pin_and_mutable_dependencies(self):
        for pin in ("4.1.0", "4.1.0-RC.2", "4.1.0-SNAPSHOT"):
            self.fixture.write_poms(RC, pin, "1.2.3")
            with self.assertRaises(GateError):
                release_gate.validate_poms(self.root, RC)
        for pin in ("LATEST", "RELEASE", "[1.0,2.0)", "1.2.3-SNAPSHOT", "${unknown}"):
            self.fixture.write_poms(RC, RC, pin)
            with self.subTest(pin=pin), self.assertRaises(GateError):
                release_gate.validate_poms(self.root, RC)
        self.fixture.write_poms(RC, RC, "1.2.3")
        bom = self.root / "qqq-all-bom/pom.xml"
        bom.write_text(bom.read_text().replace("1.0.0-RC.8", "LATEST"))
        with self.assertRaises(GateError):
            release_gate.validate_poms(self.root, RC)

    def test_public_rc_distribution_poms_must_match_source_including_next(self):
        self.fixture.write_poms(RC, RC, "1.2.3")
        parent, bom = self.fixture.published_poms(resolved=True)
        for path in (parent, bom):
            path.write_text(path.read_text().replace("4.1.0", RC))
        release_gate.validate_published_poms(parent, bom, RC, self.root / "qqq-all-bom/pom.xml")
        original = bom.read_text()
        for changed in (original.replace("1.0.0-RC.8", "1.0.0-RC.9"),
                        original.replace(RC, "4.1.0-RC.2"),
                        original.replace("1.2.3", "[1,2)")):
            bom.write_text(changed)
            with self.assertRaises(GateError):
                release_gate.validate_published_poms(parent, bom, RC, self.root / "qqq-all-bom/pom.xml")

    def test_upstream_rc_requires_exact_public_prerelease_and_ga_requires_final(self):
        for version, prerelease in ((RC, True), ("4.1.0", False)):
            release = {"tag_name": "v" + version, "draft": False, "prerelease": prerelease}
            release_gate.validate_upstream_release(release, version)
            for changed in ({**release, "draft": True}, {**release, "prerelease": not prerelease},
                            {**release, "tag_name": "v4.1.0-RC.2"}, {}):
                with self.subTest(changed=changed), self.assertRaises(GateError):
                    release_gate.validate_upstream_release(changed, version)

    def test_tag_requires_verified_signature_exact_name_object_and_commit(self):
        tag = {"sha": TAG_SHA, "tag": RC, "object": {"type": "commit", "sha": RELEASE_SHA},
               "verification": {"verified": True, "reason": "valid"}}
        release_gate.validate_tag(tag, RC, RELEASE_SHA, TAG_SHA)
        mutations = [
            {**tag, "tag": "4.1.0"}, {**tag, "sha": "c" * 40},
            {**tag, "object": {"type": "commit", "sha": "c" * 40}},
            {**tag, "object": {"type": "tag", "sha": RELEASE_SHA}},
            {**tag, "verification": {"verified": False, "reason": "unsigned"}},
            {**tag, "verification": {"verified": True, "reason": "unknown_key"}}, {},
        ]
        for changed in mutations:
            with self.subTest(changed=changed), self.assertRaises(GateError):
                release_gate.validate_tag(changed, RC, RELEASE_SHA, TAG_SHA)

    def test_public_download_fails_on_missing_or_wrong_coordinates_and_parent(self):
        self.fixture.write_poms(RC, RC, "1.2.3")
        with tempfile.TemporaryDirectory() as directory:
            central = Path(directory)
            dependencies = [("com.kingsrook.qqq", "qqq-bom-pom", RC, "pom"),
                            ("com.kingsrook.qqq", "qqq-frontend-next", "1.0.0-RC.8", "jar")]
            dependencies += [("com.kingsrook.qbits", "qbit-" + name, "1.2.3", "jar")
                             for name in release_gate.QBITS]
            for group, artifact, version, kind in dependencies:
                folder = central / group.replace(".", "/") / artifact / version
                folder.mkdir(parents=True)
                stem = folder / (artifact + "-" + version)
                Path(str(stem) + ".pom").write_text(
                    f"<project><groupId>{group}</groupId><artifactId>{artifact}</artifactId>"
                    f"<version>{version}</version></project>")
                if kind == "jar":
                    Path(str(stem) + ".jar").write_bytes(b"published fixture jar")
            handler = functools.partial(QuietHandler, directory=directory)
            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            base_url = f"http://127.0.0.1:{server.server_port}"
            dest = self.root / "public"
            bom = self.root / "qqq-all-bom/pom.xml"
            receipts = release_gate.download_public_inputs(bom, RC, dest, base_url)
            self.assertEqual(19, len(receipts))
            self.assertTrue(all(len(row["sha256"]) == 64 for row in receipts))
            public_pom = central / "com/kingsrook/qqq/qqq-frontend-next/1.0.0-RC.8/qqq-frontend-next-1.0.0-RC.8.pom"
            original = public_pom.read_text()
            public_pom.write_text(original.replace("1.0.0-RC.8", "1.0.0-RC.9"))
            with self.assertRaises(GateError):
                release_gate.download_public_inputs(bom, RC, dest, base_url)
            public_pom.write_text(original.replace("</project>", "<parent><groupId>com.kingsrook</groupId>"
                                  "<artifactId>qbit-build-parent</artifactId><version>LATEST</version></parent></project>"))
            with self.assertRaises(GateError):
                release_gate.download_public_inputs(bom, RC, dest, base_url)
            public_pom.write_text(original.replace("</project>", "<parent><groupId>com.kingsrook</groupId>"
                                  "<artifactId>qbit-build-parent</artifactId><version>2.1.0-RC.1</version></parent></project>"))
            parent = central / "com/kingsrook/qbit-build-parent/2.1.0-RC.1/qbit-build-parent-2.1.0-RC.1.pom"
            parent.parent.mkdir(parents=True)
            parent.write_text("<project><groupId>com.kingsrook</groupId><artifactId>qbit-build-parent</artifactId>"
                              "<version>2.1.0-RC.1</version><dependencyManagement><dependencies><dependency>"
                              "<groupId>com.kingsrook.qqq</groupId><artifactId>qqq-bom-pom</artifactId>"
                              "<version>4.0.0</version><type>pom</type><scope>import</scope>"
                              "</dependency></dependencies></dependencyManagement></project>")
            with self.assertRaises(GateError):
                release_gate.download_public_inputs(bom, RC, dest, base_url)
            parent.write_text(parent.read_text().replace("4.0.0", RC))
            self.assertEqual(20, len(release_gate.download_public_inputs(bom, RC, dest, base_url)))
            public_pom.unlink()
            with self.assertRaises(GateError):
                release_gate.download_public_inputs(bom, RC, dest, base_url)


if __name__ == "__main__":
    unittest.main()
