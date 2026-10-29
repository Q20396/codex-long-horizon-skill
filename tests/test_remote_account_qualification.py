"""OFFLINE_SYNTHETIC H6 admission gap; no real provider access."""
import unittest
import json
import io
import os
import subprocess
import sys
import time
from dataclasses import replace
import tarfile
import tempfile
import importlib.util
from unittest.mock import patch
from pathlib import Path

import test_agent_runtime_integration as bridge_tests


class LiveEntryOfflineTests(unittest.TestCase):
    """No live credentials, network, worker or account mutation."""
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'scripts/remote_account_qualification.py'
        spec = importlib.util.spec_from_file_location('live_qualification', path)
        self.h = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.h)

    def test_live_entry_exists_and_default_does_not_read_credential(self):
        self.assertTrue(callable(getattr(self.h, 'qualify_live', None)), 'live entry missing')
        with patch.object(os, 'read', side_effect=AssertionError('credential read')):
            self.assertEqual(self.h.qualify_live(None, credential_fd=0), {'status':'NOT_STARTED'})

    def manifest(self):
        return dict(schema='20396.h6.pr-create.live.v1', api_origin='https://api.github.com',
            repository='Q20396/20396-acceptance-sandbox', repository_id=123,
            head='h6-synthetic-once', base='main', head_oid='a'*40, base_oid='b'*40,
            proposal_id='proposal', action_id='host-1', request_identity='request-1',
            payload_digest='c'*64, title='[SYNTHETIC H6] test', body='SYNTHETIC H6\nbody',
            marker='<!-- 20396-request:request-1 -->', draft=True, effect_scope='PR_CREATE',
            authorization_ref='auth', expires_at=100, post_budget=1, get_budget=10,
            byte_budget=65536, time_budget=30, storage_domain='/private/tmp/h6-fake-domain',
            storage_id='h6-live', credential_source='HOST_ANONYMOUS_PIPE_V1',
            credential_scope='https://api.github.com/repos/Q20396/20396-acceptance-sandbox')

    def witness(self, m):
        return dict(repository=m['repository'],repository_id=m['repository_id'],
            head=m['head'],base=m['base'],head_oid=m['head_oid'],base_oid=m['base_oid'],
            observed_at=1, expires_at=10, provenance='TRUSTED_HOST_PREFLIGHT_V1')

    def test_valid_live_manifest_still_blocked_without_host_channel(self):
        m=self.manifest()
        with patch.object(os, 'read', side_effect=AssertionError('credential read')):
            out=self.h.qualify_live(m,launch=True,credential_fd=0,preflight=self.witness(m),now=1)
        self.assertEqual(out['status'],'BLOCKED_CREDENTIAL_CHANNEL_UNCONFIRMED')
        self.assertEqual(out['posts'],0)
        self.assertEqual(out['gets'],0)
        self.assertEqual(out['provenance'],'LIVE_PR_CREATE_NOT_EXECUTED')

    def test_manifest_rejects_wrong_target_mode_types_and_budgets(self):
        m=self.manifest()
        changes=({'repository':'Q20396/codex-long-horizon-skill'}, {'api_origin':'https://api.example.invalid'},
            {'schema':'20396.h6.pr-create.v1'}, {'credential_source':'EXPLICIT_SYNTHETIC_MEMORY'},
            {'repository_id':True},{'post_budget':2},{'get_budget':11},{'time_budget':31},
            {'draft':False},{'head_oid':'a'*39},{'extra':True},{'expires_at':float('nan')})
        for change in changes:
            with self.subTest(change=tuple(change)):
                out=self.h.qualify_live(dict(m,**change),launch=True,preflight=self.witness(m),now=1)
                self.assertEqual(out['status'],'QUALIFICATION_REJECTED')
                self.assertEqual(out['posts'],0)

    def test_witness_missing_stale_or_changed_rejected(self):
        m=self.manifest(); w=self.witness(m)
        for bad in (None,dict(w,head_oid='f'*40),dict(w,repository_id=True),dict(w,expires_at=1),
                    dict(w,observed_at=2),dict(w,provenance='MODEL_ASSERTION'),dict(w,extra=1)):
            with self.subTest(witness=bad):
                self.assertEqual(self.h.qualify_live(m,launch=True,preflight=bad,now=1)['status'],
                    'QUALIFICATION_REJECTED')

    def test_launch_recover_flags_and_missing_now_rejected(self):
        m=self.manifest()
        for extra in ({'launch':1},{'launch':True,'recover':1},{'launch':True,'now':None}):
            kw=dict(launch=True,preflight=self.witness(m),now=1);kw.update(extra)
            self.assertEqual(self.h.qualify_live(m,**kw)['status'],'QUALIFICATION_REJECTED')

    def pipe(self, value):
        rd,wr=os.pipe();os.write(wr,value);os.close(wr)
        return rd

    def test_fake_pipe_credential_exact_and_fd_closed(self):
        fd=self.pipe(b'fake-only-token')
        self.assertEqual(self.h._read_live_credential(fd), (('Authorization','Bearer fake-only-token'),))
        with self.assertRaises(OSError):os.fstat(fd)

    def test_credential_rejects_malformed_and_closes_pipe(self):
        for value in (b'',b'fake\n',b'fake\r',b'a\x00b',b'a b',b'x'*8193,b'\xff'):
            fd=self.pipe(value)
            with self.subTest(size=len(value)):
                with self.assertRaises(ValueError):self.h._read_live_credential(fd)
                with self.assertRaises(OSError):os.fstat(fd)

    def test_regular_file_and_writable_pipe_rejected(self):
        with tempfile.TemporaryFile() as f:
            fd=os.dup(f.fileno())
            with self.assertRaises(ValueError):self.h._read_live_credential(fd)
            with self.assertRaises(OSError):os.fstat(fd)
        rd,wr=os.pipe()
        try:
            with self.assertRaises(ValueError):self.h._read_live_credential(wr)
            with self.assertRaises(OSError):os.fstat(wr)
        finally:os.close(rd)

    def test_unfinished_pipe_deadline_no_retry_or_leak(self):
        rd,wr=os.pipe()
        try:
            with patch.object(self.h.time,'monotonic',side_effect=(1,7)):
                with self.assertRaises(ValueError):self.h._read_live_credential(rd)
            with self.assertRaises(OSError):os.fstat(rd)
        finally:os.close(wr)

    def test_eof_after_deadline_rejected_and_fd_closed(self):
        fd=self.pipe(b'fake-only-token')
        # Start, first wait, EOF wait, final acceptance: expiry on EOF arrival.
        with patch.object(self.h.time,'monotonic',side_effect=(1,1,1,7)):
            with self.assertRaises(ValueError):self.h._read_live_credential(fd)
        with self.assertRaises(OSError):os.fstat(fd)

    def test_exact_production_transport_selected_with_no_spawn(self):
        # Reuse actual core classes; observe dispatch without performing I/O.
        bridge_tests.BridgeTests.setUpClass()
        try:
            remote=bridge_tests.BridgeTests.m.remote
            adapter=self.h._live_adapter(remote,(('Authorization','Bearer fake-only-token'),))
            self.assertIs(type(adapter),remote.PullRequestCreateAdapter)
            self.assertIs(type(adapter.transport),remote.PRCreateBoundedHTTPS)
            with self.assertRaisesRegex(ValueError,'PR_BINDING_BUDGET_REQUIRED'):
                adapter.transport.request('POST','https://api.github.com/repos/Q20396/20396-acceptance-sandbox/pulls',(),b'')
            fake_budget=object()
            with self.assertRaisesRegex(ValueError,'PR_BINDING_BUDGET_REQUIRED'):
                remote._pr_selected(adapter,object(),fake_budget)
            # Current unresolved channel is not caller-attestable, even with a valid FD.
            self.assertFalse(self.h._live_channel_ready())
        finally:bridge_tests.BridgeTests.tearDownClass()


