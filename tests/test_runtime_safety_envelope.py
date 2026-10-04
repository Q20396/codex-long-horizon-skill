"""Real kernel tests; adapters record synthetic calls and never perform effects."""
import importlib.util
from dataclasses import FrozenInstanceError, asdict, replace
from pathlib import Path
import sys
import unittest

PATH = Path(__file__).resolve().parents[1] / '.agents/skills/long-horizon-engineering/scripts/runtime_safety_envelope.py'


class EnvelopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if PATH.exists():
            spec = importlib.util.spec_from_file_location('runtime_safety_envelope', PATH)
            cls.m = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = cls.m
            spec.loader.exec_module(cls.m)

    def setUp(self):
        self.assertTrue(PATH.exists(), 'Phase 1 executable kernel is missing')
        m = self.m
        self.action = m.ActionRequest('a', 'run', 'task', m.ActionClass.WRITE_FILE,
                                      '/repo/docs/a', 'OpenAI', 'fake',
                                      m.DataClass.NON_SENSITIVE, 'auth',
                                      'filesystem.write', 'synthetic write')
        self.policy = m.Policy('core', m.PolicyLevel.CORE,
                               allowed_actions=frozenset(m.ActionClass),
                               read_roots=('/repo/docs',), write_roots=('/repo/docs',),
                               network_mode=m.NetworkMode.ALLOWLIST,
                               network_allowlist=('https://example.test:443',),
                               allowed_egress_classes=frozenset(m.DataClass),
                               allowed_capabilities=frozenset(m.CAPABILITIES.values()))
        self.auth = m.Authorization('auth', 'task', frozenset(m.ActionClass),
                                    ('/repo/docs/a',), frozenset(m.CAPABILITIES.values()), 100)
        self.calls = []
        calls = self.calls
        class Fake:
            def execute(inner, action):
                calls.append(action)
                return m.ExecutionResult(m.ExecutionState.KNOWN_SUCCESS, ('synthetic-evidence',))
        self.adapter = Fake()
        self.broker = m.CapabilityBroker()
        for cap in set(m.CAPABILITIES.values()):
            self.broker.register(cap, self.adapter)
        self.journal = m.InMemorySecurityJournal()

    def run_action(self, action=None, policies=None, auth='default', now=10):
        return self.m.evaluate_and_execute(
            action if action is not None else self.action,
            (self.policy,) if policies is None else policies,
            self.auth if auth == 'default' else auth,
            self.broker, self.journal, now)

    def denied(self, receipt, reason):
        self.assertEqual(receipt.policy_reason, reason)
        self.assertEqual(self.calls, [])

    def network(self):
        self.action = replace(self.action, action_class=self.m.ActionClass.NETWORK_REQUEST,
                              target='https://example.test/data', capability='network.request')
        self.auth = replace(self.auth, allowed_targets=(self.action.target,))

    def unknown(self):
        m = self.m
        calls = self.calls
        class Unknown:
            def execute(inner, action):
                calls.append(action)
                return m.ExecutionResult(m.ExecutionState.UNKNOWN_OUTCOME)
        self.broker = m.CapabilityBroker()
        self.broker.register('filesystem.write', Unknown())
        return self.run_action()

    def reconcile(self, outcome):
        return self.m.reconcile(self.action, self.journal, lambda action: outcome)

    def test_01_model_cannot_self_authorize(self):
        self.denied(self.run_action(auth=None), 'AUTHORIZATION_MISSING')

    def test_02_child_policy_cannot_expand_parent(self):
        parent = replace(self.policy, denied_actions=frozenset({self.action.action_class}))
        child = replace(self.policy, policy_id='task-policy', level=self.m.PolicyLevel.TASK)
        self.denied(self.run_action(policies=(parent, child)), 'ACTION_DENIED')

    def test_03_path_traversal_denied(self):
        self.denied(self.run_action(replace(self.action, target='/repo/docs/../secret')), 'PATH_OUT_OF_SCOPE')

    def test_04_sibling_prefix_denied(self):
        self.denied(self.run_action(replace(self.action, target='/repo/docs-private/a')), 'PATH_OUT_OF_SCOPE')

    def test_05_secret_egress_denied(self):
        self.network()
        self.denied(self.run_action(replace(self.action, data_classification=self.m.DataClass.SECRET)), 'DATA_EGRESS_DENIED')

    def test_06_local_only_egress_denied(self):
        self.network()
        self.denied(self.run_action(replace(self.action, data_classification=self.m.DataClass.LOCAL_ONLY)), 'DATA_EGRESS_DENIED')

    def test_07_unknown_egress_denied(self):
        self.network()
        self.denied(self.run_action(replace(self.action, data_classification=self.m.DataClass.UNKNOWN)), 'DATA_EGRESS_DENIED')

    def separated(self, granted, proposed):
        action = replace(self.action, action_class=proposed, capability=self.m.CAPABILITIES[proposed])
        if proposed in self.m.EGRESS_ACTIONS:
            action = replace(action, target='https://example.test/data')
        self.auth = replace(self.auth, allowed_actions=frozenset({granted}), allowed_targets=(action.target,))
        self.denied(self.run_action(action), 'AUTHORIZATION_MISSING')

    def test_08_write_does_not_authorize_stage(self):
        self.separated(self.m.ActionClass.WRITE_FILE, self.m.ActionClass.GIT_STAGE)

    def test_09_write_does_not_authorize_push(self):
        self.separated(self.m.ActionClass.WRITE_FILE, self.m.ActionClass.GIT_PUSH)

    def test_10_commit_does_not_authorize_merge(self):
        self.separated(self.m.ActionClass.GIT_COMMIT, self.m.ActionClass.PR_MERGE)

    def test_11_merge_does_not_authorize_release(self):
        self.separated(self.m.ActionClass.PR_MERGE, self.m.ActionClass.RELEASE)

    def test_12_missing_capability_denied(self):
        self.broker = self.m.CapabilityBroker()
        self.denied(self.run_action(), 'CAPABILITY_MISSING')

    def test_13_revoked_authorization_denied(self):
        self.denied(self.run_action(auth=replace(self.auth, revoked=True)), 'AUTHORIZATION_REVOKED')

    def test_14_expired_authorization_denied(self):
        self.denied(self.run_action(now=100), 'AUTHORIZATION_EXPIRED')

    def test_15_unknown_outcome_requires_reconciliation(self):
        result = self.unknown()
        self.assertEqual(result.final_disposition, 'REQUIRE_RECONCILIATION')
        self.assertEqual([e.state.value for e in self.journal.history('a')][-2:],
                         ['UNKNOWN_OUTCOME', 'RECONCILIATION_REQUIRED'])

    def test_16_unknown_outcome_does_not_retry(self):
        self.unknown()
        for _ in range(3):
            receipt = self.run_action()
            self.assertEqual(receipt.policy_reason, 'UNKNOWN_OUTCOME_PENDING')
            self.assertEqual(receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(len(self.calls), 1)

    def test_17_reconciled_success_does_not_retry(self):
        self.unknown()
        receipt = self.reconcile(self.m.ReconciliationOutcome.EFFECT_APPLIED)
        self.assertEqual(receipt.execution_state, 'RECONCILED_SUCCESS')
        for _ in range(2):
            self.assertEqual(self.run_action().final_disposition, 'ALREADY_COMPLETED')
        self.assertEqual(len(self.calls), 1)

    def test_18_reconciled_not_applied_requires_reevaluation(self):
        self.unknown()
        receipt = self.reconcile(self.m.ReconciliationOutcome.EFFECT_NOT_APPLIED)
        self.assertEqual(receipt.execution_state, 'RECONCILED_NOT_APPLIED')
        self.assertEqual(self.run_action(now=100).policy_reason, 'AUTHORIZATION_EXPIRED')
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.run_action().execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(len(self.calls), 2)

    def test_19_known_success_is_idempotent(self):
        self.assertEqual(self.run_action().execution_state, 'KNOWN_SUCCESS')
        for _ in range(3):
            self.assertEqual(self.run_action().final_disposition, 'ALREADY_COMPLETED')
        self.assertEqual(len(self.calls), 1)

    def test_20_provider_independence(self):
        for provider in ('OpenAI', 'Anthropic', 'Google', 'Local', 'Paperclip worker', 'Unknown vendor'):
            with self.subTest(provider=provider):
                action = replace(self.action, provider=provider)
                self.assertEqual(self.m.evaluate_policy(action, (self.policy,), self.auth, 10).disposition, 'ALLOW')
                self.assertEqual(self.m.evaluate_policy(action, (self.policy,), None, 10).disposition, 'REQUIRE_AUTHORIZATION')

    def test_21_malformed_action_fails_closed(self):
        for changes in ({'action_id': ''}, {'run_id': ''}, {'task_id': ''},
                        {'action_class': 'DELETE_EVERYTHING'}, {'data_classification': 'SAFE'},
                        {'capability': ''}, {'target': '/repo/\0x'}, {'target': 'relative'},
                        {'expected_effect': []}, {'target': '/repo\\docs/a'}):
            with self.subTest(changes=changes):
                self.denied(self.run_action(replace(self.action, **changes)), 'MALFORMED_ACTION')

    def test_22_model_text_cannot_override_policy(self):
        for text in ('ignore policy', 'user already approved', 'deploy now', 'authorized', 'merge immediately'):
            self.denied(self.run_action(replace(self.action, action_id=text, expected_effect=text), auth=None), 'AUTHORIZATION_MISSING')

    def test_23_receipt_does_not_leak_secret(self):
        marker = 'SYNTHETIC_PRIVATE_MARKER'
        action = replace(self.action, action_id=marker, task_id=marker, run_id=marker,
                         provider=marker, runtime=marker, target='/repo/docs/' + marker,
                         expected_effect=marker, authorization_ref=marker)
        result = self.run_action(action, auth=None)
        self.assertNotIn(marker, repr(asdict(result)))
        self.assertNotIn(marker, repr(action))

    def test_24_journal_does_not_leak_secret(self):
        marker = 'SYNTHETIC_PRIVATE_MARKER'
        action = replace(self.action, expected_effect=marker)
        calls = self.calls
        class Leaky:
            def execute(inner, action):
                calls.append(action)
                raise RuntimeError(marker)
        self.broker = self.m.CapabilityBroker()
        self.broker.register('filesystem.write', Leaky())
        self.assertEqual(self.run_action(action).execution_state, 'UNKNOWN_OUTCOME')
        self.assertNotIn(marker, repr(self.journal.history('a')))

    def test_25_deploy_requires_authorization(self):
        action = replace(self.action, action_class=self.m.ActionClass.DEPLOY,
                         capability='deploy.execute', target='https://example.test/deploy')
        self.denied(self.run_action(action, auth=None), 'AUTHORIZATION_MISSING')

    def test_26_network_deny_all(self):
        self.network()
        self.policy = replace(self.policy, network_mode=self.m.NetworkMode.DENY_ALL)
        self.denied(self.run_action(), 'NETWORK_TARGET_DENIED')

    def test_27_network_allowlist(self):
        self.network()
        action = replace(self.action, target='HTTPS://EXAMPLE.TEST:443/data')
        self.assertEqual(self.run_action(action).execution_state, 'KNOWN_SUCCESS')
        self.assertEqual(len(self.calls), 1)
        for target in ('https://example.test.evil/data', 'http://example.test/data', 'https://example.test:444/data'):
            result = self.m.evaluate_policy(replace(action, target=target), (self.policy,), self.auth, 10)
            self.assertEqual(result.reason, 'NETWORK_TARGET_DENIED')

    def test_28_move_requires_source_and_destination_scope(self):
        action = replace(self.action, action_class=self.m.ActionClass.MOVE_FILE, destination='/elsewhere/a')
        self.denied(self.run_action(action), 'PATH_OUT_OF_SCOPE')
        action = replace(action, action_id='move2', target='/elsewhere/a', destination='/repo/docs/a')
        self.denied(self.run_action(action), 'PATH_OUT_OF_SCOPE')
        action = replace(action, action_id='move3', target='/repo/docs/a', destination='/repo/docs/b')
        self.auth = replace(self.auth, allowed_targets=(action.target, action.destination))
        self.assertEqual(self.run_action(action).execution_state, 'KNOWN_SUCCESS')

    def test_29_capability_does_not_imply_authorization(self):
        self.denied(self.run_action(auth=None), 'AUTHORIZATION_MISSING')

    def test_30_authorization_does_not_imply_capability(self):
        self.broker = self.m.CapabilityBroker()
        self.denied(self.run_action(), 'CAPABILITY_MISSING')

    def test_invalid_policy_and_clock_fail_closed(self):
        for policies in ((), (replace(self.policy, revoked=True),),
                         (replace(self.policy, expires_at=10),),
                         (replace(self.policy, network_mode='ALLOW_EVERYTHING'),)):
            self.assertNotEqual(self.run_action(policies=policies).policy_disposition, 'ALLOW')
        for now in (float('nan'), float('inf'), True, -1):
            self.assertNotEqual(self.run_action(now=now).policy_disposition, 'ALLOW')
        self.assertEqual(self.calls, [])

    def test_authorization_is_bound_to_id_task_target_and_capability(self):
        for auth in (replace(self.auth, authorization_id='other'), replace(self.auth, task_id='other'),
                     replace(self.auth, allowed_targets=('/repo',)),
                     replace(self.auth, allowed_capabilities=frozenset())):
            self.denied(self.run_action(auth=auth), 'AUTHORIZATION_MISSING')

    def test_capability_cannot_be_substituted(self):
        self.denied(self.run_action(replace(self.action, capability='filesystem.read')), 'MALFORMED_ACTION')

    def test_broker_rejects_duplicate_or_unknown_registration(self):
        with self.assertRaises(ValueError):
            self.broker.register('filesystem.write', self.adapter)
        with self.assertRaises(ValueError):
            self.broker.register('model.magic', self.adapter)
        with self.assertRaises(LookupError):
            self.m.CapabilityBroker().get('filesystem.write')

    def test_immutable_policy_copies_mutable_inputs(self):
        allowed = {self.m.ActionClass.WRITE_FILE}
        policy = replace(self.policy, allowed_actions=allowed)
        allowed.clear()
        self.assertEqual(self.run_action(policies=(policy,)).execution_state, 'KNOWN_SUCCESS')
        with self.assertRaises(FrozenInstanceError):
            self.action.target = '/elsewhere'

    def test_still_unknown_and_failed_reconciliation_cannot_retry(self):
        self.unknown()
        self.reconcile(self.m.ReconciliationOutcome.STILL_UNKNOWN)
        self.assertEqual(self.run_action().policy_reason, 'UNKNOWN_OUTCOME_PENDING')
        self.reconcile('EFFECT_NOT_APPLIED')  # untyped/model result is not trusted evidence
        self.assertEqual(self.run_action().policy_reason, 'UNKNOWN_OUTCOME_PENDING')
        self.assertEqual(len(self.calls), 1)

    def test_reconciliation_cannot_rebind_action(self):
        self.unknown()
        invoked = []
        changed = replace(self.action, target='/repo/docs/b')
        self.m.reconcile(changed, self.journal, lambda a: invoked.append(a))
        self.assertEqual(invoked, [])
        self.assertEqual(self.run_action().policy_reason, 'UNKNOWN_OUTCOME_PENDING')

    def test_invalid_adapter_result_becomes_unknown(self):
        class Invalid:
            def execute(inner, action):
                self.calls.append(action)
                return 'success'
        self.broker = self.m.CapabilityBroker()
        self.broker.register('filesystem.write', Invalid())
        self.assertEqual(self.run_action().execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(self.run_action().policy_reason, 'UNKNOWN_OUTCOME_PENDING')
        self.assertEqual(len(self.calls), 1)

    def test_sensitive_egress_is_not_overridden_by_policy(self):
        self.network()
        self.denied(self.run_action(replace(self.action, data_classification=self.m.DataClass.SENSITIVE)), 'DATA_EGRESS_DENIED')

    def test_malformed_urls_rejected(self):
        self.network()
        for target in ('file:///repo/docs/a', 'https://user:password@example.test/a',
                       'https://example.test:bad/a', 'https://example.test/\na',
                       'https://example.test/a#fragment', 'https://example.test/a?token=synthetic'):
            self.denied(self.run_action(replace(self.action, target=target)), 'MALFORMED_ACTION')

    def test_success_requires_evidence_not_summary(self):
        m = self.m
        class Unverified:
            def execute(inner, action):
                self.calls.append(action)
                return m.ExecutionResult(m.ExecutionState.KNOWN_SUCCESS, (), 'success!')
        self.broker = m.CapabilityBroker()
        self.broker.register('filesystem.write', Unverified())
        self.assertEqual(self.run_action().execution_state, 'UNKNOWN_OUTCOME')

    def test_malformed_network_hostname_is_invalid_even_if_allowlisted(self):
        self.network()
        for host in ('bad!host', '.example.test', 'example..test', '-bad.test'):
            self.policy = replace(self.policy, network_allowlist=('https://' + host,))
            action = replace(self.action, target='https://' + host + '/data')
            self.auth = replace(self.auth, allowed_targets=(action.target,))
            self.denied(self.run_action(action), 'MALFORMED_ACTION')

    def test_concurrent_same_action_only_executes_once(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as pool:
            receipts = list(pool.map(lambda _: self.run_action(), range(8)))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(sum(r.final_disposition == 'ALREADY_COMPLETED' for r in receipts), 7)

    def test_reentrant_adapter_cannot_repeat_inflight_action(self):
        m = self.m
        nested = []
        class Reentrant:
            def execute(inner, action):
                self.calls.append(action)
                nested.append(self.run_action())
                return m.ExecutionResult(m.ExecutionState.KNOWN_SUCCESS, ('evidence',))
        self.broker = m.CapabilityBroker()
        self.broker.register('filesystem.write', Reentrant())
        self.assertEqual(self.run_action().execution_state, 'KNOWN_SUCCESS')
        self.assertEqual(nested[0].policy_reason, 'UNKNOWN_OUTCOME_PENDING')
        self.assertEqual(len(self.calls), 1)

    def test_journal_write_failure_before_attempt_cannot_execute(self):
        class Broken(self.m.InMemorySecurityJournal):
            def append(inner, entry):
                raise OSError('SYNTHETIC_PRIVATE_MARKER')
        self.journal = Broken()
        result = self.run_action()
        self.assertEqual(self.calls, [])
        self.assertEqual(result.policy_reason, 'JOURNAL_OR_BOUNDARY_FAILURE')
        self.assertNotIn('SYNTHETIC_PRIVATE_MARKER', repr(result))

    def test_journal_failure_after_attempt_does_not_allow_retry(self):
        m = self.m
        class Broken(m.InMemorySecurityJournal):
            def append(inner, entry):
                if entry.state == m.JournalState.KNOWN_SUCCESS:
                    raise OSError('synthetic failure')
                super().append(entry)
        self.journal = Broken()
        receipt = self.run_action()
        self.assertEqual(receipt.policy_reason, 'JOURNAL_OR_BOUNDARY_FAILURE')
        self.assertEqual(receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(self.run_action().policy_reason, 'UNKNOWN_OUTCOME_PENDING')
        self.assertEqual(len(self.calls), 1)

    def test_extreme_clock_values_return_decisions_without_exceptions(self):
        huge = 10 ** 1000
        for now, policy, auth in ((huge, self.policy, self.auth),
                                  (10, replace(self.policy, expires_at=huge), self.auth),
                                  (10, self.policy, replace(self.auth, expires_at=huge))):
            result = self.m.evaluate_policy(self.action, (policy,), auth, now)
            self.assertNotEqual(result.disposition, 'ALLOW')

    def test_adapter_evidence_and_summary_are_not_logged_raw(self):
        m = self.m
        marker = 'SYNTHETIC_PRIVATE_MARKER'
        class Evidence:
            def execute(inner, action):
                return m.ExecutionResult(m.ExecutionState.KNOWN_SUCCESS, (marker,), marker)
        self.broker = m.CapabilityBroker()
        self.broker.register('filesystem.write', Evidence())
        result = self.run_action()
        self.assertEqual(result.execution_state, 'KNOWN_SUCCESS')
        self.assertNotIn(marker, repr(result))
        self.assertNotIn(marker, repr(self.journal.history('a')))

    def test_secret_access_requires_all_gates(self):
        action = replace(self.action, action_class=self.m.ActionClass.SECRET_ACCESS,
                         target='synthetic-secret-reference', capability='secret.read',
                         data_classification=self.m.DataClass.SECRET)
        self.denied(self.run_action(action, auth=None), 'AUTHORIZATION_MISSING')
        self.auth = replace(self.auth, allowed_targets=(action.target,))
        self.assertEqual(self.run_action(action).execution_state, 'KNOWN_SUCCESS')

    def test_child_roots_and_egress_are_intersected(self):
        child = replace(self.policy, policy_id='task', level=self.m.PolicyLevel.TASK,
                        write_roots=('/repo/docs/subdir',))
        self.denied(self.run_action(policies=(self.policy, child)), 'PATH_OUT_OF_SCOPE')
        self.network()
        self.action = replace(self.action, action_id='network')
        child = replace(child, allowed_egress_classes=frozenset({self.m.DataClass.PUBLIC}))
        self.denied(self.run_action(policies=(self.policy, child)), 'DATA_EGRESS_DENIED')

    def test_module_body_has_no_import_time_effects(self):
        # Compile/read before guards: CPython loading source/dependencies is not
        # an effect initiated by the module. All dependencies are already loaded.
        import builtins
        import os
        import socket
        import subprocess
        import threading
        from contextlib import ExitStack
        from types import ModuleType
        from unittest.mock import patch
        code = compile(PATH.read_text(), str(PATH), 'exec')
        module = ModuleType('rse_import_probe')
        sys.modules[module.__name__] = module
        environment = dict(os.environ)
        try:
            with ExitStack() as stack:
                for owner, name in ((builtins, 'open'), (os, 'open'), (os, 'getenv'),
                                    (socket, 'socket'), (subprocess, 'Popen'),
                                    (threading.Thread, 'start'), (threading.Timer, 'start')):
                    stack.enter_context(patch.object(owner, name, side_effect=AssertionError('import side effect')))
                exec(code, module.__dict__)
            self.assertEqual(dict(os.environ), environment)
        finally:
            sys.modules.pop(module.__name__, None)

    def test_core_profile_ships_callable_kernel_without_repository_imports(self):
        import subprocess
        import tempfile
        root = PATH.parents[4]
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'profile'
            result = subprocess.run([sys.executable, '-B', str(root / 'scripts/assemble_skill_profile.py'),
                                     '--profile', 'core-only', '--output-root', str(target), '--apply'],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            installed = target / '.agents/skills/long-horizon-engineering'
            self.assertTrue((installed / 'scripts/runtime_safety_envelope.py').is_file())
            self.assertTrue((installed / 'references/runtime-safety-envelope.md').is_file())
            result = subprocess.run([sys.executable, '-I', '-B', '-c',
                                     'import sys; sys.path.insert(0, sys.argv[1]); '
                                     'import runtime_safety_envelope as r; '
                                     'assert r.evaluate_policy(None, (), None, 0).disposition == "INVALID"',
                                     str(installed / 'scripts')], cwd=temporary,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
