"""Synthetic storage only; removing fsync/replay must break these contracts."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/long-horizon-engineering/scripts'


class DurableTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(sys.path.remove, str(SCRIPTS))
        self.r = importlib.import_module('runtime_safety_envelope')
        self.assertTrue(hasattr(self.r, 'DurableSecurityJournal'), 'durable journal missing')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name).resolve() / 'journal'
        self.j = self.r.DurableSecurityJournal(self.path, storage_id='fixture', create=True)
        self.a = self.r.ActionRequest('a', 'run', 'task', self.r.ActionClass.WRITE_FILE,
            '/synthetic/file', 'provider', 'runtime', self.r.DataClass.NON_SENSITIVE,
            'auth', 'filesystem.write', 'SECRET_MARKER')
        self.policy = self.r.Policy('core', self.r.PolicyLevel.CORE,
            allowed_actions=frozenset(self.r.ActionClass), write_roots=('/synthetic',),
            allowed_capabilities=frozenset({'filesystem.write'}))
        self.auth = self.r.Authorization('auth', 'task', frozenset(self.r.ActionClass),
            ('/synthetic/file',), frozenset({'filesystem.write'}), 100)
        self.calls = []
        outer = self
        class Adapter:
            def execute(self, action):
                outer.calls.append(action.action_id)
                recovered = outer.reopen()
                outer.assertEqual(recovered.latest('a').state.value, 'ATTEMPTED')
                return outer.r.ExecutionResult(outer.r.ExecutionState.KNOWN_SUCCESS, ('evidence',))
        self.broker = self.r.CapabilityBroker()
        self.broker.register('filesystem.write', Adapter())

    def reopen(self):
        return self.r.DurableSecurityJournal(self.path, storage_id='fixture')

    def execute(self, auth=True):
        return self.r.evaluate_and_execute(self.a, (self.policy,), self.auth if auth else None,
            self.broker, self.j, 1)

    def test_barrier_precedes_effect_and_confirmed_outcome_replays(self):
        self.assertEqual(self.execute().execution_state, 'KNOWN_SUCCESS')
        self.assertEqual(self.calls, ['a'])
        self.j = self.reopen()
        self.assertEqual(self.execute().final_disposition, 'ALREADY_COMPLETED')
        self.assertEqual(self.calls, ['a'])
        self.assertNotIn('SECRET_MARKER', self.path.read_text())

    def test_failed_sync_prevents_effect_and_latches_closed(self):
        with patch('os.fsync', side_effect=OSError('synthetic')):
            self.execute()
        self.execute()
        self.assertEqual(self.calls, [])

    def test_attempted_sync_failure_never_invokes_adapter(self):
        original = os.fsync
        count = 0
        def sync(fd):
            nonlocal count
            count += 1
            if count == 3:
                raise OSError('ATTEMPTED sync failed')
            original(fd)
        with patch('os.fsync', side_effect=sync):
            self.execute()
        self.assertEqual(self.calls, [])
        self.execute()
        self.assertEqual(self.calls, [])

    def test_partial_outcome_write_recovery_fails_closed(self):
        original = os.write
        def write(fd, data):
            if b'KNOWN_SUCCESS' in data:
                return original(fd, data[:len(data)//2])
            return original(fd, data)
        with patch('os.write', side_effect=write):
            self.assertEqual(self.execute().execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(self.calls, ['a'])
        with self.assertRaisesRegex(ValueError, 'DURABLE_STATE_UNTRUSTED'):
            self.reopen()

    def test_empty_recovery_is_not_fresh_storage(self):
        self.path.write_bytes(b'')
        with self.assertRaisesRegex(ValueError, 'DURABLE_STATE_UNTRUSTED'):
            self.reopen()

    def test_invalid_and_truncated_records_fail_closed(self):
        self.execute()
        data = self.path.read_bytes()
        for bad in (data[:-1], data + b'{}\n', data.replace(b'ATTEMPTED', b'NOT_REAL!')):
            self.path.write_bytes(bad)
            with self.assertRaisesRegex(ValueError, 'DURABLE_STATE_UNTRUSTED'):
                self.reopen()

    def test_missing_recovery_never_creates(self):
        with self.assertRaisesRegex(ValueError, 'DURABLE_STATE_UNTRUSTED'):
            self.r.DurableSecurityJournal(self.path.parent / 'absent', storage_id='fixture')
        self.assertFalse((self.path.parent / 'absent').exists())

    def test_recovery_does_not_grant_authority(self):
        self.j = self.reopen()
        self.execute(auth=False)
        self.assertEqual(self.calls, [])

    def test_recovered_material_blocks_new_action_and_needs_reconciliation(self):
        self.assertTrue(hasattr(self.j, 'bind_material'), 'material binding missing')
        self.assertTrue(self.j.bind_material('a', 'a' * 64, 'b' * 64))
        for state in ('PROPOSED', 'AUTHORIZED', 'ATTEMPTED'):
            self.r._append(self.j, self.a, self.r.JournalState(state))
        self.j = self.reopen()
        self.assertFalse(self.j.bind_material('new-action', 'a' * 64, 'b' * 64))
        self.assertEqual(self.r.reconcile(self.a, self.j, lambda a: 'SUCCESS').execution_state, 'UNKNOWN_OUTCOME')
        self.assertFalse(self.reopen().bind_material('new-action', 'a' * 64, 'b' * 64))
        out = self.r.reconcile(self.a, self.j, lambda a: self.r.ReconciliationOutcome.EFFECT_NOT_APPLIED)
        self.assertEqual(out.final_disposition, 'RECONCILED_NOT_APPLIED')
        self.assertTrue(self.reopen().bind_material('new-action', 'a' * 64, 'b' * 64))

    def test_records_bind_authorization_and_attempt_without_raw_identity(self):
        self.execute()
        rows = [json.loads(line) for line in self.path.read_text().splitlines()][1:]
        self.assertTrue(all('authorization' in row and 'attempt' in row for row in rows))
        self.assertTrue(all(row['authorization'].startswith('sha256:') for row in rows))
        self.assertEqual(len({row['attempt'] for row in rows}), 1)

    def test_invalid_transition_and_conflicting_identity_latch_closed(self):
        self.r._append(self.j, self.a, self.r.JournalState.PROPOSED)
        with self.assertRaisesRegex(ValueError, 'DURABLE_STATE_UNTRUSTED'):
            self.r._append(self.j, self.a, self.r.JournalState.KNOWN_SUCCESS, evidence=(self.r._ref('e'),))
        self.execute()
        self.assertEqual(self.calls, [])

    def test_changed_storage_and_symlink_rejected(self):
        self.path.write_bytes(self.path.read_bytes() + b'{}\n')
        self.execute()
        self.assertEqual(self.calls, [])
        link = self.path.parent / 'link'
        link.symlink_to(self.path)
        with self.assertRaisesRegex(ValueError, 'DURABLE_STATE_UNTRUSTED'):
            self.r.DurableSecurityJournal(link, storage_id='fixture')

    def test_outcome_write_failure_retains_unknown_after_restart(self):
        original = self.j.append
        def fail(entry):
            if entry.state == self.r.JournalState.KNOWN_SUCCESS:
                raise OSError('outcome lost')
            return original(entry)
        with patch.object(self.j, 'append', side_effect=fail):
            self.assertEqual(self.execute().execution_state, 'UNKNOWN_OUTCOME')
        self.j = self.reopen()
        self.assertEqual(self.execute().execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(self.calls, ['a'])

    def test_real_exit_after_barrier_fresh_interpreter_blocks_retry(self):
        # Child exits inside the adapter: no Python exception/finally recovery.
        code = '''
import os, sys
sys.path.insert(0, sys.argv[1])
import runtime_safety_envelope as r
j=r.DurableSecurityJournal(sys.argv[2], storage_id='fixture')
a=r.ActionRequest('a','run','task',r.ActionClass.WRITE_FILE,'/synthetic/file','provider','runtime',r.DataClass.NON_SENSITIVE,'auth','filesystem.write','SECRET_MARKER')
p=r.Policy('core',r.PolicyLevel.CORE,allowed_actions=frozenset(r.ActionClass),write_roots=('/synthetic',),allowed_capabilities=frozenset({'filesystem.write'}))
auth=r.Authorization('auth','task',frozenset(r.ActionClass),('/synthetic/file',),frozenset({'filesystem.write'}),100)
class Adapter:
 def execute(self,a): os._exit(73)
b=r.CapabilityBroker(); b.register('filesystem.write',Adapter())
out=r.evaluate_and_execute(a,(p,),auth,b,j,1)
print(out.execution_state, flush=True)
'''
        args = [sys.executable, '-c', code, str(SCRIPTS), str(self.path)]
        first = subprocess.run(args, capture_output=True, timeout=10)
        self.assertEqual(first.returncode, 73)
        second = subprocess.run(args, capture_output=True, timeout=10)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(second.stdout.strip(), b'UNKNOWN_OUTCOME')

    def test_import_has_no_storage_side_effects(self):
        code = '''
import os, sys
sys.path.insert(0, sys.argv[1])
def forbidden(*a, **k): raise AssertionError('storage on import')
os.open=forbidden
import runtime_safety_envelope
'''
        out = subprocess.run([sys.executable, '-c', code, str(SCRIPTS)], capture_output=True, timeout=10)
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_real_crash_before_invocation_and_after_effect(self):
        # Every scenario runs in its own fresh storage, with actual abrupt exit.
        code = '''
import os, sys
sys.path.insert(0, sys.argv[1])
import runtime_safety_envelope as r
path, mode, phase = sys.argv[2:]
j=r.DurableSecurityJournal(path, storage_id='windows', create=phase=='crash')
a=r.ActionRequest('a','run','task',r.ActionClass.WRITE_FILE,'/synthetic/file','provider','runtime',r.DataClass.NON_SENSITIVE,'auth','filesystem.write','write')
p=r.Policy('core',r.PolicyLevel.CORE,allowed_actions=frozenset(r.ActionClass),write_roots=('/synthetic',),allowed_capabilities=frozenset({'filesystem.write'}))
auth=r.Authorization('auth','task',frozenset(r.ActionClass),('/synthetic/file',),frozenset({'filesystem.write'}),100)
original=j.append
def append(e):
 if phase=='crash' and mode=='before_barrier' and e.state==r.JournalState.ATTEMPTED: os._exit(74)
 if phase=='crash' and mode=='before_outcome' and e.state==r.JournalState.KNOWN_SUCCESS: os._exit(74)
 original(e)
 if phase=='crash' and mode=='after_barrier' and e.state==r.JournalState.ATTEMPTED: os._exit(74)
j.append=append
class Adapter:
 def execute(self,a):
  with open(path+'.effect','ab') as f: f.write(b'x')
  return r.ExecutionResult(r.ExecutionState.KNOWN_SUCCESS,('effect',))
b=r.CapabilityBroker(); b.register('filesystem.write',Adapter())
print(r.evaluate_and_execute(a,(p,),auth,b,j,1).execution_state)
'''
        for mode in ('before_barrier', 'after_barrier', 'before_outcome'):
            path = self.path.parent / mode
            args = [sys.executable, '-c', code, str(SCRIPTS), str(path), mode]
            self.assertEqual(subprocess.run(args + ['crash'], capture_output=True, timeout=10).returncode, 74)
            effect = Path(str(path) + '.effect')
            self.assertEqual(effect.exists(), mode == 'before_outcome')
            result = subprocess.run(args + ['recover'], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), b'UNKNOWN_OUTCOME')
            if effect.exists():
                self.assertEqual(effect.read_bytes(), b'x')

    def test_complete_record_truncation_is_explicitly_bounded(self):
        self.execute()
        # Removing outcome leaves ATTEMPTED: conservative UNKNOWN, not success.
        self.path.write_bytes(b''.join(self.path.read_bytes().splitlines(keepends=True)[:-1]))
        self.j = self.reopen()
        self.assertEqual(self.execute().execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(self.calls, ['a'])

    def test_conflicting_action_request_is_rejected(self):
        from dataclasses import replace
        self.r._append(self.j, self.a, self.r.JournalState.PROPOSED)
        with self.assertRaisesRegex(ValueError, 'DURABLE_STATE_UNTRUSTED'):
            self.r._append(self.j, replace(self.a, target='/synthetic/other'), self.r.JournalState.AUTHORIZED)

    def test_rehashed_invalid_transition_is_rejected(self):
        import hashlib
        self.execute()
        lines = self.path.read_bytes().splitlines(keepends=True)
        row = json.loads(lines[1]); row['entry']['state'] = 'KNOWN_SUCCESS'
        row['entry']['evidence_refs'] = [self.r._ref('evidence')]
        row.pop('digest'); row['digest'] = hashlib.sha256(self.j._encode(row)).hexdigest()
        self.path.write_bytes(lines[0] + self.j._encode(row))
        with self.assertRaisesRegex(ValueError, 'DURABLE_STATE_UNTRUSTED'):
            self.reopen()


import test_agent_runtime_integration as bridge_tests


class DurableBridgeTests(unittest.TestCase):
    setUpClass = classmethod(bridge_tests.BridgeTests.setUpClass.__func__)
    tearDownClass = classmethod(bridge_tests.BridgeTests.tearDownClass.__func__)
    proposal = bridge_tests.BridgeTests.proposal
    prepare = bridge_tests.BridgeTests.prepare
    bind = bridge_tests.BridgeTests.bind
    execute = bridge_tests.BridgeTests.execute

    def setUp(self):
        bridge_tests.BridgeTests.setUp(self)
        self.path = self.root / 'durable'
        self.journal = self.r.DurableSecurityJournal(self.path, storage_id='bridge', create=True)

    def test_new_proposal_cannot_evade_restart_unknown(self):
        p = self.prepare().prepared
        self.bind(p)
        # A real local write occurred, then the adapter lost its response.
        original = self.fs.run
        def lost(*args):
            original(*args)
            raise RuntimeError('lost response')
        with patch.object(self.fs, 'run', side_effect=lost):
            self.assertEqual(self.execute(p).receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual((self.root / 'file').read_bytes(), b'content')
        self.journal = self.r.DurableSecurityJournal(self.path, storage_id='bridge')
        self.bridge = self.m.AgentRuntimeBridge()
        q = self.prepare(self.proposal(proposal_id='different'), ident='new-action').prepared
        self.bind(p, q)
        self.assertEqual(self.execute(q).status, 'RECONCILIATION_REQUIRED')
        self.assertEqual(self.execute(p, reconcile=True).receipt.final_disposition, 'RECONCILED_SUCCESS')

    def test_remote_unknown_replays_without_network_reconciliation(self):
        p = self.prepare(self.proposal('NETWORK_REQUEST')).prepared
        self.bind(p)
        with patch.object(self.service, 'request', side_effect=TimeoutError):
            self.assertEqual(self.execute(p).receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.journal = self.r.DurableSecurityJournal(self.path, storage_id='bridge')
        self.bridge = self.m.AgentRuntimeBridge()
        q = self.prepare(self.proposal('NETWORK_REQUEST', proposal_id='new'), ident='new').prepared
        self.bind(q)
        self.assertEqual(self.execute(q).status, 'RECONCILIATION_REQUIRED')


if __name__ == '__main__':
    unittest.main()