class CompleteHostOfflineTests(LiveEntryOfflineTests):
    """Real Bridge/Binding/journal; only terminal and worker I/O replaced."""
    def test_enabled_host_entry_exists(self):
        self.assertTrue(callable(getattr(self.h,'run_live_host',None)), 'host execution entry missing')
        self.assertEqual(self.h.run_live_host(None,mode='create'), {'status':'NOT_STARTED'})

    def fixture(self):
        import importlib
        directory=Path(__file__).resolve().parents[1]/'.agents/skills/long-horizon-engineering/scripts'
        sys.path.insert(0,str(directory));self.addCleanup(lambda:sys.path.remove(str(directory)))
        core=importlib.import_module('agent_runtime_integration')
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        m=self.manifest();m['storage_domain']=str(Path(tmp.name).resolve());m['expires_at']=100
        p,_,_,_=self.h._host_prepared(core,m,1);m['payload_digest']=p.payload_digest
        state={'calls':[],'objects':[],'lose':False,'corrupt':False,'wrong_ref':False}
        def fake_io(transport,budget,payload,method,url,headers,body,*,timeout,response_limit,qualification=None):
            transport._admit_request(budget,payload,method,url,body,timeout,response_limit,qualification)
            state['calls'].append((method,url))
            if qualification and qualification['kind']=='repo':
                value=dict(id=m['repository_id'],full_name=m['repository'])
            elif qualification and qualification['kind'] in ('head','base'):
                side=qualification['kind'];value=dict(commit=dict(sha=('f'*40 if state['wrong_ref'] else m[side+'_oid'])))
            elif method=='POST':
                self.assertTrue((Path(m['storage_domain'])/'create-reserved.json').exists())
                self.assertIn(b'ATTEMPTED',(Path(m['storage_domain'])/'journal').read_bytes())
                v=json.loads(body);value=dict(v,id=84,number=42,
                    head=dict(ref=m['head'],label='Q20396:'+m['head'],repo=dict(full_name=m['repository'],id=m['repository_id']),sha=m['head_oid']),
                    base=dict(ref=m['base'],repo=dict(full_name=m['repository'],id=m['repository_id']),sha=m['base_oid']))
                state['objects'].append(value)
                if state['lose']:raise TimeoutError('FAKE_SECRET_MUST_NOT_LEAK')
            elif qualification and qualification['kind']=='pull':value=state['objects'][0]
            else:value=state['objects']
            if state['corrupt']:value={'bad':'shape'}
            data=json.dumps(value).encode();status=201 if method=='POST' else 200
            transport._observe_qualification(payload,method,status,(),data)
            return status,(),data
        self.addCleanup(patch.stopall)
        patch.object(core.remote.PRCreateBoundedHTTPS,'_request',fake_io).start()
        patch.object(self.h,'_capture_host',return_value=(('Authorization','Bearer FAKE_SECRET_MUST_NOT_LEAK'),)).start()
        patch.object(self.h.time,'time',return_value=1).start()
        return core,m,state

    def test_real_binding_create_and_phase_cannot_repeat(self):
        _,m,s=self.fixture()
        out=self.h.run_live_host(m,mode='create',launch=True)
        self.assertEqual(out['execution_state'],'KNOWN_SUCCESS',out)
        self.assertEqual(out['posts'],1);self.assertEqual(out['gets'],8)
        self.assertNotIn('FAKE_SECRET',json.dumps(out))
        before=list(s['calls']);again=self.h.run_live_host(m,mode='create',launch=True)
        self.assertEqual(again['status'],'LIVE_HOST_BLOCKED');self.assertEqual(s['calls'],before)

    def test_unknown_original_recovery_real_binding_zero_post(self):
        _,m,s=self.fixture();s['lose']=True
        first=self.h.run_live_host(m,mode='create',launch=True)
        self.assertEqual(first['execution_state'],'UNKNOWN_OUTCOME',first)
        s['lose']=False
        recovered=self.h.run_live_host(m,mode='recover',launch=True)
        self.assertEqual(recovered['reconciliation_state'],'RECONCILED_SUCCESS',recovered)
        self.assertEqual(recovered['posts'],0);self.assertEqual(recovered['gets'],2)
        self.assertEqual(sum(x[0]=='POST' for x in s['calls']),1)
        before=list(s['calls']);self.h.run_live_host(m,mode='recover',launch=True)
        self.assertEqual(s['calls'],before)

    def test_no_tty_and_changed_identity_zero_requests(self):
        _,m,s=self.fixture()
        with patch.object(self.h,'_capture_host',side_effect=ValueError('NO_TTY')):
            self.assertEqual(self.h.run_live_host(m,mode='create',launch=True)['status'],'LIVE_HOST_BLOCKED')
        self.assertEqual(s['calls'],[])
        self.h.run_live_host(m,mode='create',launch=True)
        before=list(s['calls']);changed=dict(m,request_identity='other',action_id='other',proposal_id='other')
        self.h.run_live_host(changed,mode='create',launch=True);self.h.run_live_host(changed,mode='recover',launch=True)
        self.assertEqual(s['calls'],before)

    def test_durable_reservation_failure_zero_network_and_no_refund(self):
        _,m,s=self.fixture()
        with patch.object(os,'fsync',side_effect=OSError('FAKE_SECRET')):
            out=self.h.run_live_host(m,mode='create',launch=True)
        self.assertEqual(out['status'],'LIVE_HOST_BLOCKED');self.assertEqual(s['calls'],[])
        self.assertTrue(any(Path(m['storage_domain']).glob('*.json')))
        self.h.run_live_host(m,mode='create',launch=True);self.assertEqual(s['calls'],[])

    def test_preflight_wrong_ref_zero_post(self):
        _,m,s=self.fixture();s['wrong_ref']=True
        out=self.h.run_live_host(m,mode='create',launch=True)
        self.assertEqual(out['status'],'LIVE_HOST_BLOCKED');self.assertEqual(sum(x[0]=='POST' for x in s['calls']),0)

    def test_budget_reservation_caps_and_legacy_fence(self):
        core,m,s=self.fixture()
        # Existing strict legacy fence is exercised through the actual Bridge.
        real=core.rse.DurableSecurityJournal.binding_classification
        def legacy(journal):
            real(journal);return ({'legacy':True,'historical_barrier':True},)
        with patch.object(core.rse.DurableSecurityJournal,'binding_classification',legacy):
            out=self.h.run_live_host(m,mode='create',launch=True)
        self.assertEqual(sum(x[0]=='POST' for x in s['calls']),0)
        self.assertNotEqual(out.get('execution_state'),'KNOWN_SUCCESS')

    def test_recovery_cannot_create_storage_or_reset_corruption(self):
        _,m,s=self.fixture();root=Path(m['storage_domain'])
        self.h.run_live_host(m,mode='recover',launch=True);self.assertEqual(s['calls'],[])
        self.h.run_live_host(m,mode='create',launch=True)
        session=root/'session.json';session.write_bytes(b'{}\n')
        before=list(s['calls']);self.h.run_live_host(m,mode='recover',launch=True)
        self.assertEqual(s['calls'],before);self.assertEqual(session.read_bytes(),b'{}\n')

    def test_phase_reservation_survives_abrupt_effect_boundary(self):
        core,m,s=self.fixture()
        with patch.object(core.AgentRuntimeBridge,'execute',side_effect=KeyboardInterrupt):
            self.h.run_live_host(m,mode='create',launch=True)
        before=list(s['calls'])
        self.assertTrue((Path(m['storage_domain'])/'create-reserved.json').exists())
        self.h.run_live_host(m,mode='create',launch=True)
        self.h.run_live_host(m,mode='recover',launch=True)
        self.assertEqual(s['calls'],before)  # Missing cleanup outcome is not permission.

    def test_short_write_does_not_repair_or_send(self):
        _,m,s=self.fixture();write=os.write
        def short(fd,data):return write(fd,data[:1])
        with patch.object(os,'write',short):self.h.run_live_host(m,mode='create',launch=True)
        self.assertEqual(s['calls'],[])
        self.h.run_live_host(m,mode='create',launch=True);self.assertEqual(s['calls'],[])

    def test_terminal_refusal_no_fallback_and_cli_not_started(self):
        import signal
        m=self.manifest()
        with patch.object(os,'open',side_effect=OSError('NO_TTY')):
            with self.assertRaises(Exception):self.h._capture_host(m,'create')
        with patch.object(sys,'argv',['remote_account_qualification.py']):
            self.assertEqual(self.h._live_host_cli(),{'status':'NOT_STARTED'})

    def test_terminal_getpass_fake_io_never_reads_stdin(self):
        import getpass,signal,termios
        m=self.manifest();identity=self.h.hashlib.sha256(self.h._host_encode(m)).hexdigest()
        with patch.object(os,'open',return_value=123),patch.object(os,'isatty',return_value=True),\
             patch.object(os,'dup',return_value=124),patch.object(os,'fdopen',return_value=io.StringIO()),\
             patch.object(os,'close'),patch.object(termios,'tcgetattr',return_value=[]),\
             patch.object(signal,'getsignal',return_value=signal.SIG_DFL),\
             patch.object(signal,'getitimer',return_value=(0.0,0.0)),patch.object(signal,'signal'),\
             patch.object(signal,'setitimer'),patch.object(getpass,'getpass',side_effect=['CREATE '+identity,'FAKE_ONLY']),\
             patch.object(sys,'stdin',None):
            self.assertEqual(self.h._capture_host(m,'create'),(('Authorization','Bearer FAKE_ONLY'),))

    def test_selected_outcome_v2_does_not_claim_group_cleanup(self):
        _,m,s=self.fixture();s['lose']=True
        first=self.h.run_live_host(m,mode='create',launch=True)
        record=json.loads((Path(m['storage_domain'])/'create-outcome.json').read_bytes())
        self.assertEqual(record['schema'],'20396.h6.outcome.v2')
        self.assertEqual(record['direct_completion'],'NO_WORKER_LAUNCHED')
        self.assertEqual(record['group_cleanup'],'UNKNOWN');self.assertEqual(record['descendants'],'UNKNOWN')
        s['lose']=False
        second=self.h.run_live_host(m,mode='recover',launch=True)
        self.assertEqual(second['posts'],0)
        self.assertEqual(sum(method=='POST' for method,url in s['calls']),1)

    def test_old_v1_outcome_cannot_be_promoted(self):
        _,m,s=self.fixture();s['lose']=True
        self.h.run_live_host(m,mode='create',launch=True)
        path=Path(m['storage_domain'])/'create-outcome.json'
        old=dict(schema='20396.h6.outcome.v1',session_sha256='a'*64,cleanup='CONFIRMED_OR_NO_WORKER')
        data=self.h._host_encode(old);path.write_bytes(data);before=list(s['calls'])
        self.h.run_live_host(m,mode='recover',launch=True)
        self.assertEqual(s['calls'],before);self.assertEqual(path.read_bytes(),data)


