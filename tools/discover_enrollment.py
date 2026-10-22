"""Discover current enrollment targets without assuming unknown repositories conform."""
import audit_estate


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
                plans.append(inspect(target, version))
            except (ValueError, OSError) as error:
                findings.append({**target, 'state': 'unresolved', 'reason': str(error)})
    return plans, findings
