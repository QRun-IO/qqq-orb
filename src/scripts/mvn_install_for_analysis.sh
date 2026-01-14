#!/bin/bash
set -e

echo "Building and installing project for static analysis..."
mvn install -DskipTests -Dmaven.javadoc.skip=true -Dcheckstyle.skip=true
echo "Build complete - artifacts installed to local repository"