class HostSafeDiagnosticsTests(LiveEntryOfflineTests):
    """Synthetic inputs and injected I/O failures only; no real terminal or worker."""
    def capture_fixture(self, **faults):
        from contextlib import contextmanager, ExitStack
        import getpass,signal,termios
        @contextmanager
        def fixture():
            m=self.manifest();d=self.h._HostDiagnostics();events=[];handler=[]
            identity=self.h.hashlib.sha256(self.h._host_encode(m)).hexdigest()
            class Stream:
                def write(self,value):pass
                def close(self):
                    events.append('stream')
                    if faults.get('cleanup'):raise OSError(5,'SYNTHETIC_PRIVATE')
            def close(fd):
                events.append(fd)
                if faults.get('cleanup'):raise OSError(9,'SYNTHETIC_PRIVATE')
            def sig(sig,value):
                if value==signal.SIG_DFL:
                    events.append('signal')
                    if faults.get('cleanup'):raise RuntimeError('SYNTHETIC_PRIVATE')
                else:
                    handler.append(value)
                    if faults.get('handler'):raise RuntimeError('SYNTHETIC_PRIVATE')
            def timer(which,value):
                if value==0:
                    events.append('timer')
                    if faults.get('cleanup'):raise RuntimeError('SYNTHETIC_PRIVATE')
                elif faults.get('timer'):raise RuntimeError('SYNTHETIC_PRIVATE')
            reads=[]
            def get(prompt,stream):
                reads.append(1)
                if len(reads)==1:return 'CREATE '+identity
                if faults.get('timeout'):handler[0]()
                if 'primary' in faults:raise faults['primary']
                return faults.get('token','SYNTHETIC_ONLY')
            with ExitStack() as stack:
                for obj,name,kw in (
                    (os,'open',dict(return_value=123)),(os,'isatty',dict(return_value=True)),
                    (os,'dup',dict(side_effect=OSError(9,'SYNTHETIC_PRIVATE')) if faults.get('dup') else dict(return_value=124)),
                    (os,'fdopen',dict(side_effect=OSError(9,'SYNTHETIC_PRIVATE')) if faults.get('fdopen') else dict(return_value=Stream())),
                    (os,'close',dict(side_effect=close)),(termios,'tcgetattr',dict(return_value=[])),
                    (signal,'getsignal',dict(return_value=signal.SIG_DFL)),
                    (signal,'getitimer',dict(return_value=(0.,0.))),
                    (signal,'signal',dict(side_effect=sig)),(signal,'setitimer',dict(side_effect=timer)),
                    (getpass,'getpass',dict(side_effect=get))):stack.enter_context(patch.object(obj,name,**kw))
                yield m,d,events,reads
        return fixture()

    def test_capture_pat_read_preserves_primary_and_independent_cleanup(self):
        primary=ValueError('SYNTHETIC_PRIVATE')
        with self.capture_fixture(primary=primary,cleanup=True) as (m,d,events,reads):
            try:self.h._capture_host(m,'create',_diagnostics=d)
            except BaseException as caught:
                self.assertIs(caught,primary);self.assertIs(d.primary[0],primary)
                tb=sys.exc_info()[2]
                self.assertTrue(any(t is d.primary[1] for t in self.tracebacks(tb)))
            else:self.fail('primary missing')
        self.assertEqual(events,['timer','signal','stream',123])
        self.assertEqual(d.first['stage'],'PAT_READ');self.assertEqual(len(d.secondary),4)
        self.assertNotIn('SYNTHETIC_PRIVATE',json.dumps(d.report()))

    @staticmethod
    def tracebacks(tb):
        while tb is not None:
            yield tb;tb=tb.tb_next

    def test_capture_validation_and_timeout_are_distinct(self):
        for faults,stage in (({'token':''},'TOKEN_VALIDATE'),({'timeout':True},'INPUT_TIMEOUT')):
            with self.subTest(stage=stage),self.capture_fixture(**faults) as (m,d,events,reads):
                with self.assertRaises(ValueError):self.h._capture_host(m,'create',_diagnostics=d)
                self.assertEqual(d.first['stage'],stage)
                self.assertEqual(events,['timer','signal','stream',123])

    def test_capture_cleanup_only_failure_is_primary(self):
        with self.capture_fixture(cleanup=True) as (m,d,events,reads):
            try:self.h._capture_host(m,'create',_diagnostics=d)
            except RuntimeError as caught:self.assertIs(caught,d.primary[0])
            else:self.fail('cleanup failure missing')
            self.assertEqual(d.first['stage'],'CAPTURE_TIMER_CANCEL')
            self.assertEqual(len(d.secondary),3)
        self.assertEqual(events,['timer','signal','stream',123])
        # Installation/start failures are already inside the cleanup region.
        for fault,stage in (('handler','CAPTURE_HANDLER'),('timer','CAPTURE_TIMER')):
            with self.capture_fixture(**{fault:True}) as (m,d,events,reads):
                with self.assertRaises(RuntimeError):self.h._capture_host(m,'create',_diagnostics=d)
                self.assertEqual(d.first['stage'],stage)
                self.assertIn('signal',events);self.assertIn('stream',events);self.assertIn(123,events)

    def test_capture_dup_fdopen_failures_close_owned_fds(self):
        for fault,stage,expected in (('dup','TTY_DUP',[123]),('fdopen','TTY_STREAM',[124,123])):
            with self.capture_fixture(**{fault:True}) as (m,d,events,reads):
                with self.assertRaises(OSError):self.h._capture_host(m,'create',_diagnostics=d)
                self.assertEqual(d.first['stage'],stage);self.assertEqual(events,expected)
                self.assertEqual(reads,[])

    def test_diagnostic_failure_preserves_primary_object_and_traceback(self):
        primary=EOFError('SYNTHETIC_PRIVATE')
        with self.capture_fixture(primary=primary,cleanup=True) as (m,d,events,reads),\
                patch.object(self.h,'_host_safe_error',side_effect=RuntimeError('SYNTHETIC_PRIVATE')):
            try:self.h._capture_host(m,'create',_diagnostics=d)
            except BaseException as caught:
                self.assertIs(caught,primary)
                self.assertTrue(any(t is d.primary[1] for t in self.tracebacks(sys.exc_info()[2])))
            else:self.fail('primary missing')
        self.assertTrue(d.failed);self.assertEqual(events,['timer','signal','stream',123])
        self.assertEqual(d.first['error'],'OTHER')

    def test_exact_error_errno_and_stack_redaction_caps(self):
        class SecretNamedError(OSError):
            def __getattribute__(self,name):raise AssertionError('ATTRIBUTE_READ')
            def __str__(self):raise AssertionError('STRING_READ')
            def __repr__(self):raise AssertionError('REPR_READ')
        def recurse(n):
            if n:return recurse(n-1)
            raise SecretNamedError(13,'SYNTHETIC_PRIVATE')
        try:recurse(30)
        except BaseException as error:
            facts=self.h._host_safe_error(error,sys.exc_info()[2])
        self.assertEqual(facts['error'],'OTHER');self.assertIsNone(facts['errno'])
        self.assertEqual(len(facts['frames']),8);self.assertTrue(facts['truncated'])
        self.assertTrue(all(x['file']==x['function']=='OTHER' for x in facts['frames']))
        self.assertNotIn('SecretNamedError',json.dumps(facts));self.assertNotIn('SYNTHETIC_PRIVATE',json.dumps(facts))
        self.assertEqual(self.h._host_safe_error(PermissionError(13,'x'),None)['errno'],13)
        self.assertIsNone(self.h._host_safe_error(OSError(123456,'x'),None)['errno'])
        d=self.h._HostDiagnostics()
        for unused in range(20):d.note(ValueError('SYNTHETIC_PRIVATE'),None)
        self.assertEqual(len(d.secondary),8);self.assertTrue(d.truncated)

    def test_core_import_primary_survives_path_cleanup(self):
        import importlib
        from types import SimpleNamespace
        primary=ImportError('SYNTHETIC_PRIVATE');d=self.h._HostDiagnostics()
        class Paths(list):
            def remove(self,value):raise OSError(5,'SYNTHETIC_PRIVATE')
        fake=SimpleNamespace(path=Paths(),exc_info=sys.exc_info)
        with patch.object(self.h,'sys',fake),patch.object(importlib,'import_module',side_effect=primary):
            try:self.h._core_module(_diagnostics=d)
            except BaseException as caught:self.assertIs(caught,primary)
            else:self.fail('primary missing')
        self.assertEqual(d.first['stage'],'CORE_IMPORT')
        self.assertEqual(d.secondary[0]['stage'],'CORE_PATH_REMOVE')

    def test_postinput_expiry_and_import_stages_no_extra_clock(self):
        m=self.manifest()
        for ticks,stage in (([1,101],'POST_INPUT_EXPIRY'),([1,1],'CORE_IMPORT')):
            with patch.object(self.h,'_capture_host',return_value=()),\
                    patch.object(self.h.time,'time',side_effect=ticks) as clock,\
                    patch.object(self.h,'_core_module',side_effect=ImportError('SYNTHETIC_PRIVATE')):
                out=self.h.run_live_host(m,mode='create',launch=True)
            self.assertEqual(out['diagnostics']['primary']['stage'],stage)
            self.assertEqual(clock.call_count,2);self.assertEqual((out['gets'],out['posts']),(0,0))

    def test_storage_policy_hash_and_owner_stages_zero_dispatch(self):
        from types import SimpleNamespace
        m=self.manifest()
        with tempfile.TemporaryDirectory() as directory:
            m['storage_domain']=str(Path(directory).resolve())
            owner=SimpleNamespace(CrossProcessOwner=lambda *a:(_ for _ in ()).throw(OSError(5,'SYNTHETIC_PRIVATE')))
            core=SimpleNamespace(rse=owner,sc=None)
            for failure,stage in (('stat','STORAGE_STAT'),('policy','STORAGE_POLICY'),('hash','CODE_HASH_HOST'),('owner','OWNER_CONSTRUCT')):
                with self.subTest(stage=stage),patch.object(self.h,'_capture_host',return_value=()),\
                        patch.object(self.h.time,'time',return_value=1),patch.object(self.h,'_core_module',return_value=core):
                    if failure=='stat':
                        with patch.object(Path,'stat',side_effect=OSError(5,'SYNTHETIC_PRIVATE')):
                            out=self.h.run_live_host(m,mode='create',launch=True)
                    elif failure=='policy':
                        with patch.object(os,'getuid',return_value=-1):out=self.h.run_live_host(m,mode='create',launch=True)
                    elif failure=='hash':
                        with patch.object(Path,'read_bytes',side_effect=OSError(5,'SYNTHETIC_PRIVATE')):
                            out=self.h.run_live_host(m,mode='create',launch=True)
                    else:out=self.h.run_live_host(m,mode='create',launch=True)
                self.assertEqual(out['diagnostics']['primary']['stage'],stage)
                self.assertEqual((out['gets'],out['posts']),(0,0));self.assertEqual(list(Path(directory).iterdir()),[])

    def test_five_hash_stages_are_fixed_and_distinct(self):
        expected=['CODE_HASH_HOST','CODE_HASH_HOST_TEST','CODE_HASH_DOC','CODE_HASH_CORE','CODE_HASH_CORE_TEST']
        for index,stage in enumerate(expected):
            d=self.h._HostDiagnostics()
            with patch.object(Path,'read_bytes',side_effect=[b'fixed']*index+[OSError(5,'SYNTHETIC_PRIVATE')]):
                with self.assertRaises(OSError):self.h._host_code_identity(_diagnostics=d)
            self.assertEqual(d.stage,stage)

    def test_owner_body_primary_survives_close_failure(self):
        from contextlib import contextmanager
        primary=ValueError('SYNTHETIC_PRIVATE');events=[];d=self.h._HostDiagnostics()
        class Owner:
            @contextmanager
            def operation(self):
                try:yield
                finally:events.append('operation');raise RuntimeError('SYNTHETIC_PRIVATE')
            def close(self):events.append('close');raise OSError(5,'SYNTHETIC_PRIVATE')
        try:
            with self.h._host_owner(Owner(),d) as owner:
                with self.h._host_operation(owner,d):raise primary
        except BaseException as caught:self.assertIs(caught,primary)
        else:self.fail('primary missing')
        self.assertEqual(events,['operation','close']);self.assertIs(d.primary[0],primary)
        self.assertEqual(len(d.secondary),2)
        # Prior diagnostic state is never global/shared with a new invocation.
        self.assertIsNone(self.h._HostDiagnostics().primary)
        core,m,state=CompleteHostOfflineTests.fixture(self)
        original=core.rse.CrossProcessOwner.close
        def close(owner):
            original(owner)
            raise OSError(5,'SYNTHETIC_PRIVATE')
        with patch.object(core.rse.CrossProcessOwner,'close',close):
            out=self.h.run_live_host(m,mode='create',launch=True)
        self.assertEqual(out['status'],'LIVE_HOST_BLOCKED')
        self.assertEqual(out['execution_state'],'KNOWN_SUCCESS')
        self.assertEqual((out['posts'],out['gets']),(1,8))
        self.assertEqual(out['diagnostics']['primary']['stage'],'OWNER_CLOSE')

    def test_success_capture_no_diagnostics_or_extra_inputs(self):
        with self.capture_fixture() as (m,d,events,reads):
            self.assertEqual(self.h._capture_host(m,'create',_diagnostics=d),(('Authorization','Bearer SYNTHETIC_ONLY'),))
            self.assertIsNone(d.primary);self.assertEqual(len(reads),2)
        self.assertEqual(events,['timer','signal','stream',123])
        with patch.object(self.h,'_capture_host',side_effect=AssertionError('NOT_ALLOWED')):
            self.assertEqual(self.h.run_live_host(None,mode='create'),{'status':'NOT_STARTED'})


