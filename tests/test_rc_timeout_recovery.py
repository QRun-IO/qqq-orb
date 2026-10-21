"""A timeout recovery must prove the original upload, not forgive a failed build."""
import copy
import unittest

from test_rc_guard import scope, SHA, OTHER, Failure, bump, status, evaluate

REPO = 'QRun-IO/qbit-alerts'
WORKFLOW = '86efe478-29d6-41a4-93f0-d74b178bf329'
DEPLOYMENT = '993e5a6d-23ce-4696-8e5a-9176ae19e670'
VERSION = '0.1.0-RC.17'
PURL = 'pkg:maven/com.kingsrook.qbits/qbit-alerts@' + VERSION


def evidence():
    publisher = status('failure')['check_runs'][0]
    publisher['details_url'] = 'https://app.circleci.com/workflow/' + WORKFLOW + '?utm_source=github'
    job = {'username': 'QRun-IO', 'reponame': 'qbit-alerts', 'vcs_revision': SHA,
           'branch': 'release/0.1', 'build_num': 148, 'status': 'failed', 'outcome': 'failed',
           'start_time': '2026-10-21T00:01:00Z',
           'workflows': {'workflow_name': 'publish_release_candidate',
                         'job_name': 'qqq-orb/mvn_publish', 'workflow_id': WORKFLOW},
           'steps': [{'actions': [{'name': 'Run Maven Verify', 'status': 'success'}]},
                     {'actions': [{'name': 'Publish to Sonatype Central (releases and SNAPSHOTs)',
                                   'status': 'timedout', 'timedout': True, 'step': 124, 'index': 0}]}]}
    return job, publisher


def validate(job, publisher):
    return scope['validate_timeout'](job, publisher, REPO, SHA, 'release/0.1', '148', '2026-10-21T00:00:00Z')


class TimeoutRecoveryTests(unittest.TestCase):
    def test_exact_upload_timeout_after_successful_verify(self):
        self.assertEqual((124, 0), validate(*evidence()))

    def test_other_source_branch_repository_or_attempt_is_rejected(self):
        for key, value in [('vcs_revision', OTHER), ('branch', 'develop'),
                           ('username', 'untrusted'), ('reponame', 'other'), ('build_num', 149)]:
            with self.subTest(key=key), self.assertRaises(Failure):
                job, publisher = evidence()
                job[key] = value
                validate(job, publisher)

    def test_non_circle_or_unrelated_workflow_cannot_authorize_recovery(self):
        for key, value in [('head_sha', OTHER), ('app', {'id': 1}), ('status', 'in_progress'),
                           ('conclusion', 'success'), ('name', 'test_only'),
                           ('details_url', 'https://example.com/workflow/' + WORKFLOW),
                           ('details_url', 'https://app.circleci.com/workflow/another')]:
            with self.subTest(key=key, value=value), self.assertRaises(Failure):
                job, publisher = evidence()
                publisher[key] = value
                validate(job, publisher)

    def test_prior_failure_or_missing_verify_never_becomes_release_success(self):
        for action in [{'name': 'Run Maven Verify', 'status': 'failed'},
                       {'name': 'Run Maven Verify', 'status': 'skipped'},
                       {'name': 'Some other build', 'status': 'success'}]:
            with self.subTest(action=action), self.assertRaises(Failure):
                job, publisher = evidence()
                job['steps'][0]['actions'][0] = action
                validate(job, publisher)

    def test_only_a_terminal_deployment_timeout_is_eligible(self):
        for change in [{'name': 'Run Maven Verify'}, {'timedout': False}, {'status': 'failed'},
                       {'step': -1}, {'index': '0'}]:
            with self.subTest(change=change), self.assertRaises(Failure):
                job, publisher = evidence()
                job['steps'][-1]['actions'][0].update(change)
                validate(job, publisher)

    def test_failed_later_git_push_is_not_an_upload_timeout(self):
        job, publisher = evidence()
        job['steps'].append({'actions': [{'name': 'Commit version', 'status': 'failed'}]})
        with self.assertRaises(Failure):
            validate(job, publisher)

    def test_publisher_cannot_predate_the_cut(self):
        job, publisher = evidence()
        job['start_time'] = '2026-10-20T23:59:00Z'
        with self.assertRaises(Failure):
            validate(job, publisher)

    def test_receipt_requires_one_upload_and_expected_staged_coordinates(self):
        log = ('[INFO] Installing x to /home/circleci/project/target/central-staging/'
               'com/kingsrook/qbits/qbit-alerts/' + VERSION + '/qbit-alerts-' + VERSION + '.pom\n'
               '[INFO] Uploaded bundle successfully, deployment name: Deployment, deploymentId: '
               + DEPLOYMENT + '. Deployment will publish automatically\n')
        self.assertEqual((DEPLOYMENT, [PURL]), scope['upload_receipt'](log, 'qbit-alerts', VERSION))
        for invalid in [log + log, log.replace('Uploaded bundle successfully', 'Upload failed'),
                        log.replace('qbit-alerts', 'qbit-other'), log.replace(VERSION, '0.1.0-RC.16')]:
            with self.subTest(invalid=invalid), self.assertRaises(Failure):
                scope['upload_receipt'](invalid, 'qbit-alerts', VERSION)

    def test_central_must_confirm_the_exact_receipt_and_all_coordinates(self):
        result = {'deploymentId': DEPLOYMENT, 'deploymentState': 'PUBLISHED', 'purls': [PURL]}
        scope['validate_deployment'](result, DEPLOYMENT, [PURL])
        for key, value in [('deploymentId', 'other'), ('deploymentState', 'PUBLISHING'),
                           ('deploymentState', 'FAILED'), ('purls', []), ('purls', [PURL, 'other'])]:
            with self.subTest(key=key, value=value), self.assertRaises(Failure):
                invalid = copy.deepcopy(result)
                invalid[key] = value
                scope['validate_deployment'](invalid, DEPLOYMENT, [PURL])

    def test_retry_bump_cannot_hide_other_source_changes(self):
        source = '<project><revision>0.1.0-RC.16</revision><name>Alerts</name></project>'
        actual = source.replace('0.1.0-RC.16', VERSION)
        commit = bump(version=VERSION)
        commit['files'] = [{'filename': 'pom.xml', 'status': 'modified'}]
        scope['validate_recovery_bump'](commit, source, actual, VERSION, SHA)
        for changed in [actual.replace('Alerts', 'Other'), actual + '<extra/>', source]:
            with self.subTest(changed=changed), self.assertRaises(Failure):
                scope['validate_recovery_bump'](commit, source, changed, VERSION, SHA)
        commit['files'].append({'filename': 'other.java', 'status': 'modified'})
        with self.assertRaises(Failure):
            scope['validate_recovery_bump'](commit, source, actual, VERSION, SHA)

    def test_recovery_still_requires_exact_bump_parent_and_verified_version(self):
        self.assertEqual(VERSION, evaluate(SHA, status('failure'), bump(version=VERSION), VERSION))
        for commit in [bump(parent=OTHER, version=VERSION), bump(version='0.1.0-RC.18')]:
            with self.subTest(commit=commit), self.assertRaises(Failure):
                evaluate(SHA, status('failure'), commit, VERSION)
        with self.assertRaises(Failure):
            evaluate(SHA, status('failure'), bump(version=VERSION))


if __name__ == '__main__':
    unittest.main()
