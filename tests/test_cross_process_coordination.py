"""Real independent interpreters, synthetic effects, pipe-synchronized admission."""
import importlib
import io
import os
from pathlib import Path
import subprocess
import select
import signal
import threading
from contextlib import contextmanager
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/long-horizon-engineering/scripts'

# The initial RED used H1 RSE admission and demonstrated two actual adapter
# entries. This final probe exercises the supported coordinated Bridge path.
RACE = r'''
import os, sys
sys.path.insert(0, sys.argv[1])
import agent_runtime_integration as m
r, sc, cet, local = m.rse, m.sc, m.cet, m.local
root, identity = sys.argv[2:4]
mode = sys.argv[4] if len(sys.argv)>4 else 'hold'
try:
 owner = r.CrossProcessOwner(root)
except ValueError as e:
 print(str(e), flush=True); sys.exit(0)
j = r.DurableSecurityJournal(root+'/journal', storage_id='fixture', create=identity=='A' and mode!='recover', owner=owner)
chain = sc.JsonlSecurityChain('chain','install',root+'/chain',create=identity=='A' and mode!='recover',owner=owner)
bridge = m.AgentRuntimeBridge(owner=owner)
ctx=cet.TraceContext('trace','install','project','task','run',identity,None,'provider',None,'runtime')
prepared=bridge.prepare(dict(proposal_id=identity,requested_action_class='CREATE_FILE',requested_target=root+'/effect',requested_parameters={'content_bytes':b'x'}),context=ctx,trusted_agent_id='agent',authorization_ref='auth',data_classification=r.DataClass.NON_SENSITIVE,now=1).prepared
p = r.Policy('core',r.PolicyLevel.CORE,allowed_actions={r.ActionClass.CREATE_FILE},write_roots=(root,),allowed_capabilities={'filesystem.write'})
auth = r.Authorization('auth','task',{r.ActionClass.CREATE_FILE},(root+'/effect',),{'filesystem.write'},100)
append = j.append
def fault(entry):
 if mode=='before_proposed' and entry.state==r.JournalState.PROPOSED: os._exit(73)
 if mode=='before_barrier' and entry.state==r.JournalState.ATTEMPTED: os._exit(73)
 if mode=='before_outcome' and entry.state==r.JournalState.KNOWN_SUCCESS: os._exit(73)
 append(entry)
 if mode=='after_barrier' and entry.state==r.JournalState.ATTEMPTED: os._exit(73)
j.append=fault
class Adapter(local.FilesystemAdapter):
 def run(self, *args):
  if mode=='hold':
   print('ENTERED', flush=True)
   if identity == 'A': sys.stdin.readline()
  if mode=='during_effect': os._exit(73)
  if mode=='parent_death':
   child=os.fork()
   if child==0:
    print('CHILD_READY',flush=True)
    sys.stdin.readline()
    with open(root+'/effect','wb') as stream: stream.write(b'x')
    print('CHILD_DONE',flush=True)
    os._exit(0)
   os._exit(73)
  return super().run(*args)
b=r.CapabilityBroker(); b.register('filesystem.write', Adapter(workspace_root=root))
binding=local.RuntimeBinding(b,j,chain,sc.SecurityAuthority('actor',sc.AuthorityRole.RUNTIME,'install'),approved_payload_digests={identity:prepared.payload_digest})
out=bridge.execute(prepared,binding=binding,expected_payload_digest=prepared.payload_digest,expected_prepared_digest=prepared.prepared_digest,policy_stack=(p,),authorization=auth,context=ctx,now=2)
print(out.receipt.final_disposition, flush=True)
if mode=='recover':
 print(out.status,flush=True)
 print(j.latest('A').state.value if j.latest('A') else 'EMPTY',flush=True)
owner.close()
'''

