#!/usr/bin/env python3
"""Fetch and verify exact-source qqq-all Circle smoke evidence; never synthesize GH runs."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
from urllib.parse import urlparse

REPO = 'QRun-IO/qqq-all'
PROJECT = 'gh/' + REPO
UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


class EvidenceError(ValueError):
    pass


def require(value, message):
    if not value:
        raise EvidenceError(message)


def workflow_id(url):
    parsed = urlparse(url or '')
    require(parsed.scheme == 'https' and parsed.netloc == 'app.circleci.com', 'Untrusted Circle workflow URL')
    match = re.fullmatch('/workflow/(' + UUID + ')', parsed.path)
    require(match is not None, 'Unrecognized Circle workflow URL')
    return match.group(1)


def validate(sha, selected, workflow, pipeline, jobs, checks, siblings):
    require(re.fullmatch(r'[0-9a-f]{40}', sha or ''), 'Expected full release SHA')
    require(re.fullmatch(UUID, selected or ''), 'Expected workflow UUID')
    require(workflow.get('id') == selected and workflow.get('project_slug') == PROJECT,
            'Wrong workflow identity or project')
    require(workflow.get('name') == 'verify-and-smoke' and workflow.get('status') == 'success',
            'Smoke workflow is not successful')
    # A rerun may execute selected jobs only. Do not infer inherited successes.
    require(not workflow.get('rerun_of') and workflow.get('auto_rerun_number', 0) == 0,
            'Rerun ancestry is not supported')
    require(workflow.get('pipeline_id') == pipeline.get('id') and pipeline.get('project_slug') == PROJECT,
            'Wrong pipeline identity or project')
    vcs = pipeline.get('vcs', {})
    require(vcs.get('revision') == sha and vcs.get('branch') == 'develop' and not vcs.get('tag'),
            'Pipeline is not the exact develop source')
    require(vcs.get('origin_repository_url', '').removesuffix('.git') == 'https://github.com/' + REPO,
            'Wrong source repository')
    trigger = pipeline.get('trigger', {})
    require(trigger.get('type') == 'webhook' and bool(trigger.get('received_at'))
            and bool(trigger.get('actor', {}).get('login')), 'Unproven webhook trigger')
    candidates = [c for c in checks if c.get('name') == 'verify-and-smoke' and c.get('app', {}).get('id') == 18001]
    require(candidates, 'No Circle publisher check')
    latest = max(candidates, key=lambda c: c.get('id', 0))
    require(latest.get('head_sha') == sha and latest.get('status') == 'completed'
            and latest.get('conclusion') == 'success', 'Latest Circle check did not pass this source')
    require(workflow_id(latest.get('details_url')) == selected, 'Selected workflow is not the latest trusted check')
    same = [w for w in siblings if w.get('name') == 'verify-and-smoke']
    require(len(same) == 1 and same[0].get('id') == selected,
            'Multiple workflow attempts require explicit ancestry reconciliation')
    require(jobs and all(j.get('status') == 'success' and j.get('type') == 'build' for j in jobs),
            'Workflow has missing, skipped, canceled, approval, or unsuccessful jobs')
    for name in ('build-and-test', 'core', 'full'):
        matches = [j for j in jobs if j.get('name') == name]
        require(len(matches) == 1 and matches[0].get('job_number') and matches[0].get('id'),
                'Missing or duplicate required smoke job: ' + name)
    return {'schema': 'qqq-all-circle-smoke/v1', 'repository': REPO, 'sha': sha,
            'branch': 'develop', 'workflow_id': selected, 'pipeline_id': pipeline['id'],
            'check_run_id': latest['id'], 'workflow': workflow, 'pipeline': pipeline,
            'jobs': jobs, 'check_runs': checks, 'pipeline_workflows': siblings}


def gh(path):
    result = subprocess.run(['gh', 'api', '--method', 'GET', path], capture_output=True, timeout=60)
    require(result.returncode == 0, 'GitHub evidence read failed')
    return json.loads(result.stdout)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise EvidenceError('Circle API redirect refused')


def circle(path):
    token = os.environ.get('CIRCLECI_TOKEN')
    require(token, 'CIRCLECI_TOKEN is required for Circle evidence mode')
    request = urllib.request.Request('https://circleci.com/api/v2/' + path,
                                     headers={'Circle-Token': token, 'Accept': 'application/json'})
    with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
        raw = response.read(2_000_001)
    require(len(raw) <= 2_000_000, 'Evidence response exceeds bound')
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--workflow-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(re.fullmatch(UUID, args.workflow_id), 'Invalid workflow ID')
    require(re.fullmatch(r'[0-9a-f]{40}', args.sha), 'Invalid source SHA')
    workflow = circle('workflow/' + args.workflow_id)
    pipeline_id = workflow.get('pipeline_id', '')
    require(re.fullmatch(UUID, pipeline_id), 'Invalid pipeline ID')
    pipeline = circle('pipeline/' + pipeline_id)
    jobs = circle('workflow/' + args.workflow_id + '/job')
    siblings = circle('pipeline/' + pipeline_id + '/workflow')
    require(not jobs.get('next_page_token') and not siblings.get('next_page_token'),
            'Paginated workflow evidence requires reconciliation')
    checks = gh('repos/' + REPO + '/commits/' + args.sha + '/check-runs?filter=all&per_page=100')
    require(checks.get('total_count', 0) <= 100, 'Too many check runs to establish latest attempt')
    evidence = validate(args.sha, args.workflow_id, workflow, pipeline, jobs['items'], checks['check_runs'], siblings['items'])
    args.output.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print('Exact-source Circle smoke evidence verified')


if __name__ == '__main__':
    try:
        main()
    except (EvidenceError, OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        sys.exit('Circle smoke evidence rejected or unavailable; no release authorization')
