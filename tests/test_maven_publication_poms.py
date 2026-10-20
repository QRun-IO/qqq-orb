#!/usr/bin/env python3
"""Real Maven publication contract. Requires Java/Maven; no remote deploy or secrets.

Run explicitly with make test-publication-poms. Public plugins are downloaded to
an isolated temporary local repository; nothing is installed to the user's m2.
"""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
GOAL = 'org.codehaus.mojo:flatten-maven-plugin:1.7.3:flatten'
FLAGS = ['-Dflatten.mode=resolveCiFriendliesOnly', '-DupdatePomFile=true']
NS = {'m': 'http://maven.apache.org/POM/4.0.0'}


def pom(body):
    return '<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>' + body + '</project>'


def run_case(base, repository, lifecycle):
    project = base / ('bound' if lifecycle else 'plain')
    project.mkdir()
    group = 'example.bound' if lifecycle else 'example.plain'
    flatten = ("<plugin><groupId>org.codehaus.mojo</groupId><artifactId>flatten-maven-plugin</artifactId>"
               "<version>1.7.3</version><configuration><updatePomFile>true</updatePomFile>"
               "<flattenMode>resolveCiFriendliesOnly</flattenMode></configuration><executions>"
               "<execution><id>flatten</id><phase>process-resources</phase><goals><goal>flatten</goal>"
               "</goals></execution></executions></plugin>") if lifecycle else ''
    (project / 'pom.xml').write_text(pom(f"""
      <groupId>{group}</groupId><artifactId>parent</artifactId><version>${{revision}}</version><packaging>pom</packaging>
      <name>Publication fixture</name><description>Inherited release metadata</description><url>https://example.invalid/fixture</url>
      <licenses><license><name>Fixture license</name><url>https://example.invalid/license</url></license></licenses>
      <properties><revision>1.2.3</revision><maven.compiler.release>17</maven.compiler.release></properties>
      <modules><module>library</module><module>application</module></modules>
      <dependencyManagement><dependencies><dependency><groupId>{group}</groupId><artifactId>library</artifactId>
      <version>${{revision}}</version></dependency></dependencies></dependencyManagement>
      <build><pluginManagement><plugins><plugin><groupId>org.apache.maven.plugins</groupId>
      <artifactId>maven-compiler-plugin</artifactId><version>3.13.0</version><configuration><release>17</release></configuration>
      </plugin></plugins></pluginManagement><plugins>{flatten}</plugins></build>
    """), encoding='utf-8')
    for artifact in ('library', 'application'):
        child = project / artifact
        child.mkdir()
        dependencies = (f'<dependencies><dependency><groupId>{group}</groupId><artifactId>library</artifactId></dependency></dependencies>'
                        if artifact == 'application' else '')
        (child / 'pom.xml').write_text(pom(f'<parent><groupId>{group}</groupId><artifactId>parent</artifactId>'
            '<version>${revision}</version></parent>' + f'<artifactId>{artifact}</artifactId>' + dependencies), encoding='utf-8')
    sources = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in project.rglob('pom.xml')}
    settings = base / 'settings.xml'
    settings.write_text('<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0"/>', encoding='utf-8')
    maven = shutil.which('mvn') or shutil.which('mvn.cmd')
    if not maven:
        raise RuntimeError('Maven is required for this explicit integration gate')
    command = [maven, '-B', '-ntp', '-s', str(settings), '-gs', str(settings), '-Dmaven.repo.local=' + str(repository)]
    def execute(directory, goals):
        subprocess.run(command + goals, cwd=directory, check=True, timeout=600)
    execute(project, FLAGS + [GOAL, 'install'])
    for path, digest in sources.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'Source POM was rewritten'
    installed = repository / group.replace('.', '/')
    for artifact in ('parent', 'library', 'application'):
        tree = ET.parse(installed / artifact / '1.2.3' / (artifact + '-1.2.3.pom'))
        for node in tree.findall('m:version', NS) + tree.findall('m:parent/m:version', NS):
            assert node.text == '1.2.3', 'Unresolved deployed coordinate: ' + artifact
    parent = ET.parse(installed / 'parent/1.2.3/parent-1.2.3.pom')
    assert parent.findtext('m:licenses/m:license/m:name', namespaces=NS) == 'Fixture license'
    assert parent.find('m:dependencyManagement', NS) is not None
    assert parent.find('m:build/m:pluginManagement', NS) is not None, 'Parent build contract was stripped'
    # Remove reactor availability: cold consumer can use only installed artifacts.
    hidden = project.with_name(project.name + '-unavailable')
    project.rename(hidden)
    consumer = base / ('consumer-bound' if lifecycle else 'consumer-plain')
    consumer.mkdir()
    (consumer / 'pom.xml').write_text(pom(f'<parent><groupId>{group}</groupId><artifactId>parent</artifactId>'
        '<version>1.2.3</version><relativePath/></parent><artifactId>cold-consumer</artifactId>'
        f'<dependencies><dependency><groupId>{group}</groupId><artifactId>application</artifactId>'
        '<version>1.2.3</version></dependency></dependencies>'), encoding='utf-8')
    execute(consumer, ['validate', 'org.apache.maven.plugins:maven-help-plugin:3.5.1:effective-pom', '-Doutput=effective.xml',
                       'org.apache.maven.plugins:maven-dependency-plugin:3.7.1:build-classpath', '-Dmdep.outputFile=classpath.txt'])
    effective = ET.parse(consumer / 'effective.xml')
    assert effective.findtext('m:licenses/m:license/m:name', namespaces=NS) == 'Fixture license'
    managed = effective.find('m:dependencyManagement/m:dependencies/m:dependency', NS)
    assert managed.findtext('m:version', namespaces=NS) == '1.2.3'
    plugins = effective.findall('m:build/m:pluginManagement/m:plugins/m:plugin', NS)
    compiler = next(p for p in plugins if p.findtext('m:artifactId', namespaces=NS) == 'maven-compiler-plugin')
    assert compiler.findtext('m:configuration/m:release', namespaces=NS) == '17'
    classpath = (consumer / 'classpath.txt').read_text()
    assert 'application-1.2.3.jar' in classpath and 'library-1.2.3.jar' in classpath
    print('PASS real resolved publication + cold consumer: ' + ('lifecycle-bound' if lifecycle else 'no-existing-flatten'))


def main():
    deployment = (ROOT / 'src/scripts/mvn_jar_deploy.sh').read_text()
    for flag in FLAGS:
        assert flag in deployment, 'Deployment missing tested flatten configuration'
    assert GOAL + ' deploy' in deployment, 'Flatten and deploy must share a Maven process'
    with tempfile.TemporaryDirectory(prefix='qqq-publication-') as directory:
        base = Path(directory)
        for lifecycle in (False, True):
            run_case(base, base / 'repository', lifecycle)


if __name__ == '__main__': main()
