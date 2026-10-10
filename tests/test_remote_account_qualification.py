"""OFFLINE_SYNTHETIC H6 admission gap; no real provider access."""
import unittest
import json
import io
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


class H6MaterialQualification(unittest.TestCase):
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
                status, returned, data = f.provider.request(method,url,headers,body,**kw)
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
        out=h.qualify(m,**args)
        self.assertEqual(out['posts'],0)
        for path in (f.root/'journal', f.root/'chain'):
            self.assertNotIn(b'synthetic-only',path.read_bytes())

    def test_harness_unknown_readonly_recovery_and_replacement_credentials(self):
        h,m,args,f = self.harness_fixture()
        f.provider.lose_response=True
        self.assertEqual(h.qualify(m,create=True,**args)['execution_state'],'UNKNOWN_OUTCOME')
        args['credential_headers']=(('Authorization','different-synthetic-only'),)
        self.assertEqual(h.qualify(m,**args)['posts'],0)
        out=h.qualify(m,recover=True,**args)
        self.assertEqual(out['status'],'RECONCILED_SUCCESS',out)
        self.assertEqual(out['posts'],0)
        self.assertEqual(out['gets'],4)
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