class DirectCompletionBarrierTests(unittest.TestCase):
    def test_narrow_completion_cannot_clear_unknown_or_replace_original_get(self):
        # Real Bridge/journal/reconciler, synthetic provider; no native worker.
        from test_remote_runtime_binding import DirectWorkerFakeTests
        fake = DirectWorkerFakeTests('runTest'); fake.setUp()
        try:
            fake.direct_contract(); state = fake.completed()
            self.assertEqual(state.direct_worker_completion, 'DIRECT_WORKER_COMPLETION')
            self.assertEqual(state.record.group, 'UNKNOWN')
        finally:
            fake.doCleanups()
        bridge_tests.BridgeTests.setUpClass()
        f = bridge_tests.BridgeTests('runTest')
        try:
            f.setUp()
            p = f.prepare(f.proposal('PR_CREATE')).prepared
            changed = f.proposal('PR_CREATE', proposal_id='other')
            changed['requested_parameters']['request_identity'] = 'other-request'
            q = f.prepare(changed, ident='other-action').prepared
            f.bind(p,q); f.provider.lose_response = True
            self.assertEqual(f.execute(p).receipt.execution_state, 'UNKNOWN_OUTCOME')
            prior = f.journal.latest('host-1')
            # The diagnostic is not a reconciliation input or authorization.
            f.execute(q)
            f.execute(q,reconcile=True)
            f.execute(p,reconcile=True,authorization=None)
            self.assertEqual(f.journal.latest('host-1'), prior)
            self.assertEqual([r[0] for r in f.provider.requests], ['POST'])
            result = f.execute(p,reconcile=True)
            self.assertEqual(result.receipt.final_disposition, 'RECONCILED_SUCCESS')
            self.assertEqual([r[0] for r in f.provider.requests], ['POST','GET'])
            self.assertIn('20396-request:request-1', f.provider.resources[0]['body'])
            self.assertNotIn('other-request', f.provider.resources[0]['body'])
        finally:
            f.doCleanups(); bridge_tests.BridgeTests.tearDownClass()


