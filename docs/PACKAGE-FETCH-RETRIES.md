# CI package fetch failures

Java bootstrap and Next browser dependency setup use APT's native three retries
after the initial fetch, with 30-second HTTP/HTTPS inactivity timeouts. APT update
fails if any required index cannot be downloaded; stale indexes must not silently
turn an exhausted fetch into a successful setup. Signature and checksum checks
remain enabled. Next dependency installation also has a ten-minute step limit.
These settings retry downloads, not builds or tests. Existing required gates stay
unchanged, and terminal APT errors retain the failing URL and HTTP status.

`python3 tests/test_apt_fetch_policy.py` uses actual apt-helper against a local
HTTP fixture. It checks a normal download, recovery after two HTTP 503 responses,
four-attempt exhaustion, immediate HTTP 404 failure, and checksum rejection.
Run on Debian/Ubuntu with Python and APT; no external network is needed. The test
is included in the existing CircleCI contract suite and `make test-pipelines`.

Validation performed locally: actual APT fixture in both python:3.12-slim and the
cached Ubuntu Next CI image; existing Java/browser installation regression
scripts; Next worker gate preservation tests; Maven CI contract tests; actionlint;
shellcheck; YAML parsing; and orb packing. Official authenticated CircleCI schema
validation is pending approval to transmit the configuration to CircleCI.

Related: QRun-IO/qqq#1307. No release rerun or successful full-browser-matrix claim
is implied by these local checks. Publish and adopt the shared workflow change
before rerunning the current frontend candidate's full acceptance matrix.
