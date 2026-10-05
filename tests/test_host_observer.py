"""Synthetic trusted host evidence: no real sensor or effect execution."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, FrozenInstanceError, replace
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SKILL = Path('.agents/skills/long-horizon-engineering')
SCRIPTS = ROOT / SKILL / 'scripts'


class HostObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_path = sys.path[:]
        cls.names = ('host_observer', 'critical_execution_trace', 'runtime_safety_envelope',
                     'security_authority_chain', 'runtime_binding', 'remote_runtime_binding',
                     'agent_runtime_integration')
        cls.saved_modules = {n: sys.modules.get(n) for n in cls.names}
        sys.path.insert(0, str(SCRIPTS))
        cls.c = importlib.import_module('critical_execution_trace')
        cls.h = (importlib.import_module('host_observer')
                 if (SCRIPTS / 'host_observer.py').exists() else None)

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = cls.saved_path
        for name, module in cls.saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def setUp(self):
        self.trace = self.c.CriticalTrace('trace', 'install')

    def observation(self, **kwargs):
        self.assertIsNotNone(self.h, 'trusted host ingestion is missing')
        args = dict(schema_version='20396-host-observation/v1', observer_id='observer',
                    provenance_ref='ref:provenance', session_id='session', observation_id='one',
                    sequence=1, observed_at=1, event_class='FILE_WRITE', action_id_ref=None,
                    target_ref='ref:opaque-target', effect_digest='a' * 64, coverage='SCOPED_COMPLETE')
        args.update(kwargs)
        return self.h.HostObservation(**args)

    def context(self, action='action'):
        return self.c.TraceContext('trace', 'install', 'project', 'task', 'run', action,
                                   None, 'trusted', None, 'runtime')

    def ingestor(self, **kwargs):
        self.assertIsNotNone(self.h, 'trusted host ingestion is missing')
        return self.h.HostObservationIngestor('observer', 'ref:provenance', trace=self.trace, **kwargs)

    def test_host_source_available(self):
        self.assertIn('HOST_OBSERVED', {source.value for source in self.c.ObservationSource})

    def test_coarse_git_effect_is_retained_without_push_claim(self):
        result = self.ingestor().ingest(self.observation(event_class='GIT_EFFECT'))
        self.assertTrue(result.accepted)
        event, = self.trace.events()
        self.assertEqual((event.source.value, event.event_type.value), ('HOST_OBSERVED', 'GIT_EFFECT'))
        self.assertIsNone(event.destination)
        self.assertIsNone(event.capability)
        self.assertEqual(event.status.value, 'OBSERVED')

    def test_coarse_remote_effect_is_retained_without_success_claim(self):
        result = self.ingestor().ingest(self.observation(event_class='REMOTE_EFFECT'))
        self.assertTrue(result.accepted)
        event, = self.trace.events()
        self.assertEqual((event.source.value, event.event_type.value), ('HOST_OBSERVED', 'REMOTE_EFFECT'))
        self.assertEqual(event.status.value, 'OBSERVED')
        self.assertNotIn('http', json.dumps(asdict(event)).lower())

    def test_host_move_retains_opaque_reference_without_fabricated_paths(self):
        result = self.ingestor().ingest(self.observation(event_class='FILE_MOVE'))
        self.assertTrue(result.accepted)
        event, = self.trace.events()
        self.assertEqual((event.source.value, event.event_type.value), ('HOST_OBSERVED', 'FILE_MOVE'))
        self.assertTrue(event.target.startswith('sha256:'))
        self.assertIsNone(event.destination)

    def test_valid_observation_is_immutable_and_anchors_existing_chain(self):
        chain = self.c.sc.InMemorySecurityChain('chain', 'install')
        actor = self.c.sc.SecurityAuthority('actor', self.c.sc.AuthorityRole.RUNTIME, 'install')
        observation = self.observation()
        with self.assertRaises(FrozenInstanceError):
            observation.sequence = 2
        result = self.ingestor(chain=chain, actor=actor).ingest(observation)
        self.assertEqual((result.accepted, result.reason, result.correlation_status),
                         (True, 'ACCEPTED', 'UNCORRELATED'))
        self.assertEqual(result.effective_coverage, 'SCOPED_COMPLETE')
        self.assertEqual(len(chain.records()), 1)
        self.assertEqual(chain.records()[0].event_type, 'CRITICAL_TRACE_EVENT')
        self.assertEqual(chain.records()[0].schema_version, '20396-security-chain/v1')
        self.assertEqual(result.chain_ref, chain.records()[0].record_hash)
        self.assertEqual(result.cet_event_ref, self.c.sc.artifact_digest(self.trace.events()[0]))
        self.assertTrue(chain.verify().valid)

    def test_observer_and_provenance_spoofs_do_not_emit(self):
        ingestor = self.ingestor()
        for change in ({'observer_id': 'imposter'}, {'provenance_ref': 'ref:spoof'}):
            result = ingestor.ingest(self.observation(**change))
            self.assertEqual((result.accepted, result.reason), (False, 'UNTRUSTED_OBSERVER'))
        self.assertEqual(self.trace.events(), ())

    def test_normal_sequence_rollback_and_duplicate_sequence(self):
        ingestor = self.ingestor()
        for sequence in (1, 2, 3):
            self.assertTrue(ingestor.ingest(self.observation(sequence=sequence, observation_id=str(sequence))).accepted)
        for sequence in (2, 3):
            result = ingestor.ingest(self.observation(sequence=sequence, observation_id='new'))
            self.assertEqual((result.accepted, result.reason), (False, 'OBSERVATION_SEQUENCE_INVALID'))
        self.assertEqual(len(self.trace.events()), 3)

    def test_gap_remains_partial_for_session_after_contiguous_event_and_revisit(self):
        ingestor = self.ingestor()
        ingestor.ingest(self.observation(sequence=5))
        gap = ingestor.ingest(self.observation(sequence=7, observation_id='gap'))
        self.assertEqual((gap.accepted, gap.reason, gap.effective_coverage), (True, 'SEQUENCE_GAP', 'PARTIAL'))
        ingestor.ingest(self.observation(session_id='new', observation_id='restart'))
        later = ingestor.ingest(self.observation(sequence=8, observation_id='later'))
        self.assertEqual(later.effective_coverage, 'PARTIAL')
        self.assertEqual(ingestor.ingest(self.observation(sequence=4, observation_id='old')).reason,
                         'OBSERVATION_SEQUENCE_INVALID')

    def test_new_session_can_restart(self):
        ingestor = self.ingestor()
        self.assertTrue(ingestor.ingest(self.observation(sequence=100)).accepted)
        self.assertTrue(ingestor.ingest(self.observation(session_id='new', observation_id='two')).accepted)

    def test_duplicate_id_is_idempotent_and_conflict_does_not_overwrite(self):
        chain = self.c.sc.InMemorySecurityChain('chain', 'install')
        actor = self.c.sc.SecurityAuthority('actor', self.c.sc.AuthorityRole.RUNTIME, 'install')
        ingestor = self.ingestor(chain=chain, actor=actor)
        observation = self.observation()
        first = ingestor.ingest(observation)
        duplicate = ingestor.ingest(observation)
        self.assertEqual((duplicate.accepted, duplicate.reason), (False, 'IDEMPOTENT_DUPLICATE'))
        self.assertEqual(duplicate.cet_event_ref, first.cet_event_ref)
        self.assertEqual(ingestor.ingest(replace(observation, sequence=2)).reason, 'OBSERVATION_ID_CONFLICT')
        self.assertEqual((len(self.trace.events()), len(chain.records())), (1, 1))

    def test_explicit_correlation_absent_unknown_and_chronology(self):
        known = {'ref:action': self.context()}
        ingestor = self.ingestor(known_actions=known)
        known.clear()  # Caller mutation must not change the trusted snapshot.
        for sequence, link, status in ((1, 'ref:action', 'CORRELATED'),
                                       (2, None, 'UNCORRELATED'),
                                       (3, 'ref:unknown', 'UNRESOLVED_LINK')):
            result = ingestor.ingest(self.observation(sequence=sequence, observation_id=str(sequence),
                                                     action_id_ref=link, observed_at=1))
            self.assertTrue(result.accepted)
            self.assertEqual(result.correlation_status, status)
        self.assertEqual(len(self.trace.events_for_action('action')), 1)

    def test_malformed_fields_fail_closed(self):
        self.assertIsNotNone(self.h, 'trusted host ingestion is missing')
        bad = {'schema_version': ('wrong',), 'observer_id': ('', [], True),
               'session_id': ('', 'x' * 129), 'observation_id': ('', 'bad\n'),
               'sequence': (True, 0, -1, 1.5, 2**54),
               'observed_at': (True, -1, float('nan'), float('inf'), 2**54),
               'event_class': ('GIT_PUSH', 'ARBITRARY', []),
               'coverage': ('COMPLETE', 'FULL', 'KERNEL_COMPLETE', []),
               'target_ref': ('/private/path', 'https://test/?token=synthetic', 'ref:', {}),
               'action_id_ref': ('bad link',), 'provenance_ref': ('https://test',),
               'effect_digest': ('a', 'A' * 64, [])}
        for field, values in bad.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        self.observation(**{field: value})
        self.assertEqual(self.ingestor().ingest(object()).reason, 'MALFORMED_OBSERVATION')

    def test_coverage_values_and_optional_refs(self):
        for coverage in ('SCOPED_COMPLETE', 'PARTIAL', 'UNKNOWN'):
            self.trace = self.c.CriticalTrace('trace', 'install')
            result = self.ingestor().ingest(self.observation(coverage=coverage, target_ref=None,
                                                           effect_digest=None))
            self.assertTrue(result.accepted)
            self.assertEqual(result.effective_coverage, coverage)

    def test_public_cet_cannot_construct_host_or_coarse_adapter_events(self):
        self.assertIn('HOST_OBSERVED', {source.value for source in self.c.ObservationSource})
        for source, kind in (('HOST_OBSERVED', 'FILE_WRITE'), ('HOST_OBSERVED', 'FILE_MOVE'),
                             ('ADAPTER_OBSERVED', 'GIT_EFFECT'), ('ADAPTER_OBSERVED', 'REMOTE_EFFECT')):
            with self.subTest(source=source, kind=kind):
                with self.assertRaises(ValueError):
                    self.c.CriticalEvent('forged', self.c.CriticalEventType[kind], self.context(),
                        self.c.ObservationSource[source], 1, 'ref:opaque', self.c.rse.DataClass.PUBLIC)
        with self.assertRaises(ValueError):
            self.c.ObservedEffects(self.context(), source=self.c.ObservationSource.HOST_OBSERVED)

    def test_adapter_move_still_requires_two_concrete_paths(self):
        args = ('move', self.c.CriticalEventType.FILE_MOVE, self.context(),
                self.c.ObservationSource.ADAPTER_OBSERVED, 1, '/repo/a', self.c.rse.DataClass.PUBLIC)
        with self.assertRaises(ValueError):
            self.c.CriticalEvent(*args)
        event = self.c.CriticalEvent(*args, destination='/repo/b')
        self.assertEqual((event.target, event.destination), ('/repo/a', '/repo/b'))

    def test_source_separation_and_no_automatic_cross_layer_verdict(self):
        context = self.context()
        adapter = self.c.CriticalEvent('adapter', self.c.CriticalEventType.FILE_WRITE, context,
            self.c.ObservationSource.ADAPTER_OBSERVED, 1, '/repo/a', self.c.rse.DataClass.PUBLIC)
        self.trace.append(adapter)
        ingestor = self.ingestor(known_actions={'ref:action': context})
        ingestor.ingest(self.observation(action_id_ref='ref:action'))
        ingestor.ingest(self.observation(sequence=2, observation_id='extra', event_class='NETWORK_REQUEST',
                                        action_id_ref='ref:action'))
        analysis = self.c.analyze_trace(self.trace, (self.c.DeclaredEffects(context, writes=('/repo/a',)),),
                                      internal_network_origins=(), approved_network_origins=())
        self.assertEqual({event.source.value for event in self.trace.events()},
                         {'ADAPTER_OBSERVED', 'HOST_OBSERVED'})
        self.assertEqual((analysis.event_count, analysis.observed_event_count), (3, 1))
        self.assertEqual((analysis.divergences, analysis.risk_findings), ((), ()))

    def test_evidence_cannot_authorize_or_reconcile_unknown_action(self):
        rse = self.c.rse
        action = rse.ActionRequest('action', 'run', 'task', rse.ActionClass.WRITE_FILE, '/repo/a',
            'trusted', 'runtime', rse.DataClass.PUBLIC, None, 'filesystem.write', 'synthetic')
        receipt = replace(rse._receipt(action, rse.PolicyDecision('REQUIRE_AUTHORIZATION', 'NO_AUTHORIZATION')),
                          execution_state='UNKNOWN_OUTCOME', reconciliation_state='STILL_UNKNOWN')
        before = asdict(receipt)
        broker = rse.CapabilityBroker()
        self.ingestor(known_actions={'ref:action': self.context()}).ingest(
            self.observation(action_id_ref='ref:action'))
        correlation = self.c.correlate_rse(action, receipt, self.trace.events()[0], attempt_linked=True)
        self.assertEqual(asdict(receipt), before)
        self.assertEqual(correlation.divergences, ())
        self.assertEqual(correlation.execution_state, 'UNKNOWN_OUTCOME')
        self.assertFalse(broker.has('filesystem.write'))

    def test_private_reference_markers_are_hashed_and_raw_credentials_rejected(self):
        chain = self.c.sc.InMemorySecurityChain('chain', 'install')
        actor = self.c.sc.SecurityAuthority('actor', self.c.sc.AuthorityRole.RUNTIME, 'install')
        result = self.ingestor(chain=chain, actor=actor).ingest(self.observation(
            observation_id='SYNTHETIC_PRIVATE_MARKER', session_id='SYNTHETIC_PRIVATE_MARKER',
            target_ref='ref:SYNTHETIC_PRIVATE_MARKER', action_id_ref='ref:SYNTHETIC_PRIVATE_MARKER'))
        exported = json.dumps([asdict(result), [asdict(e) for e in self.trace.events()],
                               [asdict(record) for record in chain.records()]])
        self.assertNotIn('SYNTHETIC_PRIVATE_MARKER', exported)
        self.assertTrue(result.accepted)
        for value in ('https://test/?token=SYNTHETIC_TOKEN', 'Authorization: Bearer SYNTHETIC_TOKEN'):
            with self.assertRaises(ValueError):
                self.observation(target_ref=value)

    def test_concurrent_duplicate_emits_once(self):
        chain = self.c.sc.InMemorySecurityChain('chain', 'install')
        actor = self.c.sc.SecurityAuthority('actor', self.c.sc.AuthorityRole.RUNTIME, 'install')
        ingestor = self.ingestor(chain=chain, actor=actor)
        observation = self.observation()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(ingestor.ingest, (observation, observation)))
        self.assertEqual(sorted(result.reason for result in results), ['ACCEPTED', 'IDEMPOTENT_DUPLICATE'])
        self.assertEqual((len(self.trace.events()), len(chain.records())), (1, 1))

    def test_operator_evidence_names_observer_session_and_gap_fields(self):
        ingestor = self.ingestor()
        ingestor.ingest(self.observation())
        ingestor.ingest(self.observation(sequence=3, observation_id='gap'))
        event = next(event for event in self.trace.events() if 'sequence:3' in event.evidence_refs)
        refs = event.evidence_refs
        for label in ('observer-sha256:', 'provenance-sha256:', 'session-sha256:',
                      'observation-sha256:'):
            self.assertEqual(sum(ref.startswith(label) for ref in refs), 1)
        self.assertIn('sequence-gap:YES', refs)
        self.assertIn('coverage:PARTIAL', refs)
        self.assertIn('correlation:UNCORRELATED', refs)

    def test_capacity_fails_closed_without_evicting_replay_evidence(self):
        ingestor = self.ingestor()
        first = self.observation()
        ingestor.ingest(first)
        for sequence in range(2, 129):
            self.assertTrue(ingestor.ingest(self.observation(sequence=sequence,
                observation_id=str(sequence), session_id=str(sequence))).accepted)
        result = ingestor.ingest(self.observation(sequence=129, observation_id='overflow'))
        self.assertFalse(result.accepted)
        self.assertEqual(ingestor.ingest(first).reason, 'IDEMPOTENT_DUPLICATE')
        self.assertEqual(len(self.trace.events()), 128)

    def test_chain_rejection_emits_nothing_and_does_not_allow_retry(self):
        chain = self.c.sc.InMemorySecurityChain('chain', 'install')
        actor = self.c.sc.SecurityAuthority('actor', self.c.sc.AuthorityRole.RUNTIME, 'other-install')
        ingestor = self.ingestor(chain=chain, actor=actor)
        self.assertFalse(ingestor.ingest(self.observation()).accepted)
        self.assertFalse(ingestor.ingest(self.observation(observation_id='retry')).accepted)
        self.assertEqual((self.trace.events(), chain.records()), ((), ()))

    def test_chain_write_then_exception_propagates_and_latches_lifecycle_closed(self):
        for exception_type in (RuntimeError, KeyboardInterrupt, SystemExit):
            with self.subTest(exception_type=exception_type.__name__):
                self.trace = self.c.CriticalTrace('trace', 'install')

                class WriteThenRaise(self.c.sc.InMemorySecurityChain):
                    fail_once = True

                    def append(self, event):
                        record = super().append(event)
                        if self.fail_once:
                            self.fail_once = False
                            raise exception_type('synthetic publishing failure')
                        return record

                chain = WriteThenRaise('chain', 'install')
                actor = self.c.sc.SecurityAuthority('actor', self.c.sc.AuthorityRole.RUNTIME, 'install')
                ingestor = self.ingestor(chain=chain, actor=actor)
                with self.assertRaises(exception_type):
                    ingestor.ingest(self.observation())
                self.assertEqual((len(chain.records()), len(self.trace.events())), (1, 0))
                next_result = ingestor.ingest(self.observation(sequence=2, observation_id='next'))
                self.assertEqual((next_result.accepted, next_result.reason, next_result.effective_coverage),
                                 (False, 'MALFORMED_OBSERVATION', 'UNKNOWN'))
                self.assertEqual((len(chain.records()), len(self.trace.events())), (1, 0))

    def test_historical_observation_cannot_record_with_current_expired_authority(self):
        chain = self.c.sc.InMemorySecurityChain('chain', 'install')
        actor = self.c.sc.SecurityAuthority('actor', self.c.sc.AuthorityRole.RUNTIME,
                                            'install', expires_at=10)
        with patch.object(time, 'time', return_value=20):
            result = self.ingestor(chain=chain, actor=actor).ingest(self.observation(observed_at=1))
        self.assertFalse(result.accepted)
        self.assertEqual((self.trace.events(), chain.records()), ((), ()))

    def test_future_observation_does_not_choose_chain_authorization_time(self):
        chain = self.c.sc.InMemorySecurityChain('chain', 'install')
        actor = self.c.sc.SecurityAuthority('actor', self.c.sc.AuthorityRole.RUNTIME,
                                            'install', expires_at=100)
        with patch.object(time, 'time', return_value=20):
            result = self.ingestor(chain=chain, actor=actor).ingest(self.observation(observed_at=30))
        self.assertFalse(result.accepted)
        self.assertEqual((self.trace.events(), chain.records()), ((), ()))

    def test_host_only_intermediary_does_not_create_legacy_risk_path(self):
        root = self.c.TraceContext('trace', 'install', 'project', 'task', 'run',
                                   'read', None, 'trusted', None, 'runtime')
        middle = replace(root, action_id='middle', parent_action_id='read')
        network = replace(root, action_id='network', parent_action_id='middle')
        for identity, kind, context, timestamp, target, classification in (
            ('read', 'FILE_READ', root, 1, '/synthetic/private', self.c.rse.DataClass.SENSITIVE),
            ('network', 'NETWORK_REQUEST', network, 3, 'https://outside.invalid', self.c.rse.DataClass.PUBLIC)):
            self.trace.append(self.c.CriticalEvent(identity, self.c.CriticalEventType[kind], context,
                self.c.ObservationSource.ADAPTER_OBSERVED, timestamp, target, classification))
        self.assertEqual(self.c.detect_trace_risks(self.trace,
            internal_network_origins=(), approved_network_origins=()), ())
        self.ingestor(known_actions={'ref:middle': middle}).ingest(self.observation(
            event_class='REMOTE_EFFECT', action_id_ref='ref:middle', observed_at=2))
        self.assertEqual(len(self.trace.events()), 3)
        self.assertEqual(self.c.detect_trace_risks(self.trace,
            internal_network_origins=(), approved_network_origins=()), ())

    def test_host_event_does_not_change_existing_legacy_risk_evidence_digest(self):
        root = self.context('read')
        network = replace(root, action_id='network', parent_action_id='read')
        self.trace.append(self.c.CriticalEvent('read', self.c.CriticalEventType.FILE_READ, root,
            self.c.ObservationSource.ADAPTER_OBSERVED, 1, '/synthetic/private', self.c.rse.DataClass.SENSITIVE))
        self.trace.append(self.c.CriticalEvent('network', self.c.CriticalEventType.NETWORK_REQUEST, network,
            self.c.ObservationSource.ADAPTER_OBSERVED, 3, 'https://outside.invalid', self.c.rse.DataClass.PUBLIC))
        before = self.c.detect_trace_risks(self.trace, internal_network_origins=(), approved_network_origins=())
        self.assertEqual(len(before), 1)
        self.ingestor(known_actions={'ref:read': root}).ingest(self.observation(
            event_class='REMOTE_EFFECT', action_id_ref='ref:read', observed_at=2))
        after = self.c.detect_trace_risks(self.trace, internal_network_origins=(), approved_network_origins=())
        self.assertEqual(after, before)

    def test_valid_historical_observation_preserves_evidence_time_and_records_current_time(self):
        chain = self.c.sc.InMemorySecurityChain('chain', 'install')
        actor = self.c.sc.SecurityAuthority('actor', self.c.sc.AuthorityRole.RUNTIME,
                                            'install', expires_at=100)
        with patch.object(time, 'time', return_value=20):
            result = self.ingestor(chain=chain, actor=actor).ingest(self.observation(observed_at=1))
        self.assertTrue(result.accepted)
        self.assertEqual(self.trace.events()[0].timestamp, 1)
        self.assertEqual(chain.records()[0].timestamp, 20)

    def test_all_normalization_classes_are_retained_as_host_evidence(self):
        ingestor = self.ingestor()
        for sequence, kind in enumerate(('FILE_READ', 'FILE_WRITE', 'FILE_CREATE', 'FILE_DELETE',
            'FILE_MOVE', 'PROCESS_START', 'PROCESS_EXIT', 'NETWORK_REQUEST', 'GIT_EFFECT', 'REMOTE_EFFECT'), 1):
            self.assertTrue(ingestor.ingest(self.observation(sequence=sequence,
                observation_id=str(sequence), event_class=kind)).accepted)
        self.assertTrue(all(e.source.value == 'HOST_OBSERVED' for e in self.trace.events()))

    def test_core_install_and_import_have_no_effects(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'core'
            assembled = subprocess.run([sys.executable, str(ROOT / 'scripts/assemble_skill_profile.py'),
                '--profile', 'core-only', '--output-root', str(target), '--apply'], cwd=ROOT,
                capture_output=True, text=True, timeout=30)
            self.assertEqual(assembled.returncode, 0, assembled.stderr)
            installed = target / SKILL
            self.assertTrue((installed / 'references/host-observer.md').is_file())
            probe = '''
import builtins, os, socket, subprocess, sys, threading
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
before = dict(os.environ)
with patch.object(builtins, 'open', side_effect=AssertionError('open')), \\
     patch.object(os, 'open', side_effect=AssertionError('os.open')), \\
     patch.object(socket, 'socket', side_effect=AssertionError('network')), \\
     patch.object(subprocess, 'Popen', side_effect=AssertionError('process')), \\
     patch.object(threading.Thread, 'start', side_effect=AssertionError('thread')):
    import host_observer
    import runtime_safety_envelope as rse
    assert not rse.CapabilityBroker().has('filesystem.write')
assert before == dict(os.environ)
print('INACTIVE_HOST_CORE_IMPORT')
'''
            imported = subprocess.run([sys.executable, '-I', '-B', '-c', probe,
                str(installed / 'scripts')], cwd=temporary, capture_output=True, text=True, timeout=30)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            self.assertEqual(imported.stdout.strip(), 'INACTIVE_HOST_CORE_IMPORT')


if __name__ == '__main__':
    unittest.main()
