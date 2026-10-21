#!/usr/bin/env python3
"""Exercise the real version script and Maven install; never publish remotely."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = {'m': 'http://maven.apache.org/POM/4.0.0'}
BASH = os.environ.get('TEST_BASH') or shutil.which('bash')
MAVEN = shutil.which('mvn') or shutil.which('mvn.cmd')


def run(args, directory, env=None):
    subprocess.run(args, cwd=directory, env=env, check=True, timeout=300)


def project(body):
    return '<project xmlns="http://maven.apache.org/POM/4.0.0">\n<modelVersion>4.0.0</modelVersion>\n' + body + '\n</project>\n'


def main():
    assert BASH and MAVEN, 'Real Bash, Java and Maven are required'
    with tempfile.TemporaryDirectory(prefix='qqq-version-') as temporary:
        base = Path(temporary)
        for name, version, revision, branch, expected, reactor in (
            ('literal', '0.4.0-SNAPSHOT', '0.4.0-RC.1', 'release/0.4', '0.4.0-RC.2', False),
            ('friendly', '${revision}', '0.4.0-RC.1', 'release/0.4', '0.4.0-RC.2', False),
            ('reactor', '0.4.0-SNAPSHOT', '0.4.0-RC.1', 'release/0.4', '0.4.0-RC.2', True),
            ('unchanged', '0.3.0-SNAPSHOT', '0.4.0-SNAPSHOT', 'develop', '0.4.0-SNAPSHOT', False),
        ):
            root = base / name
            root.mkdir()
            modules = '<modules><module>child</module></modules>' if reactor else ''
            (root / 'pom.xml').write_text(project(f'''<groupId>example.version</groupId>
<artifactId>{name}</artifactId><version>{version}</version><packaging>pom</packaging>
<properties>
<revision>{revision}</revision>
</properties>
{modules}'''), encoding='utf-8')
            if reactor:
                (root / 'child').mkdir()
                (root / 'child/pom.xml').write_text(project(f'''<parent><groupId>example.version</groupId>
<artifactId>{name}</artifactId><version>{version}</version></parent>
<artifactId>child</artifactId><packaging>pom</packaging>'''), encoding='utf-8')
            run(['git', 'init', '-q'], root)
            env = dict(os.environ, CIRCLE_BRANCH=branch, CIRCLE_TAG='')
            run([BASH, str(ROOT / 'src/scripts/calculate_version.sh')], root, env)
            if name == 'friendly':
                assert ET.parse(root / 'pom.xml').findtext('m:version', namespaces=NS) == '${revision}'
            # Install to a temporary repository so the actual artifact coordinate
            # proves the fix, rather than merely checking the revision property.
            repository = base / 'repository'
            run([MAVEN, '-B', '-ntp', '-Dmaven.repo.local=' + str(repository),
                 '-Dflatten.mode=resolveCiFriendliesOnly', '-DupdatePomFile=true',
                 'org.codehaus.mojo:flatten-maven-plugin:1.7.3:flatten', 'install'], root)
            for artifact in ([name, 'child'] if reactor else [name]):
                installed = repository / 'example/version' / artifact / expected / f'{artifact}-{expected}.pom'
                assert installed.exists(), installed
                pom = ET.parse(installed)
                actual = pom.findtext('m:version', namespaces=NS) or pom.findtext('m:parent/m:version', namespaces=NS)
                assert actual == expected, (artifact, actual, expected)
            print(f'PASS: {name} installed at {expected}', flush=True)


if __name__ == '__main__':
    main()
