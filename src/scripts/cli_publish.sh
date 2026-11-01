#!/bin/bash
set -euo pipefail

# Validate tag and fixed package destinations before asking for credentials.
# Prints the npm dist-tag shared by all four packages.
dist_tag=$(node --input-type=commonjs - <<'NODE'
const fs = require('node:fs');
const packages = [
  ['packages/ui-api-client/package.json', '@qrun-io/qqq-ui-api-client'],
  ['packages/core/package.json', '@qrun-io/qqq-core'],
  ['packages/conformance/package.json', '@qrun-io/qqq-ui-api-conformance'],
  ['packages/cli/package.json', '@qrun-io/qqq-cli'],
];
for (const [path, expectedName] of packages) {
  const pkg = JSON.parse(fs.readFileSync(path, 'utf8'));
  if (pkg.name !== expectedName || pkg.publishConfig?.registry !== 'https://npm.pkg.github.com') {
    throw new Error('Unexpected GitHub Packages destination: ' + path);
  }
}
const client = JSON.parse(fs.readFileSync(packages[0][0], 'utf8'));
if (!process.env.CIRCLE_TAG || process.env.CIRCLE_TAG !== 'v' + client.version) {
  throw new Error('Version tag must match the client package version');
}
// The CLI pins core exactly and shares its version: publish only that pair.
const core = JSON.parse(fs.readFileSync(packages[1][0], 'utf8'));
const cli = JSON.parse(fs.readFileSync(packages[3][0], 'utf8'));
if (core.version !== cli.version || cli.dependencies?.['@qrun-io/qqq-core'] !== core.version) {
  throw new Error('Core package version must match the CLI version and its exact core dependency');
}
// Final releases become latest; any prerelease part (e.g. -rc.1, -beta.2) in
// any of the four keeps every package on rc, so latest never points at an rc.
const versions = packages.map(([path]) => JSON.parse(fs.readFileSync(path, 'utf8')).version);
console.log(versions.some((version) => version.includes('-')) ? 'rc' : 'latest');
NODE
)
: "${GITHUB_TOKEN:?GitHub Packages write credential GITHUB_TOKEN is required}"
export NODE_AUTH_TOKEN="$GITHUB_TOKEN"
# Store only an environment substitution, never the token itself.
npm_config=$(mktemp)
chmod 600 "$npm_config"
trap 'rm -f "$npm_config"' EXIT
cat > "$npm_config" <<'NPMRC'
@qrun-io:registry=https://npm.pkg.github.com
//npm.pkg.github.com/:_authToken=${NODE_AUTH_TOKEN}
NPMRC
export NPM_CONFIG_USERCONFIG="$npm_config"
# Fail closed if the Circle context token cannot authenticate to this registry.
# Authentication alone is not proof of package write permission; hosted publish
# migration remains gated on verifying the actual context's package access.
npm whoami --registry https://npm.pkg.github.com >/dev/null
npm publish -w @qrun-io/qqq-ui-api-client --registry https://npm.pkg.github.com --tag "$dist_tag"
npm publish -w @qrun-io/qqq-core --registry https://npm.pkg.github.com --tag "$dist_tag"
npm publish -w @qrun-io/qqq-ui-api-conformance --registry https://npm.pkg.github.com --tag "$dist_tag"
npm publish -w @qrun-io/qqq-cli --registry https://npm.pkg.github.com --tag "$dist_tag"
