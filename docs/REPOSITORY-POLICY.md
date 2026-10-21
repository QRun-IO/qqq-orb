# Application-free branch verification

Use `profile: repository-policy` only on a branch containing repository policies,
documentation, workflow configuration and optional unused Maven wrappers. It uses
the same canonical setup caller as other profiles and one small Python verification
job. It checks tracked YAML/JSON syntax and rejects application manifests, source
files, unknown file types and symlinks. It never builds or publishes an application.

The manifest accepts only `profile`, `orb_version` and `default_branch`. The latter
remains the repository's actual default branch. A future application promotion must
select its real build profile in the same change; adding source without doing so fails.

Estate policy can set `branch_profiles: {main: repository-policy}` without changing
the default branch's application profile. Require the CircleCI `setup` and `verify`
checks on the policy branch. This profile does not establish application release
readiness or replace the build/release checks on source-bearing branches.
