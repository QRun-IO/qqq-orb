import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src/scripts"))
"""Release gate checks use fixtures so the workflow can fail closed before publication."""

import tempfile
import unittest
from pathlib import Path

from qqq_all_release_gate import GateError, validate_poms, validate_published_poms, validate_smoke


RELEASE_SHA = "a" * 40
QBITS = (
    "quick-search", "user-role-permissions", "customizable-table-views",
    "standard-process-trace", "webhooks", "workflows", "geo-data",
    "sftp-data-integration",
)


def management(qqq_version="${qqq.version}", qbit_version=None):
    qbit_version = qbit_version or (lambda name: f"${{qbit-{name}.version}}")
    dependencies = (
        "<dependency><groupId>com.kingsrook.qqq</groupId><artifactId>qqq-bom-pom</artifactId>"
        f"<version>{qqq_version}</version><type>pom</type><scope>import</scope></dependency>"
    )
    dependencies += "".join(
        "<dependency><groupId>com.kingsrook.qbits</groupId>"
        f"<artifactId>qbit-{name}</artifactId><version>{qbit_version(name)}</version></dependency>"
        for name in QBITS
    )
    dependencies += (
        "<dependency><groupId>com.kingsrook.qqq</groupId><artifactId>qqq-frontend-next</artifactId>"
        "<version>1.0.0-RC.8</version></dependency>"
    )
    return f"<dependencyManagement><dependencies>{dependencies}</dependencies></dependencyManagement>"


class ReleaseGateTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "qqq-all-bom").mkdir()
        self.write_poms("4.1.0", "4.1.0", "1.2.3")

    def write_poms(self, revision, qqq_version, qbit_version):
        (self.root / "pom.xml").write_text(
            f"<project><properties><revision>{revision}</revision></properties></project>"
        )
        (self.root / "qqq-all-bom/pom.xml").write_text(
            "<project><properties>"
            f"<qqq.version>{qqq_version}</qqq.version>"
            "<qqq-frontend-next.version>1.0.0-RC.8</qqq-frontend-next.version>"
            + "".join(f"<qbit-{name}.version>{qbit_version}</qbit-{name}.version>" for name in QBITS)
            + "</properties>" + management() + "</project>"
        )

    def published_poms(self, resolved=False):
        parent = self.root / "published-parent.pom"
        bom = self.root / "published-bom.pom"
        parent.write_text("<project xmlns='http://maven.apache.org/POM/4.0.0'>"
                          "<groupId>com.kingsrook.qqq</groupId>"
                          "<artifactId>qqq-all-parent</artifactId><version>4.1.0</version></project>")
        managed = (management("4.1.0", lambda name: "1.2.3") if resolved else management())
        bom.write_text("<project xmlns='http://maven.apache.org/POM/4.0.0'><parent>"
                       "<groupId>com.kingsrook.qqq</groupId>"
                       "<artifactId>qqq-all-parent</artifactId><version>4.1.0</version></parent>"
                       "<artifactId>qqq-all-bom</artifactId><properties><qqq.version>4.1.0</qqq.version>"
                       "<qqq-frontend-next.version>1.0.0-RC.8</qqq-frontend-next.version>"
                       + "".join(f"<qbit-{name}.version>1.2.3</qbit-{name}.version>" for name in QBITS)
                       + "</properties>" + managed + "</project>")
        return parent, bom

    def test_release_poms_require_ga_versions(self):
        validate_poms(self.root, "4.1.0")
        for revision, qqq_version, qbit_version in (
            ("4.1.0-SNAPSHOT", "4.1.0", "1.2.3"),
            ("4.1.0", "4.1.0-SNAPSHOT", "1.2.3"),
            ("4.1.0", "4.1.0", "1.2.3-SNAPSHOT"),
        ):
            with self.subTest(revision=revision, qqq=qqq_version, qbit=qbit_version):
                self.write_poms(revision, qqq_version, qbit_version)
                with self.assertRaises(GateError):
                    validate_poms(self.root, "4.1.0")
        self.write_poms("4.1.0", "4.1.0", "1.2.3")
        source_bom = self.root / "qqq-all-bom/pom.xml"
        source_bom.write_text(source_bom.read_text().replace(
            "<artifactId>qbit-webhooks</artifactId>",
            "<artifactId>qbit-other</artifactId>"))
        with self.assertRaises(GateError):
            validate_poms(self.root, "4.1.0")

    def test_smoke_run_must_match_release_sha_and_both_jobs(self):
        run = {
            "name": "Smoke", "path": ".github/workflows/smoke.yml",
            "head_sha": RELEASE_SHA, "head_branch": "develop", "event": "push",
            "conclusion": "success",
        }
        jobs = {"jobs": [
            {"name": "core", "conclusion": "success"},
            {"name": "full", "conclusion": "success"},
        ]}
        validate_smoke(run, jobs, RELEASE_SHA)
        for changed_run, changed_jobs in (
            ({**run, "head_sha": "b" * 40}, jobs),
            ({**run, "conclusion": "failure"}, jobs),
            ({**run, "path": ".github/workflows/other.yml"}, jobs),
            ({**run, "event": "workflow_dispatch"}, jobs),
            ({**run, "head_branch": "main"}, jobs),
            (run, {"jobs": [jobs["jobs"][0]]}),
            (run, {"jobs": [jobs["jobs"][0], {"name": "full", "conclusion": "skipped"}]}),
        ):
            with self.subTest(run=changed_run, jobs=changed_jobs):
                with self.assertRaises(GateError):
                    validate_smoke(changed_run, changed_jobs, RELEASE_SHA)

    def test_published_parent_and_bom_must_be_release_poms(self):
        parent, bom = self.published_poms()
        validate_published_poms(parent, bom, "4.1.0", self.root / "qqq-all-bom/pom.xml")
        self.published_poms(resolved=True)
        validate_published_poms(parent, bom, "4.1.0", self.root / "qqq-all-bom/pom.xml")
        parent.write_text(parent.read_text().replace("qqq-all-parent", "wrong-parent"))
        with self.assertRaises(GateError):
            validate_published_poms(parent, bom, "4.1.0", self.root / "qqq-all-bom/pom.xml")
        self.published_poms(resolved=True)
        bom.write_text(bom.read_text().replace("4.1.0", "4.1.0-SNAPSHOT"))
        with self.assertRaises(GateError):
            validate_published_poms(parent, bom, "4.1.0", self.root / "qqq-all-bom/pom.xml")

    def test_published_bom_rejects_managed_dependency_overrides(self):
        parent, bom = self.published_poms(resolved=True)
        original = bom.read_text()
        mutations = (
            original.replace("<artifactId>qqq-bom-pom</artifactId>",
                             "<artifactId>qqq-other-bom</artifactId>"),
            original.replace("<type>pom</type><scope>import</scope>",
                             "<type>pom</type><scope>compile</scope>"),
            original.replace("<version>4.1.0</version><type>pom</type><scope>import</scope>",
                             "<version>4.1.0-SNAPSHOT</version><type>pom</type><scope>import</scope>"),
            original.replace("<artifactId>qbit-webhooks</artifactId><version>1.2.3</version>",
                             "<artifactId>qbit-webhooks</artifactId><version>1.2.3-SNAPSHOT</version>"),
            original.replace("<artifactId>qbit-webhooks</artifactId><version>1.2.3</version>",
                             "<artifactId>qbit-webhooks</artifactId><version>1.2.4</version>"),
            original.replace("<dependency><groupId>com.kingsrook.qbits</groupId>"
                             "<artifactId>qbit-webhooks</artifactId><version>1.2.3</version>"
                             "</dependency>", ""),
            original.replace("</dependencies></dependencyManagement>",
                             "<dependency><groupId>com.kingsrook.qbits</groupId>"
                             "<artifactId>qbit-webhooks</artifactId><version>1.2.4</version>"
                             "</dependency></dependencies></dependencyManagement>"),
            original.replace("</project>", "<profiles><profile><id>override</id>"
                             "<activation><activeByDefault>true</activeByDefault></activation>"
                             "<dependencyManagement><dependencies><dependency>"
                             "<groupId>com.kingsrook.qbits</groupId>"
                             "<artifactId>qbit-webhooks</artifactId>"
                             "<version>1.2.3-SNAPSHOT</version>"
                             "</dependency></dependencies></dependencyManagement>"
                             "</profile></profiles></project>"),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                self.assertNotEqual(original, mutation)
                bom.write_text(mutation)
                with self.assertRaises(GateError):
                    validate_published_poms(parent, bom, "4.1.0", self.root / "qqq-all-bom/pom.xml")
        bom.write_text(original.replace(
            "<qbit-webhooks.version>1.2.3</qbit-webhooks.version>",
            "<qbit-webhooks.version>1.2.4</qbit-webhooks.version>"))
        with self.assertRaises(GateError):
            validate_published_poms(parent, bom, "4.1.0", self.root / "qqq-all-bom/pom.xml")


if __name__ == "__main__":
    unittest.main()
