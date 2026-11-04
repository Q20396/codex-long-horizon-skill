"""Opt-in install/update handoff: synthetic fixtures, never model activation."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


assembly = load('handoff_profile_assembly', ROOT / 'scripts/assemble_skill_profile.py')
updater = load('handoff_installed_updater', ROOT /
               '.agents/skills/long-horizon-engineering/scripts/update_installed_skill.py')


class LocalModelInstallHandoffTests(unittest.TestCase):
    def fixture(self, root):
        entry = root / 'scripts/local_model_assist.py'
        entry.parent.mkdir(parents=True)
        entry.write_text('# synthetic entry placeholder\n', encoding='utf-8')
        return entry

    def test_exact_isolated_command_and_no_raw_output(self):
        for module in (assembly, updater):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); entry = self.fixture(root)
                with patch.object(module.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run:
                    result = module.prepare_local_assist(root, 'qwen3.5:4b')
                self.assertEqual(result['state'], 'PREPARED')
                self.assertIs(result['runtime_started'], False)
                argv = run.call_args.args[0]
                self.assertEqual(argv, [sys.executable, '-I', '-B', str(entry),
                                        'prepare', '--model-id', 'qwen3.5:4b'])
                self.assertEqual(run.call_args.kwargs['stdout'], subprocess.DEVNULL)
                self.assertEqual(run.call_args.kwargs['stderr'], subprocess.DEVNULL)
                self.assertEqual(run.call_args.kwargs['stdin'], subprocess.DEVNULL)
                self.assertEqual(run.call_args.kwargs['timeout'], 10)
                self.assertNotIn('shell', run.call_args.kwargs)

    def test_missing_or_symlink_entry_does_not_launch(self):
        for module in (assembly, updater):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                with patch.object(module.subprocess, 'run') as run:
                    self.assertEqual(module.prepare_local_assist(root, 'qwen3.5:4b')['reason'], 'ENTRY_UNAVAILABLE')
                    entry = self.fixture(root)
                    target = root / 'original.py'; entry.rename(target); entry.symlink_to(target)
                    self.assertEqual(module.prepare_local_assist(root, 'qwen3.5:4b')['reason'], 'ENTRY_UNAVAILABLE')
                    run.assert_not_called()

    def test_failure_is_fixed_and_does_not_escape(self):
        cases = [(SimpleNamespace(returncode=7), None, 'PREPARE_FAILED'),
                 (None, subprocess.TimeoutExpired('synthetic', 10), 'PREPARE_TIMEOUT'),
                 (None, OSError('synthetic private raw text'), 'PREPARE_UNAVAILABLE')]
        for module in (assembly, updater):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); self.fixture(root)
                for value, error, reason in cases:
                    with self.subTest(module=module.__name__, reason=reason), patch.object(
                            module.subprocess, 'run', return_value=value, side_effect=error):
                        result = module.prepare_local_assist(root, 'qwen3.5:4b')
                        self.assertEqual(result['reason'], reason)
                        self.assertNotIn('private', json.dumps(result))

    def assembly_main(self, argv, *, handoff=False, included=True):
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(assembly, 'load_manifest', return_value={}))
            stack.enter_context(patch.object(assembly, 'selected_paths', return_value=(
                [assembly.LHE_PREFIX + 'SKILL.md'] if included else [])))
            stack.enter_context(patch.object(assembly, 'unresolved_lhe_references', return_value=[]))
            assemble = stack.enter_context(patch.object(assembly, 'assemble', return_value=None))
            follow = stack.enter_context(patch.object(assembly, 'prepare_local_assist',
                                                      return_value={'state': 'NOT_READY'}))
            out = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            code = assembly.main(argv)
            return code, out.getvalue(), assemble.call_count, follow.call_count

    def test_default_assembly_never_invokes_handoff(self):
        code, text, count, follow = self.assembly_main(
            ['--profile', 'local-governance-core', '--output-root', '/synthetic/out', '--apply'])
        self.assertEqual((code, count, follow), (0, 1, 0))
        result = json.loads(text)
        self.assertNotIn('local_assist_handoff', result)
        self.assertEqual(result['local_assist_offer']['state'], 'OPT_IN_REQUIRED')
        self.assertIs(result['local_assist_offer']['probe_started'], False)

    def test_no_offer_before_success_or_without_lhe(self):
        code, text, _, follow = self.assembly_main(['--profile', 'local-governance-core'])
        self.assertEqual(code, 0)
        self.assertNotIn('local_assist_offer', json.loads(text))
        self.assertEqual(follow, 0)
        code, text, _, follow = self.assembly_main(
            ['--profile', 'fixture', '--output-root', '/synthetic/out', '--apply'], included=False)
        self.assertNotIn('local_assist_offer', json.loads(text))
        self.assertEqual(follow, 0)

    def test_offer_contains_accurate_isolated_commands_and_no_activation(self):
        for module in (assembly, updater):
            with self.subTest(module=module.__name__), patch.object(module.subprocess, 'run') as run:
                root = Path('/synthetic/installed')
                offer = module.local_assist_offer(root, 'qwen3.5:4b')
                self.assertEqual(offer['status_argv'], [sys.executable, '-I', '-B',
                    str(root / 'scripts/local_model_assist.py'), 'status'])
                self.assertEqual(offer['prepare_argv'], [sys.executable, '-I', '-B',
                    str(root / 'scripts/local_model_assist.py'), 'prepare', '--model-id', 'qwen3.5:4b'])
                self.assertEqual(offer['decline_behavior'], 'KEEP_20396_AND_CODEX_UNCHANGED')
                self.assertFalse(offer['probe_started'])
                self.assertFalse(offer['runtime_started'])
                run.assert_not_called()

    def test_failed_assembly_does_not_offer_or_prepare(self):
        with patch.object(assembly, 'load_manifest', return_value={}), \
                patch.object(assembly, 'selected_paths', return_value=[assembly.LHE_PREFIX + 'SKILL.md']), \
                patch.object(assembly, 'unresolved_lhe_references', return_value=[]), \
                patch.object(assembly, 'assemble', side_effect=assembly.ProfileError('synthetic')), \
                patch.object(assembly, 'local_assist_offer') as offer, \
                patch.object(assembly, 'prepare_local_assist') as follow, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(assembly.main(['--profile', 'fixture', '--output-root', '/synthetic/out',
                                           '--apply', '--local-assist']), 2)
            offer.assert_not_called()
            follow.assert_not_called()

    def test_handoff_failure_keeps_completed_assembly_success(self):
        code, text, count, follow = self.assembly_main(
            ['--profile', 'local-governance-core', '--output-root', '/synthetic/out',
             '--apply', '--local-assist'])
        self.assertEqual((code, count, follow), (0, 1, 1))
        result = json.loads(text)
        self.assertTrue(result['applied'])
        self.assertEqual(result['local_assist_handoff']['state'], 'NOT_READY')

    def test_assembly_optin_requires_apply_before_any_install(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.assembly_main(
                ['--profile', 'local-governance-core', '--local-assist'])[0:1], (2,))
            self.assertEqual(self.assembly_main(
                ['--profile', 'local-governance-core', '--local-assist-model', 'qwen3.5:4b'])[0:1], (2,))

    def test_updater_requires_explicit_single_skill_and_apply(self):
        for argv in (['--local-assist'], ['--local-assist', '--apply'],
                     ['--local-assist', '--apply', '--skill', 'ai-video-production'],
                     ['--local-assist-model', 'qwen3.5:4b']):
            with self.subTest(argv=argv), patch.object(updater, 'update_skill') as update:
                with self.assertRaises(SystemExit):
                    updater.main(argv)
                update.assert_not_called()

    def test_update_success_precedes_handoff_and_failure_does_not_rollback(self):
        calls = []
        target = SimpleNamespace(target=Path('/synthetic/installed'))
        with patch.object(updater, 'resolve_target_plan', return_value=target), \
                patch.object(updater, 'update_skill', side_effect=lambda *a: calls.append('updated')), \
                patch.object(updater, 'prepare_local_assist', side_effect=lambda *a: calls.append('prepared') or {'state': 'NOT_READY'}), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            updater.main(['--target-root', '/synthetic', '--skill', 'long-horizon-engineering',
                          '--apply', '--local-assist'])
        self.assertEqual(calls, ['updated', 'prepared'])
        self.assertIn('NOT_READY', output.getvalue())

    def test_default_update_never_invokes_handoff(self):
        with patch.object(updater, 'resolve_target_plan', return_value=SimpleNamespace(target=Path('/synthetic'))), \
                patch.object(updater, 'update_skill') as update, \
                patch.object(updater, 'prepare_local_assist') as follow, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            updater.main(['--target-root', '/synthetic', '--skill', 'long-horizon-engineering', '--apply'])
            update.assert_called_once()
            follow.assert_not_called()
        self.assertIn('Local compute offer:', output.getvalue())
        offer = json.loads(output.getvalue().split('Local compute offer: ', 1)[1])
        self.assertEqual(offer['state'], 'OPT_IN_REQUIRED')
        self.assertFalse(offer['probe_started'])

    def test_failed_update_never_prepares(self):
        with patch.object(updater, 'resolve_target_plan', return_value=SimpleNamespace(target=Path('/synthetic'))), \
                patch.object(updater, 'update_skill', side_effect=updater.UpdateError('synthetic')), \
                patch.object(updater, 'prepare_local_assist') as follow, \
                patch.object(updater, 'local_assist_offer') as offer, \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(updater.UpdateError):
                updater.main(['--target-root', '/synthetic', '--skill', 'long-horizon-engineering',
                              '--apply', '--local-assist'])
            follow.assert_not_called()
            offer.assert_not_called()

    def test_actual_installed_isolated_prepare_handoff(self):
        # Actual owned temporary installation + accurate -I child entry. No probe,
        # download, runtime, cloud, customer configuration or model is invoked.
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'installed'
            result = subprocess.run([
                sys.executable, '-B', str(ROOT / 'scripts/assemble_skill_profile.py'),
                '--profile', 'local-governance-core', '--output-root', str(target),
                '--apply', '--local-assist', '--local-assist-model', 'qwen3.5:4b',
            ], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report['applied'])
            self.assertEqual(report['local_assist_offer']['state'], 'OPT_IN_REQUIRED')
            self.assertEqual(report['local_assist_handoff']['state'], 'PREPARED')
            self.assertIs(report['local_assist_handoff']['runtime_started'], False)
            self.assertTrue((target / '.agents/skills/long-horizon-engineering/scripts/local_model_assist.py').is_file())


class InstalledWizardHandoffTests(unittest.TestCase):
    def install_and_prepare(self, root):
        installed=root/'installed'
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/assemble_skill_profile.py'),
            '--profile','local-governance-core','--output-root',str(installed),'--apply'],
            stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout);offer=report['local_assist_offer']
        prepared=subprocess.run(offer['prepare_argv'],stdin=subprocess.DEVNULL,
            capture_output=True,text=True,timeout=10)
        self.assertEqual(prepared.returncode,0,prepared.stderr)
        guide=json.loads(prepared.stdout)['guide']
        entry=installed/'.agents/skills/long-horizon-engineering/scripts/local_model_assist.py'
        self.assertEqual(guide['wizard_argv'],[sys.executable,'-I','-B',str(entry.resolve()),'wizard',
            '--node','this-device','--model-id','qwen3.5:4b'])
        self.assertEqual(guide['required_arguments'],['--disk-root','--install-root'])
        return installed,offer,guide

    def test_default_installed_offer_prepare_hands_off_exact_wizard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);installed,offer,guide=self.install_and_prepare(root)
            self.assertFalse(offer['probe_started']);self.assertFalse(offer['runtime_started'])
            self.assertFalse((root/'customer-runtime').exists())
            self.assertNotIn('<', ''.join(guide['wizard_argv']))

    def test_actual_installed_wizard_nontty_stops_before_customer_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);installed,offer,guide=self.install_and_prepare(root)
            runtime=root/'customer-runtime'
            result=subprocess.run(guide['wizard_argv']+['--disk-root',str(root),'--install-root',str(runtime)],
                stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertEqual(json.loads(result.stdout)['state'],'STOP')
            self.assertFalse(runtime.exists())
            self.assertEqual(sorted(p.name for p in root.iterdir()),['installed'])

    def test_actual_installed_wizard_public_no_refuses_without_effects(self):
        # A self-owned PTY carries only public "no"; never secret input, probe,
        # runtime or customer files. This exercises the exact installed CLI.
        import os,pty
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);installed,offer,guide=self.install_and_prepare(root)
            runtime=root/'customer-runtime';master,slave=pty.openpty()
            process=None
            try:
                process=subprocess.Popen(guide['wizard_argv']+['--disk-root',str(root),'--install-root',str(runtime)],
                    stdin=slave,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,close_fds=True)
                os.close(slave);slave=None
                os.write(master,b'no\n')
                output,error=process.communicate(timeout=10)
                self.assertEqual(process.returncode,0,error)
                decoder=json.JSONDecoder();states=[]
                for offset,char in enumerate(output):
                    if char=='{':
                        try:
                            value,end=decoder.raw_decode(output[offset:])
                            if isinstance(value,dict) and 'state' in value:states.append(value)
                        except ValueError:pass
                self.assertTrue(states,output);self.assertEqual(states[-1]['state'],'SKIPPED')
                self.assertFalse(states[-1].get('probe_performed',False));self.assertFalse(runtime.exists())
                self.assertEqual(sorted(p.name for p in root.iterdir()),['installed'])
            finally:
                if slave is not None:os.close(slave)
                os.close(master)
                if process is not None and process.poll() is None:
                    process.kill();process.wait(timeout=2)


class OwnedServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = ROOT/'.agents/skills/long-horizon-engineering/scripts'
        sys.path.insert(0, str(directory))
        try:
            cls.adapter = load('handoff_owned_service_adapter', directory/'local_model_assist.py')
        finally:
            sys.path.remove(str(directory))

    def fixture(self, tmp, actions=None):
        a=self.adapter
        stage=object.__new__(a.PinnedStage)
        stage.root=Path(tmp); stage.node_id='synthetic-node'; stage.binding='a'*64
        stage.activity='NEVER_STARTED'; stage.persistent_mode=False
        stage.runner=SimpleNamespace(recovery_required=False)
        stage.started=1000; stage.max_seconds=30; stage.clock=lambda:1001
        stage.validate_runtime_files=lambda: {'runtime_path':str(Path(tmp)/'runtime/ollama'), 'archive_sha256':'b'*64}
        stage.validate_model_files=lambda: {'models_root':str(Path(tmp)/'registered.models'), 'manifest_sha256':'c'*64}
        stage._root_check=lambda: None
        consent=a.LifecycleConsent(stage.node_id,a.service_binding(stage),100,
            actions if actions is not None else {'start-service','stop-service'})
        return stage,consent

    def test_authority_before_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage,consent=self.fixture(tmp,{'start-service'})
            process=unittest.mock.Mock()
            service=self.adapter.OwnedOllamaService(stage,consent,popen=process,wall_clock=lambda:1)
            with self.assertRaises(self.adapter.Stopped): service.start()
            process.assert_not_called(); self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_exact_private_environment_and_no_qualification(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage,consent=self.fixture(tmp)
            handle=unittest.mock.Mock(); factory=unittest.mock.Mock(return_value=handle)
            service=self.adapter.OwnedOllamaService(stage,consent,popen=factory,wall_clock=lambda:1)
            with patch.dict('os.environ',{'SECRET_TEST':'never-inherit'}): result=service.start()
            args,kw=factory.call_args
            self.assertEqual(args[0],[str(Path(tmp)/'runtime/ollama'),'serve'])
            self.assertEqual(kw['env']['OLLAMA_MODELS'],str(Path(tmp)/'registered.models'))
            self.assertNotIn('SECRET_TEST',kw['env']); self.assertEqual(kw['stdout'],subprocess.DEVNULL)
            self.assertEqual(kw['env']['OLLAMA_NO_CLOUD'],'1')
            self.assertEqual(result['health'],'NOT_RUN'); self.assertEqual(result['descendants'],'UNKNOWN')
            with self.assertRaises(self.adapter.Stopped): service.start()
            self.assertEqual(factory.call_count,1)

    def test_receipt_failure_never_executes(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage,consent=self.fixture(tmp)
            def fail(): raise self.adapter.Stopped('SYNTHETIC_IDENTITY_CHANGED')
            stage.validate_runtime_files=fail
            factory=unittest.mock.Mock()
            service=self.adapter.OwnedOllamaService(stage,consent,popen=factory,wall_clock=lambda:1)
            with self.assertRaises(self.adapter.Stopped): service.start()
            factory.assert_not_called(); self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_original_handle_graceful_and_no_cleanup_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage,consent=self.fixture(tmp); handle=unittest.mock.Mock()
            handle.poll.return_value=None; handle.wait.return_value=0
            service=self.adapter.OwnedOllamaService(stage,consent,popen=lambda *a,**k:handle,wall_clock=lambda:1)
            service.start(); result=service.stop(); self.assertEqual(result,service.stop())
            handle.terminate.assert_called_once(); handle.kill.assert_not_called();handle.wait.assert_called_once()
            self.assertEqual(result['direct_process'],'EXIT_CONFIRMED');self.assertEqual(result['descendants'],'UNKNOWN')

    def test_timeout_one_kill_and_unknown_stays_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage,consent=self.fixture(tmp); handle=unittest.mock.Mock();handle.poll.return_value=None
            handle.wait.side_effect=subprocess.TimeoutExpired('synthetic',1)
            service=self.adapter.OwnedOllamaService(stage,consent,popen=lambda *a,**k:handle,wall_clock=lambda:1)
            service.start();result=service.stop();self.assertEqual(result,service.stop())
            handle.terminate.assert_called_once();handle.kill.assert_called_once();self.assertEqual(handle.wait.call_count,2)
            self.assertEqual(result['direct_process'],'UNKNOWN')

    def test_stage_budget_checked_before_files_and_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage,consent=self.fixture(tmp); stage.clock=lambda:1025
            factory=unittest.mock.Mock()
            service=self.adapter.OwnedOllamaService(stage,consent,popen=factory,
                clock=lambda:1,wall_clock=lambda:1)
            with self.assertRaisesRegex(self.adapter.Stopped,'START_SOFTWARE_DEADLINE'): service.start()
            factory.assert_not_called();self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_post_spawn_soft_deadline_cleans_only_original_handle(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage,consent=self.fixture(tmp); readings=iter([1001,1002,1003,1025])
            stage.clock=lambda:next(readings)
            handle=unittest.mock.Mock();handle.poll.return_value=None;handle.wait.return_value=0
            factory=unittest.mock.Mock(return_value=handle)
            service=self.adapter.OwnedOllamaService(stage,consent,popen=factory,
                clock=lambda:7,wall_clock=lambda:1)
            result=service.start()
            self.assertEqual(result['state'],'START_SOFTWARE_DEADLINE')
            self.assertEqual(result['cleanup']['direct_process'],'EXIT_CONFIRMED')
            self.assertEqual(result['descendants'],'UNKNOWN')
            handle.terminate.assert_called_once();handle.kill.assert_not_called()
            self.assertEqual(service.stop(),result['cleanup']);handle.wait.assert_called_once()

    def test_activity_save_failure_zero_popen(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage,consent=self.fixture(tmp);stage.persistent_mode=True
            stage.save_ownership=unittest.mock.Mock(side_effect=self.adapter.Stopped('SYNTHETIC_SAVE_FAILED'))
            factory=unittest.mock.Mock();service=self.adapter.OwnedOllamaService(stage,consent,popen=factory,wall_clock=lambda:1)
            with self.assertRaises(self.adapter.Stopped):service.start()
            self.assertEqual(stage.activity,'POSSIBLY_ACTIVE');factory.assert_not_called()

    def test_activity_marked_before_popen(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage,consent=self.fixture(tmp);stage.persistent_mode=True
            stage.save_ownership=unittest.mock.Mock()
            def spawn(*args,**kwargs):
                self.assertEqual(stage.activity,'POSSIBLY_ACTIVE')
                stage.save_ownership.assert_called_once()
                return unittest.mock.Mock()
            self.adapter.OwnedOllamaService(stage,consent,popen=spawn,wall_clock=lambda:1).start()

    def test_pending_and_legacy_activity_require_reconciliation(self):
        for pending,activity in [(True,'NEVER_STARTED'),(False,'UNKNOWN'),(False,'POSSIBLY_ACTIVE')]:
            with tempfile.TemporaryDirectory() as tmp:
                stage,consent=self.fixture(tmp);stage.runner.recovery_required=pending;stage.activity=activity
                factory=unittest.mock.Mock()
                service=self.adapter.OwnedOllamaService(stage,consent,popen=factory,wall_clock=lambda:1)
                with self.assertRaises(self.adapter.Stopped):service.start()
                factory.assert_not_called();self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_setup_offer_is_prefix_with_required_customer_path(self):
        for module in (assembly,updater):
            offer=module.local_assist_offer(Path('/synthetic/installed'),'qwen3.5:4b')
            self.assertEqual(offer['setup_entry_argv'][-1],'setup')
            self.assertEqual(offer['setup_required_arguments'],['--disk-root'])


class ExactQualityTests(unittest.TestCase):
    setUpClass = classmethod(OwnedServiceTests.setUpClass.__func__)
    def quality_fixture(self, output='{"count":2}', scopes=None, criteria_scope='file:/synthetic/criteria.json'):
        a=self.adapter; candidate=a.load_catalog()['models'][0]
        transport=lambda *args: {}
        client=a.OllamaClient('http://127.0.0.1:11434',candidate['provider_version'],
            candidate['id'],candidate['manifest_sha256'],transport=transport,local_service_ref='synthetic-local-only')
        client.execute=unittest.mock.Mock(return_value=(output,{'prompt_eval_count':4,'eval_count':3}))
        binding=a.quality_binding(client,'log-summary','file:/synthetic/task.txt',criteria_scope)
        grant=a.Grant('synthetic-node',scopes or {'qualify'},100,'synthetic',binding)
        snapshot={'memory_total_gb':128,'memory_available_gb':100,'unified_memory':True,
                  'free_storage_gb':100}
        return client,grant,snapshot

    def run_quality(self, output='{"count":2}', **kwargs):
        client,grant,snapshot=self.quality_fixture(output)
        return self.adapter.qualify_exact_input('synthetic-node',snapshot,client,'log-summary',
            'file:/synthetic/task.txt','count two log entries',{'count':2},
            'file:/synthetic/criteria.json',grant,native_probe=True,now=lambda:1,**kwargs)

    def test_injected_positive_never_mints_node(self):
        result=self.run_quality()
        self.assertEqual(result['state'],'SYNTHETIC_CHECK_PASSED')
        self.assertFalse(result['qualified']);self.assertNotIn('node',result)
        self.assertEqual(result['usage']['total_tokens'],7)
        self.assertNotIn('count two log entries',json.dumps(result))
        self.assertNotIn('"count": 2',json.dumps(result))
        self.assertEqual(result['check_scope'],'EXACT_INPUT')

    def test_json_boolean_number_duplicate_and_nonjson_do_not_pass(self):
        for output in ('{"count":true}','{"count":2,"count":2}','not JSON','{"count":NaN}'):
            with self.subTest(output=output):
                self.assertEqual(self.run_quality(output)['state'],'QUALITY_CHECK_FAILED')

    def test_criteria_path_binding_checked_before_inference(self):
        client,grant,snapshot=self.quality_fixture()
        with self.assertRaises(self.adapter.Stopped):
            self.adapter.qualify_exact_input('synthetic-node',snapshot,client,'log-summary',
                'file:/synthetic/task.txt','task',{'count':2},'file:/different/criteria.json',
                grant,now=lambda:1)
        client.execute.assert_not_called()

    def test_payload_and_criteria_caps_before_inference(self):
        for payload,expected in [('x'*32769,{}),('task',{'large':'x'*16385})]:
            client,grant,snapshot=self.quality_fixture()
            with self.assertRaises(self.adapter.Stopped):
                self.adapter.qualify_exact_input('synthetic-node',snapshot,client,'log-summary',
                    'file:/synthetic/task.txt',payload,expected,'file:/synthetic/criteria.json',grant,now=lambda:1)
            client.execute.assert_not_called()

    def test_exact_binding_changes_with_input_or_criteria_and_cannot_legacy_dispatch(self):
        a=self.adapter;client,grant,snapshot=self.quality_fixture()
        config=a.exact_task_binding(client,'log-summary','file:/synthetic/task.txt','a'*64,'b'*64)
        self.assertNotEqual(config,a.exact_task_binding(client,'log-summary','file:/synthetic/task.txt','c'*64,'b'*64))
        self.assertNotEqual(config,a.exact_task_binding(client,'log-summary','file:/synthetic/task.txt','a'*64,'c'*64))
        self.assertNotEqual(config,a.task_binding(client,'log-summary','file:/synthetic/task.txt'))
        # Synthetic Node models the issued record shape, never real qualification evidence.
        q=a.pool.Qualification('synthetic-node','ollama',client.model,config,'log-summary',client.version)
        node=a.pool.Node('synthetic-node',provider='ollama',model=client.model,config=config,
             consent=True,deployment_authorized=True,probed=True,runtime_validated=True,
             privacy_scopes={'file:/synthetic/task.txt'},qualifications={q},memory_available=100,
             provider_version=client.version)
        task=a.pool.Task('synthetic','log-summary','file:/synthetic/task.txt',payload='changed body')
        with self.assertRaises(a.Stopped): a.run_local(task,client,grant,node)
        client.execute.assert_not_called()

    def exact_record_fixture(self, path='/synthetic/task.txt', payload='customer log', output='{"count":2}'):
        # Manually declared synthetic schema fixture. NATIVE is only parser data;
        # this test does not obtain or claim actual native qualification evidence.
        import hashlib,time
        a=self.adapter;client,unused,snapshot=self.quality_fixture(output)
        scope='file:'+path;criteria_scope='file:/synthetic/criteria.json'
        input_sha=hashlib.sha256(payload.encode()).hexdigest()
        criteria_sha=hashlib.sha256(b'{"count":2}').hexdigest()
        config=a.exact_task_binding(client,'log-summary',scope,input_sha,criteria_sha)
        node_fields={'node_id':'synthetic-node','provider':'ollama','model':client.model,'config':config,
            'consent':True,'deployment_authorized':True,'probed':True,'runtime_validated':True,
            'privacy_scopes':[scope],'memory_available':100,'provider_version':client.version,
            'qualifications':[{'node_id':'synthetic-node','provider':'ollama','model':client.model,
                'config':config,'task_class':'log-summary','provider_version':client.version}]}
        record={'schema_version':2,'qualified':True,'evidence_kind':'NATIVE','check_scope':'EXACT_INPUT',
            'data_scope':scope,'criteria_scope':criteria_scope,'input_sha256':input_sha,
            'criteria_sha256':criteria_sha,'expires_at':time.time()+60,'exact_config':config,
            'quality_binding':a.quality_binding(client,'log-summary',scope,criteria_scope),'node':node_fields}
        node=a.pool.Node(**{**node_fields,'qualifications':frozenset(a.pool.Qualification(**q) for q in node_fields['qualifications'])})
        grant=a.Grant('synthetic-node',{'infer','return-to-cloud'},time.time()+60,'synthetic-only',config)
        task=a.pool.Task('synthetic','log-summary',scope,privacy='CLOUD_ALLOWED',
            output_privacy='CLOUD_ALLOWED',payload=payload)
        return client,grant,node,record,task

    def test_exact_record_valid_input_and_output_dispatch(self):
        client,grant,node,record,task=self.exact_record_fixture()
        result,usage=self.adapter.run_local(task,client,grant,node,qualification_record=record)
        self.assertEqual(result.state,'COMPLETED');self.assertEqual(result.output,'{"count":2}')
        self.assertEqual(len(usage),1);client.execute.assert_called_once()

    def test_exact_record_changed_body_same_path_zero_inference(self):
        client,grant,node,record,task=self.exact_record_fixture()
        from dataclasses import replace
        with self.assertRaises(self.adapter.Stopped):
            self.adapter.run_local(replace(task,payload='changed'),client,grant,node,qualification_record=record)
        client.execute.assert_not_called()

    def test_exact_record_missing_record_zero_inference(self):
        client,grant,node,record,task=self.exact_record_fixture()
        with self.assertRaises(self.adapter.Stopped):self.adapter.run_local(task,client,grant,node)
        client.execute.assert_not_called()

    def test_changed_output_not_released_but_usage_retained(self):
        client,grant,node,record,task=self.exact_record_fixture(output='{"count":999}')
        result,usage=self.adapter.run_local(task,client,grant,node,qualification_record=record)
        self.assertNotEqual(result.state,'COMPLETED');self.assertIsNone(result.output)
        self.assertEqual(self.adapter.public_usage(usage[0])['total_tokens'],7)
        client.execute.assert_called_once()

    def test_cli_record_a_cannot_read_file_b(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a_path=str(root/'A.txt');b_path=str(root/'B.txt')
            Path(b_path).write_text('synthetic unauthorized B body')
            client,grant,node,record,task=self.exact_record_fixture(path=a_path)
            grant_path=root/'grant.json';record_path=root/'record.json'
            grant_path.write_text(json.dumps({'node_id':grant.node_id,'scopes':list(grant.scopes),
                'expires_at':grant.expires_at,'reference':grant.reference,'binding':grant.binding}))
            record_path.write_text(json.dumps(record))
            args=['assist','--node','synthetic-node','--grant-file',str(grant_path),
                '--qualification-file',str(record_path),'--input-file',b_path,'--task-id','synthetic',
                '--local-service-ref','synthetic-local-only','--model-id',client.model,'--return-to-cloud']
            with patch.object(self.adapter,'OllamaClient',return_value=client), \
                 patch.object(self.adapter,'read_task_bytes') as reader, \
                 patch.object(self.adapter.os,'open',wraps=self.adapter.os.open) as opened, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.adapter.main(args),2)
            self.assertFalse(any(str(call.args[0]) == b_path for call in opened.call_args_list))
            reader.assert_not_called();client.execute.assert_not_called()

    def test_expiry_cannot_exceed_grant_and_unknown_usage_not_zero(self):
        self.assertEqual(self.run_quality(expires_at=10000)['expires_at'],100)
        record=self.adapter.usage_record({},call_id='synthetic',model='synthetic',started=1,finished=2)
        result=self.adapter.public_usage(record)
        self.assertEqual(result,{'input_tokens':None,'output_tokens':None,'total_tokens':None,'metric_source':'UNKNOWN'})


if __name__ == '__main__':
    unittest.main()
