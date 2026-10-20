#!/bin/bash
# Run with bash; uses only Python, Git and a temporary repository (no network/Maven).
set -euo pipefail
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../src/scripts" && pwd)
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
cd "$scratch"
git init -q
mkdir -p module/nested .mvn/wrapper
printf '<project><version>1</version></project>\n' > pom.xml
printf '<project><dependency>one</dependency></project>\n' > module/pom.xml
printf '<project/>\n' > module/nested/pom.xml
printf 'distributionUrl=https://example.invalid/maven.zip\n' > .mvn/wrapper/maven-wrapper.properties
printf 'class Example {}\n' > module/Example.java
git add .
export MAVEN_CACHE_FINGERPRINT_FILE="$scratch/fingerprint"
fingerprint() { bash "$script_dir/maven_cache_fingerprint.sh" || return; cat "$MAVEN_CACHE_FINGERPRINT_FILE"; }
original=$(fingerprint)
[[ "$original" == "$(fingerprint)" ]]
printf 'class Example { int changed; }\n' > module/Example.java
[[ "$original" == "$(fingerprint)" ]] # source-only edits reuse dependencies
printf '<project><dependency>two</dependency></project>\n' > module/pom.xml
module_change=$(fingerprint)
[[ "$original" != "$module_change" ]] # root POM unchanged
printf '<project><version>2</version></project>\n' > module/nested/pom.xml
nested_change=$(fingerprint)
[[ "$module_change" != "$nested_change" ]]
printf 'distributionUrl=https://example.invalid/new.zip\n' > .mvn/wrapper/maven-wrapper.properties
[[ "$nested_change" != "$(fingerprint)" ]]
# Maven runs from child directories must fingerprint the same complete reactor.
root_hash=$(fingerprint)
cd module
[[ "$root_hash" == "$(fingerprint)" ]]
cd ..
# Deleting a tracked input fails closed, rather than silently sharing the old key.
rm module/pom.xml
if fingerprint >/dev/null 2>&1; then echo 'missing tracked POM accepted' >&2; exit 1; fi
printf 'PASS: stable, multi-module, wrapper, subdirectory and missing-input fingerprints\n'
