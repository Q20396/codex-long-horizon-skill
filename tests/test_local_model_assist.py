"""Synthetic only: no hardware tool, socket, runtime, model or cloud calls."""
from contextlib import redirect_stdout
import importlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]/'.agents/skills/long-horizon-engineering/scripts'
sys.path.insert(0, str(SCRIPTS))
m = importlib.import_module('local_model_assist')
PIN = 'a'*64


class FakeTransport:
    def __init__(self, failure=None, digest=PIN, version='0.40.13', reply=None):
        self.calls = []
        self.failure, self.pin, self.version, self.reply = failure, digest, version, reply

    def __call__(self, method, path, body):
        self.calls.append((method, path, body))
        if self.failure == path:
            raise OSError('PRIVATE diagnostic must not escape')
        if path == '/api/version':
            return {'version': self.version}
        if path == '/api/tags':
            return {'models': [{'name': 'qwen3.5:4b', 'digest': self.pin}]}
        return self.reply if self.reply is not None else {
            'model': 'qwen3.5:4b', 'done': True, 'message': {'content': 'synthetic summary'},
            'prompt_eval_count': 12, 'eval_count': 4}


class AssistTests(unittest.TestCase):
    def grant(self, scopes=('probe',), binding='', expiry=100):
        return m.Grant('node', frozenset(scopes), expiry, 'human-synthetic-ref', binding)

    def client(self, transport=None, endpoint='http://127.0.0.1:11434'):
        return m.OllamaClient(endpoint, '0.40.13', 'qwen3.5:4b', PIN,
                              transport=transport or FakeTransport(), local_service_ref='owner-local-only-ref')

    def task(self, privacy='LOCAL_ONLY'):
        return m.pool.Task('task', 'log-summary', 'fixture', privacy=privacy,
                           output_privacy=privacy, payload='synthetic test fixture')

    def node(self, client, task):
        binding=m.task_binding(client,task.task_class,task.data_scope)
        q=m.pool.Qualification('node','ollama',client.model,binding,task.task_class,client.version)
        return m.pool.Node('node',provider='ollama',model=client.model,config=binding,consent=True,
            deployment_authorized=True,probed=True,runtime_validated=True,privacy_scopes={'fixture'},
            qualifications={q},memory_available=16,provider_version=client.version)

    def run_local(self, transport=None, privacy='LOCAL_ONLY', local_output=True):
        client = self.client(transport)
        task = self.task(privacy)
        scopes = ['infer']+(['return-to-cloud'] if privacy == 'CLOUD_ALLOWED' else [])
        grant = self.grant(scopes, m.task_binding(client, task.task_class, task.data_scope))
        return m.run_local(task, client, grant, self.node(client,task),
                           local_output=local_output, now=1)

    def test_catalog_fixed_three_and_no_remote_model(self):
        c = m.load_catalog()
        self.assertEqual(len(c['models']), 3)
        self.assertEqual(c['runtime']['version'], '0.40.13')
        for model in c['models']:
            self.assertEqual(model['status'], 'UNQUALIFIED')
            self.assertEqual(len(model['manifest_sha256']), 64)
            self.assertNotIn('cloud', model['id'])

    def test_probe_declined_zero_reader_calls(self):
        calls = []
        with self.assertRaises(m.Stopped):
            m.probe('node', self.grant(()), lambda n: calls.append(n), now=1)
        self.assertEqual(calls, [])

    def test_probe_expired_zero_reader_calls(self):
        with self.assertRaises(m.Stopped):
            m.probe('node', self.grant(expiry=1), lambda n: self.fail('called'), now=1)

    def test_probe_wrong_node(self):
        with self.assertRaises(m.Stopped):
            m.probe('other', self.grant(), lambda n: self.fail('called'), now=1)

    def test_probe_filters_private_identity(self):
        self.assertEqual(m.probe('node', self.grant(), lambda n: {'os': 'Linux', 'serial': 'PRIVATE'}, now=1),
                         {'node_id': 'node', 'os': 'Linux'})

    def test_linux_vendor_snapshot_no_serial(self):
        calls=[]
        def command(argv):
            calls.append(argv)
            return 'NVIDIA fixture, 24576, 20480, 570.0'
        reader=m.PlatformReader('/fixture', command=command,
             read_text=lambda _: 'MemTotal: 67108864 kB\nMemAvailable: 50331648 kB',
             system=lambda:'Linux', architecture=lambda:'x86_64', disk_free=lambda _:100*1024**3)
        value=m.probe('node',self.grant(),reader,now=1)
        self.assertEqual(value['gpu_memory_gb'],20)
        self.assertEqual(value['memory_available_gb'],48)
        self.assertEqual(len(calls),1)

    def test_mac_unified_available_not_invented(self):
        def command(argv):
            return str(64*1024**3) if argv[0].endswith('sysctl') else json.dumps({'SPDisplaysDataType':[{'sppci_model':'Apple fixture','serial':'PRIVATE'}]})
        reader=m.PlatformReader('/fixture',command=command,system=lambda:'Darwin',
            architecture=lambda:'arm64',disk_free=lambda _:100*1024**3)
        v=m.probe('node',self.grant(),reader,now=1)
        self.assertTrue(v['unified_memory'])
        self.assertIsNone(v['memory_available_gb'])
        self.assertNotIn('PRIVATE',json.dumps(v))

    def test_missing_tool_keeps_unknown(self):
        reader=m.PlatformReader('/fixture',command=lambda _: (_ for _ in ()).throw(FileNotFoundError()),
            system=lambda:'Windows',architecture=lambda:'AMD64',disk_free=lambda _:100)
        v=m.probe('node',self.grant(),reader,now=1)
        self.assertIsNone(v['gpu_memory_gb'])

    def test_insufficient_resources_skipped(self):
        c=m.load_catalog();r=m.recommend({'memory_total_gb':8,'memory_available_gb':4,
          'gpu_memory_gb':4,'free_storage_gb':100,'unified_memory':False},c,'log-summary')
        self.assertEqual(r['state'],'SKIPPED')

    def test_missing_memory_unknown_not_zero(self):
        self.assertEqual(m.recommend({},m.load_catalog(),'log-summary')['state'],'UNKNOWN')

    def test_unified_memory_not_double_counted(self):
        r=m.recommend({'memory_total_gb':16,'memory_available_gb':12,'unified_memory':True,
                       'free_storage_gb':100},m.load_catalog(),'log-summary')
        self.assertEqual(r['state'],'SKIPPED')  # reserve8 leaves8 < candidate9

    def test_recommend_is_not_qualification(self):
        r=m.recommend({'memory_total_gb':64,'memory_available_gb':48,'unified_memory':True,
                       'free_storage_gb':100},m.load_catalog(),'log-summary')
        self.assertEqual(r['state'],'CANDIDATE_ONLY')
        self.assertEqual(r['candidate']['status'],'UNQUALIFIED')

    def test_unknown_task_rejected(self):
        with self.assertRaises(m.Stopped):m.recommend({},m.load_catalog(),'arbitrary-code')

    def test_new_install_requires_consent(self):
        c=m.load_catalog()['models'][0]
        self.assertEqual(m.onboarding({},c)['state'],'CONSENT_REQUIRED')

    def test_upgrade_reuses_exact_existing(self):
        c=m.load_catalog()['models'][0];b=m.digest(c)
        r=m.onboarding({'provider_version':c['provider_version'],'model_digest':c['manifest_sha256']},c,b,b,authorization_expires_at=100,now=1)
        self.assertEqual(r['state'],'REUSE_EXISTING');self.assertEqual(r['actions'],[])
        self.assertTrue(r['preserve_custom_config'])

    def test_changed_candidate_invalidates_authority(self):
        c=m.load_catalog()['models'][0]
        self.assertEqual(m.onboarding({},c,'old','old')['state'],'CONSENT_REQUIRED')

    def test_partial_download_unknown_never_auto_retries_or_cleans(self):
        c=m.load_catalog()['models'][0]
        self.assertEqual(m.onboarding({'pending_unknown':True},c,m.digest(c),m.digest(c)),
                         {'state':'UNKNOWN','actions':[],'binding':m.digest(c)})

    def test_install_missing_adapter_does_not_pretend_success(self):
        c=m.load_catalog()['models'][0];r=m.onboarding({},c,authorized_binding=m.digest(c),authorization_expires_at=100,now=1)
        self.assertEqual(r['state'],'INSTALL_ADAPTER_REQUIRED');self.assertEqual(r['actions'],[])

    def test_skip_when_user_declines_model(self):
        self.assertEqual(m.onboarding({},None),{'state':'SKIPPED','actions':[]})

    def test_endpoint_rejects_remote_proxy_auth_query_and_paths(self):
        for value in ['https://127.0.0.1:11434','http://localhost:11434','http://10.0.0.1:11434',
                      'http://u:p@127.0.0.1:11434','http://127.0.0.1:11434/x','http://127.0.0.1:11434?q=x']:
            with self.subTest(value=value),self.assertRaises(m.Stopped):self.client(endpoint=value)

    def test_unknown_runtime_or_cloud_name_zero_http(self):
        for version,model in [(None,'qwen3.5:4b'),('','qwen3.5:4b'),('UNKNOWN','qwen3.5:4b'),
                              ('0.40.13',''),('0.40.13','qwen:480b-cloud')]:
            with self.assertRaises(m.Stopped):
                m.OllamaClient('http://127.0.0.1:11434',version,model,PIN,
                               transport=lambda *a:self.fail('HTTP'),local_service_ref='owner')

    def test_local_service_owner_assertion_required(self):
        with self.assertRaises(m.Stopped):m.OllamaClient('http://127.0.0.1:11434','0.40.13','qwen3.5:4b',PIN)

    def test_redirect_rejected(self):
        with self.assertRaises(m.Stopped):m.NoRedirect().redirect_request(None,None,302,'',{},'http://127.0.0.1:11434/x')

    def test_runtime_version_change(self):
        with self.assertRaises(m.Stopped):self.client(FakeTransport(version='different')).inspect()

    def test_model_pin_change(self):
        with self.assertRaises(m.Stopped):self.client(FakeTransport(digest='b'*64)).inspect()

    def test_unknown_network_latched_no_retry(self):
        t=FakeTransport(failure='/api/chat');c=self.client(t)
        with self.assertRaises(m.pool.UnknownOutcome):c.execute(self.task())
        count=len(t.calls)
        with self.assertRaises(m.Stopped):c.inspect()
        self.assertEqual(len(t.calls),count)

    def test_pool_real_adapter_shape_synthetic_only(self):
        result,usage=self.run_local()
        self.assertEqual(result.state,'COMPLETED');self.assertEqual(result.output,'synthetic summary')
        self.assertEqual(usage[0].total_tokens,16)
        self.assertEqual(usage[0].metric_source,m.accounting.MetricSource.RUNTIME_REPORTED)

    def test_local_only_result_withheld_from_cloud_caller(self):
        result,_=self.run_local(local_output=False)
        self.assertIsNone(result.output);self.assertTrue(result.output_withheld)

    def test_cloud_return_requires_separate_scope(self):
        c=self.client();task=self.task('CLOUD_ALLOWED');g=self.grant(['infer'],m.task_binding(c,task.task_class,task.data_scope))
        with self.assertRaises(m.Stopped):m.run_local(task,c,g,self.node(c,task),now=1)

    def test_authorized_cloud_return_not_cloud_execution(self):
        result,_=self.run_local(privacy='CLOUD_ALLOWED')
        self.assertEqual(result.state,'COMPLETED');self.assertNotEqual(result.state,'FALLBACK_OPENAI')

    def test_inference_failure_no_cloud_retry(self):
        t=FakeTransport(failure='/api/chat');result,usage=self.run_local(t,privacy='CLOUD_ALLOWED')
        self.assertTrue(result.reconciliation_required);self.assertIsNone(result.output)
        self.assertEqual(sum(p=='/api/chat' for _,p,_ in t.calls),1)
        self.assertEqual(len(usage),1);self.assertIsNone(usage[0].total_tokens)

    def test_incomplete_reply_not_success_and_latched(self):
        t=FakeTransport(reply={'done':False});c=self.client(t)
        with self.assertRaises(m.pool.UnknownOutcome):c.execute(self.task())
        calls=len(t.calls)
        with self.assertRaises(m.pool.UnknownOutcome):c.execute(self.task())
        self.assertEqual(len(t.calls),calls)

    def test_nonempty_reference_cannot_mint_qualified_node(self):
        c=self.client();task=self.task();g=self.grant(['infer'],m.task_binding(c,task.task_class,task.data_scope))
        with self.assertRaises(m.Stopped):m.run_local(task,c,g,'string-not-a-node',now=1)

    def test_unqualified_or_insufficient_node_rejected_before_http(self):
        from dataclasses import replace
        t=FakeTransport();c=self.client(t);task=self.task()
        g=self.grant(['infer'],m.task_binding(c,task.task_class,task.data_scope))
        for node in [replace(self.node(c,task),runtime_validated=False),
                     replace(self.node(c,task),memory_available=0),
                     replace(self.node(c,task),provider_version='changed')]:
            with self.assertRaises(m.Stopped):m.run_local(task,c,g,node,now=1)
        self.assertEqual(t.calls,[])

    def test_input_cap_before_request(self):
        t=FakeTransport();c=self.client(t)
        task=m.pool.Task('x','log-summary','fixture',payload='x'*(m.MAX_INPUT+1))
        with self.assertRaises(m.Stopped):c.execute(task)
        self.assertEqual(t.calls,[])

    def test_missing_usage_unknown_not_zero(self):
        r=m.usage_record({},call_id='u',model='x',started=1,finished=2)
        self.assertIsNone(r.total_tokens);self.assertEqual(r.metric_source,m.accounting.MetricSource.UNKNOWN)

    def record(self,call,inp,out):
        return m.usage_record({'input_tokens':inp,'output_tokens':out},call_id=call,model='fixed-cloud',
                              started=1,finished=2,provider='openai',cloud=True)

    def test_all_cloud_calls_counted_can_be_negative_savings(self):
        a=[self.record('baseline',100,10)];b=[self.record('primary',50,10),self.record('review',60,20)]
        r=m.compare_cloud_usage(a,b,same_task=True,same_model=True,quality_passed=True,complete=True)
        self.assertEqual(r['saved_tokens'],-30)

    def test_incomplete_quality_or_usage_no_savings_claim(self):
        a=[self.record('b',100,10)]
        for key in ['same_task','same_model','quality_passed','complete']:
            facts=dict(same_task=True,same_model=True,quality_passed=True,complete=True);facts[key]=False
            self.assertEqual(m.compare_cloud_usage(a,a,**facts)['state'],'UNKNOWN')

    def test_duplicate_calls_rejected(self):
        r=self.record('duplicate',1,1)
        self.assertEqual(m.compare_cloud_usage([r,r],[r],same_task=True,same_model=True,
          quality_passed=True,complete=True)['state'],'UNKNOWN')

    def cli_fixture(self, directory, qualified=True):
        from dataclasses import asdict, replace
        f=Path(directory)/'synthetic.txt';f.write_text('synthetic input')
        model=m.load_catalog()['models'][0]
        transport=FakeTransport(digest=model['manifest_sha256'])
        client=m.OllamaClient('http://127.0.0.1:11434',model['provider_version'],model['id'],
                             model['manifest_sha256'],transport=transport,local_service_ref='synthetic-owner')
        scope='file:'+str(f)
        task=m.pool.Task('cli','log-summary',scope,privacy='CLOUD_ALLOWED',output_privacy='CLOUD_ALLOWED',
                         memory_required=model['memory_gb'])
        node=replace(self.node(client,task),privacy_scopes={scope},runtime_validated=qualified)
        g=self.grant(['infer','return-to-cloud'],m.task_binding(client,task.task_class,scope),expiry=2**40)
        gf=Path(directory)/'grant.json';gf.write_text(json.dumps(asdict(g),default=list))
        qf=Path(directory)/'qualification.json'
        node_data=asdict(node)
        node_data['qualifications']=[asdict(q) for q in node.qualifications]
        qf.write_text(json.dumps({'expires_at':2**40,'node':node_data},default=list))
        args=['assist','--node','node','--grant-file',str(gf),'--qualification-file',str(qf),
              '--input-file',str(f),'--task-id','cli','--local-service-ref','synthetic-owner','--return-to-cloud']
        return args,transport

    def test_expired_upgrade_authority_does_not_authorize_reuse(self):
        c=m.load_catalog()['models'][0];b=m.digest(c)
        self.assertEqual(m.onboarding({},c,b,b,authorization_expires_at=1,now=1)['state'],'CONSENT_REQUIRED')

    def test_cleanup_unknown_not_swallowed_as_partial_probe(self):
        reader=m.PlatformReader('/fixture',command=lambda _: (_ for _ in ()).throw(m.CleanupUnknown('PROBE_CLEANUP_UNKNOWN')),
            system=lambda:'Darwin',architecture=lambda:'arm64',disk_free=lambda _:100)
        with self.assertRaises(m.CleanupUnknown):m.probe('node',self.grant(),reader,now=1)

    def test_command_cleanup_failure_has_fixed_unknown(self):
        from unittest.mock import MagicMock
        proc=MagicMock();proc.poll.return_value=None
        proc.kill.side_effect=OSError('PRIVATE diagnostic')
        selector=MagicMock();selector.__enter__.return_value=selector
        selector.select.side_effect=m.Stopped('PROBE_COMMAND_TIMEOUT')
        with patch.object(m.subprocess,'Popen',return_value=proc),patch.object(m.selectors,'DefaultSelector',return_value=selector):
            with self.assertRaisesRegex(m.CleanupUnknown,'^PROBE_CLEANUP_UNKNOWN$'):m._command(['fixture-only'])
        proc.kill.assert_called_once();proc.stdout.close.assert_called_once()

    def test_malformed_qualification_is_fixed_stop(self):
        with tempfile.TemporaryDirectory() as d:
            args,transport=self.cli_fixture(d)
            Path(d,'qualification.json').write_text('[]')
            with patch.object(m.os,'open',side_effect=AssertionError('input body read')),redirect_stdout(io.StringIO()) as out:
                self.assertEqual(m.main(args),2)
            self.assertEqual(json.loads(out.getvalue())['state'],'STOP')
            self.assertEqual(transport.calls,[])

    def test_assist_cli_synthetic_end_to_end_no_socket(self):
        with tempfile.TemporaryDirectory() as d:
            args,transport=self.cli_fixture(d)
            with patch.object(m.OllamaClient,'_http',lambda _,a,b,c:transport(a,b,c)),redirect_stdout(io.StringIO()) as out:
                rc=m.main(args)
            self.assertEqual(rc,0,out.getvalue())
            self.assertEqual(json.loads(out.getvalue())['output'],'synthetic summary')
            self.assertEqual(sum(p=='/api/chat' for _,p,_ in transport.calls),1)

    def test_cli_unqualified_stops_before_input_body(self):
        with tempfile.TemporaryDirectory() as d:
            args,transport=self.cli_fixture(d,qualified=False)
            with patch.object(m.os,'open',side_effect=AssertionError('input body read')),redirect_stdout(io.StringIO()):
                self.assertEqual(m.main(args),2)
            self.assertEqual(transport.calls,[])

    def test_cli_without_return_permission_stops_before_body(self):
        with tempfile.TemporaryDirectory() as d:
            args,transport=self.cli_fixture(d);args.remove('--return-to-cloud')
            with patch.object(m.os,'open',side_effect=AssertionError('input body read')),redirect_stdout(io.StringIO()):
                self.assertEqual(m.main(args),2)
            self.assertEqual(transport.calls,[])

    def test_status_cli_no_probe_or_inference(self):
        with patch.object(m.PlatformReader,'__call__',side_effect=AssertionError('probe')),redirect_stdout(io.StringIO()) as out:
            self.assertEqual(m.main(['status']),0)
        self.assertFalse(json.loads(out.getvalue())['automatic_install_hook'])

    def test_prepare_cli_does_not_download(self):
        with patch.object(m.OllamaClient,'call',side_effect=AssertionError('network')),redirect_stdout(io.StringIO()) as out:
            self.assertEqual(m.main(['prepare']),0)
        self.assertEqual(json.loads(out.getvalue())['state'],'CONSENT_REQUIRED')

    def test_probe_cli_without_grant_zero_calls(self):
        with patch.object(m.PlatformReader,'__call__',side_effect=AssertionError('probe')),redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(['probe','--disk-root','/fixture']),2)