class H6MaterialQualification(unittest.TestCase):
    def test_created_object_survives_process_crash_and_original_get_recovery(self):
        code = r'''
import os,sys,json,tempfile
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from test_remote_account_qualification import H6MaterialQualification
root=Path(sys.argv[2]); mode=sys.argv[3]; tempfile.tempdir=str(root)
t=H6MaterialQualification('runTest')
try:
 h,m,args,f=t.harness_fixture()
 m['storage_domain']=str(root/'storage')
 if mode=='create': (root/'storage').mkdir()
 else: f.provider.resources=json.loads((root/'objects').read_text())
 original=args['synthetic_transport'].request
 def request(method,*a,**kw):
  if method=='POST':
   with open(root/'posts','a') as stream: stream.write('POST\n')
  result=original(method,*a,**kw)
  if method=='POST':
   (root/'objects').write_text(json.dumps(f.provider.resources))
   os._exit(73)
  return result
 args['synthetic_transport'].request=request
 out=h.qualify(m,create=mode=='create',recover=mode=='recover',**args)
 print(json.dumps(out))
finally: t.doCleanups()
'''
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            args=[sys.executable,'-B','-c',code,str(Path(__file__).resolve().parent),str(root)]
            first=subprocess.run(args+['create'],capture_output=True,timeout=15)
            self.assertEqual(first.returncode,73,first.stderr)
            self.assertEqual(len(json.loads((root/'objects').read_text())),1)
            second=subprocess.run(args+['recover'],capture_output=True,timeout=15)
            self.assertEqual(second.returncode,0,second.stderr)
            result=json.loads(second.stdout)
            self.assertEqual(result['status'],'RECONCILED_SUCCESS',result)
            self.assertEqual((result['posts'],result['gets']),(0,4))
            self.assertEqual(result['get_readback'][0]['objects'],[{'id':84,'number':42}])
            self.assertEqual((root/'posts').read_text(),'POST\n')
        self.assertFalse(root.exists())

    def harness_fixture(self):
        bridge_tests.BridgeTests.setUpClass(); self.addCleanup(bridge_tests.BridgeTests.tearDownClass)
        f = bridge_tests.BridgeTests('runTest'); self.addCleanup(f.doCleanups); f.setUp()
        spec = importlib.util.spec_from_file_location('qualification', Path(__file__).resolve().parents[1] /
            'scripts/remote_account_qualification.py')
        h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
        proposal = f.proposal('PR_CREATE')
        proposal['requested_parameters'].update(title='[SYNTHETIC H6] test', body=b'SYNTHETIC H6\nbody',
            timeout=30, response_limit=65536)
        p = f.prepare(proposal).prepared
        m = dict(schema='20396.h6.pr-create.v1', api_origin='https://api.example.invalid', repository='team/repo',
            repository_id=123, head='feature', base='main', head_oid='a'*40, base_oid='b'*40,
            proposal_id='proposal', action_id='host-1', request_identity='request-1', payload_digest=p.payload_digest,
            title='[SYNTHETIC H6] test', body='SYNTHETIC H6\nbody', marker='<!-- 20396-request:request-1 -->',
            draft=True, effect_scope='PR_CREATE', authorization_ref='auth', expires_at=100,
            post_budget=1, get_budget=4, byte_budget=65536, time_budget=30,
            storage_domain=str(f.root), storage_id='h6', credential_source='EXPLICIT_SYNTHETIC_MEMORY',
            credential_scope='https://api.example.invalid/repos/team/repo')
        class Synthetic:
            provenance='OFFLINE_SYNTHETIC'
            def request(self, method, url, headers, body, **kw):
                if url.endswith('/repos/team/repo'):
                    return 200, (), json.dumps(dict(id=123,full_name='team/repo')).encode()
                if '/branches/' in url:
                    return 200, (), json.dumps(dict(commit=dict(sha=('a' if url.endswith('/feature') else 'b')*40))).encode()
                try:
                    status, returned, data = f.provider.request(method,url,headers,body,**kw)
                except TimeoutError:
                    if method == 'POST' and f.provider.lose_response:
                        raise h.InjectedObservationLoss() from None
                    raise
                value = json.loads(data)
                for record in value if type(value) is list else [value]:
                    for side in ('head', 'base'):
                        record[side]['repo']['id'] = 123
                        record[side]['sha'] = ('a' if side == 'head' else 'b')*40
                return status, returned, json.dumps(value).encode()
        auth=f.r.Authorization('auth','task',{f.r.ActionClass.PR_CREATE},(p.action_request.target,),
            {p.action_request.capability},100)
        args=dict(launch=True,synthetic_transport=Synthetic(),credential_headers=(('Authorization','synthetic-only'),),
            authority=auth,policy_stack=(f.policy,),context=p.context,now=1,trusted_agent_id='host-agent')
        return h,m,args,f

    def test_harness_success_and_completed_barrier(self):
        h,m,args,f = self.harness_fixture()
        for changes in ({'expires_at':0}, {'payload_digest':'0'*64}, {'post_budget':2},
                {'repository_id':True}, {'head_oid':'bad'}, {'schema':'unknown'}, {'unexpected':'field'}):
            bad=dict(m); bad.update(changes)
            rejected=h.qualify(bad,create=True,**args)
            self.assertEqual((rejected['posts'],rejected['gets']),(0,0))
            self.assertFalse((f.root/'journal').exists())
        out=h.qualify(m,create=True,**args)
        self.assertEqual(out.get('execution_state'),'KNOWN_SUCCESS',out)
        self.assertEqual(out['posts'],1)
        self.assertEqual(out['adapter_response']['http_status'],201)
        self.assertEqual(out['adapter_response']['objects'],[{'id':84,'number':42}])
        self.assertEqual(out['get_readback'],[])
        out=h.qualify(m,**args)
        self.assertEqual(out['posts'],0)
        for path in (f.root/'journal', f.root/'chain'):
            self.assertNotIn(b'synthetic-only',path.read_bytes())

    def test_harness_unknown_readonly_recovery_and_replacement_credentials(self):
        h,m,args,f = self.harness_fixture()
        f.provider.lose_response=True
        lost=h.qualify(m,create=True,**args)
        self.assertEqual(lost['execution_state'],'UNKNOWN_OUTCOME')
        self.assertEqual(lost['fault_provenance'],['INJECTED_OBSERVATION_LOSS'])
        args['credential_headers']=(('Authorization','different-synthetic-only'),)
        self.assertEqual(h.qualify(m,**args)['posts'],0)
        out=h.qualify(m,recover=True,**args)
        self.assertEqual(out['status'],'RECONCILED_SUCCESS',out)
        self.assertEqual(out['posts'],0)
        self.assertEqual(out['gets'],4)
        self.assertEqual(out['get_readback'][0]['objects'],[{'id':84,'number':42}])
        self.assertEqual(len(out['get_readback'][0]['response_sha256']),64)
        self.assertNotIn('different-synthetic-only',json.dumps(out))
        self.assertEqual(sum(r[0]=='POST' for r in f.provider.requests),1)

    def test_harness_recovery_without_authority_no_io(self):
        h,m,args,f = self.harness_fixture()
        f.provider.lose_response=True; h.qualify(m,create=True,**args)
        args['authority']=None
        out=h.qualify(m,recover=True,**args)
        self.assertEqual((out['posts'],out['gets']),(0,0))

    def test_authority_expiring_during_preflight_prevents_post(self):
        h,m,args,f = self.harness_fixture()
        m['expires_at']=1.03; args['authority']=replace(args['authority'],expires_at=1.03)
        original=args['synthetic_transport'].request
        def delayed(*a,**kw):
            time.sleep(.04)
            return original(*a,**kw)
        args['synthetic_transport'].request=delayed
        self.assertEqual(h.qualify(m,create=True,**args)['posts'],0)

    def test_authority_expiring_during_readback_preserves_unknown(self):
        h,m,args,f = self.harness_fixture()
        f.provider.lose_response=True; h.qualify(m,create=True,**args)
        args['authority']=replace(args['authority'],expires_at=1.03)
        original=args['synthetic_transport'].request
        def delayed(method,url,*a,**kw):
            if '/pulls?' in url: time.sleep(.04)
            return original(method,url,*a,**kw)
        args['synthetic_transport'].request=delayed
        out=h.qualify(m,recover=True,**args)
        self.assertNotEqual(out['status'],'RECONCILED_SUCCESS')
        owner=f.r.CrossProcessOwner(str(f.root))
        try:
            journal=f.r.DurableSecurityJournal(f.root/'journal',storage_id='h6',owner=owner)
            self.assertEqual(journal.latest('host-1').state,f.r.JournalState.RECONCILIATION_REQUIRED)
        finally:
            owner.close()

    def test_harness_fsync_failure_and_cancel_no_execution(self):
        h,m,args,f = self.harness_fixture()
        with patch('os.fsync',side_effect=OSError('synthetic-only')):
            self.assertEqual(h.qualify(m,create=True,**args)['posts'],0)
        args['cancelled']=lambda:True
        self.assertEqual(h.qualify(m,**args)['gets'],0)
        self.assertEqual(f.provider.requests,[])

    def test_harness_corrupt_journal_no_provider_calls(self):
        h,m,args,f = self.harness_fixture()
        h.qualify(m,create=True,**args)
        (f.root/'journal').write_bytes(b'corrupt\n')
        out=h.qualify(m,**args)
        self.assertEqual((out['posts'],out['gets']),(0,0))

    def test_harness_get_failure_matrix_remains_unknown(self):
        h,m,args,f = self.harness_fixture()
        f.provider.lose_response=True; h.qualify(m,create=True,**args)
        record=f.provider.resources[0]
        original=args['synthetic_transport'].request
        for status,headers,data in [(200,(),b'[]'),(401,(),b'{}'),(403,(),b'{}'),
                (200,(),b'{'),(200,(('Link','next'),),b'[]')]:
            def request(method,url,hdr,body,**kw):
                if '/pulls?' in url: return status,headers,data
                return original(method,url,hdr,body,**kw)
            args['synthetic_transport'].request=request
            out=h.qualify(m,recover=True,**args)
            self.assertNotEqual(out['status'],'RECONCILED_SUCCESS')
            self.assertEqual(out['posts'],0)
        args['synthetic_transport'].request=original
        for resources in ([record,record],[]):
            f.provider.resources=resources
            self.assertNotEqual(h.qualify(m,recover=True,**args)['status'],'RECONCILED_SUCCESS')

    def test_harness_inactive_without_explicit_launch(self):
        path = Path(__file__).resolve().parents[1] / 'scripts/remote_account_qualification.py'
        self.assertTrue(path.exists(), 'H6 explicit harness missing')
        spec = importlib.util.spec_from_file_location('h6_qualification', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.assertEqual(module.qualify(None)['status'], 'NOT_STARTED')

    def test_real_baseline_fixture_is_unclassified_and_bytes_unchanged(self):
        baseline = 'e266154d72b9aed5b1f426806eecbc60afdb3d0a'
        root = Path(__file__).resolve().parents[1]
        # Execute immutable historical code, not a fabricated legacy envelope.
        archive = subprocess.run(['git', 'archive', baseline,
            '.agents/skills/long-horizon-engineering/scripts', 'tests/test_agent_runtime_integration.py',
            'tests/test_remote_runtime_binding.py'], cwd=root, check=True, capture_output=True, timeout=30).stdout
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory).resolve()
            with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
                for member in stream:
                    if member.isfile():
                        self.assertFalse(Path(member.name).is_absolute() or '..' in Path(member.name).parts)
                        target = destination / member.name; target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(stream.extractfile(member).read())
            code = r'''
import sys,json
sys.path.insert(0,sys.argv[1]+'/tests')
from test_agent_runtime_integration import BridgeTests
BridgeTests.setUpClass(); t=BridgeTests('runTest'); t.setUp()
try:
 owner=t.r.CrossProcessOwner(str(t.root))
 try:
  t.journal=t.r.DurableSecurityJournal(str(t.root/'journal'),storage_id='legacy-h6',create=True,owner=owner)
  t.chain=t.s.JsonlSecurityChain('chain','install',str(t.root/'chain'),create=True,owner=owner)
  t.bridge=t.m.AgentRuntimeBridge(owner=owner)
  p=t.prepare(t.proposal('PR_CREATE')).prepared; t.bind(p)
  t.provider.lose_response=sys.argv[2]=='unknown'; t.execute(p)
  print((t.root/'journal').read_text(),end='')
 finally: owner.close()
finally: t.doCleanups(); BridgeTests.tearDownClass()
'''
            bridge_tests.BridgeTests.setUpClass()
            self.addCleanup(bridge_tests.BridgeTests.tearDownClass)
            r = bridge_tests.BridgeTests.m.rse
            for mode in ('unknown', 'completed'):
                data = subprocess.run([sys.executable, '-B', '-c', code, directory, mode],
                    capture_output=True, check=True, timeout=30).stdout
                path = destination / ('legacy-' + mode); path.write_bytes(data); path.chmod(0o600)
                journal = r.DurableSecurityJournal(path, storage_id='legacy-h6')
                metadata = journal.binding_classification()
                self.assertTrue(metadata[0]['legacy'] and metadata[0]['historical_barrier'])
                self.assertIsNone(metadata[0]['effect_class'])
                self.assertEqual(path.read_bytes(), data)
                self.assertIsInstance(json.loads(data.splitlines()[1])['binding'], list)
                f = bridge_tests.BridgeTests('runTest'); f.setUp()
                try:
                    f.journal = journal
                    p = f.prepare(f.proposal('PR_CREATE'), ident='new').prepared
                    f.bind(p)
                    self.assertEqual(f.execute(p).status, 'LEGACY_PR_MATERIAL_UNRESOLVED')
                    self.assertEqual(f.provider.requests, [])
                    # Fallback does not deny unrelated filesystem effects.
                    q = f.prepare(f.proposal(), ident='file-action').prepared
                    f.bind(q)
                    self.assertEqual(f.execute(q).receipt.execution_state, 'KNOWN_SUCCESS')
                    self.assertTrue(path.read_bytes().startswith(data))
                    classes = journal.binding_classification()
                    self.assertEqual(len(classes),2)
                    self.assertEqual(classes[1]['effect_class'],'CREATE_FILE')
                    # Actual historical reader must reject the mixed new envelope.
                    old_read = "import sys; sys.path.insert(0,sys.argv[1]); import runtime_safety_envelope as r; r.DurableSecurityJournal(sys.argv[2],storage_id='legacy-h6')"
                    old = subprocess.run([sys.executable,'-B','-c',old_read,
                        str(destination/'.agents/skills/long-horizon-engineering/scripts'),str(path)],
                        capture_output=True,timeout=30)
                    self.assertNotEqual(old.returncode,0)
                    self.assertIn(b'DURABLE_STATE_UNTRUSTED',old.stderr)
                finally:
                    f.doCleanups()

    def test_changed_request_identity_cannot_repeat_unknown_material(self):
        bridge_tests.BridgeTests.setUpClass()
        self.addCleanup(bridge_tests.BridgeTests.tearDownClass)
        fixture = bridge_tests.BridgeTests('runTest')
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        owner = fixture.r.CrossProcessOwner(str(fixture.root))
        self.addCleanup(owner.close)
        fixture.journal = fixture.r.DurableSecurityJournal(
            str(fixture.root / 'journal'), storage_id='h6-probe', create=True, owner=owner)
        fixture.chain = fixture.s.JsonlSecurityChain(
            'chain', 'install', str(fixture.root / 'chain'), create=True, owner=owner)
        fixture.bridge = fixture.m.AgentRuntimeBridge(owner=owner)
        first = fixture.prepare(fixture.proposal('PR_CREATE'), ident='action-1').prepared
        self.assertEqual(first.material_effect_identity,
            fixture.prepare(fixture.proposal('PR_CREATE'), ident='alternate').prepared.material_effect_identity)
        proposal = fixture.proposal('PR_CREATE', proposal_id='second')
        proposal['requested_parameters']['request_identity'] = 'request-2'
        second = fixture.prepare(proposal, ident='action-2').prepared
        fixture.bind(first, second)
        fixture.provider.lose_response = True
        result = fixture.execute(first)
        self.assertEqual(result.receipt.execution_state, 'UNKNOWN_OUTCOME')
        fixture.execute(second)
        self.assertEqual(sum(r[0] == 'POST' for r in fixture.provider.requests), 1)
        before = (fixture.root / 'journal').read_bytes()
        metadata = fixture.journal.binding_classification()
        self.assertEqual(metadata[0]['effect_class'], 'PR_CREATE')
        self.assertEqual(metadata[0]['material_identity_version'], 'PR_INTENDED_V1')
        self.assertEqual((fixture.root / 'journal').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
