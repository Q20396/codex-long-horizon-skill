"""Phase 5: one real macOS path and one explicitly synthetic comparison fixture.

No production handshake API. FakeSigner/FakeVerifier exercise the existing
checkpoint contract, not cryptography. Process reality is only the OS wait result.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import asdict, replace
import importlib
import hashlib
import json
import os
from pathlib import Path
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from test_signed_checkpoints import FakeSigner, FakeVerifier

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/long-horizon-engineering/scripts'
NATIVE = sys.platform == 'darwin' and hasattr(select, 'kqueue')
PID_READY_TIMEOUT = 3
NOTE_EXEC_TIMEOUT = 3
CHILD_EXIT_TIMEOUT = 8
SECRET_MARKER = 'PHASE5_SYNTHETIC_PRIVATE_MARKER'


def isolated_python_args(executable, code, *arguments):
    """One test-only launch policy for isolated no-network child fixtures."""
    return [executable, '-I', '-B', '-S', '-c', code, *arguments]

# TEST-ONLY SYNCHRONIZATION: only decimal PID and an empty release file.
# The parent learns no host event from this protocol. RuntimeBinding's deadline
# bounds and reaps the child even if a parent assertion fails before release.
CHILD_CODE = '''import os, sys, time
from pathlib import Path
pid_path, release_path = map(Path, sys.argv[1:])
staging = pid_path.with_suffix('.tmp')
staging.write_text(str(os.getpid()), encoding='ascii')
staging.replace(pid_path)
deadline = time.monotonic() + 5
while not release_path.exists():
    if time.monotonic() >= deadline:
        raise SystemExit(124)
    time.sleep(0.01)
os.execv(sys.executable, [sys.executable, '-I', '-B', '-S', '-c', 'raise SystemExit(0)'])
'''


def wait_for_pid(path, timeout):
    """Only handshake readiness is polled; host evidence always comes from kqueue."""
    deadline = time.monotonic() + timeout
    while not path.exists():
        if time.monotonic() >= deadline:
            raise AssertionError('PID_READY_TIMEOUT')
        time.sleep(0.01)
    with path.open('rb') as stream:
        raw = stream.read(12)
    if not re.fullmatch(rb'[1-9][0-9]{0,9}', raw) or int(raw) >= 2**31:
        raise AssertionError('MALFORMED_PID')
    return int(raw)


class EndToEndSecurityRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_path = sys.path[:]
        cls.names = ('agent_runtime_integration', 'runtime_binding', 'remote_runtime_binding',
            'runtime_safety_envelope', 'critical_execution_trace', 'security_authority_chain',
            'host_observer', 'host_observer_macos', 'cross_layer_verification', 'signed_checkpoints')
        cls.saved_modules = {name: sys.modules.get(name) for name in cls.names}
        sys.path.insert(0, str(SCRIPTS))
        cls.m = importlib.import_module('agent_runtime_integration')
        cls.h = importlib.import_module('host_observer')
        cls.v = importlib.import_module('cross_layer_verification')
        cls.cp = importlib.import_module('signed_checkpoints')
        cls.native = importlib.import_module('host_observer_macos')

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = cls.saved_path
        for name, module in cls.saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def setUp(self):
        self.r, self.c, self.s = self.m.rse, self.m.cet, self.m.sc
        self.tmp = tempfile.TemporaryDirectory(prefix='phase5-')
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(lambda: self.assertFalse(self.root.exists()))
        self.addCleanup(self.tmp.cleanup)
        self.executable = os.path.realpath(sys.executable)
        self.bridge = self.m.AgentRuntimeBridge()
        self.broker = self.r.CapabilityBroker()
        self.journal = self.r.InMemorySecurityJournal()
        self.chain = self.s.InMemorySecurityChain('phase5-chain', 'install')
        self.actor = self.s.SecurityAuthority('runtime', self.s.AuthorityRole.RUNTIME, 'install')
        self.context = self.c.TraceContext('trace', 'install', 'project', 'task', 'run',
            'action', None, 'trusted-host', None, 'runtime')
        self.trace = self.c.CriticalTrace('trace', 'install')
        self.policy = self.r.Policy('bounded', self.r.PolicyLevel.CORE,
            frozenset({self.r.ActionClass.EXECUTE_PROCESS}),
            allowed_capabilities=frozenset({'process.execute'}))
        self.authorization = self.r.Authorization('auth', 'task',
            frozenset({self.r.ActionClass.EXECUTE_PROCESS}), (self.executable,),
            frozenset({'process.execute'}), 100)

    def prepare(self, timeout=6, child_code=CHILD_CODE):
        self.proposal = self.m.AgentActionProposal('proposal', 'EXECUTE_PROCESS',
            self.executable, dict(argv=tuple(isolated_python_args(self.executable, child_code,
                str(self.root / 'pid'), str(self.root / 'release'))),
                cwd=str(self.root), timeout=timeout),
            declared_effects={'processes': (self.executable,)}, reason_text=SECRET_MARKER)
        result = self.bridge.prepare(self.proposal, context=self.context,
            trusted_agent_id='trusted-controller', authorization_ref='auth',
            data_classification=self.r.DataClass.NON_SENSITIVE, now=1)
        self.assertEqual(result.status, 'PREPARED')
        self.prepared = result.prepared
        self.adapter = self.m.local.ProcessAdapter(workspace_root=str(self.root),
            allowed_executables=(self.executable,), default_timeout=timeout, max_timeout=6)
        counter = patch.object(self.adapter, 'run', wraps=self.adapter.run)
        self.executions = counter.start()  # Delegates every call to the real adapter.
        self.addCleanup(counter.stop)
        self.broker.register('process.execute', self.adapter)
        self.binding = self.m.local.RuntimeBinding(self.broker, self.journal, self.chain,
            self.actor, approved_payload_digests={'action': self.prepared.payload_digest})
        return self.prepared

    def execute(self, **changes):
        p = self.prepared
        args = dict(binding=self.binding, expected_payload_digest=p.payload_digest,
            expected_prepared_digest=p.prepared_digest, policy_stack=(self.policy,),
            authorization=self.authorization, context=self.context, now=2)
        args.update(changes)
        return self.bridge.execute(p, **args)

    def snapshot(self):
        return (self.chain.records(), self.trace.events(), self.journal.history('action'),
                asdict(self.authorization), asdict(self.policy), self.broker.has('process.execute'))

    def verify_without_effects(self, value):
        before = self.snapshot()
        # Removing verifier purity must fail even if final state happens to match.
        with ExitStack() as guard:
            for obj, name in ((self.binding, 'execute'), (self.binding, 'reconcile'),
                    (self.adapter, 'run'),
                    (self.bridge, 'execute'), (self.chain, 'append'), (self.trace, 'append'),
                    (self.native.MacOSExecObserver, 'register'),
                    (self.native.MacOSExecObserver, 'wait_for_exec'),
                    (self.native.MacOSExecObserver, 'close'),
                    (self.native.MacOSExecObserver, '__init__')):
                guard.enter_context(patch.object(obj, name, side_effect=AssertionError('VERIFIER_EFFECT')))
            findings = self.v.CrossLayerVerifier.verify(value)
        self.assertEqual(self.snapshot(), before)
        return findings

    @unittest.skipUnless(NATIVE, 'BETA: TARGET_VALIDATION_ENVIRONMENT_UNAVAILABLE (macOS kqueue)')
    def test_real_proposal_to_native_evidence_and_checkpoint(self):
        # Breaks caught: bypassed RSE/binding, pre-registration exec, fabricated host,
        # dropped EXIT, reality inferred from NOTE_EXEC, writes/retries from verifier.
        p = self.prepare()
        self.assertEqual((p.declaration_status, p.declared_effects.processes),
                         ('DECLARED', (self.executable,)))
        self.assertEqual(self.chain.records(), ())
        observer = self.native.MacOSExecObserver('phase5-native')
        order = []
        try:
            with ThreadPoolExecutor(max_workers=1) as worker:
                result_future = worker.submit(self.execute)
                pid = wait_for_pid(self.root / 'pid', PID_READY_TIMEOUT)
                order.append('PID_PUBLISHED')
                self.assertFalse(result_future.done(), 'child must wait for registration')
                self.assertFalse((self.root / 'release').exists())
                observer.register(pid, action_id_ref='ref:action')
                order.append('REGISTERED')
                (self.root / 'release').touch(exist_ok=False)
                order.append('RELEASED')
                observation = observer.wait_for_exec(NOTE_EXEC_TIMEOUT)
                self.assertIsNotNone(observation, 'NOTE_EXEC_TIMEOUT: no fallback or retry')
                order.append('NATIVE_NOTE_EXEC')
                out = result_future.result(CHILD_EXIT_TIMEOUT)
        finally:
            observer.close()
        self.assertEqual(order, ['PID_PUBLISHED', 'REGISTERED', 'RELEASED', 'NATIVE_NOTE_EXEC'])
        self.assertEqual({f.name for f in self.root.iterdir()}, {'pid', 'release'})
        self.assertEqual((self.root / 'pid').read_bytes(), str(pid).encode())
        self.assertEqual((self.root / 'release').read_bytes(), b'')
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)  # RuntimeBinding reaped its own child.
        self.assertEqual((out.receipt.policy_disposition, out.receipt.execution_state),
                         ('ALLOW', 'KNOWN_SUCCESS'))
        runtime = out.runtime_result
        self.assertEqual((runtime.boundary_status, runtime.evidence.reason,
                          runtime.evidence.exit_code, runtime.evidence.payload_digest),
                         ('OK', 'EXITED', 0, p.payload_digest))
        self.assertEqual((runtime.stdout, runtime.stderr), (b'', b''))
        self.assertEqual(self.executions.call_count, 1)
        adapter_events = tuple(e for e in out.events if e.source.value == 'ADAPTER_OBSERVED')
        declared_events = tuple(e for e in out.events if e.source.value == 'DECLARED')
        self.assertEqual([(e.event_type.value, e.exit_code) for e in adapter_events],
                         [('PROCESS_START', None), ('PROCESS_EXIT', 0)])
        self.assertEqual([e.event_type.value for e in declared_events], ['PROCESS_START'])
        self.assertTrue(all(e.context == p.context and e.target == self.executable
                            for e in adapter_events + declared_events))
        self.assertEqual((observation.event_class, observation.target_ref,
            observation.action_id_ref, observation.coverage, observation.sequence),
            ('PROCESS_EXEC', 'ref:pid-' + str(pid), 'ref:action', 'PARTIAL', 1))
        ingestor = self.h.HostObservationIngestor('macos-kqueue-proc',
            'ref:macos-kqueue-evfilt-proc-note-exec', trace=self.trace,
            known_actions={'ref:action': p.context}, chain=self.chain, actor=self.actor)
        ingested = ingestor.ingest(observation)
        self.assertEqual((ingested.accepted, ingested.correlation_status,
                          ingested.effective_coverage), (True, 'CORRELATED', 'PARTIAL'))
        self.assertEqual([(e.source.value, e.event_type.value) for e in self.trace.events()],
                         [('HOST_OBSERVED', 'PROCESS_EXEC')])
        self.assertEqual(ingested.chain_ref, self.chain.records()[-1].record_hash)

        # Source refs stay distinct; full prepared identity is justified by the
        # checked proposal parameters, approved payload and actual bound invocation.
        material = 'sha256:' + p.material_effect_identity
        ref = lambda obj: 'sha256:' + self.s.artifact_digest(obj)
        effect = lambda kind, identity, source: (kind, identity, 'ref:action', (source,), 'CORRELATED')
        declared_ref, auth_ref = ref(declared_events[0]), ref(out.receipt)
        reality_ref = ref(runtime.evidence)
        # Native NOTE_EXEC names a PID, not the program/argv identity. None is
        # intentional: do not copy the adapter's material identity into host data.
        value = self.v.VerificationInput('ref:action',
            declared_effects=(effect('PROCESS_START', material, declared_ref),),
            authorized_effects=(effect('PROCESS_START', material, auth_ref),),
            adapter_observed_effects=tuple(effect(e.event_type.value, material, ref(e))
                                           for e in adapter_events),
            host_observed_effects=(effect('PROCESS_EXEC', None, 'sha256:' + ingested.cet_event_ref),),
            target_reality_effects=(effect('PROCESS_EXIT', material, reality_ref),),
            adapter_coverage=runtime.completeness.value, host_coverage=ingested.effective_coverage,
            target_reality_status='VERIFIED')
        sources = (declared_ref, auth_ref, ref(adapter_events[0]),
                   'sha256:' + ingested.cet_event_ref, reality_ref)
        self.assertEqual(len(set(sources)), 5)
        findings = self.verify_without_effects(value)
        self.assertEqual([(f.layer_a, f.effect_class, f.result) for f in findings], [
            ('DECLARED', 'PROCESS_START', 'MATCH'),
            ('AUTHORIZED', 'PROCESS_EXIT', 'EXTRA'),
            ('AUTHORIZED', 'PROCESS_START', 'MATCH'),
            ('ADAPTER_OBSERVED', 'PROCESS_EXEC', 'UNKNOWN'),
            ('ADAPTER_OBSERVED', 'PROCESS_EXIT', 'NOT_OBSERVED'),
            ('ADAPTER_OBSERVED', 'PROCESS_START', 'NOT_OBSERVED'),
            ('HOST_OBSERVED', 'PROCESS_EXEC', 'UNKNOWN'),
            ('HOST_OBSERVED', 'PROCESS_EXIT', 'UNKNOWN')])
        # Losing the wait result must never let adapter/host observations fill reality.
        unknown = self.verify_without_effects(replace(value, target_reality_effects=None,
                                                     target_reality_status='UNKNOWN'))
        self.assertEqual([(f.result, f.reason) for f in unknown if f.layer_b == 'TARGET_REALITY'],
                         [('UNKNOWN', 'TARGET_REALITY_UNKNOWN')])
        records = self.chain.records()
        self.assertTrue(self.chain.verify().valid)
        self.assertEqual([record.event_type for record in records], [
            'RSE_RECEIPT_RECORDED', 'CRITICAL_TRACE_EVENT', 'CRITICAL_TRACE_EVENT',
            'RSE_RECEIPT_RECORDED', 'CRITICAL_TRACE_EVENT', 'CRITICAL_TRACE_EVENT'])
        self.assertEqual([record.artifact_digest for record in records], [
            self.s.artifact_digest(runtime.receipt), self.s.artifact_digest(adapter_events[0]),
            self.s.artifact_digest(adapter_events[1]), self.s.artifact_digest(out.receipt),
            self.s.artifact_digest(declared_events[0]), self.s.artifact_digest(self.trace.events()[0])])
        self.assertTrue(set(self.s.artifact_digest(f) for f in findings).isdisjoint(
            record.artifact_digest for record in records))
        self.assertEqual(self.executions.call_count, 1)
        self.assertEqual(sum(e.event_type.value == 'PROCESS_START' for e in adapter_events), 1)
        signer = FakeSigner(self.cp)
        verifier = FakeVerifier(signer)
        checkpoint = self.cp.create_checkpoint(self.chain,
            self.s.SecurityAuthority('admin', self.s.AuthorityRole.INSTALLATION_ADMIN, 'install'),
            signer, verifier, checkpoint_id='phase5', now=time.time(),
            algorithm=signer.algorithm, key_id=signer.key)
        self.assertEqual((checkpoint.sequence, checkpoint.chain_head_hash),
                         (len(records), records[-1].record_hash))
        self.assertTrue(self.cp.verify_security_history(self.chain, checkpoint, verifier).valid)
        self.assertEqual(self.chain.records(), records)
        signed_payload = self.cp.canonical_payload(checkpoint)
        self.assertIn(signed_payload, signer.messages.values())
        exported = json.dumps([asdict(x) for x in records] + [asdict(observation)] +
            [asdict(e) for e in out.events + self.trace.events()] + [asdict(f) for f in findings])
        self.assertNotIn(SECRET_MARKER, exported + signed_payload.decode())
        self.assertNotIn(SECRET_MARKER, (self.root / 'pid').read_text())
        print('PHASE5_NATIVE: runtime=PHASE_2A proposal=UNTRUSTED authorization=ALLOW '
              'pid_source=CHILD order=PID_REGISTER_RELEASE_NOTE_EXEC native=YES '
              'host=PROCESS_EXEC coverage=PARTIAL wait_result=EXITED_0 '
              'process_start=NOT_OBSERVED process_exec=UNKNOWN '
              'checkpoint=VALID_TEST_CONTRACT chain_sequence=%d head=%s' %
              (checkpoint.sequence, checkpoint.chain_head_hash))

    def test_controlled_verification_fixture_divergence_is_read_only(self):
        # Exactly one deliberate mismatch: synthetic A versus B in a complete slot.
        self.prepare()
        label = 'CONTROLLED_VERIFICATION_FIXTURE'
        def fixture(material, evidence):
            return ('PROCESS_EXEC', material, 'ref:action', (evidence,), 'CORRELATED')
        value = self.v.VerificationInput('ref:action',
            declared_effects=(), authorized_effects=(fixture('ref:A', 'ref:' + label + '.authorized'),),
            adapter_observed_effects=(fixture('ref:B', 'ref:' + label + '.adapter'),),
            host_observed_effects=(), target_reality_effects=None,
            adapter_coverage='SCOPED_COMPLETE', host_coverage='PARTIAL')
        findings = self.verify_without_effects(value)
        relevant = tuple(f for f in findings if f.layer_a == 'AUTHORIZED')
        self.assertEqual([(f.result, f.effect_ref, f.compared_effect_ref) for f in relevant],
                         [('DIVERGED', 'ref:A', 'ref:B')])
        self.assertTrue(all(f.result in ('MATCH', 'MISSING', 'EXTRA', 'DIVERGED', 'UNKNOWN', 'NOT_OBSERVED')
                            for f in findings))
        self.assertEqual((self.chain.records(), self.trace.events(), self.journal.history('action')), ((), (), ()))
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(self.executions.call_count, 0)

    def test_proposal_does_not_self_authorize(self):
        # Missing authority must block the real bridge before any child is launched.
        self.prepare()
        out = self.execute(authorization=None)
        self.assertEqual(out.receipt.policy_reason, 'AUTHORIZATION_MISSING')
        self.assertEqual(out.runtime_result.events, ())
        self.assertFalse((self.root / 'pid').exists())
        self.assertEqual(self.executions.call_count, 0)

    def artifact_request(self, content=b'A', target='artifact', attempt='ref:action-attempt-1'):
        """Trusted fixture fixes observation scope and identity before execution."""
        repository_scripts = SCRIPTS.parents[3] / 'scripts'
        self.assertTrue((repository_scripts / 'independent_target_reality.py').is_file(),
                        'independent local artifact collector missing')
        sys.path.insert(0, str(repository_scripts))
        self.addCleanup(sys.path.remove, str(repository_scripts))
        self.artifact = importlib.import_module('independent_target_reality')
        return self.artifact.bind_request(root=self.root, target=target,
            expected_size=len(content), expected_digest=hashlib.sha256(content).hexdigest(),
            attempt_ref=attempt, scope_ref='ref:artifact-only', max_bytes=32)

    def prepare_artifact(self, code="from pathlib import Path; Path('artifact').write_bytes(b'A')"):
        return self.prepare(child_code=code)

    def test_independent_artifact_actual_governed_execution_and_incomplete_host(self):
        # Break: bypass binding, repeat effect, or invent FILE_WRITE coverage/identity.
        request = self.artifact_request()
        p = self.prepare_artifact()
        out = self.execute()
        self.assertEqual((out.receipt.execution_state, self.executions.call_count),
                         ('KNOWN_SUCCESS', 1))
        before = self.snapshot()
        observation = self.artifact.collect(request)
        self.assertTrue(self.artifact.matches_request(request, observation))
        self.assertEqual((observation.status, observation.expectation_match,
                          observation.process_authorship), ('OBSERVED', 'MATCH', 'NOT_PROVEN'))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual((self.root / 'artifact').read_bytes(), b'A')
        self.assertEqual(self.trace.events(), ())
        # File observation cannot truthfully fill the verifier's process slot.
        material = 'sha256:' + p.material_effect_identity
        effect = ('PROCESS_START', material, 'ref:action', ('ref:adapter',), 'CORRELATED')
        value = self.v.VerificationInput('ref:action', declared_effects=(),
            authorized_effects=(effect,), adapter_observed_effects=(effect,),
            host_observed_effects=(), target_reality_effects=None,
            adapter_coverage='PARTIAL', host_coverage='PARTIAL', target_reality_status='UNKNOWN')
        findings = self.verify_without_effects(value)
        self.assertTrue(any(f.result == 'NOT_OBSERVED' for f in findings))
        self.assertEqual([(f.result, f.reason) for f in findings if f.layer_b == 'TARGET_REALITY'],
                         [('UNKNOWN', 'TARGET_REALITY_UNKNOWN')])
        self.assertEqual(self.executions.call_count, 1)

    def test_independent_artifact_zero_exit_without_file_stays_unknown(self):
        # Break: use adapter exit/reap evidence as actual file reality.
        request = self.artifact_request()
        self.prepare_artifact('raise SystemExit(0)')
        out = self.execute()
        self.assertEqual(out.runtime_result.evidence.exit_code, 0)
        result = self.artifact.collect(request)
        self.assertEqual((result.status, result.observed_digest), ('UNKNOWN', None))
        self.assertFalse(result.retry_authorized)
        self.assertEqual(self.executions.call_count, 1)

    def test_independent_artifact_wrong_content_survives_adapter_evidence_loss(self):
        # Break: expected/adapter digest contaminates actual bytes, or missing adapter erases them.
        request = self.artifact_request()
        self.prepare_artifact("from pathlib import Path; Path('artifact').write_bytes(b'B')")
        out = self.execute()
        result = self.artifact.collect(request)
        discarded = replace(out.runtime_result, evidence=None)
        altered = replace(out.runtime_result, evidence=replace(out.runtime_result.evidence, exit_code=97))
        self.assertIsNone(discarded.evidence)
        self.assertEqual(altered.evidence.exit_code, 97)
        self.assertEqual(self.artifact.collect(request), result)
        self.assertEqual((result.status, result.observed_digest, result.expectation_match),
            ('OBSERVED', 'df7e70e5021544f4834bbee64a9e3789febc4be81470df629cad6ddb03320a5c', 'MISMATCH'))

    def test_independent_artifact_preexisting_match_does_not_prove_denied_action(self):
        # Break: matching preexisting file upgrades missing authorization to success.
        (self.root / 'artifact').write_bytes(b'A')
        request = self.artifact_request()
        self.prepare_artifact()
        out = self.execute(authorization=None)
        result = self.artifact.collect(request)
        self.assertEqual(out.receipt.policy_reason, 'AUTHORIZATION_MISSING')
        self.assertEqual(self.executions.call_count, 0)
        self.assertEqual((result.status, result.expectation_match, result.process_authorship),
                         ('OBSERVED', 'MATCH', 'NOT_PROVEN'))
        self.assertFalse(result.retry_authorized)

    def test_independent_artifact_h1_barrier_failure_prevents_process(self):
        # Break: collector bypasses durable attempt admission or grants retry on absence.
        request = self.artifact_request()
        self.journal = self.r.DurableSecurityJournal(self.root / 'journal', storage_id='h3', create=True)
        self.prepare_artifact()
        with patch('os.fsync', side_effect=OSError('synthetic barrier failure')):
            out = self.execute()
        self.assertNotEqual(out.receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertEqual(self.executions.call_count, 0)
        before = (self.root / 'journal').read_bytes()
        self.assertEqual(self.artifact.collect(request).status, 'UNKNOWN')
        self.assertEqual((self.root / 'journal').read_bytes(), before)

    def test_independent_artifact_h2_owner_contention_prevents_effect(self):
        # Break: observation authorizes a second controller despite real ownership contention.
        from test_cross_process_coordination import RACE
        request = self.artifact_request(content=b'x', target='effect')
        owner = self.r.CrossProcessOwner(self.root)
        self.addCleanup(owner.close)
        args = isolated_python_args(sys.executable, RACE, str(SCRIPTS), str(self.root), 'B', 'recover')
        out = subprocess.run(args, capture_output=True, timeout=8)
        self.assertEqual((out.returncode, out.stdout.strip()), (0, b'OWNERSHIP_CONTENDED'))
        self.assertFalse((self.root / 'effect').exists())
        self.assertEqual(self.artifact.collect(request).status, 'UNKNOWN')
        owner.check()

    def test_independent_artifact_crash_match_preserves_material_retry_barrier(self):
        # Break: independently matched bytes clear real recovered ATTEMPTED uncertainty.
        from test_cross_process_coordination import RACE
        request = self.artifact_request(content=b'x', target='effect')
        args = isolated_python_args(sys.executable, RACE, str(SCRIPTS), str(self.root))
        crashed = subprocess.run(args + ['A', 'before_outcome'], capture_output=True, timeout=8)
        self.assertEqual(crashed.returncode, 73)
        durable_before = ((self.root / 'journal').read_bytes(), (self.root / 'chain').read_bytes())
        result = self.artifact.collect(request)
        self.assertEqual((result.status, result.expectation_match, result.process_authorship),
                         ('OBSERVED', 'MATCH', 'NOT_PROVEN'))
        self.assertEqual(((self.root / 'journal').read_bytes(), (self.root / 'chain').read_bytes()), durable_before)
        before = ((self.root / 'effect').read_bytes(), (self.root / 'effect').stat().st_mtime_ns,
                  (self.root / 'journal').read_bytes(), (self.root / 'chain').read_bytes())
        recovered = subprocess.run(args + ['A', 'recover'], capture_output=True, timeout=8)
        self.assertEqual((recovered.returncode, recovered.stdout.splitlines()),
                         (0, [b'DENY', b'RECONCILIATION_REQUIRED', b'ATTEMPTED']))
        self.assertEqual(((self.root / 'effect').read_bytes(), (self.root / 'effect').stat().st_mtime_ns), before[:2])
        self.assertEqual((self.root / 'journal').read_bytes(), before[2])
        fresh = subprocess.run(args + ['B', 'recover'], capture_output=True, timeout=8)
        self.assertEqual((fresh.returncode, fresh.stdout.splitlines()),
                         (0, [b'DENY', b'RECONCILIATION_REQUIRED', b'ATTEMPTED']))
        self.assertEqual(((self.root / 'effect').read_bytes(), (self.root / 'effect').stat().st_mtime_ns), before[:2])
        self.assertFalse(result.retry_authorized)

    def test_independent_artifact_h1_crash_recovery_remains_unknown(self):
        # Break: matched bytes clear H1 durable ATTEMPTED and re-invoke the effect.
        request = self.artifact_request(content=b'x', target='h1-effect')
        code = '''
import os, sys
sys.path.insert(0, sys.argv[1])
import agent_runtime_integration as m
r, sc, cet, local = m.rse, m.sc, m.cet, m.local
root, phase = sys.argv[2:]
j = r.DurableSecurityJournal(root+'/h1-journal', storage_id='h3-h1', create=phase=='crash')
chain = sc.InMemorySecurityChain('h3-h1','install')
ctx = cet.TraceContext('trace','install','project','task','run','A',None,'provider',None,'runtime')
bridge = m.AgentRuntimeBridge()
p = bridge.prepare(dict(proposal_id='A',requested_action_class='CREATE_FILE',requested_target=root+'/h1-effect',requested_parameters={'content_bytes':b'x'}),context=ctx,trusted_agent_id='agent',authorization_ref='auth',data_classification=r.DataClass.NON_SENSITIVE,now=1).prepared
policy = r.Policy('core',r.PolicyLevel.CORE,allowed_actions={r.ActionClass.CREATE_FILE},write_roots=(root,),allowed_capabilities={'filesystem.write'})
auth = r.Authorization('auth','task',{r.ActionClass.CREATE_FILE},(root+'/h1-effect',),{'filesystem.write'},100)
append = j.append
def fault(entry):
 if phase=='crash' and entry.state==r.JournalState.KNOWN_SUCCESS: os._exit(73)
 append(entry)
j.append = fault
broker = r.CapabilityBroker()
broker.register('filesystem.write', local.FilesystemAdapter(workspace_root=root))
binding = local.RuntimeBinding(broker,j,chain,sc.SecurityAuthority('runtime',sc.AuthorityRole.RUNTIME,'install'),approved_payload_digests={'A':p.payload_digest})
out = binding.execute(p.action_request,p.normalized_payload,policy_stack=(policy,),authorization=auth,context=ctx,now=2)
print(out.receipt.execution_state, out.receipt.reconciliation_state, flush=True)
'''
        args = isolated_python_args(sys.executable, code, str(SCRIPTS), str(self.root))
        crashed = subprocess.run(args + ['crash'], capture_output=True, timeout=8)
        self.assertEqual(crashed.returncode, 73)
        before = ((self.root / 'h1-effect').read_bytes(), (self.root / 'h1-effect').stat().st_mtime_ns,
                  (self.root / 'h1-journal').read_bytes())
        result = self.artifact.collect(request)
        self.assertEqual((result.status, result.expectation_match), ('OBSERVED', 'MATCH'))
        recovered = subprocess.run(args + ['recover'], capture_output=True, timeout=8)
        self.assertEqual((recovered.returncode, recovered.stdout.strip()),
                         (0, b'UNKNOWN_OUTCOME RECONCILIATION_REQUIRED'))
        self.assertEqual(((self.root / 'h1-effect').read_bytes(), (self.root / 'h1-effect').stat().st_mtime_ns,
                          (self.root / 'h1-journal').read_bytes()), before)
        self.assertFalse(result.retry_authorized)

    def test_isolated_child_import_does_not_modify_package_sources(self):
        # Break: -I ignores the CI environment's PYTHONDONTWRITEBYTECODE; without
        # explicit -B, child imports add unmanifested pyc files to source trees.
        # Real copies isolate the probe from the repository/package originals.
        source = self.root / 'probe-source'
        source.mkdir()
        for name in ('agent_runtime_integration', 'critical_execution_trace',
                     'remote_runtime_binding', 'runtime_binding',
                     'runtime_safety_envelope', 'security_authority_chain'):
            shutil.copy2(SCRIPTS / (name + '.py'), source / (name + '.py'))
        code = '''
import sys
sys.path.insert(0, sys.argv[1])
import agent_runtime_integration
print('BYTECODE_DISABLED' if sys.dont_write_bytecode else 'BYTECODE_ENABLED')
'''
        args = isolated_python_args(sys.executable, code, str(source))
        out = subprocess.run(args, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                             capture_output=True, timeout=8)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(list(source.rglob('*.pyc')), [], 'isolated import modified source inventory')
        self.assertEqual(out.stdout.strip(), b'BYTECODE_DISABLED')
        # Apple Python 3.9 enables this by default; require the explicit option
        # even there so the test catches launch policy regressions on that host.
        self.assertIn('-B', args[1:args.index('-c')])

    def test_pid_timeout_fails_once_without_second_execution(self):
        # A real child blocks on release; parent intentionally reads an absent path.
        # The existing runtime deadline kills/reaps it; no retry can hide the failure.
        self.prepare(timeout=1)
        with ThreadPoolExecutor(max_workers=1) as worker:
            future = worker.submit(self.execute)
            pid = wait_for_pid(self.root / 'pid', PID_READY_TIMEOUT)
            with self.assertRaisesRegex(AssertionError, '^PID_READY_TIMEOUT$'):
                wait_for_pid(self.root / 'never-published', 0)
            out = future.result(CHILD_EXIT_TIMEOUT)
        self.assertEqual((out.receipt.execution_state, out.runtime_result.evidence.reason),
                         ('UNKNOWN_OUTCOME', 'TIMEOUT'))
        self.assertEqual([e.event_type.value for e in out.runtime_result.events], ['PROCESS_START'])
        self.assertEqual(out.runtime_result.evidence.exit_code, None)
        self.assertEqual(self.trace.events(), ())
        self.assertEqual(self.executions.call_count, 1)
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        self.assertFalse((self.root / 'release').exists())

    def test_pid_input_rejects_non_decimal_out_of_range_and_trailing_payload(self):
        # Malformed PID must fail before registration, never execute file contents.
        path = self.root / 'pid'
        for raw in (b'', b'0', b'-1', b'1\n', b'1 payload', b'2147483648', b'9' * 50):
            with self.subTest(raw=raw):
                path.write_bytes(raw)
                with self.assertRaisesRegex(AssertionError, '^MALFORMED_PID$'):
                    wait_for_pid(path, 0)

    @unittest.skipUnless(NATIVE, 'BETA: TARGET_VALIDATION_ENVIRONMENT_UNAVAILABLE (macOS kqueue)')
    def test_no_native_delivery_produces_no_host_evidence(self):
        # A real registered child is still blocked, so readiness is not NOTE_EXEC.
        self.prepare()
        observer = self.native.MacOSExecObserver('phase5-no-event')
        try:
            with ThreadPoolExecutor(max_workers=1) as worker:
                future = worker.submit(self.execute)
                pid = wait_for_pid(self.root / 'pid', PID_READY_TIMEOUT)
                observer.register(pid, action_id_ref='ref:action')
                with patch.object(self.native, 'HostObservation', side_effect=AssertionError('FABRICATED_HOST')):
                    self.assertIsNone(observer.wait_for_exec(0))
                self.assertEqual(self.trace.events(), ())
                observer.close()
                (self.root / 'release').touch(exist_ok=False)
                out = future.result(CHILD_EXIT_TIMEOUT)
        finally:
            observer.close()
        self.assertEqual(out.receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertEqual(self.trace.events(), ())


if __name__ == '__main__':
    unittest.main()