class PinnedLifecycleTests(unittest.TestCase):
    def fixture(self, directory, payload=b'owned synthetic blob', *, fetcher=None,
                actions=('stage', 'cleanup'), expiry=100, max_download=None):
        import hashlib
        root = Path(directory).resolve()/'stage'
        root.mkdir(mode=0o700)
        sha = hashlib.sha256(payload).hexdigest()
        candidate = {'id': 'fixture:1', 'provider_version': '0.40.13',
                     'manifest_sha256': 'b'*64,
                     'layers': [{'digest': 'sha256:'+sha, 'size': len(payload)}]}
        catalog = {'models': [candidate]}
        blob = m.catalog_blob(candidate, catalog, kind='model-blob', sha256=sha)
        binding = m.lifecycle_binding('node',root,candidate,[blob])
        consent = m.LifecycleConsent('node', binding, expiry, frozenset(actions))
        budget = m.deployment.Budget((len(payload) if max_download is None else max_download)/1024**3,
                                     (len(payload)+3*1024**2)/1024**3, 1, 0, 30)
        journal=m.deployment.DurableJournal(root/'journal.json','node')
        try:
            stage=m.PinnedStage('node',root,candidate,[blob],consent,budget,journal,
                fetcher=fetcher or (lambda b,t:io.BytesIO(payload)),wall_clock=lambda:1,catalog=catalog)
        except BaseException:
            journal.close();raise
        self.addCleanup(journal.close);self.addCleanup(stage.close)
        return stage,consent,blob,journal

    def test_invalid_budget_and_node_refuse_before_opening_stage_root(self):
        with tempfile.TemporaryDirectory() as d:
            stage,consent,_,journal=self.fixture(d)
            with patch.object(m.os,'open',side_effect=AssertionError('opened')):
                with self.assertRaisesRegex(m.Stopped,'LIFECYCLE_BUDGET'):
                    m.PinnedStage('node',stage.root,stage.candidate,stage.blobs,consent,None,journal)
                with self.assertRaisesRegex(m.Stopped,'LIFECYCLE_NODE'):
                    m.PinnedStage('',stage.root,stage.candidate,stage.blobs,consent,
                                  stage.runner.approval.budget,journal)

    def test_effect_construction_failure_closes_owned_root_fd(self):
        with tempfile.TemporaryDirectory() as d:
            stage,consent,_,journal=self.fixture(d)
            original_close=m.os.close
            with patch.object(m.deployment,'Effect',side_effect=ValueError('fixture-only')), \
                 patch.object(m.os,'close',wraps=original_close) as close:
                with self.assertRaises(ValueError):
                    m.PinnedStage('node',stage.root,stage.candidate,stage.blobs,consent,
                        stage.runner.approval.budget,journal,catalog={'models':[stage.candidate]},wall_clock=lambda:1)
                close.assert_called_once()

    def test_peak_disk_includes_existing_files_and_journal_overhead(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,blob,_=self.fixture(d)
            peak=stage.effects[0].peak_disk_gb*1024**3
            self.assertGreaterEqual(peak,blob.size+2*1024**2)
            self.assertGreater(peak,blob.size)

    def close_failure(self, stage):
        original_close, original_fstat = m.os.close, m.os.fstat
        attempted = []
        def close(fd):
            if attempted and fd == attempted[0]:
                self.fail('ambiguous close retried')
            info=original_fstat(fd)
            owned=any((info.st_dev,info.st_ino)==(r['device'],r['inode'])
                      for r in stage.receipts.values())
            if owned:
                attempted.append(fd)
                original_close(fd)  # kernel already closed; raised outcome is ambiguous
                raise OSError('PRIVATE close diagnostic')
            return original_close(fd)
        def fstat(fd):
            if fd in attempted:self.fail('ambiguous closed FD inspected')
            return original_fstat(fd)
        return close,fstat,attempted

    def test_original_close_raise_consumed_once_no_publish_or_blind_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            stage,consent,blob,_=self.fixture(d)
            close,fstat,attempted=self.close_failure(stage)
            with patch.object(m.os,'close',side_effect=close),patch.object(m.os,'fstat',side_effect=fstat):
                outcome=stage._stage(stage.effects[0],30)
            self.assertEqual(outcome,'UNKNOWN');self.assertEqual(len(attempted),1)
            self.assertEqual(stage.failure,'STAGE_CLOSE_UNKNOWN')
            self.assertEqual(stage.additional,['STAGE_CLOSE_UNKNOWN'])
            self.assertFalse((stage.root/blob.name).exists())
            self.assertTrue((stage.root/(blob.name+'.part')).exists())
            with self.assertRaisesRegex(m.Stopped,'CLEANUP_CLOSE_UNKNOWN'):stage.cleanup(consent)

    def test_business_primary_retained_when_final_close_also_raises(self):
        with tempfile.TemporaryDirectory() as d:
            stage,consent,_,_=self.fixture(d,fetcher=lambda *_:io.BytesIO(b'X'*20))
            close,fstat,attempted=self.close_failure(stage)
            with patch.object(m.os,'close',side_effect=close),patch.object(m.os,'fstat',side_effect=fstat):
                outcome=stage._stage(stage.effects[0],30)
            self.assertEqual(outcome,'UNKNOWN');self.assertEqual(len(attempted),1)
            self.assertEqual(stage.failure,'STAGE_HASH_MISMATCH')
            self.assertEqual(stage.additional,['STAGE_CLOSE_UNKNOWN'])
            with self.assertRaisesRegex(m.Stopped,'CLEANUP_CLOSE_UNKNOWN'):stage.cleanup(consent)

    def test_stage_exact_bytes_never_claims_install_or_qualification(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,blob,_=self.fixture(d)
            result=stage.stage()
            self.assertEqual(result['state'],'STAGED_NOT_INSTALLED')
            self.assertEqual(result['installation'],'NOT_PERFORMED')
            self.assertEqual(result['task_qualification'],'NOT_RUN')
            self.assertEqual((stage.root/blob.name).read_bytes(),b'owned synthetic blob')

    def test_consent_declined_before_fetch_or_new_file(self):
        with tempfile.TemporaryDirectory() as d,self.assertRaisesRegex(m.Stopped,'LIFECYCLE_CONSENT_REQUIRED'):
            self.fixture(d,actions=(),fetcher=lambda *_:self.fail('network'))

    def test_expired_lifecycle_consent_rejected(self):
        with tempfile.TemporaryDirectory() as d,self.assertRaisesRegex(m.Stopped,'LIFECYCLE_CONSENT_REQUIRED'):
            self.fixture(d,expiry=1)

    def test_budget_insufficient_zero_fetch(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,blob,_=self.fixture(d,max_download=0,fetcher=lambda *_:self.fail('fetch'))
            result=stage.stage()
            self.assertEqual(result['effects'][0]['state'],'BUDGET_EXCEEDED')
            self.assertFalse((stage.root/blob.name).exists())

    def test_hash_failure_retains_partial_and_blocks_retry(self):
        calls=[]
        def fetch(*_):calls.append(1);return io.BytesIO(b'X'*20)
        with tempfile.TemporaryDirectory() as d:
            stage,_,blob,_=self.fixture(d,fetcher=fetch)
            self.assertEqual(stage.stage()['reason'],'STAGE_HASH_MISMATCH')
            self.assertTrue((stage.root/(blob.name+'.part')).exists())
            self.assertEqual(stage.stage()['effects'][0]['state'],'RECONCILIATION_REQUIRED')
            self.assertEqual(calls,[1])

    def test_short_download_does_not_complete(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,_,_=self.fixture(d,fetcher=lambda *_:io.BytesIO(b'part'))
            self.assertEqual(stage.stage()['reason'],'STAGE_LENGTH_MISMATCH')

    def test_extra_download_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,_,_=self.fixture(d,fetcher=lambda *_:io.BytesIO(b'X'*100))
            self.assertEqual(stage.stage()['reason'],'STAGE_SIZE_LIMIT')

    def test_download_error_retained_without_raw_diagnostic(self):
        def fail(*_):raise OSError('PRIVATE token must not escape')
        with tempfile.TemporaryDirectory() as d:
            stage,_,_,_=self.fixture(d,fetcher=fail)
            result=stage.stage()
            self.assertEqual(result['reason'],'STAGE_IO_UNKNOWN')
            self.assertNotIn('PRIVATE',json.dumps(result))

    def test_preexisting_final_file_never_overwritten_or_removed(self):
        with tempfile.TemporaryDirectory() as d:
            stage,consent,blob,_=self.fixture(d,fetcher=lambda *_:self.fail('fetch'))
            f=stage.root/blob.name;f.write_bytes(b'prior')
            self.assertEqual(stage.stage()['reason'],'STAGE_FILE_CONFLICT')
            stage.cleanup(consent)
            self.assertEqual(f.read_bytes(),b'prior')

    def test_cleanup_only_owned_stage_journal_retained(self):
        with tempfile.TemporaryDirectory() as d:
            stage,consent,blob,journal=self.fixture(d)
            self.assertEqual(stage.stage()['state'],'STAGED_NOT_INSTALLED')
            result=stage.cleanup(consent)
            self.assertFalse((stage.root/blob.name).exists())
            self.assertTrue(journal.path.exists())
            self.assertFalse(result['runtime_uninstalled'])

    def test_cleanup_partial_after_failure_never_clears_unknown_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            stage,consent,blob,_=self.fixture(d,fetcher=lambda *_:io.BytesIO(b'part'))
            stage.stage();stage.cleanup(consent)
            self.assertFalse((stage.root/(blob.name+'.part')).exists())
            self.assertEqual(stage.stage()['effects'][0]['state'],'RECONCILIATION_REQUIRED')

    def test_cleanup_without_exact_scope_does_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            stage,consent,blob,_=self.fixture(d)
            stage.stage()
            no=m.LifecycleConsent('node',consent.binding,100,frozenset({'stage'}))
            with self.assertRaisesRegex(m.Stopped,'LIFECYCLE_CONSENT_REQUIRED'):stage.cleanup(no)
            self.assertTrue((stage.root/blob.name).exists())

    def test_cleanup_mutated_owned_file_refused(self):
        with tempfile.TemporaryDirectory() as d:
            stage,consent,blob,_=self.fixture(d);stage.stage()
            (stage.root/blob.name).write_bytes(b'modified')
            with self.assertRaisesRegex(m.Stopped,'CLEANUP_IDENTITY_UNKNOWN'):stage.cleanup(consent)

    def test_stage_root_replaced_stops_without_following(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,_,_=self.fixture(d)
            stage.root.rename(stage.root.with_name('old'))
            stage.root.symlink_to(stage.root.with_name('old'),target_is_directory=True)
            with self.assertRaisesRegex(m.Stopped,'STAGE_ROOT_CHANGED'):stage.stage()

    def test_blob_source_and_catalog_pin_rejected(self):
        with self.assertRaisesRegex(m.Stopped,'ASSET_SOURCE'):
            m.PinnedBlob('https://example.com/blob',1,'a'*64,'model-blob')
        with self.assertRaisesRegex(m.Stopped,'ASSET_NOT_PINNED'):
            m.catalog_blob({'id':'x','layers':[]},{'models':[{'id':'x','layers':[]}]},
                           kind='model-blob',sha256='a'*64)

    def test_staging_synthetic_or_install_evidence_never_qualifies(self):
        candidate={'provider_version':'0.40.13','manifest_sha256':'a'*64}
        existing={'provider_version':'0.40.13','model_digest':'a'*64}
        self.assertFalse(m.lifecycle_readiness(existing,candidate)['qualified'])
        self.assertFalse(m.lifecycle_readiness(existing,candidate,evidence_kind='REAL',
            real_runtime_ref='real-runtime-ref',real_task_ref='real-task-ref')['qualified'])
        self.assertEqual(m.lifecycle_readiness({'pending_unknown':True},candidate)['state'],'UNKNOWN')

    def test_reuse_requires_authorized_actual_api_inspection(self):
        transport=FakeTransport()
        client=m.OllamaClient('http://127.0.0.1:11434','0.40.13','qwen3.5:4b',PIN,
                               transport=transport,local_service_ref='owner')
        candidate={'id':client.model,'provider_version':client.version,'manifest_sha256':PIN}
        grant=m.Grant('node',frozenset({'inspect-runtime'}),100,'approval',m.digest(candidate))
        result=m.inspect_existing_lifecycle('node',grant,client,candidate,now=1)
        self.assertEqual(result['state'],'REUSE_EXISTING_TASK_QUALIFICATION_REQUIRED')
        self.assertFalse(result['qualified']);self.assertEqual(len(transport.calls),2)

    def test_cleanup_deadline_does_not_remove_owned_file(self):
        with tempfile.TemporaryDirectory() as d:
            stage,consent,blob,_=self.fixture(d);stage.stage()
            stage.started=stage.clock()-31
            with self.assertRaisesRegex(m.Stopped,'CLEANUP_DEADLINE'):stage.cleanup(consent)
            self.assertTrue((stage.root/blob.name).exists())

    def test_expiry_between_admission_and_stage_stops_before_fetch(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,_,_=self.fixture(d,fetcher=lambda *_:self.fail('fetch'))
            stage.wall_clock=lambda:100
            with self.assertRaisesRegex(m.Stopped,'LIFECYCLE_CONSENT_REQUIRED'):stage.stage()
            self.assertEqual(stage.runner.iterations,0)
            self.assertEqual(stage.receipts,{})

    def test_restart_unknown_retains_reconcile_gate_without_fetch(self):
        with tempfile.TemporaryDirectory() as d:
            stage,consent,blob,journal=self.fixture(d,fetcher=lambda *_:io.BytesIO(b'part'))
            stage.stage();stage.close();journal.close()
            with m.deployment.DurableJournal(stage.root/'journal.json','node') as recovered:
                new=m.PinnedStage('node',stage.root,stage.candidate,stage.blobs,consent,
                    stage.runner.approval.budget,recovered,fetcher=lambda *_:self.fail('fetch'),
                    wall_clock=lambda:1,catalog={'models':[stage.candidate]})
                try:
                    self.assertEqual(new.stage()['effects'][0]['state'],'RECONCILIATION_REQUIRED')
                    self.assertEqual(new.receipts,{})  # cannot invent cleanup ownership on restart
                finally:new.close()

    def test_reuse_decline_zero_http(self):
        transport=FakeTransport()
        client=m.OllamaClient('http://127.0.0.1:11434','0.40.13','qwen3.5:4b',PIN,
                              transport=transport,local_service_ref='owner')
        c={'id':client.model,'provider_version':client.version,'manifest_sha256':PIN}
        g=m.Grant('node',frozenset(),100,'declined',m.digest(c))
        with self.assertRaises(m.Stopped):m.inspect_existing_lifecycle('node',g,client,c,now=1)
        self.assertEqual(transport.calls,[])


class RuntimeInstallTests(unittest.TestCase):
    def fixture(self,d,*,members=None,mutate_expected=None,fetch=None,actions=None):
        import tarfile,hashlib
        # Real extraction of synthetic bytes only; never opens the actual release archive.
        members=members or [('ollama',b'synthetic-runtime','0','',0o755),
                           ('LICENSE',b'synthetic-license','0','',0o644),
                           ('lib',b'','5','',0o755),
                           ('lib/a.dylib',b'synthetic-library','0','',0o755),
                           ('lib/a.0.dylib',b'','2','a.dylib',0o755)]
        data=io.BytesIO();expected=[]
        with tarfile.open(fileobj=data,mode='w:gz') as bundle:
            for name,body,kind,target,mode in members:
                item=tarfile.TarInfo(name);item.mode=mode;item.type=kind.encode()
                item.size=len(body);item.linkname=target
                bundle.addfile(item,io.BytesIO(body) if kind=='0' else None)
                expected.append(dict(name=name,size=len(body),type=kind,mode=oct(mode),linkname=target))
        payload=data.getvalue();sha=hashlib.sha256(payload).hexdigest()
        asset={'name':'ollama-darwin.tgz','bytes':len(payload),'sha256':sha,
               'members':expected,'unpacked_bytes':sum(len(x[1]) for x in members)}
        if mutate_expected:mutate_expected(asset)
        c={'id':'fixture:1','provider_version':'0.40.13','manifest_sha256':'b'*64,'layers':[]}
        catalog={'models':[c],'runtime':{'version':'0.40.13','darwin_asset':asset}}
        blob=m.catalog_blob(c,catalog,kind='runtime-archive',sha256=sha)
        root=Path(d).resolve()/'stage';root.mkdir(mode=0o700)
        binding=m.lifecycle_binding('node',root,c,[blob])
        grant=m.LifecycleConsent('node',binding,100,frozenset(actions or
            {'stage','cleanup','install-runtime','uninstall-runtime','rollback-runtime'}))
        journal=m.deployment.DurableJournal(root/'journal.json','node')
        try:
            stage=m.PinnedStage('node',root,c,[blob],grant,
                m.deployment.Budget(1,1,2,0,30),journal,
                fetcher=fetch or (lambda *_:io.BytesIO(payload)),wall_clock=lambda:1,catalog=catalog)
        except BaseException:journal.close();raise
        self.addCleanup(journal.close);self.addCleanup(stage.close)
        return stage,grant,asset

    def test_actual_catalog_has_pinned_59_member_layout_not_runtime_validation(self):
        catalog=m.load_catalog();asset=catalog['runtime']['darwin_asset']
        self.assertEqual(len(m.runtime_layout(asset)),59)
        self.assertEqual(asset['unpacked_bytes'],608745773)

    def test_install_synthetic_archive_preserves_notices_links_and_never_starts(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,asset=self.fixture(d);stage.stage();result=stage.install_runtime()
            self.assertEqual(result['state'],'RUNTIME_FILES_INSTALLED_UNVALIDATED')
            self.assertFalse(result['service_started']);self.assertEqual(result['task_qualification'],'NOT_RUN')
            base=stage.root/stage.runtime_name
            self.assertEqual((base/'ollama').read_bytes(),b'synthetic-runtime')
            self.assertEqual((base/'LICENSE').read_bytes(),b'synthetic-license')
            self.assertEqual((base/'lib/a.0.dylib').readlink(),Path('a.dylib'))
            self.assertEqual((base/'ollama').stat().st_mode & 0o777,0o755)

    def test_uninstall_same_owned_runtime_only_stage_and_journal_retained(self):
        with tempfile.TemporaryDirectory() as d:
            stage,grant,_=self.fixture(d);stage.stage();stage.install_runtime()
            old=stage.root/stage.runtime_name
            result=stage.remove_runtime(grant,idle_confirmed=True)
            self.assertFalse(old.exists());self.assertEqual(result['state'],'OWNED_RUNTIME_REMOVED')
            self.assertTrue((stage.root/'journal.json').exists())
            self.assertTrue((stage.root/stage.blobs[0].name).exists())

    def test_uninstall_missing_idle_confirmation_refuses_without_changes(self):
        with tempfile.TemporaryDirectory() as d:
            stage,grant,_=self.fixture(d);stage.stage();stage.install_runtime()
            with self.assertRaisesRegex(m.Stopped,'RUNTIME_IDLE_UNCONFIRMED'):stage.remove_runtime(grant)
            self.assertTrue((stage.root/stage.runtime_name/'ollama').exists())

    def test_mutated_runtime_refuses_entire_uninstall(self):
        with tempfile.TemporaryDirectory() as d:
            stage,grant,_=self.fixture(d);stage.stage();stage.install_runtime()
            (stage.root/stage.runtime_name/'ollama').write_bytes(b'changed')
            with self.assertRaises(m.Stopped):stage.remove_runtime(grant,idle_confirmed=True)
            self.assertTrue((stage.root/stage.runtime_name/'LICENSE').exists())

    def test_runtime_root_replacement_refuses_uninstall(self):
        with tempfile.TemporaryDirectory() as d:
            stage,grant,_=self.fixture(d);stage.stage();stage.install_runtime()
            directory=stage.root/stage.runtime_name
            directory.rename(directory.with_name('prior'))
            directory.mkdir(mode=0o700)
            with self.assertRaisesRegex(m.Stopped,'RUNTIME_REMOVE_IDENTITY_UNKNOWN'):
                stage.remove_runtime(grant,idle_confirmed=True)

    def test_exact_archive_metadata_mismatch_refuses_before_creating_directory(self):
        def mutate(asset):asset['members'][1]['mode']='0o755'
        with tempfile.TemporaryDirectory() as d:
            stage,_,_=self.fixture(d,mutate_expected=mutate);stage.stage()
            self.assertEqual(stage.install_runtime()['reason'],'RUNTIME_ARCHIVE_LAYOUT_CHANGED')
            self.assertIsNone(stage.runtime_name)

    def test_stage_pin_changed_before_install_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,_=self.fixture(d);stage.stage()
            (stage.root/stage.blobs[0].name).write_bytes(b'changed')
            self.assertEqual(stage.install_runtime()['reason'],'RUNTIME_ARCHIVE_CHANGED')

    def test_layout_rejects_escape_absolute_link_cycle_and_device(self):
        cases=[('../ollama',b'x','0','',0o755),('/ollama',b'x','0','',0o755),
               ('link',b'','2','../../x',0o755),('link',b'','2','link',0o755),
               ('device',b'','3','',0o755)]
        for bad in cases:
            with self.subTest(bad=bad[0]),tempfile.TemporaryDirectory() as d,self.assertRaises(m.Stopped):
                self.fixture(d,members=[('ollama',b'x','0','',0o755),bad])

    def test_install_conflict_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,asset=self.fixture(d);stage.stage()
            final=stage.root/(asset['sha256']+'.runtime');final.mkdir(mode=0o700)
            (final/'keep').write_bytes(b'prior')
            self.assertEqual(stage.install_runtime()['reason'],'RUNTIME_INSTALL_CONFLICT')
            self.assertEqual((final/'keep').read_bytes(),b'prior')

    def test_install_permission_expiry_has_zero_effect_iteration(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,_=self.fixture(d);stage.stage();before=stage.runner.iterations
            stage.wall_clock=lambda:100
            with self.assertRaisesRegex(m.Stopped,'LIFECYCLE_CONSENT_REQUIRED'):stage.install_runtime()
            self.assertEqual(stage.runner.iterations,before)

    def test_unowned_added_file_prevents_any_removal(self):
        with tempfile.TemporaryDirectory() as d:
            stage,grant,_=self.fixture(d);stage.stage();stage.install_runtime()
            (stage.root/stage.runtime_name/'unowned').write_bytes(b'outside-owned-list')
            with self.assertRaises(m.Stopped):stage.remove_runtime(grant,idle_confirmed=True)
            self.assertTrue((stage.root/stage.runtime_name/'LICENSE').exists())


    def test_runtime_readonly_receipt_verifies_owned_binary_without_start(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,_=self.fixture(d);stage.stage();stage.install_runtime()
            facts=stage.validate_runtime_files()
            self.assertEqual(facts['runtime_validation'],'NOT_RUN')
            self.assertTrue(facts['runtime_path'].endswith('/ollama'))
            self.assertEqual(facts['binary_receipt']['sha256'],stage.runtime_tree['ollama']['sha256'])

    def test_install_and_stage_share_original_budget(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,_=self.fixture(d);stage.stage();before=stage.runner.download_gb
            stage.install_runtime()
            self.assertEqual(stage.runner.download_gb,before)
            self.assertEqual(stage.runner.iterations,2)

    def test_partial_runtime_failure_requires_explicit_owned_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            stage,grant,_=self.fixture(d);stage.stage()
            with patch.object(m.os,'symlink',side_effect=OSError('fixture-only')):
                self.assertEqual(stage.install_runtime()['state'],'STOP')
            original=stage.root/stage.runtime_name
            self.assertTrue(original.exists())
            result=stage.remove_runtime(grant,idle_confirmed=True,rollback=True)
            self.assertEqual(result['state'],'OWNED_RUNTIME_REMOVED')
            self.assertFalse(original.exists())
            self.assertTrue(stage.runner.pending is not None)  # no authority/budget reset

    def test_install_budget_exhaustion_no_extraction(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,_=self.fixture(d);stage.stage()
            stage.runner.iterations=stage.runner.approval.budget.max_iterations
            result=stage.install_runtime()
            self.assertEqual(result['effect']['state'],'BUDGET_EXCEEDED')
            self.assertIsNone(stage.runtime_name)

    def test_runtime_parent_close_failure_once_preserves_fixed_primary(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,_=self.fixture(d);stage.stage();stage.install_runtime()
            closed=[];original=m.os.close
            def fail(fd):
                self.assertNotIn(fd,closed);closed.append(fd);original(fd)
                raise OSError('PRIVATE close')
            with patch.object(m.os,'close',side_effect=fail),self.assertRaisesRegex(m.Stopped,'RUNTIME_PARENT_CLOSE_UNKNOWN'):
                stage._runtime_parent('lib/a.dylib')
            self.assertEqual(len(closed),2)
            self.assertEqual(stage.additional[-2:],['RUNTIME_PARENT_CLOSE_UNKNOWN','RUNTIME_PARENT_CLOSE_UNKNOWN'])


class ModelRegistrationTests(unittest.TestCase):
    def fixture(self,d):
        import hashlib
        contents=[b'synthetic model layer',b'{"synthetic":"config"}']
        descriptors=[{'digest':'sha256:'+hashlib.sha256(x).hexdigest(),'size':len(x)} for x in contents]
        manifest=json.dumps({'schemaVersion':2,'config':descriptors[1],
                             'layers':[descriptors[0]]},separators=(',',':'))
        candidate={'id':'fixture:1','provider_version':'0.40.13',
            'manifest_sha256':hashlib.sha256(manifest.encode()).hexdigest(),
            'layers':[descriptors[0]],'config_blob':descriptors[1],'manifest_json':manifest}
        catalog={'models':[candidate],'runtime':{'version':'0.40.13'}}
        blobs=[m.catalog_blob(candidate,catalog,kind='model-blob',sha256=x['digest'].split(':')[1])
               for x in descriptors]
        mapping={b.sha256:content for b,content in zip(blobs,contents)}
        root=Path(d).resolve()/'stage';root.mkdir(mode=0o700)
        grant=m.LifecycleConsent('node',m.lifecycle_binding('node',root,candidate,blobs),100,
            frozenset({'stage','cleanup','install-model','uninstall-model','rollback-model'}))
        journal=m.deployment.DurableJournal(root/'journal.json','node')
        try:
            stage=m.PinnedStage('node',root,candidate,blobs,grant,m.deployment.Budget(1,1,3,0,30),
                journal,fetcher=lambda blob,_:io.BytesIO(mapping[blob.sha256]),wall_clock=lambda:1,catalog=catalog)
        except BaseException:journal.close();raise
        self.addCleanup(journal.close);self.addCleanup(stage.close)
        return stage,grant,contents

    def test_catalog_manifests_include_pinned_config_and_fit_bounded_loader(self):
        catalog=m.load_catalog()
        for candidate in catalog['models']:
            manifest=m.model_manifest(candidate)
            self.assertEqual(m.hashlib.sha256(manifest).hexdigest(),candidate['manifest_sha256'])
            self.assertEqual(m.catalog_blob(candidate,catalog,kind='model-blob',
                sha256=candidate['config_blob']['digest'].split(':')[1]).size,candidate['config_blob']['size'])

    def test_synthetic_model_registration_exact_manifest_and_copied_blobs(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,contents=self.fixture(d);stage.stage();before=stage.runner.download_gb
            result=stage.install_model()
            self.assertEqual(result['state'],'MODEL_FILES_REGISTERED_UNVALIDATED')
            self.assertEqual(result['task_qualification'],'NOT_RUN');self.assertFalse(result['service_started'])
            self.assertEqual(stage.runner.download_gb,before);self.assertEqual(stage.runner.iterations,3)
            root=stage.root/stage.model_name
            manifest=root/'manifests/registry.ollama.ai/library/fixture/1'
            self.assertEqual(manifest.read_text(),stage.candidate['manifest_json'])
            for blob,content in zip(stage.blobs,contents):
                target=root/('blobs/sha256-'+blob.sha256)
                self.assertEqual(target.read_bytes(),content)
                self.assertEqual(target.stat().st_nlink,1)
                self.assertNotEqual(target.stat().st_ino,(stage.root/blob.name).stat().st_ino)

    def test_registration_requires_every_owned_staged_layer_and_config(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,_=self.fixture(d)
            self.assertEqual(stage.install_model()['reason'],'MODEL_STAGE_REQUIRED')
            self.assertIsNone(stage.model_name)

    def test_registered_files_readback_not_inference_or_qualification(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,_=self.fixture(d);stage.stage();stage.install_model()
            result=stage.validate_model_files()
            self.assertFalse(result['qualified']);self.assertEqual(result['model_validation'],'NOT_RUN')
            self.assertEqual(result['manifest_sha256'],stage.candidate['manifest_sha256'])

    def test_model_uninstall_preserves_stage_journal_and_other_models(self):
        with tempfile.TemporaryDirectory() as d:
            stage,grant,_=self.fixture(d);stage.stage();stage.install_model()
            root=stage.root/stage.model_name
            prior=stage.root/'another-model';prior.mkdir();(prior/'keep').write_bytes(b'prior')
            result=stage.remove_model(grant,idle_confirmed=True)
            self.assertEqual(result['state'],'OWNED_MODEL_REMOVED');self.assertFalse(root.exists())
            self.assertEqual((prior/'keep').read_bytes(),b'prior')
            self.assertTrue((stage.root/'journal.json').exists())
            self.assertTrue((stage.root/stage.blobs[0].name).exists())

    def test_changed_staged_config_is_refused_no_manifest_published(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,_=self.fixture(d);stage.stage()
            (stage.root/stage.blobs[1].name).write_bytes(b'changed')
            result=stage.install_model()
            self.assertEqual(result['state'],'STOP')
            self.assertEqual(result['reason'],'MODEL_STAGE_CHANGED')
            self.assertFalse(stage.model_complete)

    def test_changed_registered_model_blocks_uninstall_before_any_delete(self):
        with tempfile.TemporaryDirectory() as d:
            stage,grant,_=self.fixture(d);stage.stage();stage.install_model()
            target=stage.root/stage.model_name/('blobs/sha256-'+stage.blobs[0].sha256)
            target.write_bytes(b'changed')
            with self.assertRaises(m.Stopped):stage.remove_model(grant,idle_confirmed=True)
            self.assertTrue(target.exists())

    def test_registry_manifest_pin_and_layer_binding_refused(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,_=self.fixture(d)
            candidate=dict(stage.candidate);candidate['manifest_json']+=' '
            with self.assertRaisesRegex(m.Stopped,'MODEL_MANIFEST_HASH'):m.model_manifest(candidate)
            candidate=dict(stage.candidate);candidate['layers']=[]
            with self.assertRaisesRegex(m.Stopped,'MODEL_LAYER_BINDING'):m.model_manifest(candidate)

    def test_registration_does_not_reset_unknown_or_execution_budget(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,_=self.fixture(d);stage.stage()
            stage.runner.recovery_required=True
            result=stage.install_model()
            self.assertEqual(result['effect']['state'],'RECONCILIATION_REQUIRED')
            self.assertIsNone(stage.model_name)

    def test_parent_failure_precedes_opening_staged_input_fd(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,_=self.fixture(d);stage.stage();original=stage._runtime_parent
            opened=[];real_open=m.os.open
            def parent(name,**kwargs):
                if name.startswith('blobs/sha256-'):raise m.Stopped('SYNTHETIC_PARENT_FAILURE')
                return original(name,**kwargs)
            def observe(path,*args,**kwargs):
                opened.append(str(path));return real_open(path,*args,**kwargs)
            with patch.object(stage,'_runtime_parent',side_effect=parent),patch.object(m.os,'open',side_effect=observe):
                result=stage.install_model()
            self.assertEqual(result['reason'],'SYNTHETIC_PARENT_FAILURE')
            self.assertFalse(any(path.endswith('.blob') for path in opened))

    def test_combined_peak_reserves_runtime_model_and_staging_before_fetch(self):
        import hashlib,tarfile
        with tempfile.TemporaryDirectory() as d:
            original,_,_=self.fixture(d)
            candidate=original.candidate
            buffer=io.BytesIO()
            with tarfile.open(fileobj=buffer,mode='w:gz') as archive:
                member=tarfile.TarInfo('ollama');member.mode=0o755;member.size=80*1024
                archive.addfile(member,io.BytesIO(b'x'*member.size))
            raw=buffer.getvalue();sha=hashlib.sha256(raw).hexdigest()
            asset={'name':'ollama-darwin.tgz','bytes':len(raw),'sha256':sha,'unpacked_bytes':80*1024,
                   'members':[{'name':'ollama','size':80*1024,'type':'0','mode':'0o755','linkname':''}]}
            catalog={'models':[candidate],'runtime':{'version':'0.40.13','darwin_asset':asset}}
            root=Path(d).resolve()/'combined';root.mkdir(mode=0o700)
            blobs=list(original.blobs)+[m.catalog_blob(candidate,catalog,kind='runtime-archive',sha256=sha)]
            consent=m.LifecycleConsent('node',m.lifecycle_binding('node',root,candidate,blobs),100,
                frozenset({'stage','install-runtime','install-model'}))
            # Each retained install fits the old max calculation; their sum does not.
            existing=4096  # journal lock allocated-block conservative bound
            base=existing+sum(b.size for b in blobs)+2*1024**2+4096*(len(blobs)+2)
            runtime=asset['unpacked_bytes']+4096*len(asset['members'])
            model=sum(x['size'] for x in candidate['layers']+[candidate['config_blob']])+len(candidate['manifest_json'].encode())+4096*12
            cap=base+max(runtime,model)+1024
            with m.deployment.DurableJournal(root/'journal.json','node') as journal:
                stage=m.PinnedStage('node',root,candidate,blobs,consent,
                    m.deployment.Budget(1,cap/1024**3,5,0,30),journal,
                    fetcher=lambda *_:self.fail('no fetch under inadequate combined budget'),
                    wall_clock=lambda:1,catalog=catalog)
                try:
                    actual=stage.effects[0].peak_disk_gb*1024**3
                    self.assertGreater(actual,cap)
                    self.assertEqual(stage.install_effect.peak_disk_gb,stage.model_effect.peak_disk_gb)
                    result=stage.stage()
                    self.assertEqual(result['effects'][0]['state'],'BUDGET_EXCEEDED')
                    self.assertEqual(stage.runner.iterations,0)
                finally:stage.close()

    def test_full_lifecycle_iteration_count_refused_before_any_root_open(self):
        with tempfile.TemporaryDirectory() as d:
            stage,consent,_=self.fixture(d)
            with patch.object(m.os,'open',side_effect=AssertionError('open')):
                with self.assertRaisesRegex(m.Stopped,'LIFECYCLE_ITERATION_BUDGET'):
                    m.PinnedStage('node',stage.root,stage.candidate,stage.blobs,consent,
                        m.deployment.Budget(1,1,2,0,30),None,catalog=stage.catalog)


if __name__=='__main__':unittest.main()


class OwnershipRestoreTests(unittest.TestCase):
    """Cross-command restoration of synthetic creations; records are not permits."""
    runtime_fixture = RuntimeInstallTests.fixture
    model_fixture = ModelRegistrationTests.fixture

    def fresh(self, stage, *, actions=None, expires=100):
        return m.LifecycleConsent(stage.node_id,stage.binding,expires,frozenset(actions or
            {'restore-ownership','save-ownership','cleanup','uninstall-runtime','rollback-runtime',
             'uninstall-model','rollback-model'}))

    def prepare(self,d,*,model=False):
        if model:
            stage,_,_=self.model_fixture(d)
            # Only a catalog identity for an unused runtime; no runtime source is read.
            stage.catalog['runtime']['darwin_asset']={'sha256':'f'*64}
        else:
            stage,_,_=self.runtime_fixture(d)
        stage.consent=self.fresh(stage,actions=set(stage.consent.actions)|{'save-ownership','restore-ownership'})
        self.assertEqual(stage.stage()['state'],'STAGED_NOT_INSTALLED')
        result=stage.install_model() if model else stage.install_runtime()
        self.assertIn(result['state'],{'MODEL_FILES_REGISTERED_UNVALIDATED','RUNTIME_FILES_INSTALLED_UNVALIDATED'})
        stage.save_ownership()
        return stage

    def reopen(self,stage,*,grant=None,budget=None):
        old=stage.journal.load('node')
        stage.close();stage.journal.close()
        journal=m.deployment.DurableJournal(stage.root/'journal.json','node')
        self.addCleanup(journal.close)
        restored=m.PinnedStage.restore_owned('node',stage.root,stage.candidate,stage.blobs,
            grant or self.fresh(stage),budget or stage.runner.approval.budget,journal,
            wall_clock=lambda:1,catalog=stage.catalog)
        self.addCleanup(restored.close)
        return restored,old

    def test_runtime_save_reopen_revalidate_and_preserve_consumed_budget(self):
        with tempfile.TemporaryDirectory() as d:
            stage=self.prepare(d);restored,old=self.reopen(stage)
            result=restored.validate_runtime_files()
            self.assertEqual(result['runtime_validation'],'NOT_RUN')
            self.assertTrue(Path(result['runtime_path']).is_file())
            self.assertEqual(restored.activity,'NEVER_STARTED')
            current=restored.journal.load('node')
            for key in ('download_gb','peak_disk_gb','iterations','restarts','elapsed_seconds','state'):
                self.assertEqual(current[key],old[key])
            self.assertEqual(restored.runner.iterations,2)
            self.assertEqual(restored.effects,())

    def test_model_save_reopen_pinned_config_layers_manifest_not_qualified(self):
        with tempfile.TemporaryDirectory() as d:
            stage=self.prepare(d,model=True);restored,old=self.reopen(stage)
            result=restored.validate_model_files()
            self.assertEqual(result['model_validation'],'NOT_RUN');self.assertFalse(result['qualified'])
            self.assertTrue(Path(result['models_root']).is_dir())
            self.assertEqual(restored.runner.iterations,old['iterations'])

    def test_restore_requires_fresh_unexpired_exact_scope(self):
        with tempfile.TemporaryDirectory() as d:
            stage=self.prepare(d);stage.close();stage.journal.close()
            for grant in (self.fresh(stage,expires=0),self.fresh(stage,actions={'cleanup'}),
                          m.LifecycleConsent('wrong',stage.binding,100,frozenset({'restore-ownership'}))):
                with m.deployment.DurableJournal(stage.root/'journal.json','node') as journal:
                    with self.assertRaisesRegex(m.Stopped,'LIFECYCLE_CONSENT_REQUIRED'):
                        m.PinnedStage.restore_owned('node',stage.root,stage.candidate,stage.blobs,
                            grant,stage.runner.approval.budget,journal,wall_clock=lambda:1,catalog=stage.catalog)

    def test_legacy_journal_cannot_adopt_existing_tree(self):
        with tempfile.TemporaryDirectory() as d:
            stage,_,_=self.runtime_fixture(d);stage.stage();stage.install_runtime()
            stage.close();stage.journal.close()
            with m.deployment.DurableJournal(stage.root/'journal.json','node') as journal:
                with self.assertRaisesRegex(m.Stopped,'OWNERSHIP_NOT_RECORDED_NO_ADOPTION'):
                    m.PinnedStage.restore_owned('node',stage.root,stage.candidate,stage.blobs,
                        self.fresh(stage),stage.runner.approval.budget,journal,wall_clock=lambda:1,catalog=stage.catalog)

    def test_changed_owned_file_refuses_restore_without_writes(self):
        with tempfile.TemporaryDirectory() as d:
            stage=self.prepare(d);(stage.root/stage.runtime_name/'ollama').write_bytes(b'changed')
            stage.close();stage.journal.close()
            with m.deployment.DurableJournal(stage.root/'journal.json','node') as journal:
                before=journal.path.read_bytes()
                with self.assertRaises(m.Stopped):
                    m.PinnedStage.restore_owned('node',stage.root,stage.candidate,stage.blobs,
                        self.fresh(stage),stage.runner.approval.budget,journal,wall_clock=lambda:1,catalog=stage.catalog)
                self.assertEqual(journal.path.read_bytes(),before)

    def test_root_replacement_refuses_even_with_copied_record(self):
        with tempfile.TemporaryDirectory() as d:
            stage=self.prepare(d);stage.close();stage.journal.close()
            previous=stage.root.with_name('old-root');stage.root.rename(previous);stage.root.mkdir(mode=0o700)
            (stage.root/'journal.json').write_bytes((previous/'journal.json').read_bytes())
            with m.deployment.DurableJournal(stage.root/'journal.json','node') as journal:
                with self.assertRaisesRegex(m.Stopped,'RESTORE_ROOT_IDENTITY_CHANGED'):
                    m.PinnedStage.restore_owned('node',stage.root,stage.candidate,stage.blobs,
                        self.fresh(stage),stage.runner.approval.budget,journal,wall_clock=lambda:1,catalog=stage.catalog)

    def test_unknown_io_refused_and_pending_not_cleared_by_restore(self):
        with tempfile.TemporaryDirectory() as d:
            stage=self.prepare(d);owned=stage.journal.load_owned_files('node')
            owned['io_state']='UNKNOWN';stage.journal.save_owned_files('node',owned)
            stage.close();stage.journal.close()
            with m.deployment.DurableJournal(stage.root/'journal.json','node') as journal:
                with self.assertRaisesRegex(m.Stopped,'OWNERSHIP_BINDING_OR_IO_UNKNOWN'):
                    m.PinnedStage.restore_owned('node',stage.root,stage.candidate,stage.blobs,
                        self.fresh(stage),stage.runner.approval.budget,journal,wall_clock=lambda:1,catalog=stage.catalog)
        with tempfile.TemporaryDirectory() as d:
            stage=self.prepare(d);stage.journal({'state':'PENDING','effect':'e'*64})
            restored,old=self.reopen(stage)
            self.assertTrue(restored.runner.recovery_required)
            self.assertEqual(restored.journal.load('node')['state'],'PENDING')
            self.assertEqual(restored.runner.run(m.deployment.Effect('node','configure','fixture'))['state'],
                             'RECONCILIATION_REQUIRED')

    def test_activity_legacy_unknown_and_active_record_are_not_idle_evidence(self):
        for activity in (None,'POSSIBLY_ACTIVE','DIRECT_EXIT_DESCENDANTS_UNKNOWN'):
            with self.subTest(activity=activity),tempfile.TemporaryDirectory() as d:
                stage=self.prepare(d);owned=stage.journal.load_owned_files('node')
                if activity is None:owned.pop('activity')
                else:owned['activity']=activity
                stage.journal.save_owned_files('node',owned)
                restored,_=self.reopen(stage)
                self.assertEqual(restored.activity,activity or 'UNKNOWN')
                self.assertEqual(restored.validate_runtime_files()['runtime_validation'],'NOT_RUN')

    def test_prior_budget_and_exact_pins_not_relaxed_by_restore(self):
        with tempfile.TemporaryDirectory() as d:
            stage=self.prepare(d);stage.close();stage.journal.close()
            with m.deployment.DurableJournal(stage.root/'journal.json','node') as journal:
                with self.assertRaisesRegex(m.Stopped,'RESTORE_BUDGET_ALREADY_CONSUMED'):
                    m.PinnedStage.restore_owned('node',stage.root,stage.candidate,stage.blobs,
                        self.fresh(stage),m.deployment.Budget(1,1,1,0,30),journal,
                        wall_clock=lambda:1,catalog=stage.catalog)
                owned=journal.load_owned_files('node');owned['root_binding']='f'*64
                journal.save_owned_files('node',owned)
                with self.assertRaisesRegex(m.Stopped,'OWNERSHIP_BINDING_OR_IO_UNKNOWN'):
                    m.PinnedStage.restore_owned('node',stage.root,stage.candidate,stage.blobs,
                        self.fresh(stage),stage.runner.approval.budget,journal,
                        wall_clock=lambda:1,catalog=stage.catalog)

    def test_mark_persistence_failure_prevents_every_unlink(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            stage=self.prepare(d);restored,_=self.reopen(stage)
            with patch.object(restored.journal,'save_owned_files',side_effect=RuntimeError('synthetic save unknown')) as save:
                with patch.object(m.os,'unlink') as unlink:
                    with self.assertRaisesRegex(RuntimeError,'synthetic save unknown'):
                        restored.remove_runtime(self.fresh(stage),idle_confirmed=True)
                    self.assertEqual(save.call_count,1);unlink.assert_not_called()
            self.assertTrue((restored.root/restored.runtime_name/'ollama').exists())

    def test_partial_delete_failure_retains_unknown_snapshot(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            stage=self.prepare(d);restored,_=self.reopen(stage)
            original=m.os.unlink;calls=[]
            def fail_second(path,*args,**kwargs):
                calls.append(path)
                if len(calls)==2:raise OSError('synthetic second deletion failure')
                return original(path,*args,**kwargs)
            with patch.object(m.os,'unlink',side_effect=fail_second):
                with self.assertRaisesRegex(OSError,'synthetic second deletion failure'):
                    restored.remove_runtime(self.fresh(stage),idle_confirmed=True)
            self.assertEqual(len(calls),2)
            owned=restored.journal.load_owned_files('node')
            self.assertEqual(owned['io_state'],'UNKNOWN')
            self.assertTrue(owned['runtime']['tree'])
            self.assertTrue((restored.root/restored.runtime_name).exists())

    def test_restored_uninstall_checkpoints_empty_tree_preserves_pending_and_cost(self):
        with tempfile.TemporaryDirectory() as d:
            stage=self.prepare(d);stage.journal({'state':'PENDING','effect':'e'*64})
            restored,old=self.reopen(stage)
            self.assertEqual(restored.remove_runtime(self.fresh(stage),idle_confirmed=True)['state'],
                             'OWNED_RUNTIME_REMOVED')
            current=restored.journal.load('node');owned=restored.journal.load_owned_files('node')
            self.assertEqual(owned['runtime'],{'name':None,'complete':False,'tree':{}})
            self.assertEqual(owned['io_state'],'CONFIRMED')
            for key in ('download_gb','peak_disk_gb','iterations','restarts','state','effect'):
                self.assertEqual(current[key],old[key])
            self.assertGreaterEqual(current['elapsed_seconds'],old['elapsed_seconds'])
            self.assertTrue(restored.runner.recovery_required)

    def test_save_deadline_after_durable_checkpoint_stops_without_retry(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            stage=self.prepare(d);original=stage.journal.save_owned_files
            def saved_then_expired(node,snapshot):
                original(node,snapshot)
                stage.clock=lambda:stage.started+stage.max_seconds+1
            with patch.object(stage.journal,'save_owned_files',side_effect=saved_then_expired) as save:
                with self.assertRaisesRegex(m.Stopped,'OWNERSHIP_SAVE_DEADLINE'):
                    stage.save_ownership()
                self.assertEqual(save.call_count,1)
            owned=stage.journal.load_owned_files('node')
            self.assertEqual(owned['runtime']['name'],stage.runtime_name)
            self.assertEqual(owned['io_state'],'CONFIRMED')
            self.assertEqual(stage.journal.load('node')['iterations'],2)

    def test_record_does_not_authorize_uninstall_or_prove_idle(self):
        with tempfile.TemporaryDirectory() as d:
            stage=self.prepare(d);grant=self.fresh(stage,actions={'restore-ownership'})
            restored,_=self.reopen(stage,grant=grant)
            with self.assertRaisesRegex(m.Stopped,'LIFECYCLE_CONSENT_REQUIRED'):
                restored.remove_runtime(grant,idle_confirmed=True)
            fresh=self.fresh(stage)
            with self.assertRaisesRegex(m.Stopped,'RUNTIME_IDLE_UNCONFIRMED'):
                restored.remove_runtime(fresh)
            # Persistent mutation also requires the controller's current save
            # authority; the restore-only grant does not silently gain it.
            restored.consent=fresh
            self.assertEqual(restored.remove_runtime(fresh,idle_confirmed=True)['state'],'OWNED_RUNTIME_REMOVED')
            self.assertTrue(restored.journal.path.exists())


class CustomerWizardTests(unittest.TestCase):
    """Customer phase handoff only; all resource facts/effects are synthetic."""
    def args(self, root, **changes):
        from types import SimpleNamespace
        fields = dict(node='node', model_id='qwen3.5:4b', disk_root=str(root.parent),
            install_root=str(root), wizard_phase='plan', existing_state=None,
            session_seconds=30, task_class='log-summary', input_file=None,
            quality_case_file=None, budget_file=None, grant_file=None,
            lifecycle_consent_file=None, idle_confirmed=False, port=11435)
        fields.update(changes)
        return SimpleNamespace(**fields)

    def facts(self, node):
        return dict(os='Darwin',architecture='arm64',memory_total_gb=24,
            memory_available_gb=16,unified_memory=True,free_storage_gb=30)

    def call(self, args, answers, reader=None):
        answers=iter(answers)
        with patch.object(m.sys.stdin,'isatty',return_value=True):
            return m.customer_wizard(args,ask=lambda _:next(answers),
                reader=reader or self.facts,now=lambda:100)

    def test_decline_enable_and_probe_have_no_customer_side_effect(self):
        for answers,state in [(['no'],'SKIPPED'),(['yes','no'],'PROBE_DECLINED')]:
            with self.subTest(state=state),tempfile.TemporaryDirectory() as d:
                root=Path(d).resolve()/'customer'
                reader=unittest.mock.Mock(side_effect=AssertionError('probe forbidden'))
                self.assertEqual(self.call(self.args(root),answers,reader)['state'],state)
                reader.assert_not_called();self.assertFalse(root.exists())

    def test_resource_shortage_creates_no_authority_or_root(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve()/'customer'
            result=self.call(self.args(root),['yes','yes'],lambda _:dict(
                os='Darwin',architecture='arm64',memory_total_gb=8,
                memory_available_gb=1,unified_memory=True,free_storage_gb=1))
            self.assertIn(result['state'],('SKIPPED','UNKNOWN','RESOURCES_UNQUALIFIED'))
            self.assertFalse(root.exists())

    def test_deployment_decline_does_not_create_root(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve()/'customer'
            result=self.call(self.args(root),['yes','yes','no'])
            self.assertEqual(result['state'],'DEPLOYMENT_DECLINED')
            self.assertFalse(root.exists())

    def test_selected_model_and_port_flow_to_exact_deploy_command(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve()/'customer'
            result=self.call(self.args(root),['yes','yes','yes'])
            self.assertEqual(result['state'],'DEPLOYMENT_AUTHORIZED_NOT_STARTED')
            argv=result['next_argv'];self.assertEqual(argv[1:3],['-I','-B'])
            self.assertEqual(argv[argv.index('--model-id')+1],result['recommendation']['candidate']['id'])
            self.assertEqual(argv[argv.index('--port')+1],'11435')
            for flag in ('--grant-file','--lifecycle-consent-file','--budget-file'):
                path=Path(argv[argv.index(flag)+1]);self.assertTrue(path.is_file())
                self.assertEqual(path.stat().st_mode & 0o777,0o600)
            self.assertFalse((root/'lifecycle.json').exists())

    def test_repeated_budget_config_reuses_without_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();root.chmod(0o700)
            value=dict(max_download_gb=4,max_peak_disk_gb=8,max_iterations=9,max_restarts=0,max_seconds=1800)
            first=m._wizard_record(root,'budget',value,now=lambda:100)
            before=Path(first).read_bytes()
            self.assertEqual(m._wizard_record(root,'budget',value,now=lambda:101),first)
            self.assertEqual(Path(first).read_bytes(),before)

    def test_valid_grant_reuses_at_capacity_without_renewal(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();root.chmod(0o700)
            value=dict(node_id='node',scopes=['probe'],expires_at=200,reference='fixture',binding='')
            first=m._wizard_record(root,'probe',value,now=lambda:100)
            for i in range(11):
                (root/('wizard-other-'+str(i)+'.json')).write_text('{}')
            new=dict(value,expires_at=300)
            self.assertEqual(m._wizard_record(root,'probe',new,now=lambda:101),first)
            self.assertEqual(json.loads(Path(first).read_text())['expires_at'],200)

    def test_missing_task_arguments_return_handoff_without_journal_or_service(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();root.chmod(0o700)
            args=self.args(root,wizard_phase='session',lifecycle_consent_file='not-read',budget_file='not-read')
            with patch.object(m.deployment,'DurableJournal') as journal,patch.object(m,'OwnedOllamaService') as service:
                result=self.call(args,[])
            self.assertEqual(result['state'],'TASK_QUALITY_ARGUMENTS_REQUIRED')
            journal.assert_not_called();service.assert_not_called()

    def test_failed_deploy_is_not_advanced_to_session(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();root.chmod(0o700)
            args=self.args(root,wizard_phase='deploy',lifecycle_consent_file='fixture',budget_file='fixture',grant_file='fixture')
            def stopped(argv):
                print(json.dumps({'state':'STOP','reason':'SYNTHETIC_STAGE_FAILURE'}));return 2
            with patch.object(m,'main',side_effect=stopped):result=self.call(args,[])
            self.assertEqual(result['state'],'STOP');self.assertFalse(result['retry'])
            self.assertNotIn('next_argv',result)

    def test_handoff_boolean_flags_have_argparse_shape(self):
        for idle in (False,True):
            argv=m.wizard_argv('node','qwen3.5:4b',wizard_phase='session',idle_confirmed=idle)
            self.assertNotIn('False',argv);self.assertNotIn('True',argv)
            self.assertEqual('--idle-confirmed' in argv,idle)

    def test_scope_changed_does_not_reuse_old_permission(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();root.chmod(0o700)
            value=dict(node_id='node',scopes=['probe'],expires_at=200,reference='fixture',binding='')
            first=m._wizard_record(root,'probe',value,now=lambda:100)
            second=m._wizard_record(root,'probe',dict(value,binding='b'*64),now=lambda:100)
            self.assertNotEqual(first,second)
            self.assertEqual(json.loads(Path(first).read_text())['binding'],'')

    def test_symlink_authorization_record_is_never_followed_or_reused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve()/'owned';root.mkdir(mode=0o700)
            value=dict(node_id='node',scopes=['probe'],expires_at=200,reference='fixture',binding='')
            foreign=Path(d).resolve()/'customer.json';foreign.write_text(json.dumps(value))
            (root/'wizard-probe-link.json').symlink_to(foreign)
            before=foreign.read_bytes()
            with self.assertRaises((m.Stopped,OSError)):
                m._wizard_record(root,'probe',value,now=lambda:100)
            self.assertEqual(foreign.read_bytes(),before)

    def session_fixture(self, root):
        from types import SimpleNamespace
        root.chmod(0o700)
        input_path=root/'input.txt';input_path.write_text('public synthetic input')
        criteria=root/'criteria.json';criteria.write_text('{"ok":true}')
        stage=SimpleNamespace(runner=SimpleNamespace(recovery_required=False),max_seconds=100,
            started=0,clock=lambda:0,activity='NEVER_STARTED',close=unittest.mock.Mock())
        service=SimpleNamespace(binding='c'*64,handle=SimpleNamespace(poll=lambda:0),
            start=unittest.mock.Mock(return_value={'state':'SERVICE_STARTED_UNVALIDATED'}),
            stop=unittest.mock.Mock(return_value={'state':'DIRECT_PROCESS_REAPED','descendants':'UNKNOWN'}))
        consent=dict(node_id='node',binding='a'*64,expires_at=10000,actions=['restore-ownership','save-ownership'])
        budget=dict(max_download_gb=4,max_peak_disk_gb=12,max_iterations=20,max_restarts=0,max_seconds=100)
        for name,value in [('consent.json',consent),('budget.json',budget)]:
            p=root/name;p.write_text(json.dumps(value));p.chmod(0o600)
        args=self.args(root,wizard_phase='session',lifecycle_consent_file=str(root/'consent.json'),
            budget_file=str(root/'budget.json'),input_file=str(input_path),quality_case_file=str(criteria))
        return args,stage,service

    def session_call(self,args,stage,service,answers,qualifier=None):
        from contextlib import ExitStack
        with ExitStack() as stack:
            stack.enter_context(patch.object(m.sys.stdin,'isatty',return_value=True))
            stack.enter_context(patch.object(m.deployment,'DurableJournal'))
            stack.enter_context(patch.object(m.PinnedStage,'restore_owned',return_value=stage))
            stack.enter_context(patch.object(m,'service_binding',return_value='c'*64))
            stack.enter_context(patch.object(m,'OwnedOllamaService',return_value=service))
            stack.enter_context(patch.object(m,'_wizard_port_available'))
            stack.enter_context(patch.object(m,'_wizard_wait_ready',return_value={'state':'READ_ONLY_READY'}))
            q=stack.enter_context(patch.object(m,'qualify_exact_input',side_effect=qualifier))
            output=stack.enter_context(redirect_stdout(io.StringIO()))
            it=iter(answers)
            def ask(_):
                service.start.assert_not_called()  # no blocking prompts after native start
                return next(it)
            result=m.customer_wizard(args,ask=ask,reader=self.facts,now=lambda:100)
            return result,output.getvalue(),q

    def test_session_decline_never_starts_or_reads_task(self):
        with tempfile.TemporaryDirectory() as d:
            args,stage,service=self.session_fixture(Path(d).resolve())
            with patch.object(m,'read_task_bytes',side_effect=AssertionError('body forbidden')):
                result,_,q=self.session_call(args,stage,service,['yes','no'])
            self.assertEqual(result['state'],'QUALIFICATION_DECLINED')
            service.start.assert_not_called();service.stop.assert_not_called()
            stage.close.assert_called_once();q.assert_not_called()

    def test_invalid_quality_json_fails_before_native_service(self):
        for raw in ('{"x":1,"x":2}','{"x":NaN}'):
            with self.subTest(raw=raw),tempfile.TemporaryDirectory() as d:
                args,stage,service=self.session_fixture(Path(d).resolve())
                Path(args.quality_case_file).write_text(raw)
                with self.assertRaises(m.Stopped):self.session_call(args,stage,service,['yes','yes'])
                service.start.assert_not_called();stage.close.assert_called_once()

    def test_session_handoff_keeps_service_alive_and_carries_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            args,stage,service=self.session_fixture(Path(d).resolve())
            def qualify(*a,**kw):
                service.start.assert_called_once()
                service.stop.assert_not_called()
                return dict(qualified=True,expires_at=125,exact_config='e'*64,
                    evidence_kind='SYNTHETIC_STATE_ONLY_NOT_NATIVE_QUALIFICATION')
            result,output,_=self.session_call(args,stage,service,['yes','yes','yes'],qualify)
            receipts=[json.loads(line) for line in output.splitlines()]
            ready=next(x for x in receipts if x['state']=='CODEX_TOOL_COMMAND_READY_SERVICE_ACTIVE')
            self.assertEqual(ready['argv'][4],'assist')
            self.assertIn('--return-to-cloud',ready['argv'])
            self.assertEqual(ready['codex_session'],'NOT_RUN')
            cleanup=next(x for x in receipts if x['state']=='SERVICE_CLEANUP_RECEIPT')
            self.assertEqual(cleanup['cleanup']['descendants'],'UNKNOWN')
            self.assertEqual(result['codex_session'],'NOT_OBSERVED')
            service.stop.assert_called_once();stage.close.assert_called_once()

    def test_session_cleanup_unknown_never_becomes_success(self):
        with tempfile.TemporaryDirectory() as d:
            args,stage,service=self.session_fixture(Path(d).resolve())
            service.stop.return_value={'state':'CLEANUP_UNKNOWN','descendants':'UNKNOWN'}
            def qualify(*a,**kw):return dict(qualified=True,expires_at=125,exact_config='e'*64)
            with self.assertRaisesRegex(m.Stopped,'WIZARD_CLEANUP_UNKNOWN'):
                self.session_call(args,stage,service,['yes','yes','yes'],qualify)
            stage.close.assert_called_once()

    def test_quality_failure_stops_original_service_without_claiming_codex(self):
        with tempfile.TemporaryDirectory() as d:
            args,stage,service=self.session_fixture(Path(d).resolve())
            def fail(*a,**kw):raise m.Stopped('SYNTHETIC_QUALITY_FAILURE')
            with self.assertRaisesRegex(m.Stopped,'SYNTHETIC_QUALITY_FAILURE'):
                self.session_call(args,stage,service,['yes','yes','yes'],fail)
            service.stop.assert_called_once();stage.close.assert_called_once()

    def test_active_http_deadline_clamps_each_call_and_rejects_late_return(self):
        from types import SimpleNamespace
        client=m.OllamaClient('http://127.0.0.1:11434','0.40.13','qwen3.5:4b','a'*64,
            timeout=5,local_service_ref='synthetic-private-service')
        client.session_deadline=10
        response=unittest.mock.MagicMock()
        response.__enter__.return_value=SimpleNamespace(status=200,read=lambda _:b'{}')
        opener=unittest.mock.Mock();opener.open.return_value=response
        with patch.object(m,'build_opener',return_value=opener),patch.object(m.time,'monotonic',side_effect=[9,9.5]):
            self.assertEqual(client._http('GET','/api/version',None),{})
        self.assertEqual(opener.open.call_args.kwargs['timeout'],1)
        with patch.object(m,'build_opener',return_value=opener),patch.object(m.time,'monotonic',side_effect=[9,10]):
            with self.assertRaisesRegex(m.Stopped,'SERVICE_SESSION_DEADLINE'):
                client._http('GET','/api/version',None)

    def test_expired_http_session_opens_no_socket(self):
        client=m.OllamaClient('http://127.0.0.1:11434','0.40.13','qwen3.5:4b','a'*64,
            local_service_ref='synthetic-private-service');client.session_deadline=1
        with patch.object(m,'build_opener') as opener,patch.object(m.time,'monotonic',return_value=1):
            with self.assertRaisesRegex(m.Stopped,'SERVICE_SESSION_DEADLINE'):
                client._http('GET','/api/version',None)
            opener.assert_not_called()

    def test_recovery_unknown_never_issues_delete_permission(self):
        with tempfile.TemporaryDirectory() as d:
            args,_,service=self.session_fixture(Path(d).resolve());args.wizard_phase='recovery'
            plan=m.customer_deployment_plan(args.node,args.install_root,args.model_id)
            Path(args.lifecycle_consent_file).write_text(json.dumps(dict(node_id='node',
                binding=plan['binding'],expires_at=90,actions=['restore-ownership'])))
            journal=unittest.mock.MagicMock();journal.load.return_value={'state':'PENDING','owned_files_state':'UNKNOWN'}
            factory=unittest.mock.MagicMock();factory.return_value.__enter__.return_value=journal
            with patch.object(m.deployment,'DurableJournal',factory),patch.object(m.PinnedStage,'restore_owned') as restore:
                result=self.call(args,['yes'])
            self.assertEqual(result['state'],'STOP');self.assertFalse(result['cleanup_authorized'])
            self.assertEqual(result['ownership_status_argv'][4],'ownership-status')
            restore.assert_not_called();service.start.assert_not_called()
            self.assertFalse(list(Path(d).resolve().glob('wizard-uninstall-*.json')))

    def test_recovery_known_requires_idle_and_returns_original_uninstall_only(self):
        for idle in (False,True):
            with self.subTest(idle=idle),tempfile.TemporaryDirectory() as d:
                args,stage,_=self.session_fixture(Path(d).resolve());args.wizard_phase='recovery';args.idle_confirmed=idle
                plan=m.customer_deployment_plan(args.node,args.install_root,args.model_id)
                Path(args.lifecycle_consent_file).write_text(json.dumps(dict(node_id='node',
                    binding=plan['binding'],expires_at=90,actions=['restore-ownership'])))
                stage.runtime_complete=stage.model_complete=True
                journal=unittest.mock.MagicMock();journal.load.return_value={'state':'SUCCEEDED'}
                journal.load_owned_files.return_value={'io_state':'CONFIRMED'}
                factory=unittest.mock.MagicMock();factory.return_value.__enter__.return_value=journal
                with patch.object(m.deployment,'DurableJournal',factory),patch.object(m.PinnedStage,'restore_owned',return_value=stage):
                    if idle:
                        result=self.call(args,['yes','yes'])
                        self.assertEqual(result['state'],'UNINSTALL_AUTHORIZED_NOT_EXECUTED')
                        self.assertEqual(result['next_argv'][4],'uninstall')
                        self.assertFalse(result['automatic_delete'])
                    else:
                        with self.assertRaisesRegex(m.Stopped,'UNINSTALL_REQUIRES_FRESH_HOST_IDLE_CONFIRMATION'):
                            self.call(args,['yes'])
                stage.close.assert_called_once()

    def test_busy_loopback_port_is_rejected_without_data_request(self):
        import socket
        sock=unittest.mock.MagicMock();sock.__enter__.return_value=sock;sock.connect_ex.return_value=0
        with patch.object(socket,'socket',return_value=sock),patch.object(m.time,'monotonic',return_value=1):
            with self.assertRaisesRegex(m.Stopped,'WIZARD_LOCAL_PORT_BUSY'):
                m._wizard_port_available(11434,10)
        sock.connect_ex.assert_called_once_with(('127.0.0.1',11434))

    def test_readiness_connection_refusal_is_bounded_and_never_infers(self):
        from types import SimpleNamespace
        import errno
        candidate=m.load_catalog()['models'][0]
        stage=SimpleNamespace(clock=lambda:0,started=0,max_seconds=100)
        service=SimpleNamespace(port=11434,binding='c'*64,handle=SimpleNamespace(poll=lambda:None))
        client=unittest.mock.Mock();client._http.side_effect=ConnectionRefusedError(errno.ECONNREFUSED,'synthetic')
        factory=unittest.mock.Mock(return_value=client)
        with patch.object(m.time,'monotonic',return_value=1):
            with self.assertRaisesRegex(m.Stopped,'WIZARD_READY_REFUSED'):
                m._wizard_wait_ready(stage,service,candidate,10,client_factory=factory,sleep=lambda _:None)
        self.assertEqual(factory.call_count,3);self.assertEqual(client._http.call_count,3)
        self.assertTrue(all(c.args[0]=='GET' for c in client._http.call_args_list))
        client.execute.assert_not_called()

    def test_readiness_identity_mismatch_never_retries_or_infers(self):
        from types import SimpleNamespace
        candidate=m.load_catalog()['models'][0]
        stage=SimpleNamespace(clock=lambda:0,started=0,max_seconds=100)
        service=SimpleNamespace(port=11434,binding='c'*64,handle=SimpleNamespace(poll=lambda:None))
        client=unittest.mock.Mock();client._http.return_value={'version':'unexpected'}
        factory=unittest.mock.Mock(return_value=client)
        with patch.object(m.time,'monotonic',return_value=1):
            with self.assertRaisesRegex(m.Stopped,'RUNTIME_VERSION_CHANGED'):
                m._wizard_wait_ready(stage,service,candidate,10,client_factory=factory,sleep=lambda _:None)
        self.assertEqual(factory.call_count,1);client.execute.assert_not_called()

    def test_exited_original_handle_prevents_readiness_requests(self):
        from types import SimpleNamespace
        candidate=m.load_catalog()['models'][0]
        stage=SimpleNamespace(clock=lambda:0,started=0,max_seconds=100)
        service=SimpleNamespace(port=11434,binding='c'*64,handle=SimpleNamespace(poll=lambda:1))
        factory=unittest.mock.Mock()
        with patch.object(m.time,'monotonic',return_value=1):
            with self.assertRaisesRegex(m.Stopped,'SERVICE_HANDLE_EXITED'):
                m._wizard_wait_ready(stage,service,candidate,10,client_factory=factory)
        factory.assert_not_called()
