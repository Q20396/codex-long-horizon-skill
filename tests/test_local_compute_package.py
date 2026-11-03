"""Exercise the real default-profile assembler outside the source checkout."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import importlib

ROOT = Path(__file__).resolve().parents[1]


class LocalComputePackageTests(unittest.TestCase):
    def test_ownership_persistence_unknown_has_fixed_cli_receipt(self):
        with patch.object(sys, 'path', [str(ROOT / '.agents/skills/long-horizon-engineering/scripts'), *sys.path]):
            assist = importlib.import_module('local_model_assist')
        import io, contextlib, time
        with tempfile.TemporaryDirectory() as temporary:
            root = str(Path(temporary).resolve())
            plan = assist.customer_deployment_plan('fixture', root, 'qwen3.5:4b')
            grant = {'node_id': 'fixture', 'binding': plan['binding'],
                     'expires_at': time.time()+60, 'actions': ['restore-ownership']}
            budget = {'max_download_gb': 10, 'max_peak_disk_gb': 20, 'max_iterations': 20,
                      'max_restarts': 0, 'max_seconds': 60}
            output = io.StringIO()
            with patch.object(assist, 'read_local_record', side_effect=[grant, budget]), \
                 patch.object(assist.deployment, 'DurableJournal', side_effect=RuntimeError('PRIVATE_DIAGNOSTIC')), \
                 contextlib.redirect_stdout(output):
                code = assist.main(['ownership-status', '--node', 'fixture', '--install-root', root,
                                    '--lifecycle-consent-file', 'grant', '--budget-file', 'budget'])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(output.getvalue())['state'], 'STOP')
            self.assertNotIn('PRIVATE_DIAGNOSTIC', output.getvalue())

    def test_deployment_plan_and_phase_failure_stop(self):
        with patch.object(sys, 'path', [str(ROOT / '.agents/skills/long-horizon-engineering/scripts'), *sys.path]):
            assist = importlib.import_module('local_model_assist')
        plan = assist.customer_deployment_plan('fixture', '/synthetic/private', 'qwen3.5:4b')
        self.assertGreater(plan['download_bytes'], 3_000_000_000)
        self.assertGreater(plan['minimum_new_disk_bytes'], plan['download_bytes'])
        self.assertFalse(plan['service_start_authorized'])
        calls = []
        controller = object.__new__(assist.PinnedStage)
        from types import SimpleNamespace
        controller.node_id = 'fixture'; controller.binding = plan['binding']
        controller.consent = SimpleNamespace(check=lambda *a: None)
        controller.wall_clock = lambda: 1
        controller.stage = lambda: calls.append('stage') or {'state': 'STOP'}
        controller.install_runtime = lambda: calls.append('runtime') or {'state': 'STOP'}
        controller.install_model = lambda: calls.append('model') or {'state': 'STOP'}
        self.assertEqual(assist.deploy_customer_files(controller)['state'], 'STOP')
        self.assertEqual(calls, ['stage'])
        calls.clear()
        controller.stage = lambda: calls.append('stage') or {'state': 'STAGED_NOT_INSTALLED'}
        self.assertEqual(assist.deploy_customer_files(controller)['state'], 'STOP')
        self.assertEqual(calls, ['stage', 'runtime'])

    def test_asset_redirect_accepts_only_observed_runtime_edge(self):
        with patch.object(sys, 'path', [str(ROOT / '.agents/skills/long-horizon-engineering/scripts'), *sys.path]):
            assist = importlib.import_module('local_model_assist')
        catalog = assist.load_catalog(); model = catalog['models'][0]
        blob = assist.catalog_blob(model, catalog, kind='runtime-archive',
                                  sha256=catalog['runtime']['darwin_asset']['sha256'])
        handler = assist.AssetRedirect(blob)
        req = assist.Request(blob.url)
        redirected = handler.redirect_request(req, None, 302, '', {},
                                    'https://release-assets.githubusercontent.com/owned?sig=synthetic')
        self.assertEqual(redirected.host, 'release-assets.githubusercontent.com')
        with self.assertRaisesRegex(assist.Stopped, 'ASSET_REDIRECT_REJECTED'):
            handler.redirect_request(req, None, 302, '', {}, 'https://release-assets.githubusercontent.com/again')
        with self.assertRaisesRegex(assist.Stopped, 'ASSET_REDIRECT_REJECTED'):
            assist.AssetRedirect(blob).redirect_request(req, None, 302, '', {}, 'https://unapproved.example/asset')

    def test_qualification_fixture_never_mints_native_node(self):
        with patch.object(sys, 'path', [str(ROOT / '.agents/skills/long-horizon-engineering/scripts'), *sys.path]):
            assist = importlib.import_module('local_model_assist')
        from types import SimpleNamespace
        catalog = assist.load_catalog()
        model = catalog['models'][0]
        calls = []
        client = SimpleNamespace(model=model['id'], version=model['provider_version'],
                                 pin=model['manifest_sha256'], endpoint='http://127.0.0.1:11434', transport=lambda *_: None,
                                 execute=lambda task: (calls.append(task) or '{"INFO":1,"ERROR":2}', {}))
        scope = 'file:/synthetic'
        grant = assist.Grant('fixture', {'qualify'}, 100, 'fixture',
                            assist.task_binding(client, 'log-summary', scope))
        snapshot = {'memory_total_gb': 32, 'memory_available_gb': 24,
                    'unified_memory': True, 'free_storage_gb': 30}
        result = assist.qualify_customer_task('fixture', snapshot, client,
                    'log-summary', scope, grant, native_probe=True, now=lambda: 1)
        self.assertEqual(result['state'], 'TASK_CHECK_PASSED')
        self.assertEqual(result['evidence_kind'], 'SYNTHETIC')
        self.assertFalse(result['qualified'])
        self.assertNotIn('node', result)
        self.assertEqual(len(calls), 1)
        client.execute = lambda task: ('{"INFO":1,"ERROR":2}',
                                      {'prompt_eval_count': 'UNTRUSTED_BODY',
                                       'eval_count': {'body': 'UNTRUSTED_BODY'}})
        unknown = assist.qualify_customer_task('fixture', snapshot, client,
                    'log-summary', scope, grant, now=lambda: 1)
        self.assertIsNone(unknown['usage']['total_tokens'])
        self.assertNotIn('UNTRUSTED_BODY', json.dumps(unknown))
        calls.clear()
        with self.assertRaisesRegex(assist.Stopped, 'RESOURCES_INSUFFICIENT'):
            assist.qualify_customer_task('fixture', {}, client, 'log-summary', scope, grant, now=lambda: 1)
        self.assertEqual(calls, [])

    def test_customer_setup_decline_and_scoped_consent(self):
        with patch.object(sys, 'path', [str(ROOT / '.agents/skills/long-horizon-engineering/scripts'), *sys.path]):
            assist = importlib.import_module('local_model_assist')
        calls = []
        def reader(node):
            calls.append(node)
            return {'os': 'Linux', 'memory_total_gb': 32,
                    'memory_available_gb': 24, 'free_storage_gb': 30,
                    'accelerator': 'NVIDIA', 'gpu_memory_gb': 16}
        for answers, state in ((['no'], 'SKIPPED'), (['yes', 'no'], 'PROBE_DECLINED')):
            it = iter(answers)
            result = assist.customer_setup('fixture', '/synthetic', ask=lambda _: next(it), reader=reader, now=lambda: 1)
            self.assertEqual(result['state'], state)
            self.assertEqual(calls, [])
        it = iter(['yes', 'yes'])
        result = assist.customer_setup('fixture', '/synthetic', ask=lambda _: next(it), reader=reader, now=lambda: 1)
        self.assertEqual(calls, ['fixture'])
        self.assertEqual(result['state'], 'RECOMMENDATION_ONLY')
        self.assertFalse(result['deployment_authorized'])
        self.assertFalse(result['inference_authorized'])
        self.assertEqual(result['qualification'], 'NOT_RUN')

    def test_default_install_imports_beta_without_effects(self):
        self.check_installed_beta('profile')

    def test_direct_install_imports_beta_without_effects(self):
        self.check_installed_beta('direct')

    def check_installed_beta(self, mode):
        # Catches omitted inventory entries and imports tied to repository scripts.
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'installed'
            command = [
                sys.executable, str(ROOT / 'scripts/assemble_skill_profile.py'),
                '--profile', 'local-governance-core', '--output-root', str(target),
                '--apply',
            ]
            if mode == 'direct':
                target.mkdir()
                command = [sys.executable, str(ROOT / '.agents/skills/long-horizon-engineering/scripts/update_installed_skill.py'),
                           '--target-root', str(target), '--skill', 'long-horizon-engineering', '--apply']
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            skill = target / '.agents/skills/long-horizon-engineering'
            self.assertTrue((skill / 'SKILL.md').is_file())
            # Execute the README commands verbatim (substituting the installed
            # absolute path), outside the checkout, without injected sys.path.
            for arguments, state in ((['status'], 'OPT_IN_REQUIRED'),
                                     (['prepare', '--model-id', 'qwen3.5:4b'],
                                      'CONSENT_REQUIRED'),
                                     (['deployment-plan', '--install-root', '/synthetic/private'],
                                      'DEPLOYMENT_CONSENT_REQUIRED')):
                launched = subprocess.run(
                    [sys.executable, '-I', '-B',
                     str(skill / 'scripts/local_model_assist.py'), *arguments],
                    cwd=temporary, capture_output=True, text=True, timeout=10)
                self.assertEqual(launched.returncode, 0, launched.stderr)
                self.assertEqual(json.loads(launched.stdout)['state'], state)
            for name in ('local_compute_deployment', 'local_compute_pool', 'local_model_assist'):
                self.assertTrue((skill / 'scripts' / (name + '.py')).is_file(), name)
            script = r'''
import sys, os, json
sys.path.insert(0, sys.argv[1])
def audit(event, args):
    if event.startswith(('socket.', 'subprocess.', 'os.spawn', 'os.exec')) or event in ('os.system', 'os.mkdir', 'os.remove', 'os.rename'):
        raise AssertionError('unexpected effect: ' + event)
    if event == 'open':
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            raise AssertionError('unexpected write')
sys.addaudithook(audit)
import local_compute_deployment as deployment
import local_compute_pool as pool
import local_model_assist as assist
try:
    deployment.collect_probe('unapproved', set(), lambda _: (_ for _ in ()).throw(AssertionError('reader invoked')))
except PermissionError:
    pass
else:
    raise AssertionError('probe did not require consent')
assert deployment.minimum_value_gate({}) == 'INSUFFICIENT_EVIDENCE'
assert pool.Node('unapproved').consent is False
assert callable(pool.TaskPool)
assert callable(assist.run_local)
assert assist.NAME == "本地算力辅助（Beta）"
assert assist.load_catalog()["runtime"]["version"] == "0.40.13"
print(json.dumps([deployment.__file__, pool.__file__, assist.__file__]))
'''
            result = subprocess.run([sys.executable, '-I', '-B', '-c', script,
                                     str(skill / 'scripts')], cwd=temporary,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for path in json.loads(result.stdout):
                self.assertTrue(Path(path).is_relative_to(skill))
            result = subprocess.run([sys.executable, '-B', str(skill / 'scripts/check_skill_package.py'),
                                     '--installed'], cwd=target, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
