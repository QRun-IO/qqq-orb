# Maven version preflight

The shared QQQ Maven version calculator rejects coordinates longer than 50
characters before changing POM files or starting versioned verification/deployment.
This applies to unchanged coordinates too. It does not shorten names, change commit
hashes, or expand runtime/storage limits. Use a shorter feature branch for snapshots.

The limit matches HelpBundles.load and HelpContent.bundleVersion's maxLength=50
in core. This is a shared publication constraint, including Maven artifacts without
bundles, so future bundle adoption cannot introduce incompatible coordinates.

Validation: 49/50/51-character boundaries, the original long feature branch,
unchanged oversized coordinates, and representative core/collaboration/Redis/session
and RC coordinates; no Maven mutation on failure. Existing calculator35 and
publication-contract5 tests pass. New Python tests run in the contract CI suite.

Issue QRun-IO/qqq#1312 remains open: actual filtered-resource coverage and the
runtime loader's misleading error require follow-up. The current job can perform
its initial unversioned compile before version calculation; this guard prevents
version mutation and subsequent versioned verification/deployment, not all setup.
