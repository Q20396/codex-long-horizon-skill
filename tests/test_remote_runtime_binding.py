"""Synthetic remote services; real gates and temporary Git objects, no Internet."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import hashlib
import importlib
import json
import io
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/long-horizon-engineering/scripts'


def pr_offline_spawn(mode, directory, *, delay=0):
    """Test-only bootstrap. Guards live IN the isolated child, before worker GO.

    Counts and synthetic objects survive worker death; no sockets or real API.
    No test selector is accepted by the production worker protocol.
    """
    code = r'''
import sys,os,json,time,socket,signal
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import remote_runtime_binding as m
root=Path(sys.argv[2]); mode=sys.argv[3]
def deny(*a,**k): raise AssertionError('OFFLINE_NETWORK_FORBIDDEN')
socket.getaddrinfo=deny; socket.create_connection=deny; socket.socket=deny
def audit(event,args):
 if event.startswith('socket.'): raise AssertionError('OFFLINE_NETWORK_FORBIDDEN')
sys.addaudithook(audit)
def synthetic(self,method,url,headers,body,**kw):
 assert socket.socket is deny and socket.getaddrinfo is deny
 assert kw['timeout']>0 and ('user-agent','20396-remote-runtime-binding') in headers
 (root/'guard').write_text('CHILD_GUARD_AND_FAKE_HTTP_ACTIVE')
 if mode in ('dns','connect','tls','write-before'): time.sleep(4)
 with (root/'counts').open('a') as f: f.write(method+'\n')
 if method=='POST':
  v=json.loads(body); obj=dict(v,id=84,number=42,
    head=dict(ref=v['head'],label='team:'+v['head'],repo=dict(full_name='team/repo')),
    base=dict(ref=v['base'],repo=dict(full_name='team/repo')))
  (root/'object').write_text(json.dumps(obj))
 else: obj=[json.loads((root/'object').read_text())] if (root/'object').exists() else []
 if mode in ('read','write-after','trickle','lose'): time.sleep(4)
 if mode=='die': os._exit(71)
 if mode=='ignore-term': signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(4)
 if mode=='group-child':
  if os.fork()==0:
   signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(4); os._exit(0)
 if mode=='delayed': time.sleep(.2)
 if mode=='partial': raise m._ObservedResponseFailure(200)
 return (201 if method=='POST' else 200), ((('link','next'),) if mode=='link' else ()), json.dumps(obj).encode()
m.HTTPSRemoteTransport.request=synthetic
original_frame=m._pr_frame
def frame(value,limit):
 data=original_frame(value,limit)
 if value.get('kind')=='result':
  if mode=='extra': data+=data
  if mode=='truncated': data=data[:9]
  if mode=='overflow': data=(13*1024*1024).to_bytes(4,'big')
  if mode=='bad-version': value=dict(value,version=9); data=original_frame(value,limit)
  if mode=='stderr': os.write(2,b'x'*5000)
 return data
m._pr_frame=frame
m._pr_worker_main()
'''
    if delay:
        time.sleep(delay)
    return subprocess.Popen([sys.executable, '-I', '-B', '-S', '-c', code,
        str(SCRIPTS), str(directory), mode], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
        start_new_session=True, env={'PATH':'/usr/bin:/bin','LANG':'C'})


class PRBoundedTests(unittest.TestCase):
    def setUp(self):
        self.children = []
        self.launches = []
        self._fixture_budgets = []
        self._patches = []
        self._fixture_events = []
        self.root = None
        self.f = RemoteTests('runTest')
        saved_path = sys.path[:]
        def other_cleanup():
            try:
                self.assertTrue(self.f.doCleanups(), 'PR_FIXTURE_HELPER_CLEANUP_FAILED')
            finally:
                sys.path[:] = saved_path
        self._fixture_other = other_cleanup
        self._fixture_remove = lambda: shutil.rmtree(self.root) if self.root is not None else None
        # Register before partial class/setup/patch failures. With a live launch,
        # cleanup_children still requires original owner quiescence first.
        self.addCleanup(self.cleanup_children)
        RemoteTests.setUpClass()
        self.f.setUp()
        self.m = self.f.m
        self.assertTrue(hasattr(self.m, 'PRCreateBoundedHTTPS'), 'PR supervision missing')
        self.root = Path(tempfile.mkdtemp())
        original_init = self.m._PRLaunch.__init__
        def tracked_init(state, *, request_budget=None, selected_handle_only=False):
            original_init(state, request_budget=request_budget, selected_handle_only=selected_handle_only)
            self.launches.append(state)
            self._fixture_budgets.append((state, request_budget))
        for item in (patch.object(self.m,'_PR_CLEANUP',1.0),
                     patch.object(self.m,'_PR_STARTUP',.5),
                     patch.object(self.m._PRLaunch,'__init__',tracked_init)):
            item.start()
            self._patches.append(item)
        self.transport = self.m.PRCreateBoundedHTTPS(credential_headers=(('Authorization','synthetic-only'),))
        self.p = self.m.RemoteRuntimePayload('a', self.m.rse.ActionClass.PR_CREATE,
            'https://api.example.invalid/repos/team/repo/pulls', provider='github',
            repository='team/repo', head='feature', base='main', title='Title',
            body=b'body', draft=True, request_identity='request-1', timeout=3)
        self.f.broker.register('github.pr.create', self.m.PullRequestCreateAdapter(
            transport=self.transport, allowed_origins=('https://api.example.invalid',)))
        self.f.prepare([self.p])

    def cleanup_children(self):
        # Observation only. UNKNOWN is not quiescence and cached None is not
        # permission for a second kill/wait. No unconditional LIFO callbacks.
        for state in self.launches:
            phase, owner, record = state.snapshot()
            if not (state.launcher_done.is_set() and state.cleanup_done.is_set()
                    and phase in ('CLEANUP_CONFIRMED','CLEANUP_UNKNOWN')
                    and record.quiescent and record.reaped and record.pipes_closed):
                if self._outcome is not None and self._outcome.result is not None:
                    self._outcome.result.stop()
                raise AssertionError('PR_FIXTURE_OWNER_NOT_QUIESCENT_RESOURCES_RETAINED')
        self._fixture_events.append(('ownerquiescence',))
        for item in reversed(self._patches): item.stop()
        self._fixture_other()
        self._fixture_remove()

    def spawn(self, mode, delay=0):
        def launch():
            child = pr_offline_spawn(mode, self.root, delay=delay)
            self.children.append(child)
            return child
        return patch.object(self.m, '_pr_spawn_worker', side_effect=launch)

    def count(self, method):
        return (self.root/'counts').read_text().splitlines().count(method) if (self.root/'counts').exists() else 0

    def test_stalls_and_trickle_share_one_deadline(self):
        self.assert_stall_unknown('dns', posts=0)

    def test_connect_stall_is_unknown(self):
        self.assert_stall_unknown('connect', posts=0)

    def test_tls_stall_is_unknown(self):
        self.assert_stall_unknown('tls', posts=0)

    def test_write_before_stall_is_unknown(self):
        self.assert_stall_unknown('write-before', posts=0)

    def test_write_after_stall_is_unknown(self):
        self.assert_stall_unknown('write-after', posts=1)

    def test_read_stall_is_unknown(self):
        self.assert_stall_unknown('read', posts=1)

    def test_trickle_stall_is_unknown(self):
        self.assert_stall_unknown('trickle', posts=1)

    def test_ignore_term_stall_is_unknown(self):
        self.assert_stall_unknown('ignore-term', posts=1)

    def assert_original_launch(self):
        self.assertEqual(len(self.launches), 1)
        state = self.launches[0]
        self.assertIs(type(state), self.m._PRLaunch)
        self.assertEqual(len(self._fixture_budgets), 1)
        original_state, budget = self._fixture_budgets[0]
        self.assertIs(original_state, state)
        self.assertIsNotNone(budget)
        self.assertIs(state._request_budget, budget)
        self.assertIs(state._original_request_budget, budget)
        self.assertIs(self.transport._unresolved, state)
        self.assertFalse(state.cleaned)
        self.assertEqual(state.record.group, 'UNKNOWN')
        return state, budget

    def assert_stall_unknown(self, mode, *, posts):
        with self.spawn(mode):
            start=time.monotonic(); result=self.f.execute(self.p)
            self.assertLessEqual(time.monotonic()-start,3.5)
        self.assertEqual(result.receipt.execution_state,'UNKNOWN_OUTCOME')
        self.assertEqual(len(self.children), 1)
        self.assertTrue((self.root/'guard').exists(), 'synthetic callback not entered')
        self.assertEqual((self.count('POST'),self.count('GET')), (posts,0))
        self.assertTrue(all(child.returncode is not None for child in self.children))
        self.assert_original_launch()

    def test_exact_response_preserves_unknown_and_headers(self):
        original_payload = self.p
        original_action = self.f.action(original_payload)
        with self.spawn('success'):
            result=self.f.execute(original_payload, action=original_action)
        self.assertEqual(result.receipt.execution_state,'UNKNOWN_OUTCOME')
        self.assertEqual((self.count('POST'),self.count('GET')),(1,0))
        self.assertTrue((self.root/'guard').exists())
        self.assertEqual(len(self.children),1)
        self.assertTrue(all(p.returncode is not None for p in self.children))
        self.assertNotIn('synthetic-only',repr(result))
        state, budget = self.assert_original_launch()
        with self.spawn('success'):
            retry = self.f.execute(original_payload, action=original_action)
        self.assertEqual(retry.receipt.execution_state,'UNKNOWN_OUTCOME')
        self.assertEqual(retry.receipt.policy_reason,'UNKNOWN_OUTCOME_PENDING')
        self.assertEqual((self.count('POST'),self.count('GET'),len(self.children)),(1,0,1))
        self.assertIs(self.transport._unresolved,state)
        self.assertIs(state._request_budget,budget)
        self.assertIs(self.p,original_payload)

    def test_lost_response_quarantine_blocks_retry_and_get(self):
        original_payload = self.p
        original_action = self.f.action(original_payload)
        with self.spawn('lose'):
            self.assertEqual(self.f.execute(original_payload,action=original_action).receipt.execution_state,
                             'UNKNOWN_OUTCOME')
        self.assertTrue((self.root/'guard').exists())
        state, budget = self.assert_original_launch()
        with self.spawn('success'):
            retry=self.f.execute(original_payload,action=original_action)
        self.assertEqual(retry.receipt.execution_state,'UNKNOWN_OUTCOME')
        self.assertEqual(retry.receipt.policy_reason,'UNKNOWN_OUTCOME_PENDING')
        for mode in ('link','success'):
            with self.subTest(mode=mode), self.spawn(mode):
                readback=self.f.execute(original_payload,action=original_action,reconcile=True)
                self.assertEqual(readback.receipt.execution_state,'UNKNOWN_OUTCOME')
                self.assertEqual(readback.evidence.reconciliation,'STILL_UNKNOWN')
                self.assertEqual((self.count('POST'),self.count('GET'),len(self.children)),(1,0,1))
                self.assertIs(self.transport._unresolved,state)
                self.assertIs(state._request_budget,budget)
                self.assertIs(state._original_request_budget,budget)
        self.assertIs(self.p,original_payload)
        self.assertEqual(original_action.idempotency_key,original_payload.request_identity)

    def test_malformed_ipc_and_worker_death_are_unknown(self):
        self.assert_malformed_unknown('extra')

    def test_truncated_ipc_is_unknown(self):
        self.assert_malformed_unknown('truncated')

    def test_overflow_ipc_is_unknown(self):
        self.assert_malformed_unknown('overflow')

    def test_bad_version_ipc_is_unknown(self):
        self.assert_malformed_unknown('bad-version')

    def test_stderr_overflow_is_unknown(self):
        self.assert_malformed_unknown('stderr')

    def test_worker_death_is_unknown(self):
        self.assert_malformed_unknown('die')

    def assert_malformed_unknown(self, mode):
        with self.spawn(mode):
            out=self.f.execute(self.p)
        self.assertEqual(out.receipt.execution_state,'UNKNOWN_OUTCOME')
        self.assertNotIn('synthetic-only',repr(out))
        self.assertTrue((self.root/'guard').exists(), 'synthetic callback not entered')
        self.assertEqual((self.count('POST'),self.count('GET'),len(self.children)),(1,0,1))
        self.assert_original_launch()

    def test_late_launch_never_receives_request_or_go(self):
        with self.spawn('success',delay=.8):
            start=time.monotonic(); out=self.f.execute(self.p)
            self.assertLessEqual(time.monotonic()-start,3.5)
            self.assertEqual(out.receipt.execution_state,'UNKNOWN_OUTCOME')
            time.sleep(1)
        self.assertEqual(self.count('POST'),0)
        self.assertFalse((self.root/'guard').exists())
        self.assertTrue(all(c.returncode is not None for c in self.children))

    def test_expired_response_never_becomes_success(self):
        auth=self.f.r.Authorization('auth','task',{self.p.action_class},(self.p.target,),{'github.pr.create'},1.12)
        with self.spawn('delayed'):
            out=self.f.execute(self.p,authorization=auth)
        self.assertNotEqual(out.receipt.execution_state,'KNOWN_SUCCESS')

    def test_direct_wrapper_without_binding_cannot_spawn(self):
        with self.spawn('success'),self.assertRaises(ValueError):
            self.transport.request('POST',self.p.target,(),b'{}',timeout=3,response_limit=65536)
        self.assertEqual(self.children,[])


class StageAFakeOwnershipTests(unittest.TestCase):
    """Real private lifecycle logic; all process/identity/signal/wait boundaries fake.

    Breaks caught: duplicate claimant, reclaim after publication, signal on stale
    identity or after reap, unknown clearing quarantine, unsafe fixture teardown.
    """
    def setUp(self):
        saved = sys.path[:]
        sys.path.insert(0, str(SCRIPTS))
        self.m = importlib.import_module('remote_runtime_binding')
        sys.path[:] = saved
        self.events = []
        self.clock = 0.0
        self.identity_missing = False
        self.signal_error = None
        self.wait_error = None
        self.p = SimpleNamespace(pid=900000001, returncode=None)
        for name in ('stdin','stdout','stderr'):
            setattr(self.p, name, SimpleNamespace(close=lambda n=name:self.events.append(('close',n))))
        def wait(timeout):
            self.events.append(('wait',timeout))
            if self.wait_error: raise self.wait_error
            self.p.returncode = 0
            return 0
        self.p.wait = wait
        def identity(pid):
            self.assertEqual(pid,self.p.pid)
            if self.identity_missing: raise ProcessLookupError(3,'fixture-sensitive')
            return pid
        def killpg(pid,sig):
            self.assertEqual(pid,self.p.pid)
            self.events.append(('signal',int(sig)))
            if self.signal_error: raise self.signal_error
        self.os = SimpleNamespace(getpgid=identity,getsid=identity,getpgrp=lambda:900000000,killpg=killpg)
        def sleep(value): self.clock += value
        self.patches = [patch.object(self.m,'os',self.os),
                        patch.object(self.m,'time',SimpleNamespace(monotonic=lambda:self.clock,sleep=sleep))]
        for item in self.patches: item.start()
        self.addCleanup(lambda:[item.stop() for item in reversed(self.patches)])

    def require_contract(self):
        self.assertTrue(hasattr(self.m._PRLaunch,'claim_parent'), 'exclusive ownership contract missing')

    def parent_state(self):
        self.require_contract()
        state=self.m._PRLaunch()
        state.publish(self.p)
        self.assertIs(state.claim_parent(),self.p)
        state.launcher_done.set()
        return state

    def cleanup(self,state=None):
        if hasattr(self.m._PRLaunch,'claim_parent'):
            return self.m._pr_cleanup(state or self.parent_state(),'parent',10)
        return self.m._pr_cleanup(self.p,10)

    def test_no_numeric_group_signal_after_reap(self):
        self.cleanup()
        waited=next(i for i,v in enumerate(self.events) if v[0]=='wait')
        self.assertEqual([v for v in self.events[waited+1:] if v[0]=='signal'],[])

    def test_missing_identity_forbids_signal_even_with_cached_none(self):
        self.identity_missing=True
        self.cleanup()
        self.assertEqual([v for v in self.events if v[0]=='signal'],[])

    def test_failed_cleanup_cannot_be_retried_by_second_claim(self):
        self.signal_error=PermissionError(1,'fixture-sensitive')
        state=self.parent_state() if hasattr(self.m._PRLaunch,'claim_parent') else None
        self.cleanup(state); self.cleanup(state)
        self.assertEqual([v for v in self.events if v[0]=='signal'],[('signal',15)])

    def test_publish_first_reserves_parent_and_launcher_cannot_clean(self):
        self.require_contract(); state=self.m._PRLaunch(); state.publish(self.p)
        self.assertEqual(state.snapshot()[:2],('PUBLISHED_PARENT','parent'))
        self.assertIsNone(state.begin_cleanup('launcher'))
        self.assertIs(state.claim_parent(),self.p)
        first=state.begin_cleanup('parent')
        self.assertIsNotNone(first)
        self.assertIsNone(state.begin_cleanup('parent'))
        self.assertIsNone(state.begin_cleanup('launcher'))
        self.assertFalse(state.cleaned)
        self.assertEqual(self.events,[])

    def test_cancel_first_keeps_late_launcher_owner_and_zero_go(self):
        self.require_contract(); state=self.m._PRLaunch()
        self.assertIsNone(state.claim_parent())
        with patch.object(self.m,'_pr_spawn_worker',return_value=self.p): self.m._pr_launch(state)
        self.assertEqual(state.snapshot()[:2],('CLEANUP_UNKNOWN','launcher'))
        self.assertTrue(state.launcher_done.is_set())
        self.assertIsNone(state.claim_parent())
        self.assertIsNone(state.begin_cleanup('parent'))
        self.assertFalse(state.cleaned)
        self.assertFalse(any(e[0]=='write' for e in self.events))

    def test_exception_after_publication_does_not_reclaim_handle(self):
        self.require_contract(); state=self.m._PRLaunch()
        state.ready=SimpleNamespace(set=lambda:(_ for _ in ()).throw(RuntimeError('fixture-sensitive')))
        with patch.object(self.m,'_pr_spawn_worker',return_value=self.p): self.m._pr_launch(state)
        self.assertEqual(state.snapshot()[:2],('PUBLISHED_PARENT','parent'))
        self.assertEqual(self.events,[])
        self.assertIs(state.claim_parent(),self.p)

    def test_pending_errno_timeout_and_fixed_immutable_records(self):
        for failure,stage,number in ((PermissionError(1,'fixture-sensitive'),'TERM',1),
                                     (subprocess.TimeoutExpired('fixture-sensitive',1),'WAIT',None)):
            with self.subTest(stage=stage):
                self.p.returncode=None; self.events.clear(); self.signal_error=None; self.wait_error=None
                state=self.parent_state()
                self.assertFalse(state.cleaned)
                if stage=='TERM': self.signal_error=failure
                else: self.wait_error=failure
                record=self.cleanup(state)
                self.assertEqual((record.status,record.stage,record.errno),('UNKNOWN',stage,number))
                self.assertNotIn('fixture-sensitive',repr(record))
                self.assertFalse(state.cleaned)
                with self.assertRaises(AttributeError): record.status='CONFIRMED'
                self.assertTrue(state.cleanup_done.is_set())
                print('STAGE_A_RECORD',json.dumps(asdict(record),sort_keys=True))

    def test_wait_success_does_not_confirm_group_and_reaped_never_signaled(self):
        state=self.parent_state(); record=self.cleanup(state)
        self.assertTrue(record.reaped)
        self.assertEqual((record.status,record.group),('UNKNOWN','UNKNOWN'))
        self.assertFalse(state.cleaned)

        self.events.clear(); self.cleanup(state)
        self.assertEqual(self.events,[])
        state=self.parent_state(); self.p.returncode=0
        record=self.cleanup(state)
        self.assertTrue(record.reaped)
        self.assertFalse(any(e[0]=='signal' for e in self.events))

    def test_confirmed_predicate_checks_complete_fixed_facts_not_default(self):
        self.require_contract()
        record=self.m._PRCleanupRecord('CONFIRMED','COMPLETE',None,(900000001,900000001,900000001),True,'CONFIRMED',True,True)
        self.assertTrue(self.m._pr_cleanup_confirmed(record))
        for values in ({'status':'PENDING'},{'status':'UNKNOWN'},{'reaped':False},
                       {'group':'UNKNOWN'},{'pipes_closed':False},{'quiescent':False},
                       {'errno':1},{'identity':None}):
            self.assertFalse(self.m._pr_cleanup_confirmed(replace(record,**values)))
        self.assertFalse(self.m._pr_cleanup_confirmed(None))
        self.assertFalse(self.m._pr_cleanup_confirmed(SimpleNamespace(status='CONFIRMED')))
        for values in ({'stage':'DYNAMIC_EXEC'},{'errno':'secret'},{'status':'free text'}):
            with self.assertRaises(ValueError): replace(record,**values)
        self.assertEqual(self.cleanup().status,'UNKNOWN')

    def test_teardown_observes_owner_no_resignal_and_orders_resources(self):
        self.require_contract(); state=self.parent_state(); self.cleanup(state)
        self.events.clear()
        fixture=PRBoundedTests('runTest')
        fixture.launches=[state]; fixture._fixture_events=self.events
        fixture._patches=[SimpleNamespace(stop=lambda:self.events.append(('patchrestore',)))]
        fixture._fixture_remove=lambda:self.events.append(('tempremove',))
        fixture._fixture_other=lambda:None
        fixture.cleanup_children()
        self.assertEqual(self.events,[('ownerquiescence',),('patchrestore',),('tempremove',)])
        self.assertFalse(state.cleaned)

    def test_pending_owner_stops_teardown_without_restore_or_remove(self):
        self.require_contract(); state=self.parent_state(); state.begin_cleanup('parent')
        fixture=PRBoundedTests('runTest'); fixture.launches=[state]; fixture._fixture_events=self.events
        fixture._patches=[SimpleNamespace(stop=lambda:self.events.append(('patchrestore',)))]
        fixture._fixture_remove=lambda:self.events.append(('tempremove',)); fixture._fixture_other=lambda:None
        stopped=[]
        fixture._outcome=SimpleNamespace(result=SimpleNamespace(stop=lambda:stopped.append(True)))
        with self.assertRaises(AssertionError): fixture.cleanup_children()
        self.assertEqual(self.events,[]); self.assertEqual(stopped,[True])

    def test_fake_thread_cancel_and_join_before_fixture_restore(self):
        self.require_contract(); state=self.m._PRLaunch()
        entered=threading.Event(); cancel=threading.Event(); failures=[]
        def spawn():
            entered.set()
            if not cancel.wait(1): raise RuntimeError('FAKE_CANCEL_TIMEOUT')
            return self.p
        def run():
            try:self.m._pr_launch(state)
            except BaseException as error: failures.append(type(error).__name__)
        with patch.object(self.m,'_pr_spawn_worker',side_effect=spawn):
            worker=threading.Thread(target=run)
            worker.start()
            try:
                self.assertTrue(entered.wait(1))
                self.assertIsNone(state.claim_parent())
            finally:
                start=time.monotonic(); cancel.set(); worker.join(1)
            self.assertFalse(worker.is_alive()); self.assertLessEqual(time.monotonic()-start,2)
        self.assertEqual(failures,[])
        self.assertTrue(state.launcher_done.is_set()); self.assertFalse(state.cleaned)

    def test_complete_fake_ipc_response_stays_unknown_and_quarantined(self):
        # Stub only process/IPC/authority inputs. Run the actual wrapper acceptance path.
        frames=[self.m._pr_frame({'version':1,'kind':'ready'},65536),
                self.m._pr_frame({'version':1,'kind':'armed'},65536),
                self.m._pr_frame({'version':1,'kind':'result','status':201,'headers':[],
                                  'body':'e30=','complete':True},65536),b'']
        self.p.stdin.fileno=lambda:10; self.p.stdout.fileno=lambda:11; self.p.stderr.fileno=lambda:12
        self.os.set_blocking=lambda *a:None
        self.os.read=lambda fd,n:frames.pop(0) if fd==11 else b''
        self.os.write=lambda fd,data:self.events.append(('write',len(data))) or len(data)
        ports={'in':self.p.stdin,'out':self.p.stdout,'err':self.p.stderr}
        sequence=iter(('out','in','out','in','out','in','out','err'))
        class Selector:
            def register(self,*a): pass
            def unregister(self,*a): pass
            def close(self): pass
            def select(self,timeout):
                kind=next(sequence); port=ports[kind]
                return [(SimpleNamespace(data=kind,fd=port.fileno(),fileobj=port),1)]
        class InlineThread:
            def __init__(self,target,args,**kw): self.target,self.args=target,args
            def start(self): self.target(*self.args)
        transport=self.m.PRCreateBoundedHTTPS()
        payload=SimpleNamespace(repository='team/repo',head='feature',base='main',target='https://api.example.invalid/repos/team/repo/pulls',timeout=10,response_limit=65536)
        budget=self.m._PRBudget(0,10,8,1,None,(),None)
        fake_threads=SimpleNamespace(Thread=InlineThread,Lock=threading.Lock,Event=threading.Event)
        with patch.object(self.m,'_pr_spawn_worker',return_value=self.p), \
             patch.object(self.m,'threading',fake_threads), \
             patch.object(self.m,'selectors',SimpleNamespace(DefaultSelector=Selector,EVENT_READ=1,EVENT_WRITE=2)), \
             patch.object(self.m,'rse',SimpleNamespace(evaluate_policy=lambda *a:SimpleNamespace(disposition='ALLOW'))):
            self.os.name='posix'
            with self.assertRaises(ValueError): transport._request(budget,payload,'POST',payload.target,(),b'{}',timeout=10,response_limit=65536)
            self.assertIsNotNone(transport._unresolved)
            self.assertFalse(transport._unresolved.cleaned)


class RejectedResponseFakeTests(unittest.TestCase):
    """Breaks: exit1 mistaken for rejection, invalid wire promoted, authority renewed.

    Run actual worker transfer/parser and parent/cleanup with in-memory IO only.
    """
    def setUp(self):
        DirectAbortFakeTests.setUp(self)

    def contract(self):
        self.assertTrue(hasattr(self.m._PRLaunch, 'rejected_response_direct_child_exit_observation'),
                        'rejected response contract missing')

    def parent(self, mode='valid', **options):
        self.contract()
        DirectAbortFakeTests.state(self, code=1, wait_return=1, **options)
        # Publication obtains MATCH; first cleanup observation gets ESRCH.
        calls=[]
        def pgid(pid):
            calls.append(pid)
            if len(calls)>1:
                if mode in ('sid_esrch','pgid_mismatch','pgid_invalid','getpgrp_error'):
                    return pid+1 if mode=='pgid_mismatch' else True if mode=='pgid_invalid' else pid
                if mode=='eperm': raise PermissionError(1,'private')
                raise ProcessLookupError(3, 'private')
            return pid
        self.os.getpgid=pgid
        self.os.getsid=lambda pid: (_ for _ in ()).throw(ProcessLookupError(3,'private')) \
            if len(calls)>1 and mode in ('sid_esrch','pgid_mismatch','pgid_invalid') else pid
        self.os.getpgrp=lambda: (_ for _ in ()).throw(ProcessLookupError(3,'private')) \
            if len(calls)>1 and mode=='getpgrp_error' else 900000000
        self.os.name='posix'; self.os.set_blocking=lambda *a:None
        for n,fd in (('stdin',10),('stdout',11),('stderr',12)):
            getattr(self.p,n).fileno=lambda v=fd:v
        frames=[self.m._pr_frame(dict(version=1,kind='ready'),65536),
                self.m._pr_frame(dict(version=1,kind='armed'),65536)]
        writes=[]; request={}; nonce='a'*32
        def write(fd,data):
            writes.append(json.loads(data[4:]))
            if writes[-1]['kind']=='request': request.update(writes[-1])
            return len(data)
        def rejected():
            value=dict(version=1,kind='rejected',rejection_version=1,
                       rejection_nonce=request.get('rejection_nonce',nonce),
                       reason='RESPONSE_BODY_LIMIT',response_limit=2)
            changes={'nonce':{'rejection_nonce':'b'*32},'limit':{'response_limit':3},
                'bool':{'response_limit':True},'version':{'rejection_version':True},
                'reason':{'reason':'PR_IPC_INVALID'},'extra':{'extra':0}}
            value.update(changes.get(mode,{}))
            raw=self.m._pr_frame(value,65536)
            if mode=='duplicate': raw=raw+raw
            if mode=='tail': raw+=b'x'
            if mode=='result': raw+=self.m._pr_frame(dict(version=1,kind='result'),65536)
            if mode=='missing': raw=b''
            if mode=='partial': raw=raw[:-1]
            if mode=='large':
                body=json.dumps(value).encode()+b' '*512
                raw=len(body).to_bytes(4,'big')+body
            return raw
        reads=0
        def read(fd,n):
            nonlocal reads
            if fd==12: return b'private' if mode=='stderr' else b''
            reads+=1
            if reads<=2: return frames.pop(0)
            return rejected() if reads==3 else b''
        self.os.read=read; self.os.write=write
        ports={'in':self.p.stdin,'out':self.p.stdout,'err':self.p.stderr}
        sequence=iter(('out','in','out','out','err') if mode=='prego'
                      else ('out','in','out','in','out','out','err'))
        class Selector:
            def register(self,*a): pass
            def unregister(self,*a): pass
            def close(self): pass
            def select(self,timeout):
                kind=next(sequence); port=ports[kind]
                return [(SimpleNamespace(data=kind,fd=port.fileno(),fileobj=port),1)]
        class InlineThread:
            def __init__(self,target,args,**kw): self.target,self.args=target,args
            def start(self): self.target(*self.args)
        transport=self.m.PRCreateBoundedHTTPS()
        payload=SimpleNamespace(repository='team/repo',head='f',base='main',
            target='https://api.example.invalid/repos/team/repo/pulls',timeout=10,response_limit=2)
        with patch.object(self.m,'_pr_spawn_worker',return_value=self.p), \
             patch.object(self.m,'threading',SimpleNamespace(Thread=InlineThread,Lock=threading.Lock,Event=threading.Event)), \
             patch.object(self.m,'selectors',SimpleNamespace(DefaultSelector=Selector,EVENT_READ=1,EVENT_WRITE=2)):
            with self.assertRaisesRegex(ValueError,'PR_TRANSPORT_UNCERTAIN'):
                transport._request(self.budget,payload,'POST',payload.target,(),b'{}',timeout=10,response_limit=2)
        state=transport._unresolved
        self.assertFalse(state.cleaned)
        self.assertEqual(state.record.group,'UNKNOWN')
        self.assertEqual(state.direct_child_abort_completion,'UNKNOWN')
        self.assertEqual(state.unsealed_direct_child_exit_observation,'UNKNOWN')
        self.assertFalse(any(v['kind']=='ack' for v in writes))
        return state,transport,writes

    def test_valid_wire_owned_wait1_only(self):
        state,transport,writes=self.parent()
        self.assertEqual(transport.rejected_response_direct_child_exit_observation,
                         'REJECTED_RESPONSE_DIRECT_CHILD_EXIT_OBSERVED')
        self.assertEqual(state._rejected_exit.outcome,'REJECTION_EXIT_OBSERVED')
        self.assertEqual(state.record.stage,'IDENTITY')
        self.assertEqual([e[0] for e in self.events if e[0] in ('wait','signal')],['wait'])
        self.assertEqual(writes[0]['rejection_version'],1)
        self.assertRegex(writes[0]['rejection_nonce'],r'^[0-9a-f]{32}$')
        before=list(self.events)
        self.m._pr_cleanup(state,'parent',10)
        self.assertEqual(self.events,before)

    def test_invalid_wire_never_promoted(self):
        for mode in ('nonce','limit','bool','version','reason','extra','duplicate','tail',
                     'result','missing','partial','large','stderr','prego'):
            with self.subTest(mode=mode):
                state,transport,_=self.parent(mode)
                self.assertEqual(transport.rejected_response_direct_child_exit_observation,'UNKNOWN')

    def test_exit_resource_budget_partition(self):
        for options in ({'code':0},{'code':-15},{'code':True},{'wait_return':0},
                        {'wait_error':OSError(9,'private')},{'close_error':'stdout'},
                        {'wait_delay':10}):
            with self.subTest(options=str(options)):
                # parent default arguments remain explicit, not duplicate kwargs.
                state,_,_=self.parent_with_options(options)
                self.assertEqual(state.rejected_response_direct_child_exit_observation,'UNKNOWN')

    def parent_with_options(self,options):
        original=DirectAbortFakeTests.state
        def configured(obj,**kw):
            kw.update(options)
            return original(obj,**kw)
        with patch.object(DirectAbortFakeTests,'state',configured): return self.parent()

    def test_policy_and_reference_binding(self):
        for field in ('process','_request_budget','_original_request_budget','_rejected_protocol',
                      '_rejected_exit','_rejected_context','claimant'):
            with self.subTest(field=field):
                state,_,_=self.parent()
                setattr(state,field,object())
                self.assertEqual(state.rejected_response_direct_child_exit_observation,'UNKNOWN')
        state,_,_=self.parent(); self.policy='DENY'
        self.assertEqual(state.rejected_response_direct_child_exit_observation,'UNKNOWN')
        self.policy='ALLOW'; self.clock=10
        self.assertEqual(state.rejected_response_direct_child_exit_observation,'UNKNOWN')

    def test_partial_identity_veto_preserved(self):
        for mode in ('sid_esrch','pgid_mismatch','pgid_invalid','getpgrp_error','eperm'):
            with self.subTest(mode=mode):
                state,_,_=self.parent(mode)
                self.assertEqual(state.rejected_response_direct_child_exit_observation,
                    'REJECTED_RESPONSE_DIRECT_CHILD_EXIT_OBSERVED' if mode=='sid_esrch' else 'UNKNOWN')

    def test_strict_record_and_atomic_publication(self):
        state,_,_=self.parent()
        record=state._rejected_exit
        for changes in ({'version':True},{'response_limit':True},{'reason':'OTHER'},
                        {'term_attempts':1},{'wait_returncode':0},{'go_sent':False},
                        {'rejection_nonce':'A'*32},{'failures':('OTHER',)}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError): replace(record,**changes)
        with self.assertRaises(AttributeError): record.outcome='UNKNOWN'
        self.assertTrue(state.cleanup_done.is_set())
        with self.assertRaises(ValueError):
            state.finish_direct_abort(state.claimant,state.record,state._direct_abort,
                                      rejected_record=record)
        self.assertIs(state._rejected_exit,record)
        state.cleanup_done.clear()
        self.assertEqual(state.rejected_response_direct_child_exit_observation,'UNKNOWN')

    def worker(self, mode='oversized'):
        self.contract()
        request=dict(version=1,kind='request',method='POST',
            url='https://api.example.invalid/repos/team/repo/pulls',
            headers=[['user-agent','20396-remote-runtime-binding']],credentials=[],
            body='e30=',response_limit=2,remaining=10,rejection_version=1,rejection_nonce='a'*32)
        if mode=='legacy':
            del request['rejection_version']; del request['rejection_nonce']
        if mode=='partial_optin': del request['rejection_nonce']
        if mode=='bad_version': request['rejection_version']=True
        wire=bytearray(b''.join(self.m._pr_frame(v,65536) for v in
            (request,dict(version=1,kind='go'),dict(version=1,kind='ack'))))
        output=bytearray(); exits=[]; requests=[]
        class Exit(BaseException): pass
        def leave(code): exits.append(code); raise Exit()
        def read(fd,n):
            chunk=bytes(wire[:n]); del wire[:n]; return chunk
        def write(fd,data): output.extend(data); return len(data)
        class Selector:
            def register(self,*a): pass
            def unregister(self,*a): pass
            def close(self): pass
            def select(self,*a): return [True]
        def transport_request(*args,**kw):
            requests.append(True)
            if mode=='network': raise OSError(5,'private')
            return (True if mode=='bad_status' else 201,
                    [('bad\n','x')] if mode=='bad_headers' else [],
                    'abc' if mode=='nonbytes' else b'ab' if mode=='equal' else b'a' if mode=='below' else b'abc')
        self.os.set_blocking=lambda *a:None; self.os.read=read; self.os.write=write; self.os._exit=leave
        with patch.object(self.m,'selectors',SimpleNamespace(DefaultSelector=Selector,EVENT_READ=1,EVENT_WRITE=2)), \
             patch.object(self.m,'HTTPSRemoteTransport',return_value=SimpleNamespace(request=transport_request)):
            try: self.m._pr_worker_main()
            except Exit: pass
        messages=[]
        while output:
            n=int.from_bytes(output[:4],'big')
            messages.append(json.loads(output[4:4+n])); del output[:4+n]
        return messages,exits,requests

    def test_worker_emits_one_bound_rejection(self):
        messages,exits,requests=self.worker()
        self.assertEqual(messages,[{'version':1,'kind':'ready'},{'version':1,'kind':'armed'},
            {'version':1,'kind':'rejected','rejection_version':1,'rejection_nonce':'a'*32,
             'reason':'RESPONSE_BODY_LIMIT','response_limit':2}])
        self.assertEqual(exits,[1]); self.assertEqual(len(requests),1)

    def test_worker_non_rejection_and_legacy_partition(self):
        for mode in ('legacy','partial_optin','bad_version','network','bad_status','bad_headers','nonbytes','equal','below'):
            with self.subTest(mode=mode):
                messages,exits,requests=self.worker(mode)
                self.assertFalse(any(m['kind']=='rejected' for m in messages))
                self.assertEqual(exits,[] if mode in ('equal','below') else [1])
                if mode in ('partial_optin','bad_version'): self.assertEqual(requests,[])


class DirectAbortFakeTests(unittest.TestCase):
    """Breaks: false abort completion, stolen ownership, stale budget or policy.

    No native process/thread/signal/sleep. Exercise actual cleanup and publisher.
    """
    def setUp(self):
        StageAFakeOwnershipTests.setUp(self)
        self.assertTrue(hasattr(self.m, '_PRDirectAbortRecord'), 'abort contract missing')
        self.assertTrue(hasattr(self.m._PRLaunch, 'direct_child_abort_completion'), 'abort contract missing')
        self.policy = 'ALLOW'
        def decide(*args):
            if isinstance(self.policy, Exception): raise self.policy
            self.clock += self.policy_delay
            return SimpleNamespace(disposition=self.policy)
        item = patch.object(self.m, 'rse', SimpleNamespace(evaluate_policy=decide))
        item.start(); self.addCleanup(item.stop)

    def state(self, **options):
        self.events.clear(); self.clock = 0.; self.policy_delay = 0.
        self.post = 'ESRCH'; self.signal_error = None; self.wait_error = None
        self.code = -15; self.wait_return = -15; self.close_error = None
        self.wait_delay = 0.; self.close_delay = 0.; self.policy = 'ALLOW'
        self.wait_hook = None; self.original_missing = False
        for key, value in options.items(): setattr(self, key, value)
        self.p.returncode = None
        def identity(pid):
            self.events.append(('identity', pid))
            self.assertIsNone(self.p.returncode, 'query after reap')
            if self.original_missing: raise ProcessLookupError(3, 'private')
            if any(e[0] == 'signal' for e in self.events):
                if self.post == 'ESRCH': raise ProcessLookupError(3, 'private')
                if self.post == 'EPERM': raise PermissionError(1, 'private')
                if self.post == 'MISMATCH': return pid + 1
            return pid
        self.os.getpgid = self.os.getsid = identity
        def killpg(pid, sig):
            self.events.append(('signal', int(sig)))
            if self.signal_error: raise self.signal_error
        self.os.killpg = killpg
        def wait(timeout):
            self.events.append(('wait', timeout))
            self.assertGreater(timeout, 0); self.assertLessEqual(timeout, 10-self.clock)
            if self.wait_hook: self.wait_hook()
            self.clock += self.wait_delay
            if self.wait_error: raise self.wait_error
            self.p.returncode = self.code
            return self.wait_return
        self.p.wait = wait
        for name in ('stdin', 'stdout', 'stderr'):
            def close(n=name):
                self.events.append(('close', n)); self.clock += self.close_delay
                if n == self.close_error: raise OSError(9, 'private')
            setattr(self.p, name, SimpleNamespace(close=close))
        self.budget = self.m._PRBudget(0, 10, 8, 1, None, (), None)
        state = self.m._PRLaunch(request_budget=self.budget)
        state.publish(self.p); self.assertIs(state.claim_parent(), self.p)
        state.launcher_done.set()
        return state

    def finish(self, state, deadline=10):
        self.m._pr_cleanup(state, 'parent', deadline)
        self.assertFalse(state.cleaned)
        self.assertNotEqual(state.record.group, 'CONFIRMED')
        self.assertEqual(state.direct_worker_completion, 'UNKNOWN')
        self.assertLessEqual(len([e for e in self.events if e[0]=='wait']), 1)
        return state._direct_abort

    def test_term_esrch_owned_abort(self):
        state = self.state(); record = self.finish(state)
        self.assertEqual(record.outcome, 'ABORT_OBSERVED')
        self.assertEqual(state.direct_child_abort_completion, 'DIRECT_CHILD_ABORT_COMPLETION')
        self.assertEqual((state.record.stage, state.record.errno), ('IDENTITY', None))
        self.assertEqual(record.identity_errno, 3)
        self.assertEqual([e for e in self.events if e[0] in ('signal','wait','close')],
                         [('signal',15),('wait',9.75),('close','stdin'),('close','stdout'),('close','stderr')])
        self.assertEqual(record.failures, ())

    def test_negative_cache_without_wait(self):
        state = self.state(); self.p.returncode = -15
        self.assertNotEqual(self.finish(state).outcome, 'ABORT_OBSERVED')
        self.assertEqual(state.direct_child_abort_completion, 'UNKNOWN')
        self.assertFalse(any(e[0]=='wait' for e in self.events))

    def test_signal_errors_never_complete(self):
        for error in (ProcessLookupError(3,'private'), PermissionError(1,'private'), RuntimeError('private')):
            with self.subTest(error=type(error).__name__):
                state = self.state(signal_error=error); self.finish(state)
                self.assertEqual(state.direct_child_abort_completion,'UNKNOWN')
                self.assertEqual([e for e in self.events if e[0]=='signal'],[('signal',15)])

    def test_identity_precision_and_kill(self):
        for post in ('EPERM','MISMATCH','MATCH'):
            with self.subTest(post=post):
                state = self.state(post=post); self.finish(state)
                self.assertEqual(state.direct_child_abort_completion,'UNKNOWN')
                self.assertEqual([e[1] for e in self.events if e[0]=='signal'], [15,9] if post=='MATCH' else [15])
        state = self.state(original_missing=True); self.finish(state)
        self.assertEqual(state.direct_child_abort_completion,'UNKNOWN')
        self.assertFalse(any(e[0]=='signal' for e in self.events))

    def test_wait_failures_and_disagreement(self):
        for options in ({'wait_error':subprocess.TimeoutExpired('fake',1)},
                        {'wait_error':OSError(5,'private')}, {'wait_error':RuntimeError('private')},
                        {'wait_return':0}, {'code':None}):
            with self.subTest(options=str(tuple(options))):
                state = self.state(**options); self.finish(state)
                self.assertEqual(state.direct_child_abort_completion,'UNKNOWN')
                self.assertEqual(len([e for e in self.events if e[0]=='wait']),1)

    def test_exit_precision(self):
        for code in (0, 1, -9, True):
            with self.subTest(code=code):
                state = self.state(code=code, wait_return=code); self.finish(state)
                self.assertEqual(state.direct_child_abort_completion,'UNKNOWN')

    def test_pipe_failure_and_error_priority(self):
        for name in ('stdin','stdout','stderr'):
            with self.subTest(name=name):
                state = self.state(close_error=name); record = self.finish(state)
                self.assertIn('PIPE_ERROR',record.failures)
                self.assertEqual(state.record.stage,'IDENTITY')
                self.assertEqual(state.direct_child_abort_completion,'UNKNOWN')
                self.assertEqual(len([e for e in self.events if e[0]=='close']),3)
        state = self.state(wait_error=OSError(5,'private'),close_error='stdout',policy='DENY')
        record = self.finish(state)
        self.assertEqual(record.outcome,'POLICY_DENIED')
        self.assertIn('WAIT_ERROR',record.failures); self.assertIn('PIPE_ERROR',record.failures)
        self.assertEqual((record.error_stage,record.error_errno),('WAIT',5))

    def test_budget_and_deadline_boundaries(self):
        for options in ({'wait_delay':10.}, {'close_delay':4.}, {'policy_delay':11.}):
            state = self.state(**options); record = self.finish(state)
            self.assertIn('BUDGET_EXPIRED',record.failures)
            self.assertEqual(state.direct_child_abort_completion,'UNKNOWN')
        for deadline in (11, 9, float('nan'), float('inf'), True):
            state = self.state(); record = self.finish(state,deadline)
            self.assertEqual(record.outcome,'INVALID')
            self.assertEqual(state.direct_child_abort_completion,'UNKNOWN')
        state = self.state(); self.clock=10.; self.finish(state)
        self.assertFalse(any(e[0] in ('signal','wait') for e in self.events))

    def test_current_policy_and_expiring_accessor(self):
        for policy in ('DENY', ValueError('private')):
            state = self.state(policy=policy); self.finish(state)
            self.assertEqual(state.direct_child_abort_completion,'UNKNOWN')
        state = self.state(); self.finish(state); prior=list(self.events)
        self.policy='DENY'; self.assertEqual(state.direct_child_abort_completion,'UNKNOWN')
        self.policy='ALLOW'; self.clock=10.; self.assertEqual(state.direct_child_abort_completion,'UNKNOWN')
        self.assertEqual(self.events,prior)

    def test_atomic_owner_and_no_replay(self):
        state = self.state()
        def pending():
            self.assertEqual(state.phase,'CLEANUP_PENDING')
            self.assertFalse(state.cleanup_done.is_set())
            self.assertEqual(state.direct_child_abort_completion,'UNKNOWN')
            self.assertIsNone(state.begin_cleanup('parent'))
            self.assertIsNone(state.begin_cleanup('launcher'))
        self.wait_hook=pending; record=self.finish(state); prior=list(self.events)
        self.m._pr_cleanup(state,'parent',10)
        self.assertEqual(prior,self.events)
        with self.assertRaises(ValueError): state.finish_direct_abort(state.claimant,state.record,record)
        self.assertEqual(state.direct_child_abort_completion,'DIRECT_CHILD_ABORT_COMPLETION')

    def test_pair_tampering_and_strict_record(self):
        state=self.state(); record=self.finish(state)
        for changes in ({'version':True},{'identity':(True,1,1)},{'identity':[1,1,1]},
                        {'term_attempts':True},{'term_successes':0},{'kill_attempts':1},
                        {'wait_calls':0},{'returncode':True},{'pipes_closed':False},
                        {'identity_errno':1},{'policy_allowed':False},{'outcome':'COMPLETE'},
                        {'failures':('WAIT_ERROR',)},{'error_errno':0}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError): replace(record,**changes)
        with self.assertRaises(TypeError): self.m._PRDirectAbortRecord(extra=1)
        state.record=replace(state.record,pipes_closed=False)
        self.assertEqual(state.direct_child_abort_completion,'UNKNOWN')

    def test_wrong_claimant_and_forged_publication(self):
        first=self.state(); record=self.finish(first)
        state=self.state(); token,_,_=state.begin_cleanup('parent')
        legacy=first.record
        with self.assertRaises(ValueError): state.finish_direct_abort(object(),legacy,record)
        self.assertEqual(state.phase,'CLEANUP_PENDING')
        state.finish_direct_abort(token,legacy,record)
        self.assertEqual(state.direct_child_abort_completion,'UNKNOWN')
        self.assertEqual(state.record.stage,'IDENTITY')

    def test_budget_reference_and_launcher_event(self):
        state=self.state(); self.finish(state)
        state.launcher_done.clear()
        self.assertEqual(state.direct_child_abort_completion,'UNKNOWN')
        state.launcher_done.set(); state._request_budget=replace(self.budget)
        self.assertEqual(state.direct_child_abort_completion,'UNKNOWN')

    def test_sealed_separation(self):
        state=self.state(); self.code=0; self.wait_return=0
        state.note_protocol_complete(self.budget)
        self.m._pr_cleanup(state,'parent',10)
        self.assertIsNone(state._direct_abort)
        self.assertEqual(state.direct_child_abort_completion,'UNKNOWN')
        self.assertEqual(state.direct_worker_completion,'DIRECT_WORKER_COMPLETION')
        self.assertFalse(any(e[0]=='signal' for e in self.events))

    def test_transport_diagnostic_not_authority(self):
        state=self.state(); self.finish(state)
        transport=self.m.PRCreateBoundedHTTPS(); transport._unresolved=state
        self.assertEqual(transport.direct_child_abort_completion,'DIRECT_CHILD_ABORT_COMPLETION')
        self.assertFalse(transport._unresolved.cleaned)
        prior=list(self.events)
        for _ in range(3): self.assertEqual(state.direct_child_abort_completion,'DIRECT_CHILD_ABORT_COMPLETION')
        self.assertEqual(prior,self.events)


class UnsealedExitFakeTests(unittest.TestCase):
    """Owned unsealed exit is neither effect success nor cleanup authority."""
    finish = DirectAbortFakeTests.finish

    def setUp(self):
        DirectAbortFakeTests.setUp(self)
        self.assertTrue(hasattr(self.m, '_PRUnsealedExitRecord'), 'unsealed contract missing')

    def state(self, snapshot=True, **options):
        values = dict(code=0, wait_return=0); values.update(options)
        state = DirectAbortFakeTests.state(self, **values)
        def gone(pid):
            self.events.append(('identity', pid))
            raise ProcessLookupError(3, 'private')
        self.os.getpgid = self.os.getsid = gone
        self.events.clear()
        if snapshot: self.note(state)
        return state

    def note(self, state, **changes):
        values = dict(go_sent=True, result_seen=False, ack_started=False,
                      stdout_eof=True, stderr_eof=True, error_code='PR_IPC_TRUNCATED')
        values.update(changes)
        state.note_unsealed_protocol(self.p, self.budget, **values)

    def unknown(self, state):
        self.assertEqual(state.unsealed_direct_child_exit_observation, 'UNKNOWN')
        self.assertFalse(state.cleaned)

    def test_initial_esrch_owned_zero(self):
        state=self.state(); abort=self.finish(state)
        self.assertEqual(state.unsealed_direct_child_exit_observation, 'UNSEALED_DIRECT_CHILD_EXIT_OBSERVED')
        self.assertEqual((state.record.stage,state.record.errno,state.record.group),('IDENTITY',None,'UNKNOWN'))
        self.assertEqual(abort.outcome,'TERM_UNCONFIRMED')
        self.assertEqual(abort.error_errno,3)
        self.assertEqual(state.direct_child_abort_completion,'UNKNOWN')
        self.assertEqual(self.events,[('identity',self.p.pid),('wait',10),('close','stdin'),('close','stdout'),('close','stderr')])

    def test_protocol_partition(self):
        for changes in (None, {'go_sent':False},{'stdout_eof':False},{'stderr_eof':False},
                        {'result_seen':True},{'ack_started':True},{'error_code':'OTHER'}):
            state=self.state(snapshot=False)
            if changes is not None: self.note(state,**changes)
            self.finish(state); self.unknown(state)

    def test_cached_zero_without_wait(self):
        state=self.state(); self.p.returncode=0; self.finish(state); self.unknown(state)
        self.assertFalse(any(e[0] in ('identity','wait') for e in self.events))

    def test_identity_partition(self):
        for mode in ('EPERM','MISMATCH','MISSING','INVALID'):
            state=self.state()
            if mode=='EPERM':
                def denied(pid): raise PermissionError(1,'private')
                self.os.getpgid=denied
            elif mode=='MISMATCH':
                self.os.getpgid=lambda pid:pid+1
                self.os.getsid=lambda pid:pid
            elif mode=='MISSING': state.identity=None
            else: self.p.pid=True
            self.finish(state); self.unknown(state)
            self.p.pid=900000001

    def test_signal_separation(self):
        state=DirectAbortFakeTests.state(self); self.note(state)
        self.finish(state); self.unknown(state)
        self.assertEqual(state.direct_child_abort_completion,'DIRECT_CHILD_ABORT_COMPLETION')

    def test_exit_partition(self):
        for value in (1,-15,-9,True,None):
            state=self.state(code=value,wait_return=value); self.finish(state); self.unknown(state)
        state=self.state(wait_return=1); self.finish(state); self.unknown(state)

    def test_wait_errors(self):
        for error in (subprocess.TimeoutExpired('fake',1),OSError(5,'private'),RuntimeError('private')):
            state=self.state(wait_error=error); self.finish(state); self.unknown(state)
            self.assertEqual(sum(e[0]=='wait' for e in self.events),1)

    def test_pipe_errors(self):
        for name in ('stdin','stdout','stderr'):
            state=self.state(close_error=name); self.finish(state); self.unknown(state)
            self.assertEqual(sum(e[0]=='close' for e in self.events),3)

    def test_budget_partition(self):
        for options in ({'wait_delay':10.},{'close_delay':4.},{'policy_delay':11.}):
            state=self.state(**options); self.finish(state); self.unknown(state)
        for deadline in (11,9,True,float('nan'),float('inf')):
            state=self.state(); self.finish(state,deadline); self.unknown(state)
        state=self.state(); self.clock=10.; self.finish(state); self.unknown(state)
        self.assertFalse(any(e[0]=='wait' for e in self.events))

    def test_current_policy_no_operations(self):
        for change in ('DENY',ValueError('private'),'SLOW','EXPIRED'):
            state=self.state(); self.finish(state); before=list(self.events)
            if change=='SLOW': self.policy_delay=11.
            elif change=='EXPIRED': self.clock=10.
            else: self.policy=change
            self.unknown(state); self.assertEqual(before,self.events)

    def test_reference_binding(self):
        for field in ('_unsealed_exit','_request_budget','_original_request_budget',
                      '_unsealed_protocol','record','_direct_abort','process','claimant'):
            state=self.state(); self.finish(state)
            value=getattr(state,field)
            clone=(tuple(list(value)) if type(value) is tuple else
                   SimpleNamespace(**vars(value)) if field=='process' else
                   object() if field=='claimant' else replace(value))
            setattr(state,field,clone); self.unknown(state)

    def test_atomicity_and_republication(self):
        state=self.state()
        def pending():
            self.unknown(state); self.assertFalse(state.cleanup_done.is_set())
            self.assertIsNone(state.begin_cleanup('parent'))
            self.assertIsNone(state.begin_cleanup('launcher'))
        self.wait_hook=pending; self.finish(state)
        before=list(self.events); self.m._pr_cleanup(state,'parent',10)
        self.assertEqual(before,self.events)
        with self.assertRaises(ValueError):
            state.finish_direct_abort(state.claimant,state.record,state._direct_abort,
                                      unsealed_record=state._unsealed_exit)

    def test_events_and_forged_publication(self):
        for name in ('launcher_done','cleanup_done'):
            state=self.state(); self.finish(state); getattr(state,name).clear(); self.unknown(state)
        first=self.state(); self.finish(first)
        state=self.state(); token,_,_=state.begin_cleanup('parent')
        with self.assertRaises(ValueError):
            state.finish_direct_abort(object(),first.record,first._direct_abort,unsealed_record=first._unsealed_exit)
        state.finish_direct_abort(token,first.record,first._direct_abort,unsealed_record=first._unsealed_exit)
        self.unknown(state)

    def test_sealed_separation(self):
        state=self.state(snapshot=False); state.note_protocol_complete(self.budget)
        self.m._pr_cleanup(state,'parent',10)
        self.assertIsNone(state._unsealed_exit)
        self.unknown(state)
        self.assertEqual(state.direct_worker_completion,'DIRECT_WORKER_COMPLETION')

    def test_strict_record(self):
        state=self.state(); self.finish(state); record=state._unsealed_exit
        for changes in ({'version':True},{'identity':[1,1,1]},{'term_attempts':True},
                        {'wait_returncode':True},{'wait_calls':0},{'result_seen':True},
                        {'first_identity_errno':1},{'first_identity_kind':'MATCH'},
                        {'failures':('PIPE_ERROR',)},{'error_errno':0},{'owner_quiescent':False},
                        {'identity_observations':0},{'outcome':'COMPLETE'}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError): replace(record,**changes)
        with self.assertRaises(TypeError): self.m._PRUnsealedExitRecord(extra=True)

    def test_transport_not_authority(self):
        state=self.state(); self.finish(state)
        transport=self.m.PRCreateBoundedHTTPS(); transport._unresolved=state
        self.assertEqual(transport.unsealed_direct_child_exit_observation,'UNSEALED_DIRECT_CHILD_EXIT_OBSERVED')
        self.assertIs(transport._unresolved,state); self.assertFalse(state.cleaned)
        self.assertEqual(state.record.group,'UNKNOWN')


class PartialIdentityFakeTests(unittest.TestCase):
    """Reject partial inconsistent identity without changing legacy queries."""
    setUp = UnsealedExitFakeTests.setUp
    state = UnsealedExitFakeTests.state
    note = UnsealedExitFakeTests.note
    finish = UnsealedExitFakeTests.finish
    unknown = UnsealedExitFakeTests.unknown

    def mocks(self, pgid, sid, group=900000000):
        self.trace=[]
        def query(name, value, *args):
            self.trace.append((name, 'error' if isinstance(value,Exception) else 'return',
                               getattr(value,'errno',None) if isinstance(value,Exception) else value))
            if isinstance(value,Exception): raise value
            return value
        self.os.getpgid=lambda pid:query('getpgid',pgid,pid)
        self.os.getsid=lambda pid:query('getsid',sid,pid)
        self.os.getpgrp=lambda:query('getpgrp',group)

    def finish_trace(self, state, expected):
        self.finish(state)
        print('IDENTITY_TRACE',self.id(),repr(self.trace))
        self.assertEqual(self.trace,expected)
        self.assertFalse(any(e[0]=='signal' for e in self.events))
        self.assertEqual((state.record.stage,state.record.group),('IDENTITY','UNKNOWN'))

    def test_mixed_mismatch_then_esrch_is_unknown(self):
        state=self.state(); self.mocks(900000002,ProcessLookupError(3,'private'))
        self.finish_trace(state,[('getpgid','return',900000002),('getsid','error',3)])
        self.unknown(state)  # Deliberately before new schema assertions: real RED.

    def test_invalid_prefix_then_esrch_is_unknown(self):
        for value in (True,900000001.0,None,0,-1,2147483648,'900000001'):
            with self.subTest(prefix=repr(value)):
                state=self.state(); self.mocks(value,ProcessLookupError(3,'private'))
                self.finish_trace(state,[('getpgid','return',value),('getsid','error',3)])
                self.unknown(state)

    def test_getpgrp_esrch_is_not_child_absence(self):
        state=self.state(); self.mocks(900000001,900000001,ProcessLookupError(3,'private'))
        self.finish_trace(state,[('getpgid','return',900000001),('getsid','return',900000001),('getpgrp','error',3)])
        self.unknown(state)

    def test_pure_pgid_mismatch(self):
        state=self.state(); self.mocks(900000002,900000001)
        self.finish_trace(state,[('getpgid','return',900000002),('getsid','return',900000001)])
        self.unknown(state)

    def test_pure_sid_mismatch(self):
        state=self.state(); self.mocks(900000001,900000002)
        self.finish_trace(state,[('getpgid','return',900000001),('getsid','return',900000002)])
        self.unknown(state)

    def test_first_eperm(self):
        state=self.state(); self.mocks(PermissionError(1,'private'),900000001)
        self.finish_trace(state,[('getpgid','error',1)]); self.unknown(state)

    def test_second_eperm(self):
        state=self.state(); self.mocks(900000001,PermissionError(1,'private'))
        self.finish_trace(state,[('getpgid','return',900000001),('getsid','error',1)]); self.unknown(state)

    def test_first_esrch_still_eligible(self):
        state=self.state(); self.mocks(ProcessLookupError(3,'private'),900000001)
        self.finish_trace(state,[('getpgid','error',3)])
        self.assertEqual(state.unsealed_direct_child_exit_observation,'UNSEALED_DIRECT_CHILD_EXIT_OBSERVED')

    def test_matching_prefix_second_esrch_still_eligible(self):
        state=self.state(); self.mocks(900000001,ProcessLookupError(3,'private'))
        self.finish_trace(state,[('getpgid','return',900000001),('getsid','error',3)])
        self.assertEqual(state.unsealed_direct_child_exit_observation,'UNSEALED_DIRECT_CHILD_EXIT_OBSERVED')

    def test_legacy_triple_and_unexpected_exception(self):
        self.state()
        for pgid,sid,group,expected,names in (
            (900000002,ProcessLookupError(3,'private'),900000000,(None,'LOOKUP_ERROR',3),['getpgid','getsid']),
            (900000002,900000001,900000000,(None,'MISMATCH',None),['getpgid','getsid']),
            (900000001,900000001,900000000,((900000001,)*3,'MATCH',None),['getpgid','getsid','getpgrp'])):
            self.mocks(pgid,sid,group)
            self.assertEqual(self.m._pr_identity_observation(self.p),expected)
            self.assertEqual([e[0] for e in self.trace],names)
        self.mocks(900000002,RuntimeError('private'))
        with self.assertRaises(RuntimeError): self.m._pr_identity_observation(self.p)
        self.assertEqual([e[0] for e in self.trace],['getpgid','getsid'])

    def test_facts_strictness_and_clone_binding(self):
        self.assertTrue(hasattr(self.m,'_PRIdentityQueryFacts'),'partial facts contract missing')
        state=self.state(); self.finish(state); record=state._unsealed_exit
        self.assertEqual(record.version,2)
        facts=record.identity_query_facts
        for changes in ({'version':True},{'pgid_state':'MAYBE'},{'sid_state':'MATCH'},
                        {'error_source':None},{'error_errno':True}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError): replace(facts,**changes)
        with self.assertRaises(ValueError): replace(record,version=1)
        with self.assertRaises(ValueError): replace(record,identity_query_facts=None)
        state._unsealed_exit=replace(record,identity_query_facts=replace(facts))
        self.unknown(state)


class DirectWorkerFakeTests(unittest.TestCase):
    """Catch promotion of incomplete lifecycle facts or diagnostic to authority."""
    setUp = StageAFakeOwnershipTests.setUp
    require_contract = StageAFakeOwnershipTests.require_contract
    parent_state = StageAFakeOwnershipTests.parent_state
    cleanup = StageAFakeOwnershipTests.cleanup

    def direct_contract(self):
        self.assertTrue(hasattr(self.m._PRLaunch, 'note_protocol_complete'),
                        'direct worker diagnostic missing')
        self.assertTrue(hasattr(self.m._PRLaunch, 'direct_worker_completion'))
        self.assertTrue(hasattr(self.m.PRCreateBoundedHTTPS, 'direct_worker_completion'))
        item = patch.object(self.m.rse, 'evaluate_policy',
                            return_value=SimpleNamespace(disposition='ALLOW'))
        item.start(); self.addCleanup(item.stop)
        self.budget = self.m._PRBudget(0, 10, 8, 1, None, (), None)

    def completed(self):
        self.p.returncode = None
        state = self.parent_state()
        state.note_protocol_complete(self.budget)
        self.cleanup(state)
        return state

    def test_complete_direct_worker_does_not_confirm_group_or_clear_quarantine(self):
        self.direct_contract(); state = self.completed()
        self.assertEqual(state.direct_worker_completion, 'DIRECT_WORKER_COMPLETION')
        self.assertEqual((state.record.status, state.record.group), ('UNKNOWN', 'UNKNOWN'))
        self.assertFalse(state.cleaned)
        transport = self.m.PRCreateBoundedHTTPS(); transport._unresolved = state
        self.assertEqual(transport.direct_worker_completion, 'DIRECT_WORKER_COMPLETION')
        with self.assertRaisesRegex(ValueError, 'PR_BINDING_BUDGET_REQUIRED'):
            transport.request('POST')
        self.assertIs(transport._unresolved, state)

    def test_each_missing_fact_stays_unknown(self):
        self.direct_contract()
        for field, value in (('stage','WAIT'), ('errno',1), ('identity',None),
                ('identity',(1,2,3)), ('reaped',False), ('pipes_closed',False), ('quiescent',False)):
            with self.subTest(field=field, value=value):
                state = self.completed()
                state.record = replace(state.record, **{field:value})
                self.assertEqual(state.direct_worker_completion, 'UNKNOWN')
        for event in ('launcher_done','cleanup_done'):
            state = self.completed(); getattr(state,event).clear()
            self.assertEqual(state.direct_worker_completion, 'UNKNOWN')
        for value in (None, -15, 1, False):
            state = self.completed(); self.p.returncode = value
            self.assertEqual(state.direct_worker_completion, 'UNKNOWN')
        state = self.completed(); state.claimant = None
        self.assertEqual(state.direct_worker_completion, 'UNKNOWN')

    def test_protocol_and_parent_claim_required_no_late_or_duplicate_note(self):
        self.direct_contract(); state = self.parent_state()
        self.cleanup(state)
        self.assertEqual(state.direct_worker_completion, 'UNKNOWN')
        with self.assertRaises(ValueError): state.note_protocol_complete(self.budget)
        self.p.returncode = None
        state = self.m._PRLaunch(); state.claim_parent(); state.publish(self.p)
        with self.assertRaises(ValueError): state.note_protocol_complete(self.budget)
        state = self.parent_state(); state.note_protocol_complete(self.budget)
        with self.assertRaises(ValueError): state.note_protocol_complete(self.budget)

    def test_pending_timeout_and_eperm_never_complete(self):
        self.direct_contract(); state = self.parent_state()
        state.note_protocol_complete(self.budget); state.begin_cleanup('parent')
        self.assertEqual(state.direct_worker_completion, 'UNKNOWN')
        self.wait_error = subprocess.TimeoutExpired('synthetic',1)
        state = self.completed()
        self.assertEqual(state.direct_worker_completion, 'UNKNOWN')
        self.assertFalse(state.cleaned)
        self.wait_error = None; self.events.clear(); self.p.returncode = None
        self.signal_error = PermissionError(1,'synthetic')
        state = self.parent_state()  # No protocol seal: exercise legacy signals.
        self.assertIsNone(state._protocol_budget)
        self.cleanup(state)
        self.assertEqual(state.direct_worker_completion, 'UNKNOWN')
        self.assertFalse(state.cleaned)
        self.assertEqual((state.record.status,state.record.stage,state.record.errno),
                         ('UNKNOWN','TERM',1))
        self.assertEqual(state.record.group,'UNKNOWN')
        self.assertEqual([e for e in self.events if e[0]=='signal'],[('signal',15)])

    def test_expiry_and_authority_denial_do_not_become_completion(self):
        self.direct_contract(); state = self.completed()
        self.clock = 10
        self.assertEqual(state.direct_worker_completion, 'UNKNOWN')
        self.clock = 0
        with patch.object(self.m.rse, 'evaluate_policy', return_value=SimpleNamespace(disposition='DENY')):
            self.assertEqual(state.direct_worker_completion, 'UNKNOWN')
            fresh = self.parent_state()
            with self.assertRaises(ValueError): fresh.note_protocol_complete(self.budget)
        self.clock = 8
        with self.assertRaises(ValueError): self.parent_state().note_protocol_complete(self.budget)

    def test_actual_fake_ipc_records_diagnostic_but_rejects_result(self):
        self.direct_contract(); states = []; original = self.m._pr_cleanup
        def cleanup(state, *args):
            states.append(state)
            return original(state, *args)
        with patch.object(self.m, '_pr_cleanup', side_effect=cleanup):
            StageAFakeOwnershipTests.test_complete_fake_ipc_response_stays_unknown_and_quarantined(self)
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0].direct_worker_completion, 'DIRECT_WORKER_COMPLETION')
        self.assertEqual(states[0].record.group, 'UNKNOWN')
        self.assertFalse(states[0].cleaned)


class UnresolvedPreservationFakeTests(unittest.TestCase):
    """U1-U14: real selection/lifecycle, deterministic fake external boundaries.

    Mutations caught: placeholder replacement, clearing before construction,
    late registration, skipped/duplicate cleanup, leaked or stolen lock, and
    masking an interrupt with a secondary ordinary finalization failure.
    """
    setUp = StageAFakeOwnershipTests.setUp

    def inputs(self):
        self.m.os.name='posix'
        p=SimpleNamespace(repository='team/repo',head='feature',base='main',
            target='https://api.example.invalid/repos/team/repo/pulls',timeout=10,response_limit=65536)
        return self.m._PRBudget(0,10,8,1,None,(),None),p

    def invoke(self, transport, budget, p):
        try:
            transport._request(budget,p,'POST',p.target,(),b'{}',timeout=10,response_limit=65536)
        except BaseException as error:
            return error
        return None

    def uncertain(self, error):
        self.assertIs(type(error),ValueError,'EXCEPTION_SAFETY')
        self.assertEqual(error.args,('PR_TRANSPORT_UNCERTAIN',),'EXCEPTION_SAFETY')

    def retained(self, transport, state, before):
        self.assertIs(transport._unresolved,state,'UNRESOLVED_IDENTITY_LOST')
        self.assertEqual(set(vars(state)),set(before))
        for key,value in before.items():
            self.assertIs(vars(state)[key],value,'REFERENCE_CHANGED:'+key)

    def denied(self, state, transport=None, budget=None):
        budget0,p=self.inputs(); budget=budget or budget0
        transport=transport or self.m.PRCreateBoundedHTTPS()
        transport._unresolved=state
        before=vars(state).copy()
        with patch.object(self.m.rse,'evaluate_policy',return_value=SimpleNamespace(disposition='ALLOW')), \
             patch.object(self.m,'_pr_spawn_worker',side_effect=AssertionError('UNEXPECTED_SPAWN')), \
             patch.object(self.m,'_pr_cleanup',side_effect=AssertionError('PRIOR_CLEANUP')):
            error=self.invoke(transport,budget,p)
        self.uncertain(error)
        self.retained(transport,state,before)
        self.assertFalse(transport._lock.locked(),'LOCK_LEAK')
        return transport

    def flow(self, fault=None, *, close_error=None, cleanup_error=None,
             interrupt=None, prior=None, reentrant=False):
        from contextlib import ExitStack
        self.clock=0.;self.p.returncode=None;self.events.clear()
        budget,p=self.inputs(); transport=self.m.PRCreateBoundedHTTPS();transport._unresolved=prior
        calls=[]; states=[]; registered=[]; cleanup_calls=[]; retained_at=[]
        def hit(where):
            calls.append(where)
            if fault==where: raise interrupt if interrupt is not None else RuntimeError('injected')
        for fd,name in ((10,'stdin'),(11,'stdout'),(12,'stderr')):
            getattr(self.p,name).fileno=lambda fd=fd:fd
        frames=[self.m._pr_frame(dict(version=1,kind='ready'),65536),
                self.m._pr_frame(dict(version=1,kind='armed'),65536)]
        sequence=iter(('out','in','out','in'))
        ports={'in':self.p.stdin,'out':self.p.stdout,'err':self.p.stderr}
        self.os.set_blocking=lambda *args:None
        def read(fd,n): hit('read');return frames.pop(0)
        def write(fd,data): hit('write');return len(data)
        self.os.read=read;self.os.write=write
        class Selector:
            def __init__(self): hit('selector')
            def register(self,*args): hit('register')
            def unregister(self,*args): pass
            def select(self,timeout):
                hit('select')
                kind=next(sequence);port=ports[kind]
                return [(SimpleNamespace(data=kind,fd=port.fileno(),fileobj=port),1)]
            def close(self):
                calls.append('close')
                if close_error is not None: raise close_error
        real_init=self.m._PRLaunch.__init__; real_claim=self.m._PRLaunch.claim_parent
        real_cleanup=self.m._pr_cleanup; real_decode=self.m._pr_decode
        def init(state,**kw):
            retained_at.append(transport._unresolved)
            hit('constructor');real_init(state,**kw);states.append(state)
            state.ready.wait=lambda timeout:(hit('wait') or True)
        def claim(state): hit('claim');return real_claim(state)
        def decode(data): hit('decode');return real_decode(data)
        def cleanup(state,owner,end):
            cleanup_calls.append((state,owner,end))
            if cleanup_error is not None: raise cleanup_error
            return real_cleanup(state,owner,end)
        outer=self
        class InlineThread:
            def __init__(self,target,args,**kw):
                registered.append(transport._unresolved is args[0]);hit('thread')
                self.target,self.args=target,args
            def start(self):
                registered.append(transport._unresolved is self.args[0]);hit('start')
                if reentrant:
                    before=vars(self.args[0]).copy()
                    error=outer.invoke(transport,budget,p)
                    outer.assertIs(type(error),ValueError)
                    outer.assertEqual(error.args,('PR_TRANSPORT_BUSY',))
                    outer.assertTrue(transport._lock.locked(),'LOSER_RELEASED_LOCK')
                    # Selection is checked after the outer call too, so old RED
                    # can exercise the complete deterministic schedule.
                    outer.assertEqual(vars(self.args[0]),before)
                self.target(*self.args)
        with ExitStack() as stack:
            for obj,key,value in (
                (self.m._PRLaunch,'__init__',init),(self.m._PRLaunch,'claim_parent',claim),
                (self.m,'_pr_spawn_worker',lambda:(calls.append('spawn') or self.p)),
                (self.m,'threading',SimpleNamespace(Thread=InlineThread,Lock=threading.Lock,Event=threading.Event)),
                (self.m,'selectors',SimpleNamespace(DefaultSelector=Selector,EVENT_READ=1,EVENT_WRITE=2)),
                (self.m,'_pr_cleanup',cleanup),(self.m,'_pr_decode',decode),
                (self.m.rse,'evaluate_policy',lambda *args:SimpleNamespace(disposition='ALLOW'))):
                stack.enter_context(patch.object(obj,key,value))
            error=self.invoke(transport,budget,p)
        print('U_FLOW',json.dumps(dict(test=self.id(),fault=fault,calls=calls,
            registered=registered,cleanup_count=len(cleanup_calls),
            error=type(error).__name__,lock_locked=transport._lock.locked()),sort_keys=True))
        return SimpleNamespace(transport=transport,budget=budget,payload=p,error=error,
            states=states,registered=registered,cleanup=cleanup_calls,calls=calls,retained_at=retained_at)

    def test_u01_settled_unknown_preserves_every_reference(self):
        budget,_=self.inputs();s=self.m._PRLaunch(request_budget=budget)
        s.publish(self.p);s.claim_parent();s.launcher_done.set()
        self.m._pr_cleanup(s,'parent',10)
        events=list(self.events);self.denied(s);self.denied(s)
        self.assertEqual(self.events,events)

    def test_u02_changed_budget_does_not_rejuvenate_original(self):
        f=GracefulFinalizationFakeTests('runTest');f.setUp()
        try:
            s=f.prepared();f.finish(s);f.clock=11
            # A fresh request clock/budget must not replace the diagnostic's
            # original budget, whose deadline has passed.
            budget=self.m._PRBudget(11,21,19,1,object(),(),object())
            t=self.denied(s,budget=budget)
            self.assertEqual(t.direct_worker_completion,'UNKNOWN')
            self.assertIs(s._protocol_budget,f.budget)
        finally: f.doCleanups()

    def test_u03_pending_launcher_delayed_publish_same_handle(self):
        s=self.m._PRLaunch();t=self.denied(s)
        s.publish(self.p);s.ready.set()
        self.assertIs(t._unresolved,s);self.assertIs(s.process,self.p)
        self.assertEqual(s.owner,'parent');self.assertEqual(self.events,[])

    def test_u04_cancelled_handoff_keeps_launcher_cleanup(self):
        s=self.m._PRLaunch();s.claim_parent();t=self.denied(s)
        with patch.object(self.m,'_pr_spawn_worker',return_value=self.p):self.m._pr_launch(s)
        self.assertIs(t._unresolved,s);self.assertEqual(s.owner,'launcher')
        events=list(self.events);self.denied(s,t)
        self.assertEqual(self.events,events);self.assertTrue(s.launcher_done.is_set())

    def test_u05_pending_parent_claimant_no_takeover(self):
        s=self.m._PRLaunch();s.publish(self.p);s.claim_parent()
        token,_,_=s.begin_cleanup('parent');t=self.denied(s)
        s.finish_cleanup(token,self.m._PRCleanupRecord('UNKNOWN','INVALID'))
        self.assertIs(t._unresolved,s);self.assertIs(s.claimant,token)
        self.assertTrue(s.cleanup_done.is_set());self.assertEqual(self.events,[])

    def test_u06_four_settled_diagnostics_keep_original_records(self):
        for cls in (GracefulFinalizationFakeTests,DirectAbortFakeTests,UnsealedExitFakeTests,RejectedResponseFakeTests):
            with self.subTest(kind=cls.__name__):
                f=cls('runTest');f.setUp()
                try:
                    if cls is RejectedResponseFakeTests:s,_,_=f.parent()
                    else:
                        s=f.prepared() if cls is GracefulFinalizationFakeTests else f.state()
                        f.finish(s)
                    before=list(f.events);t=self.denied(s)
                    self.assertEqual(f.events,before)
                    f.clock=11
                    for getter in ('direct_worker_completion','direct_child_abort_completion',
                                   'unsealed_direct_child_exit_observation','rejected_response_direct_child_exit_observation'):
                        self.assertEqual(getattr(t,getter),'UNKNOWN')
                finally:f.doCleanups()

    def clean_prior(self):
        s=self.m._PRLaunch();s.phase='CLEANUP_CONFIRMED'
        s.record=self.m._PRCleanupRecord('CONFIRMED','COMPLETE',None,(900000001,)*3,True,'CONFIRMED',True,True)
        self.assertTrue(s.cleaned);return s

    def test_u07_preconstruction_budget_failure_preserves_prior(self):
        for prior in (None,self.clean_prior()):
            with self.subTest(prior=prior is not None):
                self.clock=0;budget,p=self.inputs();t=self.m.PRCreateBoundedHTTPS();t._unresolved=prior
                n=[0]
                def policy(*args):
                    n[0]+=1
                    return SimpleNamespace(disposition='ALLOW' if n[0]==1 else 'DENY')
                with patch.object(self.m.rse,'evaluate_policy',policy), \
                     patch.object(self.m._PRLaunch,'__init__',side_effect=RuntimeError('constructor forbidden')) as constructor:
                    error=self.invoke(t,budget,p)
                self.assertEqual(constructor.call_count,0,'PLACEHOLDER_CONSTRUCTED')
                self.uncertain(error);self.assertIs(t._unresolved,prior)
                self.assertFalse(t._lock.locked(),'LOCK_LEAK')

    def test_u08_registration_and_construction_failure_partition(self):
        for fault in ('constructor','thread','start','wait','claim'):
            with self.subTest(fault=fault):
                prior=self.clean_prior();r=self.flow(fault,prior=prior)
                self.uncertain(r.error);self.assertFalse(r.transport._lock.locked(),'LOCK_LEAK')
                self.assertIs(r.retained_at[0],prior,'PRIOR_CLEARED_EARLY')
                self.assertEqual(len(r.retained_at),1,'PLACEHOLDER_CONSTRUCTED')
                if fault=='constructor':self.assertIs(r.transport._unresolved,prior)
                else:
                    self.assertIs(r.transport._unresolved,r.states[0]);self.assertTrue(all(r.registered),'LATE_REGISTRATION')
                self.assertEqual(r.cleanup,[])

    def test_u09_protocol_faults_keep_registered_launch_and_cleanup(self):
        for fault in ('selector','register','read','write','decode'):
            with self.subTest(fault=fault):
                r=self.flow(fault);self.uncertain(r.error)
                self.assertIs(r.transport._unresolved,r.states[0]);self.assertFalse(r.transport._lock.locked())
                self.assertEqual(len(r.cleanup),1);self.assertIs(r.cleanup[0][0],r.states[0])
                self.assertTrue(all(r.registered),'LATE_REGISTRATION')

    def test_u10_finalization_errors_never_skip_cleanup_or_release(self):
        for close,cleanup in ((True,False),(False,True),(True,True)):
            with self.subTest(close=close,cleanup=cleanup):
                r=self.flow('select',close_error=RuntimeError('close') if close else None,
                    cleanup_error=RuntimeError('cleanup') if cleanup else None)
                self.uncertain(r.error)
                self.assertEqual(len(r.cleanup),1,'CLEANUP_SKIPPED_OR_RETRIED')
                self.assertFalse(r.transport._lock.locked(),'LOCK_LEAK')
                self.assertIs(r.transport._unresolved,r.states[0]);self.assertFalse(r.states[0].cleaned)

    def test_u11_reentrant_loser_never_releases_winner_lock(self):
        r=self.flow('select',reentrant=True);self.uncertain(r.error)
        self.assertEqual(r.calls.count('spawn'),1);self.assertEqual(len(r.cleanup),1)
        self.assertTrue(all(r.registered),'LATE_REGISTRATION')
        self.assertIs(r.transport._unresolved,r.states[0]);self.assertFalse(r.transport._lock.locked())

    def test_u12_original_interrupt_wins_over_ordinary_finalizers(self):
        for fault in ('start','select'):
            with self.subTest(fault=fault):
                interrupt=KeyboardInterrupt('synthetic')
                r=self.flow(fault,interrupt=interrupt,close_error=RuntimeError('close'),cleanup_error=RuntimeError('cleanup'))
                self.assertIs(r.error,interrupt,'INTERRUPT_MASKED')
                self.assertFalse(r.transport._lock.locked(),'LOCK_LEAK')
                self.assertIs(r.transport._unresolved,r.states[0])
                self.assertEqual(len(r.cleanup),int(fault=='select'))

    def test_u13_clean_admission_replaces_only_after_construction(self):
        prior=self.clean_prior();r=self.flow('select',prior=prior)
        self.uncertain(r.error);self.assertIs(r.retained_at[0],prior,'PRIOR_CLEARED_EARLY')
        self.assertIs(r.transport._unresolved,r.states[0]);self.assertIsNot(r.states[0],prior)
        self.assertTrue(all(r.registered),'LATE_REGISTRATION');self.assertTrue(prior.cleaned)

    def test_u14_mutated_context_and_expired_authority_remain_unknown(self):
        f=RejectedResponseFakeTests('runTest');f.setUp()
        try:
            s,t,_=f.parent();s._rejected_context=None
            self.denied(s,t)
            self.assertEqual(t.rejected_response_direct_child_exit_observation,'UNKNOWN')
            f.policy='DENY';budget,p=self.inputs()
            before=vars(s).copy();error=self.invoke(t,budget,p)
            self.assertIs(type(error),ValueError);self.assertEqual(error.args,('PR_AUTHORITY_EXPIRED',))
            self.retained(t,s,before);self.assertFalse(t._lock.locked())
        finally:f.doCleanups()


class ProvenanceInterruptionFakeTests(unittest.TestCase):
    """R3 P2: provenance failure cannot skip the sole eligible cleanup.

    Real wrapper/ownership and fake I/O use the existing deterministic seam.
    The mutation caught is leaving note_unsealed_protocol in the same unguarded
    section as cleanup, which loses the one cleanup attempt on BaseException.
    """
    setUp = StageAFakeOwnershipTests.setUp
    inputs = UnresolvedPreservationFakeTests.inputs
    invoke = UnresolvedPreservationFakeTests.invoke
    uncertain = UnresolvedPreservationFakeTests.uncertain
    retained = UnresolvedPreservationFakeTests.retained
    denied = UnresolvedPreservationFakeTests.denied

    def check_note_failure(self, note_error, *, earlier=None, close_error=None,
                           cleanup_error=None, expected=None):
        entries=[]
        def note(state,*args,**kwargs):
            entries.append((state,vars(state).copy(),args,kwargs))
            self.events.append(('provenance_note',))
            raise note_error
        with patch.object(self.m._PRLaunch,'note_unsealed_protocol',note):
            r=UnresolvedPreservationFakeTests.flow(self,'select',interrupt=earlier,
                close_error=close_error,cleanup_error=cleanup_error)
        self.assertEqual(len(entries),1)
        state,before,args,kwargs=entries[0]
        self.assertEqual(before['phase'],'PARENT_CLAIMED')
        self.assertIsNone(before['_protocol_budget'])
        self.assertIs(args[0],self.p);self.assertIs(args[1],r.budget)
        self.assertEqual(kwargs['error_code'],'OTHER')
        self.assertTrue(all(r.registered))
        print('PROVENANCE_CASE',json.dumps(dict(test=self.id(),
            note=type(note_error).__name__,earlier=type(earlier).__name__,
            close=type(close_error).__name__,cleanup=type(cleanup_error).__name__,
            note_calls=len(entries),cleanup_attempts=len(r.cleanup),
            same_state=r.transport._unresolved is state,
            same_exception=r.error is expected if expected is not None else None,
            lock_released=not r.transport._lock.locked()),sort_keys=True))
        self.assertEqual(len(r.cleanup),1,'PROVENANCE_CLEANUP_SKIPPED')
        self.assertIs(r.cleanup[0][0],state)
        self.assertEqual(r.cleanup[0][1: ],('parent',r.budget.end))
        self.assertIs(r.transport._unresolved,state)
        self.assertFalse(r.transport._lock.locked())
        for field in ('process','identity','lock','ready','launcher_done','cleanup_done',
                      '_request_budget','_original_request_budget','_protocol_budget',
                      '_rejection_binding','_unsealed_protocol'):
            self.assertIs(vars(state)[field],before[field],field)
        if expected is None:self.uncertain(r.error)
        else:self.assertIs(r.error,expected,'PROVENANCE_INTERRUPT_PRIORITY')
        self.assertFalse(state.cleaned)
        events=list(self.events)
        self.denied(state,r.transport)
        self.assertEqual(self.events,events)

    def test_note_interrupt_attempts_cleanup_once(self):
        class ProvenanceStop(BaseException):pass
        for error in (KeyboardInterrupt('synthetic'),SystemExit(71),ProvenanceStop()):
            with self.subTest(kind=type(error).__name__):
                self.check_note_failure(error,expected=error)

    def test_note_interrupt_survives_secondary_ordinary_cleanup_error(self):
        for cleanup in (RuntimeError('synthetic'),OSError(5,'synthetic')):
            with self.subTest(cleanup=type(cleanup).__name__):
                error=KeyboardInterrupt('synthetic')
                self.check_note_failure(error,cleanup_error=cleanup,expected=error)

    def test_earlier_body_interrupt_wins_over_note_and_cleanup(self):
        for earlier in (KeyboardInterrupt('earlier'),SystemExit(72)):
            for cleanup in (None,RuntimeError('secondary')):
                with self.subTest(earlier=type(earlier).__name__,cleanup=type(cleanup).__name__):
                    self.check_note_failure(SystemExit(73),earlier=earlier,
                        cleanup_error=cleanup,expected=earlier)

    def test_earlier_selector_interrupt_wins_over_note(self):
        for earlier in (KeyboardInterrupt('selector'),SystemExit(74)):
            with self.subTest(earlier=type(earlier).__name__):
                self.check_note_failure(SystemExit(75),close_error=earlier,expected=earlier)

    def test_ordinary_note_error_still_attempts_cleanup_once(self):
        for cleanup in (None,RuntimeError('secondary')):
            with self.subTest(cleanup=type(cleanup).__name__):
                self.check_note_failure(RuntimeError('note'),cleanup_error=cleanup)

    def test_note_interrupt_wins_over_cleanup_interrupt(self):
        for error in (KeyboardInterrupt('note'),SystemExit(76)):
            with self.subTest(note=type(error).__name__):
                self.check_note_failure(error,cleanup_error=SystemExit(77),expected=error)

    def test_no_claimed_process_does_not_gain_cleanup_authority(self):
        for fault in ('start','claim'):
            with self.subTest(fault=fault):
                with patch.object(self.m._PRLaunch,'note_unsealed_protocol',
                                  side_effect=AssertionError('UNEXPECTED_PROVENANCE')) as note:
                    r=UnresolvedPreservationFakeTests.flow(self,fault)
                self.uncertain(r.error);self.assertEqual(note.call_count,0)
                self.assertEqual(r.cleanup,[])
                self.assertIs(r.transport._unresolved,r.states[0])
                self.assertFalse(r.transport._lock.locked())

    def test_cleanup_interrupt_after_ordinary_note_is_propagated(self):
        error=SystemExit(78)
        with self.subTest(cleanup='SystemExit'):
            self.check_note_failure(RuntimeError('note'),cleanup_error=error,expected=error)


class ResponseEnvelopeFakeTests(unittest.TestCase):
    """One-shot selected fake response matrix; no worker or real I/O."""
    setUp = StageAFakeOwnershipTests.setUp

    def frame(self, value, pad=0):
        raw = value if isinstance(value, bytes) else json.dumps(value).encode()
        raw += b' ' * max(0, pad-len(raw))
        return len(raw).to_bytes(4, 'big') + raw

    def value(self, **changes):
        v=dict(version=1,kind='result',status=201,headers=[],body='e30=',complete=True)
        v.update(changes); return v

    def check_flow(self, label, value=None, *, reason=None, notes=0, stage='result',
                   raw=None, extra=b'', stderr=b'', timing=None, padded=False,
                   missing_result=False, pending_eof=False, expected_go=1, selected=False):
        from contextlib import ExitStack
        self.clock=0; self.p.returncode=None; self.events.clear()
        self._capture_case_number=getattr(self,'_capture_case_number',0)+1
        case_id=self.id()+'/'+str(self._capture_case_number).zfill(3)+':'+label
        trace=dict(case_id=case_id,label=label,failures=[],direct_exceptions=[],decode_errors=[],base64_errors=[],notes=0,
                   writes=[],reads=[],selector_calls=0)
        ready=self.frame(dict(version=1,kind='ready'),self.m._PR_METADATA if padded else 0)
        armed=self.frame(dict(version=1,kind='armed'),self.m._PR_METADATA if padded else 0)
        result=raw if raw is not None else self.frame(self.value() if value is None else value,
                                                     self.m._PR_OUTPUT if padded else 0)
        steps=[]
        def out(data):
            for i in range(0,len(data),65536): steps.append(('out',data[i:i+65536]))
        if stage=='ready': out(result)
        else:
            out(ready)
            if stage!='pending': steps.append(('in',b''))
            if stage=='pending': out(result)
            else:
                out(armed); steps.append(('in',b''))
                if not missing_result:
                    out(result)
                    if not pending_eof: steps.append(('in',b''))
                    if extra: out(extra)
        if stderr: steps.append(('err',stderr))
        steps.extend((('out',b''),('err',b'')))
        # All fake reads honor the production read bound.
        self.assertTrue(all(len(v)<=65536 for _,v in steps))
        active=[None]; denied=[False]; registered=set()
        for fd,name in ((10,'stdin'),(11,'stdout'),(12,'stderr')):
            getattr(self.p,name).fileno=lambda fd=fd:fd
        self.os.name='posix'; self.os.set_blocking=lambda *a:None
        def read(fd,n):
            kind,data=active[0]; trace['reads'].append([kind,len(data)])
            if timing in ('before_go','policy') and b'armed' in data:
                if timing=='policy': denied[0]=True
                else: self.clock=8
            if timing=='before_note' and kind=='err' and not data: self.clock=8
            return data
        def write(fd,data):
            trace['writes'].append(json.loads(data[4:])['kind']);return len(data)
        self.os.read=read;self.os.write=write
        ports={'in':self.p.stdin,'out':self.p.stdout,'err':self.p.stderr}
        class Selector:
            def register(self,port,event,kind): registered.add(kind)
            def unregister(self,port):
                registered.discard(next(k for k,v in ports.items() if v is port))
            def close(self): trace['selector_closed']=True
            def select(self,timeout):
                trace['selector_calls']+=1
                while steps and steps[0][0]=='in' and 'in' not in registered: steps.pop(0)
                if not steps: raise AssertionError('FIXTURE_SEQUENCE_EXHAUSTED')
                active[0]=steps.pop(0);kind=active[0][0];port=ports[kind]
                return [(SimpleNamespace(data=kind,fd=port.fileno(),fileobj=port),1)]
        class InlineThread:
            def __init__(self,target,args,**kw): self.target,self.args=target,args
            def start(self): self.target(*self.args)
        req=self.m._require;decode=self.m._pr_decode;b64=self.m.base64.b64decode
        note=self.m._PRLaunch.note_protocol_complete;cleanup=self.m._pr_cleanup
        def require(condition,reason='MALFORMED_REMOTE_PAYLOAD'):
            if not condition: trace['failures'].append([reason,sys._getframe(1).f_lineno])
            return req(condition,reason)
        def decoded(data):
            try: return decode(data)
            except Exception as e: trace['decode_errors'].append(type(e).__name__);raise
        def base64decode(*a,**kw):
            try: return b64(*a,**kw)
            except Exception as e: trace['base64_errors'].append(type(e).__name__);raise
        def noted(state,budget):
            note(state,budget);trace['notes']+=1
        def cleaned(state,*args):
            v=cleanup(state,*args)
            if timing=='after_note': self.clock=10
            return v
        p=SimpleNamespace(repository='team/repo',head='feature',base='main',
            target='https://api.example.invalid/repos/team/repo/pulls',timeout=10,response_limit=65536)
        budget=self.m._PRBudget(0,10,8,1,None,(),None);transport=self.m.PRCreateBoundedHTTPS()
        if selected:
            self.m.time.time=lambda:1
            self.p.terminate=lambda:self.events.append(('terminate',))
            self.p.kill=lambda:self.events.append(('kill',))
            p.repository='Q20396/20396-acceptance-sandbox'
            p.target='https://api.github.com:443/repos/Q20396/20396-acceptance-sandbox/pulls'
            p.digest=lambda:'a'*64
            limits=self.m._PRQualificationLimits(dict(repository=p.repository,head=p.head,base=p.base,
                repository_id=123,head_oid='a'*40,base_oid='b'*40),mode='create',expires_at=100,issued_at=1)
            transport=self.m.PRCreateBoundedHTTPS(qualification_limits=limits,selected_direct=True)
        # Observe exception events in this wrapper only. Preserve the raised
        # object, traceback and control flow; never serialize raw exception data.
        wrapper_code=transport._request.__func__.__code__
        def exception_trace(frame,event,arg):
            if frame.f_code is not wrapper_code: return None
            if event=='exception':
                exc_type,exc_value,_=arg
                if exc_type is ValueError and exc_value.args==('PR_IPC_ORDER',):
                    record=['PR_IPC_ORDER',frame.f_lineno]
                    trace['direct_exceptions'].append(record)
                    if record not in trace['failures']: trace['failures'].append(record)
            return exception_trace
        with ExitStack() as stack:
            previous_trace=sys.gettrace()
            stack.callback(sys.settrace,previous_trace)
            sys.settrace(exception_trace)
            spawn=stack.enter_context(patch.object(self.m,'_pr_spawn_worker',return_value=self.p))
            for obj,key,value_ in ((self.m,'threading',SimpleNamespace(Thread=InlineThread,Lock=threading.Lock,Event=threading.Event)),
                (self.m,'selectors',SimpleNamespace(DefaultSelector=Selector,EVENT_READ=1,EVENT_WRITE=2)),
                (self.m,'rse',SimpleNamespace(evaluate_policy=lambda *a:SimpleNamespace(disposition='DENY' if denied[0] else 'ALLOW'))),
                (self.m,'_require',require),(self.m,'_pr_decode',decoded),(self.m.base64,'b64decode',base64decode),
                (self.m._PRLaunch,'note_protocol_complete',noted),(self.m,'_pr_cleanup',cleaned)):
                stack.enter_context(patch.object(obj,key,value_))
            try:
                if selected:
                    if reason:
                        with self.assertRaisesRegex(ValueError,'PR_TRANSPORT_UNCERTAIN'):
                            transport._request(budget,p,'POST',p.target,(),b'{}',timeout=10,response_limit=65536)
                        self.assertEqual(transport._selected_history,[])
                    else:
                        status,headers,data=transport._request(budget,p,'POST',p.target,(),b'{}',timeout=10,response_limit=65536)
                        self.assertEqual(status,201);self.assertEqual(data,b'{}')
                        self.assertEqual(len(transport._selected_history),1)
                        self.assertTrue(transport._selected_prior(transport._unresolved,p))
                    self.assertEqual(transport._unresolved.record.group,'UNKNOWN')
                    self.assertFalse(transport._unresolved.cleaned)
                    self.assertEqual(spawn.call_count,1)
                    self.assertTrue(transport._unresolved._selected_handle_only)
                    self.assertFalse(any(e[0]=='signal' for e in self.events))
                    if reason:
                        self.assertEqual(sum(e[0]=='terminate' for e in self.events),1)
                        self.assertTrue(transport._unresolved.record.reaped)
                    return
                with self.assertRaisesRegex(ValueError,'PR_TRANSPORT_UNCERTAIN'):
                    transport._request(budget,p,'POST',p.target,(),b'{}',timeout=10,response_limit=65536)
                state=transport._unresolved;self.assertIsNotNone(state)
                trace['diagnostic']=state.direct_worker_completion
                trace['cleanup']=asdict(state.record)
                self.assertEqual(trace['notes'],notes)
                self.assertEqual(trace['diagnostic'],'DIRECT_WORKER_COMPLETION' if notes and timing!='after_note' else 'UNKNOWN')
                self.assertEqual(state.record.group,'UNKNOWN');self.assertFalse(state.cleaned)
                self.assertEqual(trace['writes'].count('go'),expected_go)
                reasons=[v[0] for v in trace['failures'] if v[0]!='PR_TRANSPORT_UNCERTAIN']
                if reason=='BASE64': self.assertTrue(trace['base64_errors'])
                elif reason=='JSON': self.assertTrue(trace['decode_errors'])
                elif reason: self.assertIn(reason,reasons)
                else: self.assertEqual(reasons,[])
                # Restore time/authority inputs only, not quarantine or journal.
                self.clock=0;denied[0]=False
                with self.assertRaisesRegex(ValueError,'PR_TRANSPORT_UNCERTAIN'):
                    transport._request(budget,p,'POST',p.target,(),b'{}',timeout=10,response_limit=65536)
                trace['same_unresolved']=transport._unresolved is state
                trace['spawn_count']=spawn.call_count
                self.assertIs(transport._unresolved,state,'UNRESOLVED_IDENTITY_LOST')
                self.assertIsNotNone(transport._unresolved)
                self.assertFalse(transport._unresolved.cleaned)
                self.assertEqual(spawn.call_count,1)
            finally:
                print('RESPONSE_BRANCH',json.dumps(trace,sort_keys=True))

    def test_response_valid_control(self):
        self.check_flow('valid',notes=1)

    def test_selected_full_fake_protocol_retains_group_unknown(self):
        self.check_flow('selected-valid',notes=1,selected=True)

    def test_selected_bad_version_does_not_accept_result(self):
        self.check_flow('selected-invalid',self.value(version=9),reason='PR_IPC_INVALID',selected=True)

    def test_response_version_exact_int(self):
        for v in (None,2,'1',True):
            with self.subTest(version=v):
                obj=self.value(version=v)
                if v is None: del obj['version']
                self.check_flow('version-'+repr(v),obj,reason='PR_IPC_INVALID')

    def test_response_duplicate_keys(self):
        for raw in (b'{"version":1,"version":1}',b'{"version":1,"status":201,"status":201}',b'{"version":1,"nested":{"a":1,"a":2}}'):
            with self.subTest(raw=raw): self.check_flow('duplicate',raw=self.frame(raw),reason='PR_IPC_INVALID')

    def test_response_json_root_and_constants(self):
        for raw in (b'[]',b'1',b'{',b'{"version":1,"x":NaN}',b'{"version":1,"x":Infinity}'):
            with self.subTest(raw=raw): self.check_flow('json',raw=self.frame(raw),reason='JSON')

    def test_response_fields_and_types(self):
        for k in ('version','kind','status','headers','body','complete'):
            with self.subTest(missing=k):
                v=self.value();del v[k]
                self.check_flow('missing-'+k,v,reason='PR_IPC_ORDER' if k=='kind' else 'PR_IPC_INVALID')
        for k,v in (('extra',1),('complete',1),('body',[])):
            with self.subTest(field=k): self.check_flow('type-'+k,self.value(**{k:v}),reason='PR_IPC_INVALID')

    def test_response_status_exact_int_bounds(self):
        for s in (True,False,'201',99,600,100,599):
            with self.subTest(status=s):
                valid=type(s) is int and 100<=s<=599
                self.check_flow('status-'+repr(s),self.value(status=s),notes=int(valid),reason=None if valid else 'PR_IPC_INVALID')

    def test_response_headers_structure(self):
        for h in ({},[['x']],[['x','v','z']],[[1,'v']],[['x',1]],[['','v']],[['x','\r']],[['x','\n']],[['x','\0']],[['x','v']]*257):
            with self.subTest(headers=h): self.check_flow('headers',self.value(headers=h),reason='PR_IPC_INVALID')

    def test_response_headers_utf8_cap(self):
        for suffix in ('a','aa'):
            h=[['x','é'*32765+suffix]]
            with self.subTest(bytes=65535+len(suffix)):
                valid=suffix=='a';self.check_flow('utf8-'+suffix,self.value(headers=h),notes=int(valid),reason=None if valid else 'PR_IPC_INVALID')

    def test_response_base64_and_decoded_limit(self):
        import base64
        for body in ('!','e30',base64.b64encode(b'x'*65536).decode(),base64.b64encode(b'x'*65537).decode()):
            with self.subTest(encoded_size=len(body)):
                good=body==base64.b64encode(b'x'*65536).decode()
                self.check_flow('base64-'+str(len(body)),self.value(body=body),notes=int(good),reason=None if good else ('BASE64' if len(body)<4 else 'PR_IPC_INVALID'))

    def test_response_incomplete_envelope(self):
        for body,headers,valid in (('',[],True),('e30=',[],False),('',[['x','v']],False)):
            with self.subTest(body=body,headers=headers):
                self.check_flow('incomplete',self.value(complete=False,body=body,headers=headers),notes=int(valid),reason=None if valid else 'PR_IPC_INVALID')

    def test_response_frame_size_and_total(self):
        for size in (0,self.m._PR_OUTPUT+1):
            with self.subTest(size=size): self.check_flow('prefix-'+str(size),raw=size.to_bytes(4,'big'),reason='PR_IPC_OVERFLOW')
        self.check_flow('aggregate',padded=True,extra=b'x',reason='PR_IPC_OVERFLOW')

    def test_response_stderr_rejected(self):
        for size in (1,4097):
            with self.subTest(size=size): self.check_flow('stderr-'+str(size),stderr=b'x'*size,reason='PR_WORKER_STDERR' if size==1 else 'PR_IPC_OVERFLOW')

    def test_response_truncated_eof(self):
        for raw in (b'\0\0',self.frame(self.value())[:9]):
            with self.subTest(size=len(raw)):self.check_flow('truncated',raw=raw,reason='PR_IPC_TRUNCATED')
        self.check_flow('missing-result',missing_result=True,reason='PR_IPC_TRUNCATED')
        self.check_flow('pending-ack',pending_eof=True,reason='PR_IPC_TRUNCATED')

    def test_response_extra_frame_and_order(self):
        self.check_flow('extra',extra=self.frame(self.value()),reason='PR_IPC_ORDER')
        self.check_flow('armed-first',raw=self.frame(dict(version=1,kind='armed')),stage='ready',reason='PR_IPC_ORDER',expected_go=0)
        self.check_flow('pending-request',stage='pending',reason='PR_IPC_ORDER',expected_go=0)

    def test_response_expiry_before_note(self):
        self.check_flow('expiry-before-go',timing='before_go',reason='PR_DEADLINE',expected_go=0)
        self.check_flow('expiry-before-note',timing='before_note',reason='PR_DEADLINE')

    def test_response_expiry_after_note(self):
        self.check_flow('expiry-after-note',timing='after_note',notes=1)

    def test_response_policy_withdrawal(self):
        self.check_flow('policy',timing='policy',reason='PR_AUTHORITY_EXPIRED',expected_go=0)


class GracefulFinalizationFakeTests(unittest.TestCase):
    """Owned-handle-only finalization; fake OS boundaries, real lifecycle code."""
    setUp = StageAFakeOwnershipTests.setUp
    require_contract = StageAFakeOwnershipTests.require_contract
    parent_state = StageAFakeOwnershipTests.parent_state
    direct_contract = DirectWorkerFakeTests.direct_contract

    def prepared(self):
        self.direct_contract()
        state = self.parent_state()
        state.note_protocol_complete(self.budget)
        return state

    def finish(self, state, deadline=10):
        self.m._pr_cleanup(state, 'parent', deadline)
        self.assertEqual(state.record.stage, 'DIRECT_FINALIZATION')
        self.assertTrue(hasattr(state, '_direct_finalization'))
        self.assertEqual(state.record.status, 'UNKNOWN')
        self.assertEqual(state.record.group, 'UNKNOWN')
        self.assertFalse(state.cleaned)
        self.assertEqual([e for e in self.events if e[0]=='signal'], [])
        return state._direct_finalization

    def test_natural_exit_after_protocol_never_needs_current_identity(self):
        state = self.prepared(); self.identity_missing = True
        with patch.object(self.m, '_pr_identity', side_effect=AssertionError('numeric lookup')) as identity:
            record = self.finish(state)
        self.assertEqual(identity.call_count, 0)
        self.assertEqual(record.outcome, 'COMPLETE')
        self.assertEqual(state.direct_worker_completion, 'DIRECT_WORKER_COMPLETION')
        self.assertEqual(self.events, [('wait',10),('close','stdin'),('close','stdout'),('close','stderr')])

    def test_cached_exit_zero_no_wait_or_signal(self):
        state = self.prepared(); self.p.returncode = 0
        record = self.finish(state)
        self.assertEqual(record.outcome, 'COMPLETE')
        self.assertEqual([e for e in self.events if e[0]=='wait'], [])

    def test_expired_before_wait_and_crossing_deadline(self):
        state = self.prepared(); self.clock = 10
        self.assertEqual(self.finish(state).outcome, 'BUDGET_EXPIRED')
        self.assertEqual([e for e in self.events if e[0]=='wait'], [])
        self.clock = 0; self.p.returncode = None; self.events.clear()
        state = self.parent_state(); state.note_protocol_complete(self.budget)
        def wait(timeout):
            self.assertEqual(timeout, 10); self.clock=10; self.p.returncode=0
        self.p.wait=wait
        self.assertEqual(self.finish(state).outcome, 'BUDGET_EXPIRED')
        self.assertEqual(state.direct_worker_completion, 'UNKNOWN')

    def test_fresh_policy_denial_exception_and_later_expiry(self):
        state = self.prepared()
        with patch.object(self.m.rse, 'evaluate_policy', return_value=SimpleNamespace(disposition='DENY')):
            self.assertEqual(self.finish(state).outcome, 'POLICY_DENIED')
        self.assertEqual(state.direct_worker_completion, 'UNKNOWN')
        self.p.returncode=None; state=self.parent_state(); state.note_protocol_complete(self.budget)
        with patch.object(self.m.rse, 'evaluate_policy', side_effect=ValueError('policy')):
            self.assertEqual(self.finish(state).outcome, 'POLICY_DENIED')
        self.p.returncode=None; state=self.parent_state(); state.note_protocol_complete(self.budget)
        self.finish(state); self.clock=10
        self.assertEqual(state.direct_worker_completion, 'UNKNOWN')

    def test_wait_failure_once_without_escalation(self):
        self.direct_contract()
        for error,want in ((subprocess.TimeoutExpired('fake',10),'WAIT_TIMEOUT'),
                           (OSError(5,'fake'),'WAIT_ERROR'),(RuntimeError('fake'),'WAIT_ERROR')):
            with self.subTest(kind=type(error).__name__):
                self.p.returncode=None;self.events.clear();self.wait_error=error
                state=self.parent_state();state.note_protocol_complete(self.budget)
                record=self.finish(state)
                self.assertEqual(record.outcome,want)
                self.assertEqual(record.errno,5 if type(error) is OSError else None)
                self.assertEqual(len([e for e in self.events if e[0]=='wait']),1)
                self.assertEqual(state.direct_worker_completion,'UNKNOWN')

    def test_nonzero_and_invalid_returncodes(self):
        self.direct_contract()
        for code,want in ((1,'NONZERO_EXIT'),(-15,'NONZERO_EXIT'),(True,'INVALID'),(None,'INVALID')):
            with self.subTest(code=code):
                self.p.returncode=None;state=self.parent_state();state.note_protocol_complete(self.budget)
                self.p.wait=lambda timeout,c=code:setattr(self.p,'returncode',c)
                self.assertEqual(self.finish(state).outcome,want)
                self.assertEqual(state.direct_worker_completion,'UNKNOWN')

    def test_missing_original_identity_is_not_fabricated(self):
        self.direct_contract();self.identity_missing=True
        state=self.parent_state();state.note_protocol_complete(self.budget)
        record=self.finish(state)
        self.assertEqual(record.outcome,'IDENTITY_MISSING')
        self.assertIsNone(record.identity)
        self.assertEqual(state.direct_worker_completion,'UNKNOWN')

    def test_single_claimant_pending_then_atomic_terminal(self):
        state=self.prepared(); observed=[]
        def wait(timeout):
            observed.append(state.snapshot()[0]);self.assertFalse(state.cleanup_done.is_set())
            self.assertEqual(state.direct_worker_completion,'UNKNOWN')
            self.assertIsNone(state.begin_cleanup('parent'))
            self.assertIsNone(state.begin_cleanup('launcher'))
            with self.assertRaises(ValueError):state.note_protocol_complete(self.budget)
            self.p.returncode=0
        self.p.wait=wait;record=self.finish(state)
        self.assertEqual(observed,['CLEANUP_PENDING']);self.assertTrue(state.cleanup_done.is_set())
        prior=list(self.events);self.m._pr_cleanup(state,'parent',10)
        self.assertEqual(self.events,prior)
        with self.assertRaises(ValueError):state.finish_direct_finalization(state.claimant,record)

    def test_pipe_failure_and_pending_launcher_keep_unknown(self):
        state=self.prepared()
        def close():
            self.events.append(('close','stdout'));raise OSError(9,'fake')
        self.p.stdout.close=close
        record=self.finish(state)
        self.assertEqual((record.outcome,record.errno,record.pipes_closed),('PIPE_ERROR',9,False))
        self.assertEqual(len([e for e in self.events if e[0]=='close']),3)
        self.assertEqual(state.direct_worker_completion,'UNKNOWN')
        self.p.stdout.close=lambda:None;self.p.returncode=None
        state=self.parent_state();state.note_protocol_complete(self.budget);state.launcher_done.clear()
        self.assertEqual(self.finish(state).outcome,'COMPLETE')
        self.assertEqual(state.direct_worker_completion,'UNKNOWN')

    def test_deadline_mismatch_cannot_extend_budget(self):
        state=self.prepared()
        self.assertEqual(self.finish(state,11).outcome,'INVALID')
        self.assertEqual(state.direct_worker_completion,'UNKNOWN')
        self.assertTrue(all(e[1]<=10 for e in self.events if e[0]=='wait'))

    def test_strict_record_types_and_pair_tampering_fail_closed(self):
        state=self.prepared();record=self.finish(state)
        for field,value in (('outcome',1),('reaped',1),('pipes_closed',1),('quiescent',1),
                            ('within_budget',1),('policy_allowed',1),('errno',True),('errno',0),
                            ('returncode',True),('identity',(True,1,1)),('identity',[1,1,1]),
                            ('outcome','PENDING'),('reaped',False),('returncode',1)):
            with self.subTest(field=field,value=value):
                with self.assertRaises(ValueError):replace(record,**{field:value})
        with self.assertRaises(TypeError):self.m._PRDirectFinalizationRecord(extra=1)
        state.record=replace(state.record,pipes_closed=False)
        self.assertEqual(state.direct_worker_completion,'UNKNOWN')

    def test_invalid_publication_terminal_unknown_not_complete(self):
        state=self.prepared()
        self.assertTrue(hasattr(state,'finish_direct_finalization'))
        token,_,_=state.begin_cleanup('parent')
        state.finish_direct_finalization(token,object())
        self.assertEqual(state.record.stage,'INVALID');self.assertTrue(state.cleanup_done.is_set())
        self.assertEqual(state.direct_worker_completion,'UNKNOWN');self.assertFalse(state.cleaned)

    def test_incomplete_protocol_retains_old_live_identity_signal_gate(self):
        self.direct_contract();state=self.parent_state();self.identity_missing=True
        self.m._pr_cleanup(state,'parent',10)
        self.assertEqual(state.record.stage,'IDENTITY')
        self.assertEqual(state.direct_worker_completion,'UNKNOWN')
        self.assertEqual([e for e in self.events if e[0]=='signal'],[])
        with self.assertRaises(ValueError):state.note_protocol_complete(self.budget)

    def test_protocol_flow_and_same_transport_second_attempt_no_spawn(self):
        # Same transport must retain its original quarantined launch association.
        self.frame=ResponseEnvelopeFakeTests.frame.__get__(self)
        self.value=ResponseEnvelopeFakeTests.value.__get__(self)
        ResponseEnvelopeFakeTests.check_flow(self,'graceful-bound-repeat',notes=1)


class Service:
    """A service that applies mutations before optionally losing the response."""
    tls_verified = True
    follows_redirects = False

    def __init__(self):
        self.requests = []
        self.resources = []
        self.lose_response = False
        self.status = 200
        self.response = b'RESPONSE_MARKER'
        self.entered = None
        self.release = None

    def request(self, method, url, headers, body, **limits):
        self.requests.append((method, url, headers, body))
        if self.entered:
            self.entered.set()
            self.release.wait(3)
        if method not in ('GET', 'HEAD'):
            self.resources.append(body)
            if self.lose_response:
                raise TimeoutError('SYNTHETIC_SECRET_TOKEN')
        return (self.status, (), self.response)


class RemoteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_path = sys.path[:]
        sys.path.insert(0, str(SCRIPTS))
        cls.m = importlib.import_module('remote_runtime_binding') if (SCRIPTS / 'remote_runtime_binding.py').exists() else None

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = cls.saved_path

    def setUp(self):
        self.assertIsNotNone(self.m, 'remote runtime implementation missing')
        self.r, self.c, self.s = self.m.rse, self.m.cet, self.m.sc
        self.broker = self.r.CapabilityBroker()
        self.journal = self.r.InMemorySecurityJournal()
        self.chain = self.s.InMemorySecurityChain('chain', 'install')
        self.actor = self.s.SecurityAuthority('runtime', self.s.AuthorityRole.RUNTIME, 'install')
        self.service = Service()
        self.adapter = self.m.NetworkRequestAdapter(transport=self.service, allowed_origins=('https://api.example.invalid',))
        self.broker.register('network.request', self.adapter)
        self.socket_guard = patch('socket.create_connection', side_effect=AssertionError('PUBLIC_NETWORK_FORBIDDEN'))
        self.socket_guard.start()
        self.addCleanup(self.socket_guard.stop)

    def payload(self, ident='a', **values):
        return self.m.RemoteRuntimePayload(ident, self.r.ActionClass.NETWORK_REQUEST,
            'https://api.example.invalid/resource', method='POST', body=b'REQUEST_MARKER',
            request_identity='request-1', **values)

    def action(self, payload):
        return self.r.ActionRequest(payload.action_id, 'run', 'task', payload.action_class,
            payload.target, 'trusted', 'remote', self.r.DataClass.NON_SENSITIVE,
            'auth', self.r.CAPABILITIES[payload.action_class], 'effect',
            idempotency_key=payload.request_identity)

    def prepare(self, payloads):
        self.binding = self.m.RemoteRuntimeBinding(self.broker, self.journal, self.chain, self.actor,
            approved_payload_digests={p.action_id: p.digest() for p in payloads})

    def execute(self, p, **changes):
        reconcile = changes.pop('reconcile', False)
        a = changes.pop('action', self.action(p))
        policy = self.r.Policy('core', self.r.PolicyLevel.CORE, frozenset(self.r.ActionClass),
            network_mode=self.r.NetworkMode.ALLOWLIST, network_allowlist=('https://api.example.invalid',),
            allowed_egress_classes=frozenset({self.r.DataClass.NON_SENSITIVE}),
            allowed_capabilities=frozenset(self.r.CAPABILITIES.values()))
        auth = self.r.Authorization('auth', 'task', frozenset({a.action_class}), (a.target,), frozenset({a.capability}), 100)
        context = self.c.TraceContext('trace', 'install', 'project', 'task', 'run', a.action_id, None, 'trusted', None, 'remote')
        args = dict(policy_stack=(policy,), authorization=auth, context=context, now=1)
        args.update(changes)
        method = self.binding.reconcile if reconcile else self.binding.execute
        return method(a, p, **args)

    def test_destination_substitution_denied_before_send(self):
        p = self.payload(); self.prepare([p])
        out = self.execute(replace(p, target='https://api.example.invalid/other'))
        self.assertEqual(out.receipt.policy_reason, 'PAYLOAD_DIGEST_MISMATCH')
        self.assertEqual(self.service.resources, [])
        self.assertEqual(self.service.requests, [])

    def test_body_substitution_denied_before_send(self):
        p = self.payload(); self.prepare([p])
        self.assertEqual(self.execute(replace(p, body=b'other')).receipt.policy_reason, 'PAYLOAD_DIGEST_MISMATCH')
        self.assertEqual(self.service.requests, [])

    def test_network_unknown_blocks_second_attempt(self):
        p = self.payload(); self.prepare([p]); self.service.lose_response = True
        self.assertEqual(self.execute(p).receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(self.execute(p).receipt.policy_reason, 'UNKNOWN_OUTCOME_PENDING')
        self.assertEqual(self.service.resources, [b'REQUEST_MARKER'])

    def setup_git(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / 'local'; self.root.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Synthetic')
        self.git('config', 'user.email', 'synthetic@example.invalid')
        self.git('commit', '--allow-empty', '-qm', 'old')
        old = self.git('rev-parse', 'HEAD').decode().strip()
        self.git('commit', '--allow-empty', '-qm', 'new')
        new = self.git('rev-parse', 'HEAD').decode().strip()
        self.git('remote', 'add', 'origin', 'https://api.example.invalid/repo.git')
        self.git_service = GitService(self.m, old)
        adapter = self.m.GitPushAdapter(workspace_root=str(self.root), git_executable=str(Path(shutil.which('git')).resolve()),
            transport=self.git_service, allowed_origins=('https://api.example.invalid',))
        self.broker.register('git.push', adapter)
        return self.m.RemoteRuntimePayload('git', self.r.ActionClass.GIT_PUSH, 'https://api.example.invalid/repo.git',
            repository=str(self.root), remote_name='origin', local_ref=self.git('symbolic-ref', 'HEAD').decode().strip(),
            remote_ref='refs/heads/main', expected_local_oid=new, expected_remote_oid=old)

    def git(self, *args):
        return subprocess.run([shutil.which('git'), '-C', str(self.root), *args], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={'PATH': '/usr/bin:/bin', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null'}).stdout

    def test_remote_ref_drift_denied(self):
        p = self.setup_git(); self.prepare([p]); self.git_service.oid = '3' * 40
        out = self.execute(p)
        self.assertEqual(out.evidence.reason, 'REMOTE_REF_CHANGED')
        self.assertEqual(self.git_service.mutations, 0)

    def test_local_ref_drift_denied(self):
        p = self.setup_git(); self.prepare([p]); self.git('commit', '--allow-empty', '-qm', 'drift')
        out = self.execute(p)
        self.assertEqual(out.evidence.reason, 'LOCAL_REF_CHANGED')
        self.assertEqual(self.git_service.mutations, 0)

    def test_remote_url_drift_denied(self):
        p = self.setup_git(); self.prepare([p]); self.git('remote', 'set-url', 'origin', 'https://api.example.invalid/other.git')
        out = self.execute(p)
        self.assertEqual(out.evidence.reason, 'GIT_REMOTE_BINDING_MISMATCH')
        self.assertEqual(self.git_service.mutations, 0)

    def test_git_remote_name_is_case_sensitive(self):
        p = replace(self.setup_git(), remote_name='Origin'); self.prepare([p])
        self.assertEqual(self.execute(p).evidence.reason, 'GIT_REMOTE_BINDING_MISMATCH')
        self.assertEqual(self.git_service.requests, [])

    def test_git_unknown_blocks_second_push(self):
        p = self.setup_git(); self.prepare([p]); self.git_service.lose_response = True
        self.assertEqual(self.execute(p).receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(self.execute(p).receipt.policy_reason, 'UNKNOWN_OUTCOME_PENDING')
        self.assertEqual(self.git_service.mutations, 1)
        self.assertEqual(self.git_service.oid, p.expected_local_oid)

    def test_pr_fixed_user_agent_post(self):
        p = self.setup_pr(); self.prepare([p]); self.execute(p)
        self.assertEqual(dict(self.provider.requests[0][2]).get('user-agent'),
            '20396-remote-runtime-binding')

    def test_pr_fixed_user_agent_recovery(self):
        p = self.setup_pr(); self.prepare([p]); self.provider.lose_response = True
        self.execute(p); self.execute(p, reconcile=True)
        self.assertEqual(self.provider.requests[-1][0], 'GET')
        self.assertEqual(dict(self.provider.requests[-1][2]).get('user-agent'),
            '20396-remote-runtime-binding')
        self.assertEqual(sum(r[0] == 'POST' for r in self.provider.requests), 1)

    def test_pr_payload_cannot_override_user_agent(self):
        for name in ('User-Agent', 'user-agent', 'X-Extra'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                replace(self.setup_pr(), headers=((name, 'override'),))

    def setup_pr(self):
        self.provider = PRService()
        self.broker.register(self.r.CAPABILITIES[self.r.ActionClass.PR_CREATE],
            self.m.PullRequestCreateAdapter(transport=self.provider, allowed_origins=('https://api.example.invalid',)))
        return self.m.RemoteRuntimePayload('pr', self.r.ActionClass.PR_CREATE, 'https://api.example.invalid/repos/team/repo/pulls',
            provider='github', repository='team/repo', head='feature', base='main', title='Title', body=b'PR_BODY_MARKER',
            draft=True, request_identity='request-1')

    def test_pr_unknown_duplicate_denied(self):
        p = self.setup_pr(); self.prepare([p]); self.provider.lose_response = True
        self.assertEqual(self.execute(p).receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(self.execute(p).receipt.policy_reason, 'UNKNOWN_OUTCOME_PENDING')
        self.assertEqual(len(self.provider.resources), 1)

    def test_network_exact_get_and_adapter_observation(self):
        p = replace(self.payload(), method='GET', body=b'', query='b=2&a=1', headers=(('Accept', 'application/json'),))
        self.prepare([p]); out = self.execute(p)
        self.assertEqual(out.receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertEqual(self.service.requests, [('GET', 'https://api.example.invalid:443/resource?b=2&a=1',
            (('accept', 'application/json'), ('idempotency-key', 'request-1')), b'')])
        self.assertEqual(out.events[0].source, self.c.ObservationSource.ADAPTER_OBSERVED)
        self.assertEqual(out.events[0].status, self.c.EventStatus.COMPLETED)
        self.assertTrue(out.evidence.request_attempted and out.evidence.response_observed)
        self.assertIs(out.evidence.response_body_complete, True)
        self.assertEqual(out.evidence.response_parse_status, 'NOT_ATTEMPTED')
        self.assertEqual(out.evidence.response_digest, hashlib.sha256(b'RESPONSE_MARKER').hexdigest())
        self.assertTrue(self.chain.verify().valid)

    def test_prebound_fields_cannot_change(self):
        p = self.payload(query='a=1&a=2', headers=(('Accept', 'application/json'),)); self.prepare([p])
        for changes in (dict(query='a=2&a=1'), dict(headers=(('Accept', 'text/plain'),)),
                dict(request_identity='request-2'), dict(timeout=31), dict(method='PUT')):
            with self.subTest(changes=changes):
                out = self.execute(replace(p, **changes))
                self.assertEqual(out.receipt.policy_reason, 'PAYLOAD_DIGEST_MISMATCH')
        self.assertEqual(self.service.requests, [])

    def test_exact_target_action_id_and_snapshot_are_required(self):
        p = self.payload(); snapshot = {'a': p.digest()}
        self.binding = self.m.RemoteRuntimeBinding(self.broker, self.journal, self.chain, self.actor,
            approved_payload_digests=snapshot)
        changed = replace(p, body=b'different'); snapshot['a'] = changed.digest()
        self.assertEqual(self.execute(changed).receipt.policy_reason, 'PAYLOAD_DIGEST_MISMATCH')
        self.assertEqual(self.execute(p, action=replace(self.action(p), action_id='b')).receipt.policy_reason,
            'MALFORMED_REMOTE_PAYLOAD')
        self.assertEqual(self.execute(p, action=replace(self.action(p), target='https://api.example.invalid/other')).receipt.policy_reason,
            'MALFORMED_REMOTE_PAYLOAD')
        self.assertEqual(self.service.requests, [])

    def test_insecure_url_and_transport_rejected(self):
        for target in ('http://api.example.invalid/resource', 'https://user:password@api.example.invalid/resource',
                'ssh://api.example.invalid/repo', 'https://api.example.invalid:0/resource',
                'https://api.example.invalid/a/../resource', 'https://api.example.invalid/%2e%2e/resource',
                'https://api.example.invalid/resource#fragment'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                replace(self.payload(), target=target)
        self.service.tls_verified = False
        with self.assertRaises(ValueError):
            self.m.NetworkRequestAdapter(transport=self.service, allowed_origins=('https://api.example.invalid',))
        self.assertEqual(self.service.requests, [])

    def test_known_presend_rejection_no_observed_event(self):
        p = self.payload(); self.prepare([p]); self.service.tls_verified = False
        out = self.execute(p)
        self.assertEqual(out.receipt.execution_state, 'KNOWN_FAILURE')
        self.assertEqual(out.events, ())
        self.assertEqual(self.service.requests, [])

    def test_non_success_mutation_response_stays_unknown(self):
        for status in (302, 400, 500):
            p = self.payload(str(status)); self.prepare([p]); self.service.status = status
            out = self.execute(p)
            self.assertEqual(out.receipt.execution_state, 'UNKNOWN_OUTCOME')
            self.assertEqual(self.execute(p).receipt.policy_reason, 'UNKNOWN_OUTCOME_PENDING')
        self.assertEqual(len(self.service.requests), 3)

    def test_response_bounds_keep_mutation_unknown(self):
        p = self.payload(response_limit=4); self.prepare([p])
        out = self.execute(p)
        self.assertEqual(out.receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(self.execute(p).receipt.policy_reason, 'UNKNOWN_OUTCOME_PENDING')
        self.assertEqual(len(self.service.resources), 1)

    def test_payload_size_header_and_timeout_limits_before_send(self):
        p = self.payload()
        for changes in (dict(body=b'x' * (8 * 1024 * 1024 + 1)), dict(headers=(('Authorization', 'secret'),)),
                dict(headers=(('Content-Type', 'a\r\nb'),)), dict(headers=(('Accept', 'x' * 65536),)),
                dict(timeout=float('inf')), dict(timeout=121), dict(response_limit=0)):
            with self.subTest(field=next(iter(changes))), self.assertRaises(ValueError):
                replace(p, **changes)
        self.assertEqual(self.service.requests, [])

    def test_readback_only_and_digest_anchored(self):
        p = self.payload(readback_target='https://api.example.invalid/resource/status',
            expected_readback_digest=hashlib.sha256(b'RESPONSE_MARKER').hexdigest())
        self.prepare([p]); self.service.lose_response = True; self.execute(p)
        out = self.execute(p, reconcile=True)
        self.assertEqual(out.receipt.final_disposition, 'RECONCILED_SUCCESS')
        self.assertEqual([v[0] for v in self.service.requests], ['POST', 'GET'])
        self.assertEqual(out.evidence.reconciliation, 'RECONCILED_SUCCESS')
        self.assertIn(self.s.artifact_digest(out.evidence), out.receipt.evidence_refs)
        self.assertEqual(self.execute(p).receipt.policy_reason, 'ALREADY_COMPLETED')

    def test_no_readback_or_unmatched_readback_stays_unknown(self):
        p = self.payload(); self.prepare([p]); self.service.lose_response = True; self.execute(p)
        out = self.execute(p, reconcile=True)
        self.assertEqual(out.evidence.reconciliation, 'STILL_UNKNOWN')
        self.assertEqual(len(self.service.requests), 1)

    def test_all_authority_capability_and_policy_gates(self):
        for p in (self.payload(), self.setup_git(), self.setup_pr()):
            with self.subTest(kind=p.action_class):
                self.prepare([p])
                out = self.execute(p, authorization=None)
                self.assertEqual(out.receipt.policy_reason, 'AUTHORIZATION_MISSING')
                self.assertEqual(out.events, ())
                out = self.execute(p, policy_stack=(self.r.Policy('core', self.r.PolicyLevel.CORE),))
                self.assertEqual(out.receipt.policy_reason, 'ACTION_NOT_IN_SCOPE')
                self.binding.broker = self.r.CapabilityBroker()
                self.assertEqual(self.execute(p).receipt.policy_reason, 'CAPABILITY_MISSING')
        self.assertEqual(self.service.requests, [])
        self.assertEqual(self.git_service.requests, [])
        self.assertEqual(self.provider.requests, [])

    def test_same_action_concurrent_unknown_one_mutation(self):
        p = self.payload(); self.prepare([p]); self.service.lose_response = True
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.execute(p), range(4)))
        self.assertEqual(self.service.resources, [b'REQUEST_MARKER'])
        self.assertEqual(sum(v.receipt.policy_reason == 'UNKNOWN_OUTCOME_PENDING' for v in results), 3)

    def test_distinct_actions_proceed_while_first_waits(self):
        p = self.payload(); second = self.payload('b'); self.prepare([p, second])
        self.service.entered = threading.Event(); self.service.release = threading.Event()
        original = self.service.request
        def request(method, url, headers, body, **limits):
            if len(self.service.requests) == 0:
                return original(method, url, headers, body, **limits)
            self.service.resources.append(body)
            return 200, (), b'ok'
        with patch.object(self.service, 'request', side_effect=request), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.execute, p)
            self.assertTrue(self.service.entered.wait(2))
            other = pool.submit(self.execute, second)
            try:
                self.assertEqual(other.result(timeout=1).receipt.execution_state, 'KNOWN_SUCCESS')
            finally:
                self.service.release.set()
            self.assertEqual(first.result().receipt.execution_state, 'KNOWN_SUCCESS')

    def test_git_success_applies_production_bytes_to_bare_remote(self):
        p = self.setup_git(); self.prepare([p])
        remote = self.root.parent / 'bare.git'
        self.git('clone', '--bare', '--no-hardlinks', str(self.root), str(remote))
        subprocess.run([shutil.which('git'), '--git-dir', str(remote), 'update-ref', p.remote_ref, p.expected_remote_oid], check=True)
        bare = BareGitService(remote)
        self.broker.get('git.push').transport = bare
        out = self.execute(p)
        self.assertEqual(out.receipt.execution_state, 'KNOWN_SUCCESS')
        value = subprocess.check_output([shutil.which('git'), '--git-dir', str(remote), 'rev-parse', p.remote_ref]).decode().strip()
        self.assertEqual(value, p.expected_local_oid)
        self.assertEqual(bare.mutations, 1)
        self.assertIs(out.evidence.response_body_complete, True)
        self.assertEqual(out.evidence.response_parse_status, 'PARSED')

    def test_git_compare_and_swap_rejects_drift_after_lookup(self):
        p = self.setup_git(); self.prepare([p]); remote = self.root.parent / 'bare.git'
        self.git('clone', '--bare', '--no-hardlinks', str(self.root), str(remote))
        subprocess.run([shutil.which('git'), '--git-dir', str(remote), 'update-ref', p.remote_ref, p.expected_remote_oid], check=True)
        self.git('commit', '--allow-empty', '-qm', 'third')
        third = self.git('rev-parse', 'HEAD').decode().strip()
        self.git('push', str(remote), 'HEAD:refs/heads/third')
        self.git('update-ref', p.local_ref, p.expected_local_oid)
        bare = BareGitService(remote, drift_oid=third)
        self.broker.get('git.push').transport = bare
        self.assertEqual(self.execute(p).receipt.execution_state, 'UNKNOWN_OUTCOME')
        value = subprocess.check_output([shutil.which('git'), '--git-dir', str(remote), 'rev-parse', p.remote_ref]).decode().strip()
        self.assertEqual(value, third)
        self.assertEqual(self.execute(p).receipt.policy_reason, 'UNKNOWN_OUTCOME_PENDING')

    def test_git_non_fast_forward_no_mutation(self):
        p = self.setup_git(); p = replace(p, expected_remote_oid=p.expected_local_oid, expected_local_oid=p.expected_remote_oid)
        self.git('update-ref', p.local_ref, p.expected_local_oid); self.git_service.oid = p.expected_remote_oid
        self.prepare([p]); out = self.execute(p)
        self.assertEqual(out.evidence.reason, 'NON_FAST_FORWARD')
        self.assertEqual(self.git_service.mutations, 0)

    def unrelated_git(self):
        p = self.setup_git()
        tree = self.git('rev-parse', p.expected_local_oid + '^{tree}').decode().strip()
        unrelated = self.git('commit-tree', tree, '-m', 'unrelated root').decode().strip()
        self.git('update-ref', p.local_ref, unrelated)
        p = replace(p, expected_local_oid=unrelated)
        for oid in (p.expected_remote_oid, unrelated):
            header = self.git('cat-file', 'commit', oid).split(b'\n\n', 1)[0]
            self.assertEqual([row for row in header.splitlines() if row.startswith(b'parent ')], [])
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            self.git('merge-base', '--is-ancestor', p.expected_remote_oid, unrelated)
        self.assertEqual(caught.exception.returncode, 1)
        return p, tree

    def assert_ancestry_rejected(self, p):
        self.prepare([p]); out = self.execute(p)
        self.assertEqual(out.evidence.reason, 'GIT_ANCESTRY_OVERRIDE_PRESENT')
        self.assertEqual(out.receipt.execution_state, 'KNOWN_FAILURE')
        self.assertEqual(self.git_service.mutations, 0)
        self.assertEqual(self.git_service.oid, p.expected_remote_oid)
        self.assertFalse(any(request[0] == 'POST' for request in self.git_service.requests))
        return out

    def test_ancestry_graft_on_unrelated_real_roots_rejected(self):
        p, _ = self.unrelated_git()
        (self.root / '.git/info/grafts').write_text(p.expected_local_oid + ' ' + p.expected_remote_oid + '\n')
        # The fixture really changes Git's ordinary graph interpretation.
        self.git('merge-base', '--is-ancestor', p.expected_remote_oid, p.expected_local_oid)
        self.assert_ancestry_rejected(p)

    def test_ancestry_loose_replace_of_unrelated_root_rejected(self):
        p, tree = self.unrelated_git()
        replacement = self.git('commit-tree', tree, '-p', p.expected_remote_oid, '-m', 'replacement parent').decode().strip()
        self.git('update-ref', 'refs/replace/' + p.expected_local_oid, replacement)
        self.git('merge-base', '--is-ancestor', p.expected_remote_oid, p.expected_local_oid)
        self.assert_ancestry_rejected(p)

    def test_ancestry_packed_replace_of_unrelated_root_rejected(self):
        p, tree = self.unrelated_git()
        replacement = self.git('commit-tree', tree, '-p', p.expected_remote_oid, '-m', 'packed replacement parent').decode().strip()
        ref = 'refs/replace/' + p.expected_local_oid
        self.git('update-ref', ref, replacement); self.git('pack-refs', '--all', '--prune')
        self.assertFalse((self.root / '.git' / ref).exists())
        self.assertIn(ref.encode(), (self.root / '.git/packed-refs').read_bytes())
        self.git('merge-base', '--is-ancestor', p.expected_remote_oid, p.expected_local_oid)
        self.assert_ancestry_rejected(p)

    def test_ancestry_irrelevant_replace_namespace_entry_rejected(self):
        p = self.setup_git()
        self.git('update-ref', 'refs/replace/' + '4' * 40, p.expected_remote_oid)
        self.assert_ancestry_rejected(p)

    def test_ancestry_malformed_loose_replace_entry_rejected(self):
        p = self.setup_git()
        directory = self.root / '.git/refs/replace'; directory.mkdir()
        (directory / 'not-an-object-id').write_text('SYNTHETIC_INVALID_REF\n')
        self.assert_ancestry_rejected(p)

    def test_ancestry_malformed_nonempty_grafts_rejected_without_content_leak(self):
        for content in ('SYNTHETIC_GRAFT_PRIVATE_MARKER\n', '\n', '# comment only\n'):
            with self.subTest(content_kind=len(content)):
                self.broker = self.r.CapabilityBroker(); self.journal = self.r.InMemorySecurityJournal()
                p = self.setup_git()
                (self.root / '.git/info/grafts').write_text(content)
                out = self.assert_ancestry_rejected(p)
                artifacts = repr(out.evidence) + repr(out.receipt) + repr(out.events)
                artifacts += json.dumps([asdict(record) for record in self.chain.records()])
                self.assertNotIn('SYNTHETIC_GRAFT_PRIVATE_MARKER', artifacts)

    def test_ancestry_empty_grafts_allows_true_fast_forward(self):
        p = self.setup_git(); (self.root / '.git/info/grafts').write_bytes(b'')
        self.prepare([p]); out = self.execute(p)
        self.assertEqual(out.receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertEqual(self.git_service.oid, p.expected_local_oid)
        self.assertEqual(self.git_service.mutations, 1)

    def test_ancestry_unrelated_clean_roots_denied_without_override(self):
        p, _ = self.unrelated_git(); self.prepare([p])
        self.assertEqual(self.execute(p).evidence.reason, 'NON_FAST_FORWARD')
        self.assertEqual(self.git_service.oid, p.expected_remote_oid)
        self.assertEqual(self.git_service.mutations, 0)

    def test_ancestry_override_rechecked_before_graph_pack_and_send(self):
        for phase in ('remote', 'merge-base', 'pack-objects'):
            with self.subTest(phase=phase):
                self.broker = self.r.CapabilityBroker(); self.journal = self.r.InMemorySecurityJournal()
                p = self.setup_git(); adapter = self.broker.get('git.push')
                original_call, original_request = adapter.local._call, self.git_service.request
                calls = []
                def inject():
                    (self.root / '.git/info/grafts').write_text('SYNTHETIC_LATE_OVERRIDE\n')
                def call(args, **kwargs):
                    calls.append(args[0]); result = original_call(args, **kwargs)
                    if args[0] == phase:
                        inject()
                    return result
                def request(*args, **kwargs):
                    result = original_request(*args, **kwargs)
                    if phase == 'remote':
                        inject()
                    return result
                with patch.object(adapter.local, '_call', side_effect=call), \
                        patch.object(self.git_service, 'request', side_effect=request):
                    self.assert_ancestry_rejected(p)
                if phase == 'remote':
                    self.assertNotIn('merge-base', calls)
                if phase in ('remote', 'merge-base'):
                    self.assertNotIn('pack-objects', calls)

    def test_ancestry_actual_subprocess_environment_disables_replacement(self):
        p = self.setup_git(); self.prepare([p])
        actual_popen = self.m.local.subprocess.Popen
        commands = []
        def launch(argv, *args, **kwargs):
            # This is the real launcher subprocess boundary, with the exact
            # target argv/environment subsequently passed to os.execve.
            target_argv, target_environment = json.loads(argv[-3]), json.loads(argv[-1])
            self.assertEqual(kwargs['env'], {})
            self.assertEqual(target_environment.get('GIT_NO_REPLACE_OBJECTS'), '1')
            for key in ('GIT_REPLACE_REF_BASE', 'GIT_GRAFT_FILE', 'GIT_CONFIG_COUNT',
                    'GIT_CONFIG_KEY_0', 'GIT_CONFIG_VALUE_0'):
                self.assertNotIn(key, target_environment)
            commands.append(target_argv)
            return actual_popen(argv, *args, **kwargs)
        injected = {'GIT_NO_REPLACE_OBJECTS': '0', 'GIT_REPLACE_REF_BASE': 'refs/injected',
            'GIT_GRAFT_FILE': str(self.root / 'injected-grafts'), 'GIT_CONFIG_COUNT': '1',
            'GIT_CONFIG_KEY_0': 'core.useReplaceRefs', 'GIT_CONFIG_VALUE_0': 'true'}
        with patch.dict(os.environ, injected), patch.object(self.m.local.subprocess, 'Popen', side_effect=launch):
            out = self.execute(p)
        self.assertEqual(out.receipt.execution_state, 'KNOWN_SUCCESS')
        for command in ('rev-parse', 'merge-base', 'pack-objects'):
            self.assertTrue(any(command in argv for argv in commands), command)
        self.assertEqual(self.git_service.mutations, 1)

    def test_git_broad_delete_and_ssh_requests_rejected(self):
        p = self.setup_git()
        for values in (dict(remote_ref='refs/heads/*'), dict(remote_ref=''), dict(local_ref='--all'),
                dict(local_ref='--mirror'), dict(local_ref='refs/heads/a refs/heads/b'),
                dict(target='git@host:repo'), dict(target='file:///tmp/repo'), dict(expected_local_oid='0' * 40)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                replace(p, **values)
        self.assertEqual(self.git_service.mutations, 0)

    def test_git_unsafe_config_blocks_before_remote_lookup(self):
        p = self.setup_git(); self.prepare([p]); self.git('config', 'remote.origin.promisor', 'true')
        self.assertEqual(self.execute(p).receipt.execution_state, 'KNOWN_FAILURE')
        self.assertEqual(self.git_service.requests, [])

    def test_git_readback_classifications_do_not_retry(self):
        p = self.setup_git(); self.prepare([p]); self.git_service.lose_response = True; self.execute(p)
        for oid, expected in (('3' * 40, 'CONFLICT'), (p.expected_remote_oid, 'RECONCILED_NOT_APPLIED')):
            self.git_service.oid = oid
            out = self.execute(p, reconcile=True)
            self.assertEqual(out.evidence.reconciliation, expected)
        self.assertEqual(self.git_service.mutations, 1)

    def test_git_readback_success_blocks_new_push(self):
        p = self.setup_git(); self.prepare([p]); self.git_service.lose_response = True; self.execute(p)
        self.assertEqual(self.execute(p, reconcile=True).receipt.final_disposition, 'RECONCILED_SUCCESS')
        self.assertEqual(self.execute(p).receipt.policy_reason, 'ALREADY_COMPLETED')
        self.assertEqual(self.git_service.mutations, 1)

    def test_pr_exact_success_and_content_substitution(self):
        p = self.setup_pr(); self.prepare([p])
        for values in (dict(repository='team/other', target='https://api.example.invalid/repos/team/other/pulls'),
                dict(head='another'), dict(base='another'), dict(title='other'), dict(body=b'other'), dict(draft=False),
                dict(request_identity='request-2')):
            self.assertEqual(self.execute(replace(p, **values)).receipt.policy_reason, 'PAYLOAD_DIGEST_MISMATCH')
        self.assertEqual(self.provider.resources, [])
        out = self.execute(p)
        self.assertEqual(out.receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertIsNotNone(out.evidence.resource_digest)
        self.assertIs(out.evidence.response_body_complete, True)
        self.assertEqual(out.evidence.response_parse_status, 'PARSED')
        self.assertEqual(self.provider.resources[0]['body'], 'PR_BODY_MARKER\n\n<!-- 20396-request:request-1 -->')

    def test_pr_empty_multiple_and_exact_readbacks(self):
        p = self.setup_pr(); self.prepare([p]); self.provider.lose_response = True; self.execute(p)
        record = self.provider.resources[0]
        for records in ([], [record, record]):
            self.provider.resources = records
            out = self.execute(p, reconcile=True)
            self.assertEqual(out.evidence.reconciliation, 'STILL_UNKNOWN')
            self.assertEqual(self.execute(p).receipt.policy_reason, 'UNKNOWN_OUTCOME_PENDING')
        self.provider.resources = [record]
        self.assertEqual(self.execute(p, reconcile=True).receipt.final_disposition, 'RECONCILED_SUCCESS')
        self.assertEqual(sum(v[0] == 'POST' for v in self.provider.requests), 1)

    def test_pr_readback_wrong_contract_never_proves_success(self):
        p = self.setup_pr(); self.prepare([p]); self.provider.lose_response = True; self.execute(p)
        self.provider.resources[0]['head']['repo']['full_name'] = 'attacker/repo'
        self.assertEqual(self.execute(p, reconcile=True).evidence.reconciliation, 'STILL_UNKNOWN')

    def recovery_pr(self, **changes):
        p = replace(self.setup_pr(), **changes)
        self.prepare([p]); self.provider.lose_response = True
        self.assertEqual(self.execute(p).receipt.execution_state, 'UNKNOWN_OUTCOME')
        return p

    def assert_recovery_pending(self, p, out):
        self.assertEqual(out.evidence.reconciliation, 'STILL_UNKNOWN')
        self.assertEqual(self.execute(p).receipt.policy_reason, 'UNKNOWN_OUTCOME_PENDING')
        self.assertEqual(sum(request[0] == 'POST' for request in self.provider.requests), 1)

    def test_recovery_malformed_200_retains_observation_status_and_complete_digest(self):
        p = self.recovery_pr()
        body = b'{SYNTHETIC_RESPONSE_BODY'
        self.provider.readback_response = (200, (), body)
        out = self.execute(p, reconcile=True)
        self.assertTrue(out.evidence.response_observed)
        self.assertEqual(out.evidence.status_code, 200)
        self.assertTrue(out.evidence.request_attempted)
        self.assertIs(getattr(out.evidence, 'response_body_complete', None), True)
        self.assertEqual(out.evidence.response_digest, hashlib.sha256(body).hexdigest())
        self.assertEqual(getattr(out.evidence, 'response_parse_status', None), 'PARSE_FAILED')
        self.assert_recovery_pending(p, out)

    def test_recovery_no_response_is_distinct_from_parse_failure(self):
        p = self.recovery_pr(); self.provider.readback_error = TimeoutError('SYNTHETIC_SECRET_TOKEN')
        out = self.execute(p, reconcile=True)
        self.assertTrue(out.evidence.request_attempted)
        self.assertFalse(out.evidence.response_observed)
        self.assertIsNone(out.evidence.status_code)
        self.assertIsNone(getattr(out.evidence, 'response_body_complete', None))
        self.assertIsNone(out.evidence.response_digest)
        self.assertEqual(getattr(out.evidence, 'response_parse_status', None), 'NOT_ATTEMPTED')
        self.assert_recovery_pending(p, out)

    def test_recovery_valid_exact_pr_retains_parsed_response_metadata(self):
        p = self.recovery_pr()
        out = self.execute(p, reconcile=True)
        self.assertEqual(out.evidence.status_code, 200)
        self.assertTrue(out.evidence.response_observed and out.evidence.request_attempted)
        self.assertIs(getattr(out.evidence, 'response_body_complete', None), True)
        self.assertEqual(getattr(out.evidence, 'response_parse_status', None), 'PARSED')
        self.assertEqual(out.evidence.reconciliation, 'RECONCILED_SUCCESS')
        self.assertEqual(self.execute(p).receipt.policy_reason, 'ALREADY_COMPLETED')
        self.assertEqual(sum(request[0] == 'POST' for request in self.provider.requests), 1)

    def test_recovery_ambiguous_pr_is_parsed_but_still_unknown(self):
        p = self.recovery_pr(); self.provider.resources.append(dict(self.provider.resources[0], id=99, number=43))
        out = self.execute(p, reconcile=True)
        self.assertEqual(out.evidence.status_code, 200)
        self.assertTrue(out.evidence.response_observed)
        self.assertEqual(getattr(out.evidence, 'response_parse_status', None), 'PARSED')
        self.assert_recovery_pending(p, out)

    def test_recovery_non_2xx_is_observed_and_keeps_complete_body_digest(self):
        p = self.recovery_pr(); self.provider.readback_response = (503, (), b'[]')
        out = self.execute(p, reconcile=True)
        self.assertTrue(out.evidence.response_observed)
        self.assertEqual(out.evidence.status_code, 503)
        self.assertIs(getattr(out.evidence, 'response_body_complete', None), True)
        self.assertEqual(out.evidence.response_digest, hashlib.sha256(b'[]').hexdigest())
        self.assertEqual(getattr(out.evidence, 'response_parse_status', None), 'PARSED')
        self.assert_recovery_pending(p, out)

    def test_recovery_production_http_incomplete_bodies_omit_digest_and_parse(self):
        cases = (
            b'HTTP/1.1 200 OK\r\nContent-Length: 20\r\n\r\n' + b'x' * 20,
            b'HTTP/1.1 200 OK\r\nContent-Length: 20\r\n\r\n{',
            b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\n{',
        )
        for index, raw in enumerate(cases):
            with self.subTest(case=index):
                self.journal = self.r.InMemorySecurityJournal()
                self.broker = self.r.CapabilityBroker()
                p = self.recovery_pr(response_limit=8)
                transport = self.m.HTTPSRemoteTransport()
                self.broker.get(self.r.CAPABILITIES[p.action_class]).transport = transport
                with patch.object(self.m.http.client, 'HTTPSConnection', response_connection(raw)):
                    out = self.execute(p, reconcile=True)
                self.assertTrue(out.evidence.response_observed)
                self.assertEqual(out.evidence.status_code, 200)
                self.assertTrue(out.evidence.request_attempted)
                self.assertIs(getattr(out.evidence, 'response_body_complete', None), False)
                self.assertIsNone(out.evidence.response_digest)
                self.assertEqual(getattr(out.evidence, 'response_parse_status', None), 'NOT_ATTEMPTED')
                self.assert_recovery_pending(p, out)

    def test_recovery_production_http_status_survives_header_parse_failure(self):
        p = self.recovery_pr()
        self.broker.get(self.r.CAPABILITIES[p.action_class]).transport = self.m.HTTPSRemoteTransport()
        raw = b'HTTP/1.1 200 OK\r\n' + (b'X-Header: ' + b'x' * 1000 + b'\r\n') * 70 + b'\r\n'
        with patch.object(self.m.http.client, 'HTTPSConnection', response_connection(raw)):
            out = self.execute(p, reconcile=True)
        self.assertTrue(out.evidence.response_observed)
        self.assertEqual(out.evidence.status_code, 200)
        self.assertIs(getattr(out.evidence, 'response_body_complete', None), False)
        self.assertIsNone(out.evidence.response_digest)
        self.assertEqual(getattr(out.evidence, 'response_parse_status', None), 'NOT_ATTEMPTED')
        self.assert_recovery_pending(p, out)

    def test_recovery_evidence_chain_and_repr_keep_only_digest_metadata(self):
        p = self.recovery_pr()
        self.provider.readback_response = (200, (), b'{SYNTHETIC_RESPONSE_BODY SYNTHETIC_SECRET_TOKEN')
        out = self.execute(p, reconcile=True)
        digest = self.s.artifact_digest(out.evidence)
        self.assertIn(digest, out.receipt.evidence_refs)
        self.assertTrue(self.chain.verify().valid)
        serialized = json.dumps([asdict(v) for v in self.chain.records()]) + repr(out.receipt) + repr(out.evidence) + repr(out) + repr(out.events)
        for marker in ('SYNTHETIC_RESPONSE_BODY', 'SYNTHETIC_SECRET_TOKEN', 'PR_BODY_MARKER'):
            self.assertNotIn(marker, serialized)
        self.assertTrue(out.evidence.response_observed)
        self.assert_recovery_pending(p, out)

    def test_recovery_network_digest_readback_reports_current_get(self):
        p = self.payload(readback_target='https://api.example.invalid/resource/status',
            expected_readback_digest=hashlib.sha256(b'RESPONSE_MARKER').hexdigest())
        self.prepare([p]); self.service.lose_response = True; self.execute(p)
        out = self.execute(p, reconcile=True)
        self.assertEqual(out.evidence.status_code, 200)
        self.assertTrue(out.evidence.request_attempted and out.evidence.response_observed)
        self.assertIs(getattr(out.evidence, 'response_body_complete', None), True)
        self.assertEqual(getattr(out.evidence, 'response_parse_status', None), 'NOT_ATTEMPTED')
        self.assertEqual(out.evidence.reconciliation, 'RECONCILED_SUCCESS')
        self.assertEqual([request[0] for request in self.service.requests], ['POST', 'GET'])

    def test_recovery_without_readback_reports_no_request_or_response(self):
        p = self.payload(); self.prepare([p]); self.service.lose_response = True; self.execute(p)
        out = self.execute(p, reconcile=True)
        self.assertFalse(out.evidence.request_attempted or out.evidence.response_observed)
        self.assertIsNone(out.evidence.status_code)
        self.assertIsNone(getattr(out.evidence, 'response_body_complete', None))
        self.assertEqual(getattr(out.evidence, 'response_parse_status', None), 'NOT_ATTEMPTED')
        self.assertEqual(len(self.service.requests), 1)

    def test_recovery_git_protocol_parse_failure_keeps_http_evidence(self):
        p = self.setup_git(); self.prepare([p]); self.git_service.lose_response = True; self.execute(p)
        body = b'not pkt-line data'
        with patch.object(self.git_service, 'request', return_value=(200,
                (('content-type', 'application/x-git-receive-pack-advertisement'),), body)):
            out = self.execute(p, reconcile=True)
        self.assertTrue(out.evidence.response_observed and out.evidence.request_attempted)
        self.assertEqual(out.evidence.status_code, 200)
        self.assertIs(getattr(out.evidence, 'response_body_complete', None), True)
        self.assertEqual(out.evidence.response_digest, hashlib.sha256(body).hexdigest())
        self.assertEqual(getattr(out.evidence, 'response_parse_status', None), 'PARSE_FAILED')
        self.assertEqual(out.evidence.reconciliation, 'STILL_UNKNOWN')
        self.assertEqual(self.execute(p).receipt.policy_reason, 'UNKNOWN_OUTCOME_PENDING')
        self.assertEqual(self.git_service.mutations, 1)

    def test_pr_merge_and_other_actions_not_bound(self):
        p = replace(self.payload(), action_class=self.r.ActionClass.PR_MERGE)
        self.prepare([p]); self.assertEqual(self.execute(p).receipt.policy_reason, 'NOT_BOUND')
        self.assertEqual(self.service.requests, [])

    def test_secret_and_raw_content_not_in_evidence_or_chain(self):
        p = self.payload(); self.prepare([p]); self.service.lose_response = True
        out = self.execute(p)
        artifacts = repr(p) + repr(out) + repr(out.evidence) + repr(out.receipt) + repr(out.events)
        p = self.setup_pr(); self.prepare([p]); self.provider.lose_response = True
        out = self.execute(p)
        artifacts += repr(p) + repr(out) + repr(out.evidence) + repr(out.receipt) + repr(out.events)
        p = self.setup_git(); self.prepare([p]); self.git_service.lose_response = True
        out = self.execute(p)
        artifacts += repr(p) + repr(out) + repr(out.evidence) + repr(out.receipt) + repr(out.events)
        artifacts += repr(self.m.HTTPSRemoteTransport(credential_headers=(('Authorization', 'SYNTHETIC_SECRET_TOKEN'),)))
        artifacts += json.dumps([asdict(v) for v in self.chain.records()])
        self.assertNotIn('SYNTHETIC_SECRET_TOKEN', artifacts)
        self.assertNotIn('REQUEST_MARKER', artifacts)
        self.assertNotIn('RESPONSE_MARKER', artifacts)
        self.assertNotIn('PR_BODY_MARKER', artifacts)
        self.assertNotIn('TOKEN_USAGE', artifacts)

    def test_import_has_no_operational_effect_or_auto_registration(self):
        with patch('subprocess.Popen', side_effect=AssertionError('subprocess')), \
                patch('socket.socket', side_effect=AssertionError('socket')), \
                patch('threading.Thread.start', side_effect=AssertionError('thread')):
            importlib.reload(self.m)
        broker = self.r.CapabilityBroker()
        for name in ('network.request', 'git.push', 'github.pr.create'):
            self.assertFalse(broker.has(name))

    def test_https_header_budget_applies_to_chunk_trailers(self):
        body = b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1\r\nx\r\n0\r\n'
        body += (b'X-Trailer: ' + b'x' * 1000 + b'\r\n') * 70 + b'\r\n'
        class Socket:
            def makefile(self, mode):
                return io.BytesIO(body)
        response = self.m._Response(Socket()); response.begin()
        with self.assertRaises(ValueError):
            response.read()

    def test_mutation_requires_stable_request_identity(self):
        with self.assertRaises(ValueError):
            replace(self.payload(), request_identity=None)

    def test_mixed_rse_entrypoints_reserve_attempt_atomically(self):
        p = self.payload(); a = self.action(p)
        ready, release = threading.Event(), threading.Event()
        original_history = self.journal.history
        once = [False]
        def history(ident):
            result = original_history(ident)
            if threading.current_thread().name.startswith('scoped') and not once[0]:
                once[0] = True; ready.set(); release.wait(3)
            return result
        effects = []
        rse = self.r
        class Adapter:
            def execute(self, action):
                effects.append(action.action_id)
                return rse.ExecutionResult(rse.ExecutionState.KNOWN_SUCCESS, ('result',))
        broker = self.r.CapabilityBroker(); broker.register('network.request', Adapter())
        policy = self.r.Policy('core', self.r.PolicyLevel.CORE, frozenset({a.action_class}),
            network_mode=self.r.NetworkMode.ALLOWLIST, network_allowlist=('https://api.example.invalid',),
            allowed_egress_classes=frozenset({a.data_classification}), allowed_capabilities=frozenset({a.capability}))
        auth = self.r.Authorization('auth', 'task', frozenset({a.action_class}), (a.target,), frozenset({a.capability}), 100)
        args = (a, (policy,), auth, broker, self.journal, 1)
        with patch.object(self.journal, 'history', side_effect=history), \
                ThreadPoolExecutor(max_workers=1, thread_name_prefix='scoped') as scoped, ThreadPoolExecutor(max_workers=1) as legacy:
            first = scoped.submit(self.r.evaluate_and_execute, *args, action_scoped=True)
            self.assertTrue(ready.wait(2))
            second = legacy.submit(self.r.evaluate_and_execute, *args)
            try:
                # Legacy execution cannot cross the half-finished prior check.
                threading.Event().wait(0.1)
                self.assertEqual(effects, [])
            finally:
                release.set()
            first.result(timeout=3); second.result(timeout=3)
        self.assertEqual(effects, ['a'])

    def test_response_observation_survives_parse_failure(self):
        p = self.setup_pr(); self.prepare([p])
        original = self.provider.request
        def malformed(*args, **kwargs):
            original(*args, **kwargs)
            return 201, (), b'not json'
        with patch.object(self.provider, 'request', side_effect=malformed):
            out = self.execute(p)
        self.assertEqual(out.receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertTrue(out.evidence.response_observed)
        self.assertEqual(out.evidence.status_code, 201)
        self.assertIs(out.evidence.response_body_complete, True)
        self.assertEqual(out.evidence.response_parse_status, 'PARSE_FAILED')
        self.assertEqual(out.evidence.response_digest, hashlib.sha256(b'not json').hexdigest())

    def test_legacy_reconcile_waits_for_scoped_mutation(self):
        p = self.payload(); self.prepare([p]); self.service.lose_response = True
        self.service.entered = threading.Event(); self.service.release = threading.Event()
        readbacks = []
        def inspect(action):
            readbacks.append(len(self.service.resources))
            return self.r.ReconciliationOutcome.STILL_UNKNOWN
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.execute, p); self.assertTrue(self.service.entered.wait(2))
            other = pool.submit(self.r.reconcile, self.binding._bound(self.action(p), p), self.journal, inspect)
            try:
                threading.Event().wait(0.1)
                self.assertEqual(readbacks, [])
            finally:
                self.service.release.set()
            self.assertEqual(first.result().receipt.execution_state, 'UNKNOWN_OUTCOME')
            other.result(timeout=2)
        self.assertEqual(readbacks, [1])

    def test_nested_legacy_transaction_fails_closed_without_deadlock(self):
        p = self.payload(); self.prepare([p]); self.service.lose_response = True
        self.service.entered = threading.Event(); self.service.release = threading.Event()
        readbacks = []
        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.execute, p); self.assertTrue(self.service.entered.wait(2))
            try:
                with self.journal.transaction():
                    out = self.r.reconcile(self.binding._bound(self.action(p), p), self.journal, lambda _: readbacks.append(1))
                self.assertEqual(out.policy_reason, 'JOURNAL_OR_BOUNDARY_FAILURE')
                self.assertEqual(readbacks, [])
            finally:
                self.service.release.set()
            self.assertEqual(first.result(timeout=2).receipt.execution_state, 'UNKNOWN_OUTCOME')

    def test_legacy_action_lock_reservation_has_no_check_acquire_gap(self):
        looked_up_before_legacy = self.journal.action_transaction('a')
        acquired = threading.Event()
        def contender():
            with looked_up_before_legacy:
                acquired.set()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.journal.transaction():
                reserved = self.journal.action_transaction('a')
                future = pool.submit(contender)
                try:
                    self.assertFalse(acquired.wait(0.1))
                finally:
                    with reserved:
                        pass
            future.result(timeout=2)
        self.assertTrue(acquired.is_set())

    def test_scoped_reconcile_waits_for_legacy_mutation(self):
        p = self.payload(); self.prepare([p]); self.service.lose_response = True
        self.service.entered = threading.Event(); self.service.release = threading.Event()
        a = self.action(p); bound = self.binding._bound(a, p)
        context = self.c.TraceContext('trace', 'install', 'project', 'task', 'run', a.action_id, None, 'trusted', None, 'remote')
        broker = self.r.CapabilityBroker(); broker.register('network.request', self.m._Invocation(self.adapter, p, context, 1))
        policy = self.r.Policy('core', self.r.PolicyLevel.CORE, frozenset({a.action_class}),
            network_mode=self.r.NetworkMode.ALLOWLIST, network_allowlist=('https://api.example.invalid',),
            allowed_egress_classes=frozenset({a.data_classification}), allowed_capabilities=frozenset({a.capability}))
        auth = self.r.Authorization('auth', 'task', frozenset({a.action_class}), (a.target,), frozenset({a.capability}), 100)
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.r.evaluate_and_execute, bound, (policy,), auth, broker, self.journal, 1)
            self.assertTrue(self.service.entered.wait(2))
            other = pool.submit(self.execute, p, reconcile=True)
            try:
                threading.Event().wait(0.1)
                self.assertFalse(other.done())
            finally:
                self.service.release.set()
            self.assertEqual(first.result().execution_state, 'UNKNOWN_OUTCOME')
            self.assertEqual(other.result(timeout=2).receipt.execution_state, 'UNKNOWN_OUTCOME')

    def test_local_capture_default_stdin_is_eof_and_launch_failure_uncertain(self):
        p = self.setup_git(); adapter = self.broker.get('git.push').local
        code, result, _, truncated, expired = adapter._call(('hash-object', '--stdin'))
        self.assertEqual((code, result, truncated, expired), (0, b'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391\n', (False, False), False))
        with patch.object(self.m.local, '_capture_started', side_effect=RuntimeError('capture lost')):
            with self.assertRaises(self.m.local._LaunchUncertain):
                adapter._call(('hash-object', '--stdin'))
        self.assertEqual(self.git_service.requests, [])

    def test_http_trickled_headers_respect_total_deadline(self):
        class Socket:
            def makefile(self, mode): return io.BytesIO(b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n')
            def settimeout(self, value): pass
        response = self.m._Response(Socket(), deadline=2)
        with patch.object(self.m.time, 'monotonic', side_effect=[1, 1.5, 2.1]):
            with self.assertRaises(ValueError):
                response.begin()

    def test_https_request_header_budget_includes_host_credentials(self):
        transport = self.m.HTTPSRemoteTransport(credential_headers=(('Authorization', 'x' * 65000),))
        created = []
        class Connection:
            def __init__(self, *args, **kwargs): created.append(1)
            def request(self, *args, **kwargs): raise AssertionError('no request')
            def close(self): pass
        with patch.object(self.m.http.client, 'HTTPSConnection', Connection), self.assertRaises(ValueError):
            transport.request('POST', 'https://api.example.invalid/resource', (('accept', 'x' * 1000),), b'x',
                timeout=30, response_limit=4096)
        self.assertEqual(created, [])

    def test_pr_plausible_duplicate_with_altered_fields_stays_unknown(self):
        p = self.setup_pr(); self.prepare([p]); self.provider.lose_response = True; self.execute(p)
        record = self.provider.resources[0]
        self.provider.resources.append(dict(record, id=99, number=43, title='subsequently edited'))
        self.assertEqual(self.execute(p, reconcile=True).evidence.reconciliation, 'STILL_UNKNOWN')

    def test_git_remote_old_value_rechecked_after_pack(self):
        p = self.setup_git(); self.prepare([p])
        original = self.broker.get('git.push').local._call
        def call(args, **kw):
            result = original(args, **kw)
            if args[0] == 'pack-objects':
                self.git_service.oid = '3' * 40
            return result
        with patch.object(self.broker.get('git.push').local, '_call', side_effect=call):
            out = self.execute(p)
        self.assertEqual(out.evidence.reason, 'REMOTE_REF_CHANGED')
        self.assertEqual(self.git_service.mutations, 0)

    def test_reconcile_rejects_adapter_substitution(self):
        p = self.payload(); self.prepare([p]); self.service.lose_response = True; self.execute(p)
        class Other:
            calls = 0
            def execute(self, action): raise AssertionError('not allowed')
            def readback(self, action, payload):
                self.calls += 1
                return 'RECONCILED_SUCCESS', '0' * 64
        replacement = Other(); broker = self.r.CapabilityBroker(); broker.register('network.request', replacement)
        self.binding.broker = broker
        out = self.execute(p, reconcile=True)
        self.assertEqual(out.receipt.policy_reason, 'NOT_BOUND')
        self.assertEqual(replacement.calls, 0)

    def test_real_http_response_head_and_empty_success(self):
        class Socket:
            def __init__(self, body): self.body = body
            def makefile(self, mode): return io.BytesIO(self.body)
            def settimeout(self, value): pass
        for method, status in (('HEAD', 200), ('GET', 204)):
            p = replace(self.payload(method), method=method, body=b''); self.prepare([p])
            class Connection:
                def __init__(self, *args, **kwargs): pass
                def request(self, *args, **kwargs): pass
                def getresponse(inner):
                    response = inner.response_class(Socket(('HTTP/1.1 %s OK\r\nContent-Length: 0\r\n\r\n' % status).encode()), method=method)
                    response.begin(); return response
                def close(self): pass
            self.adapter.transport = self.m.HTTPSRemoteTransport()
            with patch.object(self.m.http.client, 'HTTPSConnection', Connection):
                out = self.execute(p)
            self.assertEqual(out.receipt.execution_state, 'KNOWN_SUCCESS')

    def test_https_incomplete_content_length_is_unknown(self):
        p = self.payload(); self.prepare([p])
        class Connection:
            response_class = None
            def __init__(self, *args, **kwargs): pass
            def request(self, *args, **kwargs): pass
            def getresponse(self):
                return IncompleteResponse()
            def close(self): pass
        class IncompleteResponse:
            status = 200
            length = 5
            fp = None
            def getheader(self, key): return None
            def getheaders(self): return []
            def read1(self, size): return b''
        self.adapter.transport = self.m.HTTPSRemoteTransport()
        with patch.object(self.m.http.client, 'HTTPSConnection', Connection):
            out = self.execute(p)
        self.assertEqual(out.receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertTrue(out.evidence.response_observed)
        self.assertEqual(out.evidence.status_code, 200)
        self.assertIs(out.evidence.response_body_complete, False)
        self.assertIsNone(out.evidence.response_digest)
        self.assertEqual(out.evidence.response_parse_status, 'NOT_ATTEMPTED')


class ResponseReadbackFakeTests(unittest.TestCase):
    """Reuse synthetic journal fixtures only, never native PRBoundedTests."""
    setUpClass = classmethod(RemoteTests.setUpClass.__func__)
    tearDownClass = classmethod(RemoteTests.tearDownClass.__func__)
    setUp = RemoteTests.setUp
    setup_pr = RemoteTests.setup_pr
    action = RemoteTests.action
    prepare = RemoteTests.prepare
    execute = RemoteTests.execute
    recovery_pr = RemoteTests.recovery_pr
    assert_recovery_pending = RemoteTests.assert_recovery_pending

    def test_readback_link_preserves_unknown(self):
        p=self.recovery_pr()
        for case_number,(key,value) in enumerate((('Link','next'),('lInK','next'),('Link','')),1):
            with self.subTest(key=key,value=value):
                self.provider.readback_response=(200,((key,value),),json.dumps(self.provider.resources).encode())
                n=len(self.provider.requests);out=self.execute(p,reconcile=True)
                self.assert_recovery_pending(p,out)
                self.assertEqual(len(self.provider.requests),n+1)
                self.assertEqual(self.provider.requests[-1][0],'GET')
                print('READBACK_BRANCH',json.dumps(dict(case_id=self.id()+'/'+str(case_number).zfill(3)+':Link',case='Link',header=key,classification=out.evidence.reconciliation,methods=[r[0] for r in self.provider.requests])))

    def test_readback_original_marker_only(self):
        p=self.recovery_pr();record=self.provider.resources[0];original=record['body']
        altered=replace(p,request_identity='new-request')
        n=len(self.provider.requests)
        self.assertEqual(self.execute(altered,reconcile=True).receipt.policy_reason,'PAYLOAD_DIGEST_MISMATCH')
        self.assertEqual(len(self.provider.requests),n)
        record['body']=original.replace('request-1','new-request')
        self.assert_recovery_pending(p,self.execute(p,reconcile=True))
        record['body']=original
        out=self.execute(p,reconcile=True)
        self.assertEqual(out.evidence.reconciliation,'RECONCILED_SUCCESS')
        self.assertEqual([r[0] for r in self.provider.requests],['POST','GET','GET'])
        print('READBACK_BRANCH',json.dumps(dict(case_id=self.id()+'/001:original-marker',case='original-marker',methods=[r[0] for r in self.provider.requests],classification=out.evidence.reconciliation)))


class BareGitService(Service):
    """Test-only byte transport to a temporary bare server, no production escape."""
    def __init__(self, remote, drift_oid=None):
        super().__init__(); self.remote = remote; self.drift_oid = drift_oid; self.mutations = 0

    def request(self, method, url, headers, body, **limits):
        env = {'PATH': '/usr/bin:/bin', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null'}
        command = [shutil.which('git'), '-c', 'core.hooksPath=/dev/null', 'receive-pack', '--stateless-rpc']
        if method == 'GET':
            raw = subprocess.check_output(command + ['--advertise-refs', str(self.remote)], env=env)
            return 200, (('content-type', 'application/x-git-receive-pack-advertisement'),), GitService.pkt(b'# service=git-receive-pack\n') + b'0000' + raw
        if self.drift_oid:
            subprocess.run([shutil.which('git'), '--git-dir', str(self.remote), 'update-ref', 'refs/heads/main', self.drift_oid],
                check=True, env=env)
        self.mutations += 1
        result = subprocess.run(command + [str(self.remote)], input=body, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        return 200, (), result.stdout


class GitService(Service):
    def __init__(self, module, oid):
        super().__init__(); self.m = module; self.oid = oid; self.mutations = 0

    @staticmethod
    def pkt(data):
        return ('%04x' % (len(data) + 4)).encode() + data

    def request(self, method, url, headers, body, **limits):
        self.requests.append((method, url, headers, body))
        if method == 'GET':
            response = self.pkt(b'# service=git-receive-pack\n') + b'0000'
            response += self.pkt((self.oid + ' refs/heads/main\0report-status\n').encode()) + b'0000'
            return 200, (('content-type', 'application/x-git-receive-pack-advertisement'),), response
        command_end = int(body[:4], 16)
        command = body[4:command_end].split(b'\0')[0].decode().split()
        old, new, ref = command
        assert old == self.oid and ref == 'refs/heads/main'
        assert body[command_end:command_end + 8] == b'0000PACK'
        self.mutations += 1; self.oid = new
        if self.lose_response:
            raise TimeoutError('lost')
        return 200, (), self.pkt(b'unpack ok\n') + self.pkt(b'ok refs/heads/main\n') + b'0000'


class PRService(Service):
    def request(self, method, url, headers, body, **limits):
        self.requests.append((method, url, headers, body))
        if method == 'POST':
            values = json.loads(body)
            record = dict(values, number=42, id=84,
                head={'ref': values['head'], 'label': 'team:' + values['head'], 'repo': {'full_name': 'team/repo'}},
                base={'ref': values['base'], 'repo': {'full_name': 'team/repo'}})
            self.resources.append(record)
            if self.lose_response:
                raise TimeoutError('SYNTHETIC_SECRET_TOKEN')
            return 201, (), json.dumps(record).encode()
        if getattr(self, 'readback_error', None):
            raise self.readback_error
        return getattr(self, 'readback_response', (200, (), json.dumps(self.resources).encode()))


def response_connection(raw):
    """Only connection I/O is replaced; production HTTPResponse parses bytes."""
    class Socket:
        def makefile(self, mode): return io.BytesIO(raw)
        def settimeout(self, value): pass
    class Connection:
        def __init__(self, *args, **kwargs): pass
        def request(self, method, *args, **kwargs): self.method = method
        def getresponse(self):
            response = self.response_class(Socket(), method=self.method)
            response.begin()
            return response
        def close(self): pass
    return Connection


class SelectedHandleOnlyCleanupTests(DirectWorkerFakeTests):
    """Original fake handle only; numeric APIs must never be called by cleanup."""
    def handle_state(self, *, publish=True, selected=True):
        self.direct_contract();self.events.clear();self.clock=0
        self.p.returncode=None;self.waits=0;self.escalate=False
        def terminate():
            self.assertIsNone(self.p.returncode)
            self.events.append(('terminate',))
        def kill():
            self.assertIsNone(self.p.returncode)
            self.events.append(('kill',))
        def wait(timeout):
            self.waits+=1;self.events.append(('wait',timeout))
            self.assertGreater(timeout,0);self.assertLessEqual(timeout,self.budget.end-self.clock)
            if self.escalate and self.waits==1:
                self.clock+=timeout
                raise subprocess.TimeoutExpired('synthetic',timeout)
            self.p.returncode=-9 if ('kill',) in self.events else -15
            return self.p.returncode
        self.p.terminate=terminate;self.p.kill=kill;self.p.wait=wait
        state=self.m._PRLaunch(request_budget=self.budget,selected_handle_only=selected)
        if publish:
            state.publish(self.p);self.assertIs(state.claim_parent(),self.p);state.launcher_done.set()
        return state

    def no_numeric(self):
        def forbidden(*args):raise AssertionError('NUMERIC_OPERATION_FORBIDDEN')
        self.os.kill=self.os.killpg=self.os.getpgid=self.os.getsid=forbidden

    def assert_unknown(self,state):
        self.assertFalse(state.cleaned);self.assertEqual(state.phase,'CLEANUP_UNKNOWN')
        self.assertEqual(state.record.group,'UNKNOWN');self.assertTrue(state.cleanup_done.is_set())
        self.assertIsNone(state._direct_finalization);self.assertIsNone(state._direct_abort)
        self.assertIsNone(state._unsealed_exit);self.assertIsNone(state._rejected_exit)

    def test_term_wait_uses_original_handle_without_numeric_calls(self):
        state=self.handle_state();self.no_numeric();self.cleanup(state)
        self.assertEqual([e[0] for e in self.events],['terminate','wait','close','close','close'])
        self.assertIs(state.process,self.p);self.assertIs(state._original_request_budget,self.budget)
        self.assertTrue(state.record.reaped);self.assertTrue(state.record.pipes_closed)
        self.assert_unknown(state)

    def test_timeout_escalates_once_on_same_handle_with_original_deadline(self):
        state=self.handle_state();self.escalate=True;self.no_numeric();self.cleanup(state)
        self.assertEqual([e[0] for e in self.events],['terminate','wait','kill','wait','close','close','close'])
        self.assertEqual([e[1] for e in self.events if e[0]=='wait'],[.25,9.75])
        self.assertEqual((self.budget.started,self.budget.operation_end,self.budget.end),(0,8,10))
        self.assert_unknown(state)

    def test_cached_exit_never_signals_or_waits_again(self):
        state=self.handle_state();self.p.returncode=0;self.no_numeric();self.cleanup(state)
        self.assertEqual([e[0] for e in self.events],['close']*3);self.assert_unknown(state)

    def test_expired_and_mismatched_budget_fail_closed(self):
        state=self.handle_state();self.clock=10;self.no_numeric();self.cleanup(state)
        self.assertEqual([e[0] for e in self.events],['close']*3);self.assert_unknown(state)
        # New synthetic launch, not a retry of the claimed state.
        self.p.returncode=None;self.events.clear();self.clock=0
        other=self.m._PRLaunch(request_budget=self.budget,selected_handle_only=True)
        other.process=self.p;other.owner='parent';other.phase='PARENT_CLAIMED'
        other._request_budget=replace(self.budget)
        self.cleanup(other)
        self.assertEqual(self.events,[]);self.assertEqual(other.record.stage,'INVALID');self.assert_unknown(other)

    def test_sole_claimant_blocks_second_cleanup(self):
        state=self.handle_state();self.no_numeric();self.cleanup(state);before=list(self.events)
        token=state.claimant;self.cleanup(state)
        self.assertEqual(self.events,before);self.assertIs(state.claimant,token);self.assert_unknown(state)

    def test_late_launcher_uses_original_deadline(self):
        state=self.handle_state(publish=False);self.assertIsNone(state.claim_parent());self.clock=10
        with patch.object(self.m,'_pr_spawn_worker',return_value=self.p):self.m._pr_launch(state)
        self.assertEqual([e[0] for e in self.events],['close']*3)
        self.assertEqual(state.owner,'launcher');self.assertTrue(state.launcher_done.is_set())
        self.assert_unknown(state)

    def test_first_error_survives_pipe_error_without_escalation(self):
        state=self.handle_state();self.no_numeric()
        def denied():self.events.append(('terminate',));raise PermissionError(1,'synthetic')
        def broken():self.events.append(('close','stdin'));raise OSError(9,'synthetic')
        self.p.terminate=denied;self.p.stdin.close=broken;self.cleanup(state)
        self.assertEqual((state.record.stage,state.record.errno),('TERM',1))
        self.assertEqual([e[0] for e in self.events],['terminate','close','close','close'])
        self.assertFalse(state.record.pipes_closed);self.assert_unknown(state)

    def test_interruption_preserved_after_pipe_closure(self):
        state=self.handle_state();self.no_numeric();original=KeyboardInterrupt('synthetic')
        def interrupted():raise original
        self.p.terminate=interrupted
        with self.assertRaises(KeyboardInterrupt) as caught:self.cleanup(state)
        self.assertIs(caught.exception,original)
        self.assertEqual([e[0] for e in self.events],['close']*3);self.assert_unknown(state)

    def test_default_path_not_selected(self):
        state=self.handle_state(selected=False)
        with patch.object(self.m,'_pr_cleanup_selected_handle',side_effect=AssertionError('SELECTED_DEFAULT')):
            self.cleanup(state)
        self.assertFalse(state._selected_handle_only)
        self.assertTrue(any(e[0]=='signal' for e in self.events));self.assertFalse(state.cleaned)

    def test_missing_numeric_identity_does_not_trigger_probe(self):
        state=self.handle_state();state.identity=None;self.no_numeric();self.cleanup(state)
        self.assertEqual([e[0] for e in self.events],['terminate','wait','close','close','close'])
        self.assertIsNone(state.record.identity);self.assert_unknown(state)


class SelectedDirectContractTests(DirectWorkerFakeTests):
    def test_selected_private_contract_exists(self):
        self.assertTrue(callable(getattr(self.m.PRCreateBoundedHTTPS,'_selected_snapshot',None)),
            'selected direct private acceptance missing')

    def selected_fixture(self):
        self.direct_contract();self.m.time.time=lambda:1
        m=dict(repository='Q20396/20396-acceptance-sandbox',repository_id=123,
            head='h6-synthetic-once',base='main',head_oid='a'*40,base_oid='b'*40)
        limits=self.m._PRQualificationLimits(m,mode='create',expires_at=100,issued_at=1)
        payload=SimpleNamespace(repository=m['repository'],head=m['head'],base=m['base'],
            target='https://api.github.com:443/repos/Q20396/20396-acceptance-sandbox/pulls',digest=lambda:'a'*64)
        transport=self.m.PRCreateBoundedHTTPS(qualification_limits=limits,selected_direct=True)
        self.p.returncode=None
        state=self.m._PRLaunch(request_budget=self.budget);state.publish(self.p)
        state.claim_parent();state.launcher_done.set();state.note_protocol_complete(self.budget)
        self.cleanup(state)
        return transport,payload,state

    def test_selected_bound_terminal_keeps_group_and_history(self):
        transport,payload,state=self.selected_fixture()
        entry=transport._selected_snapshot(state,self.budget,self.p,payload)
        transport._selected_history.append(entry);transport._unresolved=state
        self.assertTrue(transport._selected_prior(state,payload))
        self.assertFalse(state.cleaned);self.assertEqual(state.record.group,'UNKNOWN')
        self.assertEqual(state.phase,'CLEANUP_UNKNOWN')
        self.assertEqual(transport._selected_summary()['direct_completion'],'SELECTED_DIRECT_WORKER_COMPLETE')
        self.clock=20  # Historical terminal facts do not reset or extend old authority.
        self.assertTrue(transport._selected_prior(state,payload))
        self.assertEqual(self.budget.end,10)

    def test_selected_wrong_identity_budget_or_terminal_rejected(self):
        transport,payload,state=self.selected_fixture()
        other=replace(self.budget)
        with self.assertRaises(ValueError):transport._selected_snapshot(state,other,self.p,payload)
        state._protocol_budget=other
        with self.assertRaises(ValueError):transport._selected_snapshot(state,self.budget,self.p,payload)
        state._protocol_budget=self.budget;state.launcher_done.clear()
        with self.assertRaises(ValueError):transport._selected_snapshot(state,self.budget,self.p,payload)
        state.launcher_done.set();state.cleanup_done.clear()
        with self.assertRaises(ValueError):transport._selected_snapshot(state,self.budget,self.p,payload)
        state.cleanup_done.set();state.claimant=None
        with self.assertRaises(ValueError):transport._selected_snapshot(state,self.budget,self.p,payload)

    def test_selected_expired_denied_and_history_overflow_failclosed(self):
        transport,payload,state=self.selected_fixture();self.clock=10
        with self.assertRaises(ValueError):transport._selected_snapshot(state,self.budget,self.p,payload)
        self.clock=0
        with patch.object(self.m.rse,'evaluate_policy',return_value=SimpleNamespace(disposition='DENY')):
            with self.assertRaises(ValueError):transport._selected_snapshot(state,self.budget,self.p,payload)
        entry=transport._selected_snapshot(state,self.budget,self.p,payload)
        transport._selected_history=[entry]*9
        with self.assertRaises(ValueError):transport._selected_snapshot(state,self.budget,self.p,payload)

    def test_selected_is_default_off_and_not_diagnostic_authority(self):
        transport,payload,state=self.selected_fixture()
        default=self.m.PRCreateBoundedHTTPS();default._unresolved=state
        self.assertEqual(default.direct_worker_completion,'DIRECT_WORKER_COMPLETION')
        with self.assertRaises(ValueError):default._selected_snapshot(state,self.budget,self.p,payload)
        with self.assertRaises(ValueError):self.m.PRCreateBoundedHTTPS(selected_direct=True)
        state._protocol_budget=None  # rejection/unsealed/abort cannot seal normal completion
        with self.assertRaises(ValueError):transport._selected_snapshot(state,self.budget,self.p,payload)

class QualificationMetadataTests(unittest.TestCase):
    def setUp(self):
        import remote_runtime_binding
        self.m=remote_runtime_binding

    def test_qualification_metadata_capability_exists(self):
        self.assertTrue(callable(getattr(self.m.PRCreateBoundedHTTPS,'qualification_get',None)),
            'bounded qualification GET missing')

    def test_parent_worker_route_exact_and_encoded_rejected(self):
        q=dict(repository='Q20396/20396-acceptance-sandbox',head='h6-synthetic-once',base='main',kind='head',number=None)
        good='https://api.github.com/repos/Q20396/20396-acceptance-sandbox/branches/h6-synthetic-once'
        self.m._pr_check_qualification_route('GET',good,b'',q)
        for url in (good.replace('Q20396','other'),good+'?x=1',good.replace('h6-synthetic-once','%68%36-synthetic-once'),
                    good.replace('https://api.github.com','https://evil.invalid'),good.replace('/branches/','/branches/%2e%2e/'),
                    good.replace('h6-synthetic-once','other')):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):self.m._pr_check_qualification_route('GET',url,b'',q)
        with self.assertRaises(ValueError):self.m._pr_check_qualification_route('POST',good,b'',q)
        with self.assertRaises(ValueError):self.m._pr_check_qualification_route('GET',good,b'body',q)
        with self.assertRaises(ValueError):self.m._pr_check_qualification_route('GET',good,b'',dict(q,extra=True))

    def test_phase_limits_do_not_reset_or_refund(self):
        limits=self.m._PRQualificationLimits(dict(repository='Q20396/20396-acceptance-sandbox',repository_id=123,
            head='h6-synthetic-once',base='main',head_oid='a'*40,base_oid='b'*40),mode='recover',expires_at=100,issued_at=1)
        with patch.object(self.m.time,'time',return_value=1):
            with self.assertRaises(ValueError):limits.charge('POST',65536)
            limits.charge('GET',65536);limits.charge('GET',65536)
            with self.assertRaises(ValueError):limits.charge('GET',65536)
        self.assertEqual(limits.gets,2);self.assertEqual(limits.posts,0)

    def test_qualification_redirect_expiry_and_bytes_rejected(self):
        limits=self.m._PRQualificationLimits(dict(repository='Q20396/20396-acceptance-sandbox',repository_id=123,
            head='h6-synthetic-once',base='main',head_oid='a'*40,base_oid='b'*40),mode='create',expires_at=100,issued_at=1)
        with patch.object(self.m.time,'time',return_value=1):
            for unused in range(4):limits.charge('GET',262144)
            with self.assertRaises(ValueError):limits.charge('GET',1)
            with self.assertRaises(ValueError):limits.observe(None,'GET',302,(('Location','https://evil.invalid'),),b'{}')
        with patch.object(self.m.time,'time',return_value=101):
            with self.assertRaises(ValueError):limits.charge('GET',1)

    def test_specific_number_requires_binding_and_strict_types(self):
        q=dict(repository='Q20396/20396-acceptance-sandbox',head='h6-synthetic-once',base='main',kind='pull',number=42)
        self.assertTrue(self.m._pr_qualification_url(q).endswith('/pulls/42'))
        for number in (None,True,0,-1,'42'):
            with self.assertRaises(ValueError):self.m._pr_qualification_url(dict(q,number=number))

    def test_canonical_payload_443_parent_admission(self):
        from types import SimpleNamespace
        root='https://api.github.com/repos/Q20396/20396-acceptance-sandbox'
        commitments=dict(repository='Q20396/20396-acceptance-sandbox',repository_id=123,
            head='h6-synthetic-once',base='main',head_oid='a'*40,base_oid='b'*40)
        limits=self.m._PRQualificationLimits(commitments,mode='create',expires_at=100,issued_at=1)
        transport=self.m.PRCreateBoundedHTTPS(qualification_limits=limits)
        payload=SimpleNamespace(target=self.m._url(root+'/pulls')[1],repository=commitments['repository'],
            head=commitments['head'],base=commitments['base'],timeout=30,response_limit=65536)
        self.assertEqual(payload.target,'https://api.github.com:443/repos/Q20396/20396-acceptance-sandbox/pulls')
        q=dict(repository=payload.repository,head=payload.head,base=payload.base,kind='repo',number=None)
        with patch.object(self.m.time,'time',return_value=1),patch.object(self.m.rse,'evaluate_policy',
                return_value=SimpleNamespace(disposition='ALLOW')):
            budget=self.m._PRBudget.create(object(),payload,(),None,1)
            transport._admit_request(budget,payload,'GET',self.m._pr_qualification_url(q),b'',30,65536,q)
            self.assertEqual(limits.gets,1);self.assertEqual(limits.posts,0)
            payload.target=payload.target.replace(':443',':444')
            with self.assertRaises(ValueError):
                transport._admit_request(budget,payload,'GET',self.m._pr_qualification_url(q),b'',30,65536,q)
            self.assertEqual(limits.gets,1)

    def test_worker_wire_route_resolves_same_canonical_origin_without_alternates(self):
        q=dict(repository='Q20396/20396-acceptance-sandbox',head='h6-synthetic-once',base='main',kind='head',number=None)
        url=self.m._pr_qualification_url(q)
        self.m._pr_check_qualification_route('GET',url,b'',q)
        self.assertEqual(self.m._url(url)[0],'https://api.github.com:443')
        for bad in (url.replace('api.github.com','api.github.com:444'),url.replace('api.github.com','api.github.com.evil.invalid'),
                    url.replace('/branches/','/branches/%2e%2e/'),url.replace('h6-synthetic-once','%68%36-synthetic-once')):
            with self.assertRaises(ValueError):self.m._pr_check_qualification_route('GET',bad,b'',q)

    def test_phase_deadline_constructs_original_frozen_budget_without_reset(self):
        from types import SimpleNamespace
        from dataclasses import FrozenInstanceError
        action=object();authorization=object();payload=SimpleNamespace(timeout=30)
        with patch.object(self.m.time,'monotonic',return_value=100):
            budget=self.m._PRBudget.create(action,payload,(),authorization,1,phase_deadline=107)
            original=self.m._PRBudget.create(action,payload,(),authorization,1)
        self.assertEqual((budget.started,budget.end,budget.operation_end),(100,107,107-self.m._PR_CLEANUP))
        self.assertEqual((original.started,original.end,original.operation_end),(100,130,130-self.m._PR_CLEANUP))
        self.assertIs(budget.action,action);self.assertIs(budget.authorization,authorization)
        with self.assertRaises(FrozenInstanceError):budget.end=110

    def test_phase_without_cleanup_reserve_rejected_before_io(self):
        from types import SimpleNamespace
        with patch.object(self.m.time,'monotonic',return_value=100):
            for end in (99,100,100+self.m._PR_CLEANUP,True,float('nan'),float('inf')):
                with self.subTest(deadline=end):
                    with self.assertRaises(ValueError):
                        self.m._PRBudget.create(object(),SimpleNamespace(timeout=30),(),None,1,phase_deadline=end)

    def test_metadata_execute_reconcile_keep_constructed_budget_identity(self):
        from test_remote_account_qualification import CompleteHostOfflineTests
        fixture=CompleteHostOfflineTests('test_unknown_original_recovery_real_binding_zero_post')
        fixture.setUp()
        try:
            core,m,state=fixture.fixture();state['lose']=True
            original=core.remote._PRBudget.create;created=[];admitted=[]
            def create(*args,**kwargs):
                value=original(*args,**kwargs);created.append((value,kwargs.get('phase_deadline')));return value
            admit=core.remote.PRCreateBoundedHTTPS._admit_request
            def observe(transport,budget,*args,**kwargs):
                before=(budget.started,budget.end,budget.operation_end)
                result=admit(transport,budget,*args,**kwargs)
                self.assertEqual((budget.started,budget.end,budget.operation_end),before)
                self.assertTrue(any(budget is item[0] for item in created));admitted.append(budget)
                return result
            with patch.object(core.remote._PRBudget,'create',side_effect=create),\
                 patch.object(core.remote.PRCreateBoundedHTTPS,'_admit_request',observe):
                first=fixture.h.run_live_host(m,mode='create',launch=True)
                self.assertEqual(first['execution_state'],'UNKNOWN_OUTCOME',first)
                second=fixture.h.run_live_host(m,mode='recover',launch=True)
                self.assertEqual(second['posts'],0)
            self.assertEqual(sum(method=='POST' for method,url in state['calls']),1)
            self.assertEqual(len(created),9)  # six metadata, execute, reconcile, bound object
            self.assertEqual(len(admitted),9)
            self.assertTrue(all(deadline is not None and budget.end<=deadline
                and budget.operation_end==budget.end-core.remote._PR_CLEANUP for budget,deadline in created))
        finally:fixture.doCleanups()

if __name__ == '__main__':
    unittest.main()