OBSERVER = r'''
import os,sys
sys.path.insert(0,sys.argv[1])
import host_observer as h
r,sc,cet=h.cet.rse,h.cet.sc,h.cet
root,session,ident,phase=sys.argv[2:]
try:
 owner=r.CrossProcessOwner(root)
 chain=sc.JsonlSecurityChain('chain','install',root+'/chain',create=phase=='create',owner=owner)
 ingestor=h.HostObservationIngestor('observer','ref:source',trace=cet.CriticalTrace('trace','install'),chain=chain,
  actor=sc.SecurityAuthority('runtime',sc.AuthorityRole.RUNTIME,'install'),owner=owner,session_id=session)
 result=ingestor.ingest(h.HostObservation(h.SCHEMA,'observer','ref:source',session,ident,1,1,'FILE_WRITE',None,'ref:target',None,'SCOPED_COMPLETE'))
 print(result.accepted,result.reason,result.effective_coverage,flush=True)
 if phase=='create': sys.stdin.readline()
 assert chain.verify().valid
 print(chain.head()[0],flush=True)
 owner.close()
except ValueError as e: print(str(e),flush=True)
'''


class CrossProcessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(sys.path.remove, str(SCRIPTS))
        self.r = importlib.import_module('runtime_safety_envelope')

    def owner(self):
        self.assertTrue(hasattr(self.r, 'CrossProcessOwner'), 'lifecycle ownership missing')
        owner = self.r.CrossProcessOwner(self.root)
        self.addCleanup(owner.close)
        return owner

    def script(self, code, *, input=''):
        prefix = 'import os,sys\nsys.path.insert(0,sys.argv[1])\nimport runtime_safety_envelope as r\nroot=sys.argv[2]\n'
        process = subprocess.Popen([sys.executable,'-c',prefix+code,str(SCRIPTS),str(self.root)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        try:
            out, error = process.communicate(input,timeout=15)
            self.assertEqual(process.returncode,0,error)
            return out.strip()
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=10)

    def test_fork_child_cannot_use_owner_or_unlock_parent(self):
        out = self.script('''
owner=r.CrossProcessOwner(root)
child=os.fork()
if child==0:
 try: owner.check(); os._exit(91)
 except ValueError: pass
 owner.close()
 try: r.CrossProcessOwner(root); os._exit(92)
 except ValueError as e: os._exit(0 if str(e)=='OWNERSHIP_CONTENDED' else 93)
_,status=os.waitpid(child,0)
assert os.waitstatus_to_exitcode(status)==0, status
owner.check(); owner.close()
next_owner=r.CrossProcessOwner(root); next_owner.close()
print('FORK_SAFE')
''')
        self.assertEqual(out,'FORK_SAFE')

    def test_fork_during_construction_does_not_retain_hidden_lock(self):
        # Fork precisely after acquisition and validation, before ctor returns.
        # Removing construction registration retains a hidden child descriptor.
        out = self.script('''
original=r.CrossProcessOwner.check
armed=True
child=None
rd,wr=os.pipe()
ready_r,ready_w=os.pipe()
def check(self):
 global armed,child
 original(self)
 if armed:
  armed=False
  child=os.fork()
  if child==0:
   os.close(wr); os.write(ready_w,b'r'); os.read(rd,1); os._exit(0)
r.CrossProcessOwner.check=check
owner=r.CrossProcessOwner(root)
assert os.read(ready_r,1)==b'r'
owner.close()
try:
 next_owner=r.CrossProcessOwner(root); next_owner.close()
 print('REACQUIRED',flush=True)
except ValueError as e: print(str(e),flush=True)
os.write(wr,b'x')
os.waitpid(child,0)
''')
        self.assertEqual(out,'REACQUIRED')

    def test_unsupported_filesystem_and_hardlink_rejected(self):
        with patch.object(self.r,'_local_posix_storage',return_value=False):
            with self.assertRaisesRegex(ValueError,'OWNERSHIP_STORAGE_UNSUPPORTED'):
                self.owner()
        owner=self.owner()
        journal=self.root/'journal'
        self.r.DurableSecurityJournal(journal,storage_id='x',create=True,owner=owner)
        os.link(journal,self.root/'hardlink')
        with self.assertRaisesRegex(ValueError,'OWNERSHIP_IDENTITY_INVALID'):
            owner.check()

    def test_failed_lock_acquisition_is_explicit_and_does_not_leave_owner(self):
        import fcntl
        with patch.object(fcntl,'flock',side_effect=OSError('synthetic failure')):
            try:
                self.r.CrossProcessOwner(self.root)
            except Exception as error:
                self.assertIsInstance(error,ValueError)
                self.assertEqual(str(error),'OWNERSHIP_ACQUISITION_FAILED')
            else:
                self.fail('failed lock admitted controller')
        self.owner().check()

    def test_cross_directory_hardlink_rejected_before_recovery(self):
        original=self.root/'original'
        self.r.DurableSecurityJournal(original,storage_id='x',create=True)
        other=self.root/'other'; other.mkdir(mode=0o700)
        os.link(original,other/'journal')
        owner=self.r.CrossProcessOwner(other); self.addCleanup(owner.close)
        recovered=[]
        real_load=self.r.DurableSecurityJournal._load
        def load(journal):
            recovered.append(True)
            return real_load(journal)
        with patch.object(self.r.DurableSecurityJournal,'_load',load):
            with self.assertRaises(ValueError):
                self.r.DurableSecurityJournal(other/'journal',storage_id='x',owner=owner)
        self.assertEqual(recovered,[],'aliased storage recovered before rejecting its identity')

    def test_duplicate_owner_and_aliases_cannot_split_domain(self):
        owner = self.owner()
        with self.assertRaisesRegex(ValueError, 'OWNERSHIP_CONTENDED'):
            self.r.CrossProcessOwner(self.root)
        link = self.root / 'alias'
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'OWNERSHIP_IDENTITY_INVALID'):
            self.r.CrossProcessOwner(link)
        with self.assertRaisesRegex(ValueError, 'OWNERSHIP_STORAGE_MISMATCH'):
            self.r.DurableSecurityJournal(self.root.parent / 'outside', storage_id='x', owner=owner, create=True)

    def test_close_during_operation_is_rejected_and_closed_journal_unusable(self):
        owner = self.owner()
        journal = self.r.DurableSecurityJournal(self.root / 'journal', storage_id='fixture', create=True, owner=owner)
        with journal.transaction():
            with self.assertRaisesRegex(ValueError, 'OWNERSHIP_BUSY'):
                owner.close()
        owner.close()
        with self.assertRaisesRegex(ValueError, 'OWNERSHIP_INVALID'):
            journal.history('a')

    def test_lock_replacement_invalidates_owner(self):
        owner = self.owner()
        lock = self.root / '.h2-owner'
        lock.rename(self.root / 'old-lock')
        lock.touch(mode=0o600)
        with self.assertRaisesRegex(ValueError, 'OWNERSHIP_IDENTITY_INVALID'):
            owner.check()

    def test_unsupported_platform_rejected_before_storage_mutation(self):
        self.assertTrue(hasattr(self.r, 'CrossProcessOwner'), 'lifecycle ownership missing')
        with patch.object(sys, 'platform', 'win32'):
            with self.assertRaisesRegex(ValueError, 'OWNERSHIP_PLATFORM_UNSUPPORTED'):
                self.r.CrossProcessOwner(self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_linux_escaped_or_stacked_mount_cannot_fall_back_to_local_parent(self):
        tables=(('1 0 8:1 / / rw - ext4 /dev/a rw\n'
                 '2 1 0:2 / /trusted/remote\\040space rw - nfs server:/share rw\n',
                 '/trusted/remote space/domain'),
                ('1 0 8:1 / / rw - xfs /dev/a rw\n'
                 '2 1 0:2 / / rw - nfs server:/share rw\n','/domain'))
        for table,path in tables:
            with patch.object(sys,'platform','linux'), patch('builtins.open',return_value=io.StringIO(table)):
                self.assertFalse(self.r._local_posix_storage(0,path))

    def test_two_independent_controllers_cannot_admit_same_material(self):
        # Without lifecycle ownership B enters while A is still executing.
        args = [sys.executable, '-c', RACE, str(SCRIPTS), str(self.root)]
        first = subprocess.Popen(args + ['A'], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(select.select([first.stdout], [], [], 10)[0], 'controller readiness timeout')
            self.assertEqual(first.stdout.readline().strip(), 'ENTERED')
            before = (self.root / 'journal').read_bytes()
            second = subprocess.run(args + ['B'], capture_output=True, text=True, timeout=10)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(second.stdout.strip(), 'OWNERSHIP_CONTENDED')
            self.assertEqual((self.root / 'journal').read_bytes(), before)
        finally:
            try:
                out, error = first.communicate('\n', timeout=10)
            except subprocess.TimeoutExpired:
                first.kill()
                first.communicate(timeout=10)
                raise
        self.assertEqual(first.returncode, 0, error)
        self.assertEqual(out.strip(), 'KNOWN_SUCCESS')

    def test_actual_crash_windows_fresh_interpreter_recovery(self):
        for mode, state, effect in (('before_proposed','KNOWN_SUCCESS',True),
                ('before_barrier','AUTHORIZED',False), ('after_barrier','ATTEMPTED',False),
                ('during_effect','ATTEMPTED',False), ('before_outcome','ATTEMPTED',True)):
            with self.subTest(mode=mode):
                root=self.root/mode; root.mkdir(mode=0o700)
                args=[sys.executable,'-c',RACE,str(SCRIPTS),str(root),'A']
                crash=subprocess.run(args+[mode],capture_output=True,text=True,timeout=15)
                self.assertEqual(crash.returncode,73,crash.stderr)
                recovered=subprocess.run(args+['recover'],capture_output=True,text=True,timeout=15)
                self.assertEqual(recovered.returncode,0,recovered.stderr)
                self.assertEqual(recovered.stdout.strip().splitlines()[-1],state)
                self.assertEqual((root/'effect').exists(),effect)
                if mode!='before_proposed':
                    self.assertIn('RECONCILIATION_REQUIRED',recovered.stdout)
                    changed=subprocess.run(args[:-1]+['different','recover'],capture_output=True,text=True,timeout=15)
                    self.assertIn('RECONCILIATION_REQUIRED',changed.stdout)

    def test_parent_death_effect_child_does_not_hold_lock_or_clear_unknown(self):
        args=[sys.executable,'-c',RACE,str(SCRIPTS),str(self.root),'A']
        process=subprocess.Popen(args+['parent_death'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,text=True,start_new_session=True)
        try:
            self.assertTrue(select.select([process.stdout],[],[],10)[0])
            self.assertEqual(process.stdout.readline().strip(),'CHILD_READY')
            self.assertEqual(process.wait(timeout=10),73)
            recovered=subprocess.run(args+['recover'],capture_output=True,text=True,timeout=10)
            self.assertEqual(recovered.returncode,0,recovered.stderr)
            self.assertIn('RECONCILIATION_REQUIRED',recovered.stdout)
            self.assertFalse((self.root/'effect').exists())
            out,error=process.communicate('\n',timeout=10)
            self.assertIn('CHILD_DONE',out)
            self.assertEqual((self.root/'effect').read_bytes(),b'x')
            recovered=subprocess.run(args+['recover'],capture_output=True,text=True,timeout=10)
            self.assertIn('RECONCILIATION_REQUIRED',recovered.stdout)
        finally:
            try: os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            process.communicate(timeout=10)

    def test_exec_releases_owner_while_new_image_stays_alive(self):
        code='''
import os,sys
sys.path.insert(0,sys.argv[1])
import runtime_safety_envelope as r
owner=r.CrossProcessOwner(sys.argv[2])
os.execv(sys.executable,[sys.executable,'-c',"print('EXEC_READY',flush=True);input()"])
'''
        process=subprocess.Popen([sys.executable,'-c',code,str(SCRIPTS),str(self.root)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertTrue(select.select([process.stdout],[],[],10)[0])
            self.assertEqual(process.stdout.readline().strip(),'EXEC_READY')
            owner=self.owner(); owner.check()
        finally:
            try: process.communicate('\n',timeout=10)
            except subprocess.TimeoutExpired:
                process.kill(); process.communicate(timeout=10); raise

    def test_controlled_exec_child_cannot_retain_owner(self):
        out=self.script('''
import subprocess
owner=r.CrossProcessOwner(root)
child=subprocess.Popen([sys.executable,'-c',"print('READY',flush=True);input()"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
assert child.stdout.readline().strip()=='READY'
owner.close()
second=r.CrossProcessOwner(root); second.close()
child.communicate('\\n',timeout=10)
assert child.returncode==0
print('CHILD_SAFE')
''')
        self.assertEqual(out,'CHILD_SAFE')

    def test_independent_ingestion_contention_and_fresh_session_handoff(self):
        args=[sys.executable,'-c',OBSERVER,str(SCRIPTS),str(self.root)]
        first=subprocess.Popen(args+['old','one','create'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,text=True)
        try:
            self.assertTrue(select.select([first.stdout],[],[],10)[0])
            self.assertEqual(first.stdout.readline().strip(),'True SEQUENCE_GAP PARTIAL')
            before=(self.root/'chain').read_bytes()
            contender=subprocess.run(args+['other','one','recover'],capture_output=True,text=True,timeout=10)
            self.assertEqual(contender.stdout.strip(),'OWNERSHIP_CONTENDED')
            self.assertEqual((self.root/'chain').read_bytes(),before)
        finally:
            try: out,error=first.communicate('\n',timeout=10)
            except subprocess.TimeoutExpired:
                first.kill(); first.communicate(timeout=10); raise
        self.assertEqual(first.returncode,0,error)
        self.assertEqual(out.strip(),'3')  # session claim, observation claim, CET
        old=subprocess.run(args+['old','two','recover'],capture_output=True,text=True,timeout=10)
        self.assertEqual(old.stdout.strip(),'OBSERVER_SESSION_REUSED')
        self.assertEqual((self.root/'chain').read_bytes(),before)
        repeated=subprocess.run(args+['new','one','recover'],capture_output=True,text=True,timeout=10)
        self.assertEqual(repeated.stdout.splitlines(),['False OBSERVATION_ID_CONFLICT UNKNOWN','4'])
        fresh=subprocess.run(args+['fresh','two','recover'],capture_output=True,text=True,timeout=10)
        self.assertEqual(fresh.stdout.splitlines(),['True SEQUENCE_GAP PARTIAL','7'])


import test_agent_runtime_integration as bridge_tests


class CoordinatedBridgeTests(unittest.TestCase):
    setUpClass = classmethod(bridge_tests.BridgeTests.setUpClass.__func__)
    tearDownClass = classmethod(bridge_tests.BridgeTests.tearDownClass.__func__)
    proposal = bridge_tests.BridgeTests.proposal
    prepare = bridge_tests.BridgeTests.prepare
    bind = bridge_tests.BridgeTests.bind
    execute = bridge_tests.BridgeTests.execute

    def setUp(self):
        bridge_tests.BridgeTests.setUp(self)
        self.owner = self.r.CrossProcessOwner(self.root)
        self.addCleanup(self.owner.close)
        self.journal = self.r.DurableSecurityJournal(self.root / 'journal', storage_id='bridge', create=True, owner=self.owner)
        self.assertIn('owner', __import__('inspect').signature(self.s.JsonlSecurityChain).parameters,
            'chain ownership integration missing')
        self.chain = self.s.JsonlSecurityChain('chain', 'install', self.root / 'chain', create=True, owner=self.owner)
        self.bridge = self.m.AgentRuntimeBridge(owner=self.owner)

    def test_completed_material_rejected_after_handoff_with_new_ids(self):
        p = self.prepare().prepared
        self.bind(p)
        self.assertEqual(self.execute(p).receipt.execution_state, 'KNOWN_SUCCESS')
        self.owner.close()
        self.owner = self.r.CrossProcessOwner(self.root)
        self.addCleanup(self.owner.close)
        self.journal = self.r.DurableSecurityJournal(self.root / 'journal', storage_id='bridge', owner=self.owner)
        self.chain = self.s.JsonlSecurityChain('chain', 'install', self.root / 'chain', owner=self.owner)
        self.bridge = self.m.AgentRuntimeBridge(owner=self.owner)
        q = self.prepare(self.proposal(proposal_id='different'), ident='different').prepared
        self.bind(q)
        before = (self.root / 'file').stat().st_mtime_ns
        self.assertNotEqual(self.execute(q).receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertEqual((self.root / 'file').stat().st_mtime_ns, before)
        self.assertTrue(self.chain.verify().valid)

    def test_mismatched_chain_or_missing_bridge_owner_denied_before_effect(self):
        p = self.prepare().prepared
        for replacement in (self.s.InMemorySecurityChain('other', 'install'), None):
            if replacement is not None:
                self.chain = replacement
            else:
                self.bridge = self.m.AgentRuntimeBridge()
            self.bind(p)
            out = self.execute(p)
            self.assertEqual(out.status, 'OWNERSHIP_COMPOSITION_MISMATCH')
            self.assertFalse((self.root / 'file').exists())

    def test_closed_owner_rejects_bridge_and_chain_without_writes(self):
        p = self.prepare().prepared
        self.bind(p)
        before = (self.root / 'chain').read_bytes()
        self.owner.close()
        self.assertNotEqual(self.execute(p).receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertFalse((self.root / 'file').exists())
        self.assertFalse(self.chain.verify().valid)
        self.assertEqual((self.root / 'chain').read_bytes(), before)

    def test_fork_inherited_bridge_denies_actual_execution_parent_still_works(self):
        p=self.prepare().prepared; self.bind(p)
        rd,wr=os.pipe()
        child=os.fork()
        if child==0:
            os.close(rd)
            try:
                out=self.execute(p)
                denied=out.receipt.execution_state=='NOT_ATTEMPTED' and not (self.root/'file').exists()
                self.owner.close()
                os.write(wr,b'DENIED' if denied else b'BAD')
            finally:
                os._exit(0)
        os.close(wr)
        try:
            self.assertTrue(select.select([rd],[],[],10)[0], 'forked bridge did not respond')
            self.assertEqual(os.read(rd,32),b'DENIED')
        finally:
            os.close(rd)
            try: os.kill(child,signal.SIGKILL)
            except ProcessLookupError: pass
            os.waitpid(child,0)
        self.owner.check()
        self.assertEqual(self.execute(p).receipt.execution_state,'KNOWN_SUCCESS')

    def test_corrupt_journal_and_replaced_storage_deny_execution(self):
        p=self.prepare().prepared; self.bind(p)
        (self.root/'journal').write_bytes(b'corrupt\n')
        self.assertNotEqual(self.execute(p).receipt.execution_state,'KNOWN_SUCCESS')
        self.assertFalse((self.root/'file').exists())
        with self.assertRaisesRegex(ValueError,'DURABLE_STATE_UNTRUSTED'):
            self.r.DurableSecurityJournal(self.root/'journal',storage_id='bridge',owner=self.owner)
        (self.root/'chain').rename(self.root/'old-chain')
        (self.root/'chain').touch(mode=0o600)
        self.assertNotEqual(self.execute(p).receipt.execution_state,'KNOWN_SUCCESS')
        self.assertFalse((self.root/'file').exists())

    def test_legacy_reopen_of_coordinated_storage_is_rejected(self):
        for constructor in (lambda: self.r.DurableSecurityJournal(self.root / 'journal', storage_id='bridge'),
                lambda: self.s.JsonlSecurityChain('chain', 'install', self.root / 'chain')):
            with self.assertRaisesRegex(ValueError, 'OWNERSHIP_REQUIRED'):
                constructor()

    def test_direct_local_and_remote_bindings_cannot_bypass_composition(self):
        for kind in ('CREATE_FILE', 'NETWORK_REQUEST'):
            p = self.prepare(self.proposal(kind)).prepared
            self.bind(p)
            out = self.binding.execute(p.action_request, p.normalized_payload, policy_stack=(self.policy,),
                authorization=self.r.Authorization('auth','task',{p.action_request.action_class},
                    (p.action_request.target,),{p.trusted_capability_name},100), context=p.context, now=2)
            self.assertEqual(out.receipt.policy_reason, 'OWNERSHIP_COMPOSITION_MISMATCH')
        self.assertFalse((self.root / 'file').exists())

    def test_sync_failure_prevents_effect(self):
        p=self.prepare().prepared; self.bind(p)
        with patch('os.fsync',side_effect=OSError('synthetic barrier failure')):
            self.assertNotEqual(self.execute(p).receipt.execution_state,'KNOWN_SUCCESS')
        self.assertFalse((self.root/'file').exists())

    def test_corrupt_chain_denies_before_journal_or_effect(self):
        p=self.prepare().prepared; self.bind(p)
        (self.root/'chain').write_bytes(b'not-json\n')
        before=(self.root/'journal').read_bytes()
        self.assertNotEqual(self.execute(p).receipt.execution_state,'KNOWN_SUCCESS')
        self.assertEqual((self.root/'journal').read_bytes(),before)
        self.assertFalse((self.root/'file').exists())

    def test_chain_read_lock_order_cannot_deadlock_owner_operations(self):
        for read in (self.chain.head, lambda: self.chain.verify_against(0,self.s.GENESIS)):
            reached,release=threading.Event(),threading.Event()
            original=self.owner.operation
            @contextmanager
            def intercepted():
                reached.set()
                if not release.wait(10):
                    raise RuntimeError('test synchronization timeout')
                with original(): yield
            errors=[]
            def worker():
                try: read()
                except Exception as error: errors.append(error)
            with patch.object(self.owner,'operation',intercepted):
                thread=threading.Thread(target=worker,daemon=True); thread.start()
                try:
                    self.assertTrue(reached.wait(10))
                    acquired=self.chain._lock.acquire(blocking=False)
                    if acquired: self.chain._lock.release()
                    self.assertTrue(acquired,'chain mutex taken before owner: lock inversion')
                finally:
                    release.set(); thread.join(10)
                self.assertFalse(thread.is_alive())
                self.assertEqual(errors,[])

    def test_chain_write_failure_after_effect_is_uncertain(self):
        p=self.prepare().prepared; self.bind(p)
        with patch.object(self.chain,'append',side_effect=OSError('synthetic chain failure')):
            result=self.execute(p)
        self.assertEqual(result.receipt.execution_state,'UNKNOWN_OUTCOME')
        self.assertEqual((self.root/'file').read_bytes(),b'content')
        self.assertEqual(self.journal.latest(p.action_request.action_id).state.value,'RECONCILIATION_REQUIRED')

    def test_uncertain_chain_denies_new_material_before_another_effect(self):
        p=self.prepare().prepared; self.bind(p)
        sync=os.fsync
        chain_inode=(self.root/'chain').stat().st_ino
        def fail_chain(fd):
            if os.fstat(fd).st_ino==chain_inode:
                raise OSError('synthetic chain sync failure')
            sync(fd)
        with patch('os.fsync',side_effect=fail_chain):
            self.assertEqual(self.execute(p).receipt.execution_state,'UNKNOWN_OUTCOME')
        q=self.prepare(self.proposal(requested_target=str(self.root/'second')),ident='second').prepared
        self.bind(p,q)
        self.assertNotEqual(self.execute(q).receipt.execution_state,'KNOWN_SUCCESS')
        self.assertFalse((self.root/'second').exists(),'uncertain chain admitted another effect')

    def test_reconciliation_insufficient_evidence_and_stale_authorization(self):
        p=self.prepare().prepared; self.bind(p)
        with patch.object(self.fs,'run',side_effect=RuntimeError('lost reply')):
            self.assertEqual(self.execute(p).receipt.execution_state,'UNKNOWN_OUTCOME')
        with patch.object(self.fs,'reconcile',return_value=self.r.ReconciliationOutcome.STILL_UNKNOWN):
            self.assertEqual(self.execute(p,reconcile=True).receipt.execution_state,'UNKNOWN_OUTCOME')
        with patch.object(self.fs,'reconcile',return_value=self.r.ReconciliationOutcome.EFFECT_NOT_APPLIED):
            self.assertEqual(self.execute(p,reconcile=True).receipt.final_disposition,'RECONCILED_NOT_APPLIED')
        stale=self.execute(p)
        self.assertEqual(stale.receipt.policy_reason,'FRESH_AUTHORIZATION_REQUIRED')
        self.assertFalse((self.root/'file').exists())
        changed=self.prepare(self.proposal(proposal_id='new'),ident='new').prepared
        self.bind(p,changed)
        self.assertEqual(self.execute(changed).receipt.policy_reason,'FRESH_AUTHORIZATION_REQUIRED')
        renewed=self.prepare(authorization_ref='renewed').prepared
        self.bind(renewed)
        auth=self.r.Authorization('renewed','task',{renewed.action_request.action_class},
            (renewed.action_request.target,),{renewed.trusted_capability_name},100)
        self.assertEqual(self.execute(renewed,authorization=auth).receipt.execution_state,'KNOWN_SUCCESS')

    def test_observer_handoff_rejects_old_session_and_old_observation(self):
        import host_observer as h
        import inspect
        self.assertIn('owner', inspect.signature(h.HostObservationIngestor).parameters,
            'observer ownership integration missing')
        def make(session):
            return h.HostObservationIngestor('observer','ref:source',trace=self.c.CriticalTrace('trace','install'),
                chain=self.chain, actor=self.actor, owner=self.owner, session_id=session)
        def event(session, ident):
            return h.HostObservation(h.SCHEMA,'observer','ref:source',session,ident,1,1,
                'FILE_WRITE',None,'ref:target',None,'SCOPED_COMPLETE')
        old = make('old')
        self.assertTrue(old.ingest(event('old','one')).accepted)
        self.owner.close()
        self.owner = self.r.CrossProcessOwner(self.root)
        self.addCleanup(self.owner.close)
        self.chain = self.s.JsonlSecurityChain('chain','install',self.root / 'chain',owner=self.owner)
        before = (self.root / 'chain').read_bytes()
        with self.assertRaisesRegex(ValueError, 'OBSERVER_SESSION_REUSED'):
            make('old')
        self.assertEqual((self.root / 'chain').read_bytes(), before)
        new = make('new')
        before = (self.root / 'chain').read_bytes()
        self.assertFalse(old.ingest(event('old','two')).accepted)
        self.assertFalse(new.ingest(event('old','two')).accepted)
        self.assertFalse(new.ingest(event('new','one')).accepted)
        self.assertEqual((self.root / 'chain').read_bytes(), before)
        out = new.ingest(event('new','two'))
        self.assertEqual((out.accepted,out.reason,out.effective_coverage),(True,'SEQUENCE_GAP','PARTIAL'))
        self.assertTrue(self.chain.verify().valid)
