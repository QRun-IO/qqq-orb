"""Exercise the exact inline evaluator shipped in the reusable workflow."""
import pathlib
import textwrap
import unittest

source = pathlib.Path(__file__).resolve().parents[1].joinpath('.github/workflows/qbit-release-rc.yml').read_text()
code = source.split('          # BEGIN RC GUARD\n', 1)[1].split('          # END RC GUARD', 1)[0]
scope = {}
exec(textwrap.dedent(code), scope)
evaluate = scope['evaluate']
validate_central = scope['validate_central']
Failure = scope['ReleaseFailure']
SHA = 'a' * 40
OTHER = 'b' * 40


def status(state='success', sha=SHA):
    return {'sha': sha, 'check_runs': [{'id': 9, 'name': 'publish_release_candidate', 'app': {'id': 18001}, 'head_sha': sha, 'status': 'in_progress' if state == 'pending' else 'completed', 'conclusion': state}]}


def bump(parent=SHA, version='1.2.3-RC.4'):
    return {'sha': OTHER, 'parents': [{'sha': parent}], 'commit': {'message': f'Bump version to {version} [skip ci]'}}


class ReleaseGuardTests(unittest.TestCase):
    def test_success_exact_built_source(self):
        self.assertEqual('1.2.3-RC.4', evaluate(SHA, status(), bump()))

    def test_terminal_failure_stops_even_if_valid_bump_exists(self):
        for state in ('failure', 'error'):
            with self.subTest(state=state), self.assertRaisesRegex(Failure, 'CircleCI failed'):
                evaluate(SHA, status(state), bump())

    def test_other_sha_status_never_authorizes_or_fails_this_release(self):
        with self.assertRaisesRegex(Failure, 'exact release merge'):
            evaluate(SHA, status('success', OTHER), bump())

    def test_pending_or_absent_publisher_cannot_finalize(self):
        self.assertEqual('', evaluate(SHA, status('pending'), bump()))
        self.assertEqual('', evaluate(SHA, {'sha': SHA, 'check_runs': []}, bump()))

    def test_old_bump_waits_while_current_publisher_running(self):
        self.assertEqual('', evaluate(SHA, status('pending'), bump(OTHER)))

    def test_successful_publisher_with_wrong_source_bump_is_rejected(self):
        with self.assertRaisesRegex(Failure, 'direct child'):
            evaluate(SHA, status(), bump(OTHER))

    def test_merge_commit_or_ga_bump_cannot_finalize_rc(self):
        self.assertEqual('', evaluate(SHA, status(), {'commit': {'message': 'Merge develop'}}))
        self.assertEqual('', evaluate(SHA, status(), bump(version='1.2.3')))

    def test_duplicate_delivery_evaluates_same_immutable_candidate(self):
        self.assertEqual(evaluate(SHA, status(), bump()), evaluate(SHA, status(), bump()))
        action = scope['tag_action']
        self.assertEqual('complete', action(OTHER, OTHER, True, ''))
        self.assertEqual('release', action(OTHER, OTHER, False, SHA))
        self.assertEqual('tag', action('', OTHER, False, SHA))
        with self.assertRaises(Failure): action(SHA, OTHER, True, SHA)
        with self.assertRaises(Failure): action(OTHER, OTHER, False, '')

    def test_other_success_context_cannot_authorize_publication(self):
        result = status()
        result['check_runs'][0]['name'] = 'test_only'
        self.assertEqual('', evaluate(SHA, result, bump()))

    def test_wrong_app_and_stale_success_cannot_authorize_release(self):
        result = status()
        result['check_runs'][0]['app']['id'] = 999
        self.assertEqual('', evaluate(SHA, result, bump()))
        result = status()
        newer = dict(result['check_runs'][0], id=10, conclusion='failure')
        result['check_runs'].append(newer)
        with self.assertRaisesRegex(Failure, 'CircleCI failed'):
            evaluate(SHA, result, bump())

    def test_trusted_intent_and_wrong_run_attempt_or_repository(self):
        run = {'id': 7, 'status': 'completed', 'conclusion': 'success', 'event': 'workflow_dispatch',
               'path': '.github/workflows/release-rc.yml', 'repository': {'full_name': 'QRun-IO/qbit-test'},
               'head_repository': {'full_name': 'QRun-IO/qbit-test'}, 'run_attempt': 1}
        intent = {'repo': 'QRun-IO/qbit-test', 'merge_sha': SHA, 'branch': 'release/1.2', 'run_id': '7', 'attempt': '1'}
        check = scope['validate_intent']
        check(run, intent, 'QRun-IO/qbit-test', SHA, 'release/1.2', '7')
        for field, value in [('conclusion', 'failure'), ('run_attempt', 2), ('id', 8),
                             ('path', '.github/workflows/other.yml'), ('event', 'repository_dispatch'),
                             ('head_repository', {'full_name': 'attacker/fork'})]:
            with self.subTest(field=field), self.assertRaises(Failure):
                check(dict(run, **{field: value}), intent, 'QRun-IO/qbit-test', SHA, 'release/1.2', '7')

    def test_lock_does_not_let_stale_finalizer_clear_new_cut(self):
        check = scope['validate_lock']
        check(SHA, SHA)
        check('', SHA, completed=True)
        for current in ('', OTHER):
            with self.subTest(current=current), self.assertRaises(Failure):
                check(current, SHA)
        with self.assertRaises(Failure):
            check(OTHER, SHA, completed=True)

    def test_central_late_arrival_is_accepted_but_old_artifact_rejected(self):
        xml = '<project xmlns="http://maven.apache.org/POM/4.0.0"><artifactId>qbit-test</artifactId><version>1.2.3-RC.4</version></project>'
        validate_central('1.2.3-RC.4', 'qbit-test', xml, 'Tue, 20 Oct 2026 12:00:01 GMT', '2026-10-20T12:00:00Z')
        with self.assertRaisesRegex(Failure, 'predates'):
            validate_central('1.2.3-RC.4', 'qbit-test', xml, 'Tue, 20 Oct 2026 11:59:59 GMT', '2026-10-20T12:00:00Z')
        with self.assertRaisesRegex(Failure, 'artifact/version'):
            validate_central('1.2.3-RC.5', 'qbit-test', xml, 'Tue, 20 Oct 2026 12:00:01 GMT', '2026-10-20T12:00:00Z')


if __name__ == '__main__':
    unittest.main()
