"""One-action comparison of synthetic, source-distinct evidence; no effects."""
from contextlib import ExitStack
from dataclasses import asdict, FrozenInstanceError
import importlib
import itertools
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/long-horizon-engineering/scripts'


class CrossLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_path = sys.path[:]
        cls.names = ('cross_layer_verification', 'critical_execution_trace',
                     'runtime_safety_envelope', 'security_authority_chain', 'host_observer',
                     'host_observer_macos', 'runtime_binding', 'remote_runtime_binding',
                     'agent_runtime_integration')
        cls.saved_modules = {n: sys.modules.get(n) for n in cls.names}
        sys.path.insert(0, str(SCRIPTS))
        cls.c = importlib.import_module('critical_execution_trace')
        cls.r, cls.s = cls.c.rse, cls.c.sc
        cls.h = importlib.import_module('host_observer')
        cls.m = (importlib.import_module('cross_layer_verification')
                 if (SCRIPTS / 'cross_layer_verification.py').exists() else None)

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = cls.saved_path
        for name, module in cls.saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def setUp(self):
        self.assertIsNotNone(self.m, 'independent layers exist, but bounded Phase 4 verifier is missing')

    def effect(self, ref='ref:A', kind='FILE_WRITE', action='ref:action',
               correlation='CORRELATED', evidence=('ref:evidence',)):
        return (kind, ref, action, evidence, correlation)

    def value(self, **changes):
        args = dict(action_id='ref:action', declared_effects=(), authorized_effects=(),
                    adapter_observed_effects=(), host_observed_effects=(), target_reality_effects=(),
                    adapter_coverage='SCOPED_COMPLETE', host_coverage='SCOPED_COMPLETE',
                    target_reality_status='VERIFIED')
        args.update(changes)
        return self.m.VerificationInput(**args)

    def pair(self, value, a, b):
        return tuple(f for f in self.m.CrossLayerVerifier.verify(value)
                     if (f.layer_a, f.layer_b) == (a, b))

    def results(self, value, a, b):
        return [(f.effect_ref, f.result, f.reason) for f in self.pair(value, a, b)]

    def test_literal_directional_cases(self):
        # Catches reversed direction, class-only equality and lost EXTRA effects.
        a, b = self.effect(), self.effect('ref:B', 'FILE_READ')
        different = self.effect('ref:B')
        cases = (
            ('declared_effects', 'authorized_effects', 'DECLARED', 'AUTHORIZED'),
            ('authorized_effects', 'adapter_observed_effects', 'AUTHORIZED', 'ADAPTER_OBSERVED'),
            ('adapter_observed_effects', 'host_observed_effects', 'ADAPTER_OBSERVED', 'HOST_OBSERVED'),
        )
        for fa, fb, la, lb in cases:
            for left, right, want in (
                ((a,), (a,), [('ref:A', 'MATCH', 'EFFECT_MATCH')]),
                ((a,), (), [('ref:A', 'MISSING', 'EXPECTED_EFFECT_NOT_OBSERVED')]),
                ((a,), (different,), [('ref:A', 'DIVERGED', 'MATERIAL_EFFECT_DIFFERENCE')]),
                ((a,), (a, b), [('ref:B', 'EXTRA', 'UNEXPECTED_EFFECT_OBSERVED'),
                                ('ref:A', 'MATCH', 'EFFECT_MATCH')]),
                ((), (a,), [('ref:A', 'EXTRA', 'UNEXPECTED_EFFECT_OBSERVED')]),
            ):
                with self.subTest(pair=(la, lb), left=left, right=right):
                    self.assertEqual(self.results(self.value(**{fa: left, fb: right}), la, lb), want)

    def test_host_process_exec_match_uses_explicit_identity(self):
        e = self.effect(kind='PROCESS_EXEC')
        self.assertEqual(self.results(self.value(adapter_observed_effects=(e,), host_observed_effects=(e,)),
                         'ADAPTER_OBSERVED', 'HOST_OBSERVED'), [('ref:A', 'MATCH', 'EFFECT_MATCH')])

    def test_observation_absence_requires_scoped_complete_coverage(self):
        for field, coverage, a, b in (
            ('authorized_effects', 'adapter_coverage', 'AUTHORIZED', 'ADAPTER_OBSERVED'),
            ('adapter_observed_effects', 'host_coverage', 'ADAPTER_OBSERVED', 'HOST_OBSERVED'),
        ):
            for state, want in (('PARTIAL', 'NOT_OBSERVED'), ('UNKNOWN', 'UNKNOWN')):
                with self.subTest(field=field, coverage=state):
                    self.assertEqual(self.results(self.value(**{field: (self.effect(),), coverage: state}), a, b),
                                     [('ref:A', want, 'INSUFFICIENT_COVERAGE')])

    def test_gap_disallows_absence_but_preserves_positive_match(self):
        e = self.effect(kind='PROCESS_EXEC')
        value = self.value(adapter_observed_effects=(e,), host_gap=True)
        self.assertEqual(self.results(value, 'ADAPTER_OBSERVED', 'HOST_OBSERVED'),
                         [('ref:A', 'UNKNOWN', 'INSUFFICIENT_COVERAGE')])
        value = self.value(adapter_observed_effects=(e,), host_observed_effects=(e,), host_gap=True)
        f, = self.pair(value, 'ADAPTER_OBSERVED', 'HOST_OBSERVED')
        self.assertEqual((f.result, f.coverage_status), ('MATCH', 'UNKNOWN'))

    def test_other_action_and_uncorrelated_host_events_are_excluded(self):
        for e in (self.effect(action='ref:other'), self.effect(action=None, correlation='UNCORRELATED')):
            value = self.value(host_observed_effects=(e,), host_coverage='PARTIAL')
            self.assertEqual(self.pair(value, 'ADAPTER_OBSERVED', 'HOST_OBSERVED'), ())
            value = self.value(adapter_observed_effects=(self.effect(),), host_observed_effects=(e,),
                               host_coverage='PARTIAL')
            fs = self.pair(value, 'ADAPTER_OBSERVED', 'HOST_OBSERVED')
            self.assertEqual(len(fs), 1)
            self.assertIn(fs[0].result, ('UNKNOWN', 'NOT_OBSERVED'))

    def test_unresolved_link_cannot_match_or_be_extra_even_with_matching_action_ref(self):
        e = self.effect(correlation='UNRESOLVED_LINK')
        value = self.value(adapter_observed_effects=(self.effect(),), host_observed_effects=(e,))
        self.assertEqual(self.results(value, 'ADAPTER_OBSERVED', 'HOST_OBSERVED'),
                         [('ref:A', 'UNKNOWN', 'UNRESOLVED_CORRELATION')])
        self.assertEqual(self.results(self.value(host_observed_effects=(e,)), 'ADAPTER_OBSERVED', 'HOST_OBSERVED'),
                         [(None, 'UNKNOWN', 'UNRESOLVED_CORRELATION')])

    def test_every_layer_requires_the_current_action(self):
        for fa, fb, la, lb in (
            ('declared_effects', 'authorized_effects', 'DECLARED', 'AUTHORIZED'),
            ('authorized_effects', 'adapter_observed_effects', 'AUTHORIZED', 'ADAPTER_OBSERVED'),
            ('adapter_observed_effects', 'host_observed_effects', 'ADAPTER_OBSERVED', 'HOST_OBSERVED'),
            ('host_observed_effects', 'target_reality_effects', 'HOST_OBSERVED', 'TARGET_REALITY'),
        ):
            self.assertEqual(self.pair(self.value(**{fa: (self.effect(action='ref:other'),),
                                                    fb: (self.effect(action='ref:other'),)}), la, lb), ())

    def test_duplicate_or_incomplete_identity_never_establishes_match(self):
        a = self.effect()
        for left, right in (((a,), (a, a)), ((a, a), (a,)),
                            ((a,), (self.effect(None),)), ((self.effect(None),), (a,))):
            with self.subTest(left=left, right=right):
                fs = self.pair(self.value(authorized_effects=left, adapter_observed_effects=right),
                               'AUTHORIZED', 'ADAPTER_OBSERVED')
                self.assertTrue(fs)
                self.assertEqual({f.result for f in fs}, {'UNKNOWN'})
                self.assertEqual({f.reason for f in fs}, {'AMBIGUOUS_EFFECT_IDENTITY'})

    def test_multiple_different_candidates_do_not_pair_by_position(self):
        value = self.value(authorized_effects=(self.effect(),),
                           adapter_observed_effects=(self.effect('ref:B'), self.effect('ref:C')))
        fs = self.pair(value, 'AUTHORIZED', 'ADAPTER_OBSERVED')
        self.assertTrue(fs)
        self.assertEqual({f.result for f in fs}, {'UNKNOWN'})

    def test_unique_material_matches_survive_multiple_distinct_effects(self):
        a, b = self.effect(), self.effect('ref:B')
        self.assertEqual(self.results(self.value(authorized_effects=(a, b), adapter_observed_effects=(b, a)),
                         'AUTHORIZED', 'ADAPTER_OBSERVED'),
                         [('ref:A', 'MATCH', 'EFFECT_MATCH'), ('ref:B', 'MATCH', 'EFFECT_MATCH')])

    def test_unrelated_classes_never_diverge(self):
        fs = self.pair(self.value(authorized_effects=(self.effect(kind='PROCESS_EXEC'),),
                                 adapter_observed_effects=(self.effect('ref:B'),)),
                       'AUTHORIZED', 'ADAPTER_OBSERVED')
        self.assertEqual({f.result for f in fs}, {'MISSING', 'EXTRA'})

    def test_unsupported_semantics_are_unknown(self):
        e = self.effect(kind='UNSUPPORTED')
        fs = self.pair(self.value(declared_effects=(e,), authorized_effects=(e,)), 'DECLARED', 'AUTHORIZED')
        self.assertTrue(fs)
        self.assertEqual({(f.result, f.reason) for f in fs}, {('UNKNOWN', 'SEMANTICS_NOT_COMPARABLE')})

    def test_unavailable_source_is_not_supplied_empty_source(self):
        for changes in (dict(authorized_effects=None), dict(declared_effects=None)):
            fs = self.pair(self.value(**changes), 'DECLARED', 'AUTHORIZED')
            self.assertEqual([(f.effect_ref, f.result, f.reason) for f in fs],
                             [(None, 'UNKNOWN', 'SOURCE_UNAVAILABLE')])
        self.assertEqual(self.pair(self.value(), 'DECLARED', 'AUTHORIZED'), ())

    def test_omitted_source_is_unavailable_not_authoritatively_empty(self):
        value = self.m.VerificationInput('ref:action', declared_effects=(self.effect(),))
        self.assertEqual(self.results(value, 'DECLARED', 'AUTHORIZED'),
                         [(None, 'UNKNOWN', 'SOURCE_UNAVAILABLE')])

    def test_reality_unknown_dominates_even_empty_host_and_supplied_target(self):
        for host, reality in (((), ()), ((), (self.effect(),)), ((self.effect(),), (self.effect(),))):
            fs = self.pair(self.value(host_observed_effects=host, target_reality_effects=reality,
                                     target_reality_status='UNKNOWN'), 'HOST_OBSERVED', 'TARGET_REALITY')
            self.assertTrue(fs)
            self.assertEqual({(f.result, f.reason) for f in fs}, {('UNKNOWN', 'TARGET_REALITY_UNKNOWN')})

    def test_verified_reality_match_divergence_extra_and_absence(self):
        for left, right, want in (
            ((self.effect(),), (self.effect(),), [('ref:A', 'MATCH', 'EFFECT_MATCH')]),
            ((self.effect(),), (self.effect('ref:B'),), [('ref:A', 'DIVERGED', 'MATERIAL_EFFECT_DIFFERENCE')]),
            ((), (self.effect(),), [('ref:A', 'EXTRA', 'UNEXPECTED_EFFECT_OBSERVED')]),
            ((self.effect(),), (), [('ref:A', 'UNKNOWN', 'INSUFFICIENT_COVERAGE')]),
        ):
            self.assertEqual(self.results(self.value(host_observed_effects=left, target_reality_effects=right),
                             'HOST_OBSERVED', 'TARGET_REALITY'), want)

    def test_deterministic_order_is_independent_of_input_permutations(self):
        effects = (self.effect(), self.effect('ref:B', 'FILE_READ'), self.effect('ref:C'))
        first = None
        for ordering in itertools.permutations(effects):
            got = self.m.CrossLayerVerifier.verify(self.value(declared_effects=ordering, authorized_effects=effects,
                adapter_observed_effects=ordering, host_observed_effects=effects, target_reality_effects=ordering))
            serialized = json.dumps([asdict(f) for f in got], sort_keys=True)
            if first is None:
                first = serialized
            self.assertEqual(serialized, first)
            self.assertEqual([(f.layer_a, f.layer_b) for f in got][::3],
                [('DECLARED', 'AUTHORIZED'), ('AUTHORIZED', 'ADAPTER_OBSERVED'),
                 ('ADAPTER_OBSERVED', 'HOST_OBSERVED'), ('HOST_OBSERVED', 'TARGET_REALITY')])

    def test_deep_immutable_input_and_findings(self):
        refs = ['ref:evidence']
        effect = ['FILE_WRITE', 'ref:A', 'ref:action', refs, 'CORRELATED']
        collection = [effect]
        value = self.value(declared_effects=collection, authorized_effects=collection)
        before = asdict(value)
        refs.append('ref:later'); effect[1] = 'ref:later'; collection.clear()
        findings = self.m.CrossLayerVerifier.verify(value)
        self.assertEqual(asdict(value), before)
        f = findings[0]
        self.assertEqual((f.result, f.evidence_refs), ('MATCH', ('ref:evidence',)))
        with self.assertRaises(FrozenInstanceError):
            value.action_id = 'ref:changed'
        with self.assertRaises(FrozenInstanceError):
            f.result = 'EXTRA'

    def test_bounds_and_raw_objects_fail_closed_without_raw_error_text(self):
        marker = 'SYNTHETIC_PRIVATE_MARKER'
        invalid = (dict(action_id='/raw/path'), dict(declared_effects=[self.effect()] * 129),
                   dict(declared_effects=[self.effect(evidence=['ref:x'] * 17)]),
                   dict(declared_effects=[self.effect(marker)]), dict(adapter_coverage='COMPLETE'),
                   dict(target_reality_status='SUCCESS'), dict(host_gap=1),
                   dict(declared_effects=[{'secret': marker}]),
                   dict(declared_effects=[self.effect(action=marker)]))
        for change in invalid:
            with self.subTest(change=tuple(change)):
                with self.assertRaises(ValueError) as error:
                    self.value(**change)
                self.assertNotIn(marker, str(error.exception))

    def test_correlated_descriptor_requires_an_explicit_action_reference(self):
        with self.assertRaises(ValueError):
            self.value(host_observed_effects=(self.effect(action=None),))

    def test_source_fixtures_keep_declaration_authority_and_host_distinct(self):
        # Normalization lives with the trusted caller, never inside the verifier.
        bridge = importlib.import_module('agent_runtime_integration').AgentRuntimeBridge()
        context = self.c.TraceContext('trace', 'install', 'project', 'task', 'run', 'action',
                                      None, 'trusted', None, 'runtime')
        prepared = bridge.prepare(dict(proposal_id='p', requested_action_class='WRITE_FILE',
            requested_target='/repo/a', requested_parameters={'content_bytes': b'synthetic'},
            declared_effects={'writes': ('/repo/a',)}, reason_text='SYNTHETIC_PRIVATE_MARKER'),
            context=context, trusted_agent_id='agent',
            authorization_ref='auth', data_classification=self.r.DataClass.NON_SENSITIVE, now=1).prepared
        self.assertIsNotNone(prepared)
        action = prepared.action_request
        declaration = prepared.declared_effects
        observation = self.c.ObservedEffects(context, writes=('/repo/a',))
        policy = self.r.Policy('policy', self.r.PolicyLevel.CORE, frozenset({action.action_class}),
                               write_roots=('/repo',), allowed_capabilities=frozenset({action.capability}))
        auth = self.r.Authorization('auth', 'task', frozenset({action.action_class}), ('/repo/a',),
                                    frozenset({action.capability}), 100)
        decision = self.r.evaluate_policy(action, (policy,), auth, now=1)
        self.assertEqual(decision.disposition, 'ALLOW')
        # A grant/ALLOW alone is not an action commitment. The controller also
        # binds the prepared payload before treating that exact effect as A.
        commitment = {action.action_id: prepared.payload_digest}
        self.assertEqual(commitment[action.action_id], prepared.normalized_payload.digest())
        self.assertEqual((declaration.writes, observation.writes), (('/repo/a',), ('/repo/a',)))
        # This comparison slot is FILE_WRITE target only; the declaration does
        # not claim content, so do not substitute the full prepared payload ID.
        material_digest = self.s.artifact_digest(('FILE_WRITE', action.target))
        material = 'sha256:' + material_digest
        norm = lambda target, source: self.effect('sha256:' + self.s.artifact_digest(('FILE_WRITE', target)),
            evidence=('sha256:' + self.s.artifact_digest(source),))
        trace = self.c.CriticalTrace('trace', 'install')
        ingestor = self.h.HostObservationIngestor('observer', 'ref:provenance', trace=trace,
                                                 known_actions={'ref:action': context})
        host = self.h.HostObservation('20396-host-observation/v1', 'observer', 'ref:provenance',
            'session', 'event', 1, 1, 'FILE_WRITE', 'ref:action', 'ref:target',
            material_digest, 'PARTIAL')
        accepted = ingestor.ingest(host)
        self.assertEqual(accepted.correlation_status, 'CORRELATED')
        host_norm = self.effect('sha256:' + host.effect_digest, evidence=('sha256:' + accepted.cet_event_ref,))
        value = self.value(declared_effects=(norm(declaration.writes[0], declaration),),
            authorized_effects=(norm(action.target, auth),),
            adapter_observed_effects=(norm(observation.writes[0], observation),), host_observed_effects=(host_norm,),
            host_coverage=accepted.effective_coverage, target_reality_status='UNKNOWN')
        self.assertEqual([f.result for f in self.m.CrossLayerVerifier.verify(value)],
                         ['MATCH', 'MATCH', 'MATCH', 'UNKNOWN'])
        self.assertNotIn('SYNTHETIC_PRIVATE_MARKER', json.dumps([asdict(f) for f in self.m.CrossLayerVerifier.verify(value)]))

    def test_no_authority_reconciliation_execution_observer_or_storage_effects(self):
        local = importlib.import_module('runtime_binding')
        remote = importlib.import_module('remote_runtime_binding')
        agent = importlib.import_module('agent_runtime_integration')
        native = importlib.import_module('host_observer_macos')
        chain = self.s.InMemorySecurityChain('chain', 'install')
        trace = self.c.CriticalTrace('trace', 'install')
        journal = self.r.InMemorySecurityJournal()
        journal.append(self.r.JournalEntry(self.r._ref('action'), 'request', self.r.JournalState.UNKNOWN_OUTCOME))
        self.assertEqual(journal.latest('action').state, self.r.JournalState.UNKNOWN_OUTCOME)
        auth = self.r.Authorization('auth', 'task', frozenset({self.r.ActionClass.WRITE_FILE}),
                                   ('/repo/a',), frozenset({'filesystem.write'}), 100)
        broker = self.r.CapabilityBroker()
        actor = self.s.SecurityAuthority('runtime', self.s.AuthorityRole.RUNTIME, 'install')
        policy = self.r.Policy('policy', self.r.PolicyLevel.CORE)
        before = (asdict(auth), asdict(actor), asdict(policy), journal.latest('action'),
                  chain.records(), trace.events(), dict(broker._adapters))
        value = self.value(declared_effects=(self.effect(),), authorized_effects=(self.effect('ref:B'),),
                           target_reality_status='UNKNOWN')
        with ExitStack() as stack:
            for target in ('builtins.open', 'os.open', 'socket.socket', 'subprocess.Popen',
                           'threading.Thread.start', 'time.time', 'random.random', 'os.write',
                           'os.rename', 'os.unlink', 'os.mkdir', 'pathlib.Path.write_text',
                           'pathlib.Path.write_bytes'):
                stack.enter_context(patch(target, side_effect=AssertionError('VERIFIER_EFFECT')))
            for obj, name in ((self.s.InMemorySecurityChain, 'append'), (self.c.CriticalTrace, 'append'),
                (self.r.InMemorySecurityJournal, 'append'), (self.r.CapabilityBroker, 'register'),
                (self.r, 'reconcile'), (local.RuntimeBinding, 'execute'), (local.RuntimeBinding, 'reconcile'),
                (remote.RemoteRuntimeBinding, 'execute'), (remote.RemoteRuntimeBinding, 'reconcile'),
                (agent.AgentRuntimeBridge, 'execute'), (agent.AgentRuntimeBridge, 'reconcile'),
                (self.h.HostObservationIngestor, 'ingest'), (self.c, 'record_critical_event'),
                (self.r, 'evaluate_and_execute'), (native.MacOSExecObserver, '__init__'),
                (native.MacOSExecObserver, 'register'), (native.MacOSExecObserver, 'wait_for_exec'),
                (native.MacOSExecObserver, 'close')):
                stack.enter_context(patch.object(obj, name, side_effect=AssertionError('VERIFIER_EFFECT')))
            fs = self.m.CrossLayerVerifier.verify(value)
            self.assertEqual({f.result for f in fs}, {'DIVERGED', 'MISSING', 'UNKNOWN'})
        after = (asdict(auth), asdict(actor), asdict(policy), journal.latest('action'),
                 chain.records(), trace.events(), dict(broker._adapters))
        self.assertEqual(after, before)

    def test_existing_readback_must_establish_reality_before_normalization(self):
        local = importlib.import_module('runtime_binding')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / 'file'
            payload = local.RuntimePayload('action', content_bytes=b'synthetic-content')
            action = self.r.ActionRequest('action', 'run', 'task', self.r.ActionClass.WRITE_FILE,
                str(target), 'trusted', 'runtime', self.r.DataClass.NON_SENSITIVE,
                'auth', 'filesystem.write', 'write-file')
            adapter = local.FilesystemAdapter(workspace_root=str(root))
            self.assertEqual(adapter.reconcile(action, payload), self.r.ReconciliationOutcome.STILL_UNKNOWN)
            unknown = self.value(host_observed_effects=(self.effect(),), target_reality_status='UNKNOWN')
            self.assertEqual(self.pair(unknown, 'HOST_OBSERVED', 'TARGET_REALITY')[0].result, 'UNKNOWN')
            target.write_bytes(b'synthetic-content')  # Fixture setup, outside verifier.
            outcome = adapter.reconcile(action, payload)
            self.assertEqual(outcome, self.r.ReconciliationOutcome.EFFECT_APPLIED)
            journal = self.r.InMemorySecurityJournal()
            journal.append(self.r.JournalEntry(self.r._ref('action'), self.r._request_ref(action),
                                              self.r.JournalState.UNKNOWN_OUTCOME))
            receipt = self.r.reconcile(action, journal, lambda request: adapter.reconcile(request, payload))
            self.assertEqual(receipt.reconciliation_state, 'RECONCILED_SUCCESS')
            # A trusted caller uses the actual readback outcome and known bounded
            # target/content slot, never a success string or host observation alone.
            ref = 'sha256:' + self.s.artifact_digest((action.action_class.value, action.target,
                                                     payload.content_bytes.hex()))
            e = self.effect(ref, evidence=('sha256:' + self.s.artifact_digest(receipt),))
            value = self.value(host_observed_effects=(self.effect(ref),), target_reality_effects=(e,))
            before = (journal.history('action'), target.read_bytes())
            self.assertEqual(self.results(value, 'HOST_OBSERVED', 'TARGET_REALITY'),
                             [(ref, 'MATCH', 'EFFECT_MATCH')])
            self.assertEqual((journal.history('action'), target.read_bytes()), before)

    def test_close_timestamps_from_real_host_fixture_do_not_link_actions(self):
        context = self.c.TraceContext('trace', 'install', 'project', 'task', 'run', 'action',
                                      None, 'trusted', None, 'runtime')
        trace = self.c.CriticalTrace('trace', 'install')
        ingestor = self.h.HostObservationIngestor('observer', 'ref:provenance', trace=trace,
                                                 known_actions={'ref:action': context})
        host = self.h.HostObservation('20396-host-observation/v1', 'observer', 'ref:provenance',
            'session', 'event', 1, 1, 'PROCESS_EXEC', None, 'ref:pid-1', None, 'PARTIAL')
        result = ingestor.ingest(host)
        self.assertEqual(result.correlation_status, 'UNCORRELATED')
        normalized = self.effect(None, 'PROCESS_EXEC', host.action_id_ref, result.correlation_status,
                                 ('sha256:' + result.cet_event_ref,))
        value = self.value(adapter_observed_effects=(self.effect(kind='PROCESS_EXEC'),),
            host_observed_effects=(normalized,), host_coverage=result.effective_coverage)
        self.assertEqual(self.results(value, 'ADAPTER_OBSERVED', 'HOST_OBSERVED'),
                         [('ref:A', 'UNKNOWN', 'UNRESOLVED_CORRELATION')])

    def test_partial_source_and_gap_do_not_prove_extra_target_effect(self):
        for changes in (dict(host_coverage='PARTIAL'), dict(host_coverage='UNKNOWN'), dict(host_gap=True)):
            value = self.value(target_reality_effects=(self.effect(),), **changes)
            self.assertEqual(self.results(value, 'HOST_OBSERVED', 'TARGET_REALITY'),
                             [('ref:A', 'UNKNOWN', 'INSUFFICIENT_COVERAGE')])
        value = self.value(adapter_coverage='PARTIAL', host_observed_effects=(self.effect(),))
        self.assertEqual(self.results(value, 'ADAPTER_OBSERVED', 'HOST_OBSERVED'),
                         [('ref:A', 'UNKNOWN', 'INSUFFICIENT_COVERAGE')])

    def test_exact_match_with_incomplete_alternative_stays_unknown(self):
        value = self.value(authorized_effects=(self.effect(),),
                           adapter_observed_effects=(self.effect(), self.effect(None)))
        fs = self.pair(value, 'AUTHORIZED', 'ADAPTER_OBSERVED')
        self.assertEqual({(f.result, f.reason) for f in fs}, {('UNKNOWN', 'AMBIGUOUS_EFFECT_IDENTITY')})

    def test_findings_are_factual_and_show_both_divergent_refs(self):
        value = self.value(declared_effects=(self.effect(),), authorized_effects=(self.effect('ref:B'),),
                           adapter_observed_effects=(self.effect('ref:B'), self.effect('ref:C', 'FILE_READ')))
        findings = self.m.CrossLayerVerifier.verify(value)
        f = self.pair(value, 'DECLARED', 'AUTHORIZED')[0]
        self.assertEqual((f.effect_ref, f.compared_effect_ref), ('ref:A', 'ref:B'))
        serialized = json.dumps([asdict(x) for x in findings]).lower()
        for word in ('malicious', 'attack', 'exfiltration', 'compromised', 'lied', 'severity', 'confidence'):
            self.assertNotIn(word, serialized)


if __name__ == '__main__':
    unittest.main()
