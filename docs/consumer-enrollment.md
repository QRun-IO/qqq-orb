# Batch consumer enrollment

Use one target file for canonical consumers of every supported Circle profile and
legacy QBits whose jobs and publication filters the shared converter recognizes:

```json
[
  {"checkout": "/work/qbit-example", "default_branch": "main"},
  {"checkout": "/work/qqq", "default_branch": "develop"}
]
```

The branch values must come from repository inventory. Run on clean isolated
checkouts of the branches being migrated.

```sh
python tools/enroll_consumers.py targets.json --orb-version 0.8
python tools/enroll_consumers.py targets.json --orb-version 0.8 --write
```

The command validates the entire batch before writing. Existing manifests keep
all publication and profile options; only the managed orb version changes.
Recognized legacy QBits receive the canonical caller and inferred publication
policy. An unknown job, filter, profile option, duplicate target, symlink, or
concurrent declaration edit rejects the batch. Repeating a completed enrollment
makes no changes. Filesystem errors during the write phase can leave a partial
batch; rerun after correcting the error. This is not a filesystem transaction.

Only `.circleci/config.yml` and `.qqq-ci.yml` are changed. The tool does not delete
other workflows, infer publication from repository names, or enroll unknown
custom pipelines. Their behavior must first be represented by a central profile.
After committing and qualifying the exact source, apply the shared
[branch enforcement tool](branch-enforcement.md) to supported gate profiles.

This command provides batch source conversion. Remote discovery, signed PR
submission, merge reconciliation and scheduled enrollment are separate remaining
work; local conversion alone does not prove fleet deployment or release success.
