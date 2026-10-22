"""Discover current enrollment targets without assuming unknown repositories conform."""
import audit_estate


def approved_no_ci(target, request):
    """Recognize only unchanged documentation; executable/data sources still need inspection."""
    repo = target['repository']
    policy = audit_estate.NO_CI.get(repo)
    if policy is None:
        return None
    head = request(f'repos/{repo}/branches/{target["branch"]}')['commit']['sha']
    if head != policy['baseline_sha']:
        return None
    tree = request(f'repos/{repo}/git/trees/{head}?recursive=1')
    if tree.get('truncated') is not False or not isinstance(tree.get('tree'), list):
        raise ValueError('Approved no-CI snapshot requires a complete source tree')
    paths = {item['path'] for item in tree['tree']}
    if not set(policy['required_paths']) <= paths:
        raise ValueError('Approved no-CI identity paths are missing')
    if any(path in policy['forbidden_paths'] or any(path.startswith(prefix)
           for prefix in policy['forbidden_prefixes']) for path in paths):
        raise ValueError('Approved no-CI snapshot contains unexpected CI configuration')
    documents = {'LICENSE', 'NOTICE', '.gitignore', '.gitattributes', '.gitkeep'}
    for item in tree['tree']:
        if item.get('type') == 'tree':
            continue
        if item.get('type') != 'blob' or not (item['path'].endswith(('.md', '.txt')) or item['path'] in documents):
            return None
    return {**target, 'head': head, 'state': 'approved-no-ci',
            'source_kind': 'documentation-only', 'reason': policy['rationale']}


def discover(organization, version, inspect, request, inventory=None):
    """Inspect every active main/develop branch; retain unsupported results explicitly."""
    entries = audit_estate.discover_inventory(organization) if inventory is None else inventory
    plans, findings = [], []
    for entry in entries:
        repo = entry['nameWithOwner']
        if entry['isArchived']:
            findings.append({'repository': repo, 'state': 'archived'})
            continue
        if repo.lower() == (organization + '/qqq-orb').lower():
            findings.append({'repository': repo, 'state': 'owner-bootstrap',
                             'reason': 'Orb publisher is not its own consumer'})
            continue
        try:
            branches, page = [], 1
            while True:
                batch = request(f'repos/{repo}/branches?per_page=100&page={page}')
                if not isinstance(batch, list) or any(not isinstance(b, dict) or not isinstance(b.get('name'), str) for b in batch):
                    raise ValueError('Invalid branch inventory')
                branches.extend(b['name'] for b in batch)
                if len(batch) < 100:
                    break
                page += 1
            if len(set(branches)) != len(branches):
                raise ValueError('Duplicate branch inventory')
            selected = sorted(set(branches) & {'main', 'develop'})
            if not selected:
                raise ValueError('No current main/develop branch; explicit profile decision required')
        except (ValueError, OSError) as error:
            findings.append({'repository': repo, 'state': 'unresolved', 'reason': str(error)})
            continue
        for branch in selected:
            target = {'repository': repo, 'branch': branch}
            try:
                no_ci = approved_no_ci(target, request)
                if no_ci is not None:
                    findings.append(no_ci)
                else:
                    plans.append(inspect(target, version))
            except (ValueError, OSError) as error:
                findings.append({**target, 'state': 'unresolved', 'reason': str(error)})
    return plans, findings
