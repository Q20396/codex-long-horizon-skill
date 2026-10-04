"""Real effects use synthetic temporary files, processes and repositories only."""
from dataclasses import replace, asdict
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/long-horizon-engineering/scripts'


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_path = sys.path[:]
        cls.saved_modules = {name: sys.modules.get(name) for name in
            ('runtime_binding', 'runtime_safety_envelope', 'critical_execution_trace', 'security_authority_chain')}
        sys.path.insert(0, str(SCRIPTS))
        cls.m = importlib.import_module('runtime_binding') if (SCRIPTS / 'runtime_binding.py').exists() else None

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = cls.saved_path
        for name, module in cls.saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def setUp(self):
        self.assertIsNotNone(self.m, 'runtime binding implementation missing')
        self.r, self.c, self.s = self.m.rse, self.m.cet, self.m.sc
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.broker = self.r.CapabilityBroker()
        self.journal = self.r.InMemorySecurityJournal()
        self.chain = self.s.InMemorySecurityChain('chain', 'install')
        self.actor = self.s.SecurityAuthority('runtime', self.s.AuthorityRole.RUNTIME, 'install')
        self.fs = self.m.FilesystemAdapter(workspace_root=str(self.root))
        self.broker.register('filesystem.read', self.fs)
        self.broker.register('filesystem.write', self.fs)

    def action(self, kind='READ_FILE', target=None, ident='a', destination=None):
        kind = self.r.ActionClass[kind]
        return self.r.ActionRequest(ident, 'run', 'task', kind, str(target or self.root / 'a'),
            'trusted', 'local', self.r.DataClass.NON_SENSITIVE, 'auth', self.r.CAPABILITIES[kind],
            'synthetic effect', destination=None if destination is None else str(destination))

    def execute(self, action, payload=None, **kw):
        payload = payload or self.m.RuntimePayload(action.action_id)
        approved_digest = kw.pop('expected_payload_digest', payload.digest())
        self.binding = self.m.RuntimeBinding(self.broker, self.journal, self.chain, self.actor,
            approved_payload_digests={action.action_id: approved_digest})
        policy = self.r.Policy('core', self.r.PolicyLevel.CORE, frozenset(self.r.ActionClass),
            read_roots=(str(self.root),), write_roots=(str(self.root),),
            allowed_capabilities=frozenset(self.r.CAPABILITIES.values()))
        auth = self.r.Authorization('auth', 'task', frozenset({action.action_class}),
            tuple(t for t in (action.target, action.destination) if t), frozenset({action.capability}), 100)
        context = self.c.TraceContext('trace', 'install', 'project', 'task', 'run', action.action_id,
            None, 'trusted', None, 'local')
        args = dict(policy_stack=(policy,),
                    authorization=auth, context=context, now=1)
        args.update(kw)
        return self.binding.execute(action, payload, **args)

    def test_real_read_and_redacted_chain(self):
        (self.root / 'a').write_bytes(b'SYNTHETIC_CONTENT')
        out = self.execute(self.action())
        self.assertEqual(out.content_bytes, b'SYNTHETIC_CONTENT')
        self.assertEqual(out.receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertEqual(out.evidence.content_digest, hashlib.sha256(b'SYNTHETIC_CONTENT').hexdigest())
        self.assertEqual([e.event_type.value for e in out.events], ['FILE_READ'])
        self.assertNotIn('SYNTHETIC_CONTENT', json.dumps([asdict(x) for x in self.chain.records()]))
        self.assertTrue(self.chain.verify().valid)

    def test_denial_never_calls_adapter(self):
        with patch.object(self.fs, 'run', side_effect=AssertionError('called')):
            out = self.execute(self.action(), authorization=None)
        self.assertEqual(out.receipt.policy_reason, 'AUTHORIZATION_MISSING')
        self.assertEqual(out.events, ())

    def test_payload_substitution_and_action_mismatch(self):
        a = self.action('CREATE_FILE')
        p = self.m.RuntimePayload('a', content_bytes=b'approved')
        out = self.execute(a, replace(p, content_bytes=b'substituted'), expected_payload_digest=p.digest())
        self.assertEqual(out.boundary_status, 'PAYLOAD_DIGEST_MISMATCH')
        self.assertFalse((self.root / 'a').exists())
        out = self.execute(a, replace(p, action_id='different'))
        self.assertEqual(out.boundary_status, 'MALFORMED_RUNTIME_PAYLOAD')

    def test_create_write_delete_move(self):
        p = self.m.RuntimePayload('a', content_bytes=b'one')
        out = self.execute(self.action('CREATE_FILE'), p)
        self.assertEqual(out.receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertEqual(self.execute(self.action('CREATE_FILE'), p).receipt.final_disposition, 'ALREADY_COMPLETED')
        self.execute(self.action('WRITE_FILE', ident='b'), self.m.RuntimePayload('b', content_bytes=b'two'))
        self.assertEqual((self.root / 'a').read_bytes(), b'two')
        out = self.execute(self.action('MOVE_FILE', ident='c', destination=self.root / 'b'))
        self.assertEqual(out.receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertFalse((self.root / 'a').exists())
        self.assertEqual((self.root / 'b').read_bytes(), b'two')
        self.execute(self.action('DELETE_FILE', self.root / 'b', ident='d'))
        self.assertFalse((self.root / 'b').exists())

    def test_create_existing_write_missing_directory_fifo(self):
        (self.root / 'a').write_bytes(b'old')
        out = self.execute(self.action('CREATE_FILE'), self.m.RuntimePayload('a', content_bytes=b'new'))
        self.assertEqual(out.receipt.execution_state, 'KNOWN_FAILURE')
        self.assertEqual((self.root / 'a').read_bytes(), b'old')
        out = self.execute(self.action('WRITE_FILE', self.root / 'missing', 'b'), self.m.RuntimePayload('b', content_bytes=b'new'))
        self.assertFalse((self.root / 'missing').exists())
        directory = self.root / 'dir'; directory.mkdir()
        self.assertEqual(self.execute(self.action('DELETE_FILE', directory, 'c')).receipt.execution_state, 'KNOWN_FAILURE')
        self.assertTrue(directory.exists())
        os.mkfifo(self.root / 'fifo')
        self.assertEqual(self.execute(self.action(target=self.root / 'fifo', ident='d')).receipt.execution_state, 'KNOWN_FAILURE')

    def test_symlinks_and_move_overwrite_denied(self):
        (self.root / 'a').write_bytes(b'old')
        (self.root / 'link').symlink_to(self.root, target_is_directory=True)
        out = self.execute(self.action(target=self.root / 'link' / 'a'))
        self.assertEqual(out.receipt.execution_state, 'KNOWN_FAILURE')
        (self.root / 'b').write_bytes(b'existing')
        out = self.execute(self.action('MOVE_FILE', ident='b', destination=self.root / 'b'))
        self.assertEqual(out.receipt.execution_state, 'KNOWN_FAILURE')
        self.assertEqual((self.root / 'b').read_bytes(), b'existing')

    def test_read_write_bounds(self):
        (self.root / 'a').write_bytes(b'x' * (8 * 1024 * 1024 + 1))
        self.assertEqual(self.execute(self.action()).receipt.execution_state, 'KNOWN_FAILURE')
        with self.assertRaises(ValueError):
            self.m.RuntimePayload('b', content_bytes=b'x' * (8 * 1024 * 1024 + 1))

    def test_post_effect_uncertainty_blocks_retry_and_reconciles(self):
        a = self.action('CREATE_FILE'); p = self.m.RuntimePayload('a', content_bytes=b'new')
        with patch.object(self.m.os, 'fsync', side_effect=OSError('synthetic fsync failure')):
            out = self.execute(a, p)
        self.assertEqual(out.receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(self.execute(a, p).receipt.policy_reason, 'UNKNOWN_OUTCOME_PENDING')
        out = self.binding.reconcile(a, p)
        self.assertEqual(out.final_disposition, 'RECONCILED_SUCCESS')

    def test_concurrent_one_effect(self):
        a = self.action('CREATE_FILE'); p = self.m.RuntimePayload('a', content_bytes=b'new')
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.execute(a, p), range(4)))
        self.assertEqual(sum(x.receipt.final_disposition == 'KNOWN_SUCCESS' for x in results), 1)

    def process(self, code, ident='a', **kw):
        exe = str(Path(sys.executable).resolve())
        if not self.broker.has('process.execute'):
            self.broker.register('process.execute', self.m.ProcessAdapter(workspace_root=str(self.root), allowed_executables=(exe,)))
        a = self.action('EXECUTE_PROCESS', exe, ident)
        p = self.m.RuntimePayload(ident, argv=(exe, '-c', code), **kw)
        return self.execute(a, p)

    def test_process_success_environment_and_output_bounds(self):
        with patch.dict(os.environ, {'SYNTHETIC_PRIVATE_MARKER': 'private'}):
            out = self.process("import os,sys; print(os.getenv('SYNTHETIC_PRIVATE_MARKER','absent')); sys.stderr.write('err')")
        self.assertEqual(out.stdout, b'absent\n')
        self.assertEqual(out.stderr, b'err')
        self.assertEqual([e.event_type.value for e in out.events], ['PROCESS_START', 'PROCESS_EXIT'])
        self.assertEqual(out.completeness, self.c.TraceCompleteness.PARTIAL)
        out = self.process("import sys; sys.stdout.write('x'*1100000); sys.stderr.write('y'*1100000)", 'b')
        self.assertEqual(len(out.stdout), 1024 * 1024)
        self.assertTrue(out.evidence.stdout_truncated and out.evidence.stderr_truncated)

    def test_process_timeout_unknown(self):
        out = self.process('import time; time.sleep(1)', timeout=0.05)
        self.assertEqual(out.receipt.execution_state, 'UNKNOWN_OUTCOME')
        out = self.process('import time; time.sleep(1)', timeout=0.05)
        self.assertEqual(out.receipt.policy_reason, 'UNKNOWN_OUTCOME_PENDING')

    def test_process_shell_and_allowlist_cwd(self):
        with self.assertRaises(ValueError):
            self.m.ProcessAdapter(workspace_root=str(self.root), allowed_executables=('/bin/sh',))
        with self.assertRaises(ValueError):
            self.m.RuntimePayload('a', argv='echo bad')
        out = self.process('print(1)', cwd='/')
        self.assertEqual(out.receipt.execution_state, 'KNOWN_FAILURE')

    def git(self, *args):
        return subprocess.run([shutil.which('git'), '-C', str(self.root), *args], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={'PATH': '/usr/bin:/bin', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null'})

    def setup_git(self):
        self.git('init', '-q')
        self.git('config', 'user.name', 'Synthetic')
        self.git('config', 'user.email', 'synthetic@example.invalid')
        adapter = self.m.LocalGitAdapter(workspace_root=str(self.root), git_executable=str(Path(shutil.which('git')).resolve()))
        self.broker.register('git.stage', adapter); self.broker.register('git.commit', adapter)

    def test_git_exact_stage_hooks_signing_and_commit(self):
        self.setup_git()
        (self.root / 'a').write_text('a'); (self.root / 'b').write_text('b')
        hook = self.root / '.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\ntouch marker\n'); hook.chmod(0o700)
        self.git('config', 'commit.gpgSign', 'true')
        self.git('config', 'gpg.program', '/does/not/exist')
        stage = self.execute(self.action('GIT_STAGE', self.root), self.m.RuntimePayload('a', git_paths=('a',)))
        self.assertEqual(stage.receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertEqual(self.git('diff', '--cached', '--name-only').stdout, b'a\n')
        out = self.execute(self.action('GIT_COMMIT', self.root, 'b'), self.m.RuntimePayload('b', commit_message='SYNTHETIC_MESSAGE'))
        self.assertEqual(out.receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertEqual(out.evidence.commit_sha, self.git('rev-parse', 'HEAD').stdout.decode().strip())
        self.assertFalse((self.root / 'marker').exists())
        self.assertNotIn('SYNTHETIC_MESSAGE', json.dumps([asdict(x) for x in self.chain.records()]))

    def test_git_filter_and_broad_stage_denied(self):
        self.setup_git(); (self.root / 'a').write_text('a')
        self.git('config', 'filter.trap.clean', 'touch marker')
        (self.root / '.gitattributes').write_text('* filter=trap\n')
        out = self.execute(self.action('GIT_STAGE', self.root), self.m.RuntimePayload('a', git_paths=('a',)))
        self.assertEqual(out.receipt.execution_state, 'KNOWN_FAILURE')
        self.assertFalse((self.root / 'marker').exists())
        for path in ('.', '-A', '--all', '*.txt'):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    self.m.RuntimePayload('b', git_paths=(path,))

    def test_unknown_commit_read_only_reconciliation(self):
        self.setup_git(); (self.root / 'a').write_text('a')
        self.execute(self.action('GIT_STAGE', self.root), self.m.RuntimePayload('a', git_paths=('a',)))
        adapter = self.broker.get('git.commit')
        original = adapter._call
        def uncertain(args):
            result = original(args)
            if args[0] == 'commit':
                return result[0], result[1], result[2], result[3], True
            return result
        a = self.action('GIT_COMMIT', self.root, 'commit')
        p = self.m.RuntimePayload('commit', commit_message='synthetic reconciliation')
        with patch.object(adapter, '_call', side_effect=uncertain):
            out = self.execute(a, p)
        self.assertEqual(out.receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(self.binding.reconcile(a, p).final_disposition, 'RECONCILED_SUCCESS')
        self.assertEqual(self.git('rev-list', '--count', 'HEAD').stdout, b'1\n')

    def test_git_metadata_symlink_escape_denied(self):
        self.setup_git(); (self.root / 'a').write_text('a')
        with tempfile.TemporaryDirectory() as outside:
            objects = self.root / '.git/objects'
            shutil.rmtree(objects)
            objects.symlink_to(outside, target_is_directory=True)
            out = self.execute(self.action('GIT_STAGE', self.root), self.m.RuntimePayload('a', git_paths=('a',)))
            self.assertEqual(out.receipt.execution_state, 'KNOWN_FAILURE')
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_move_unknown_retains_digest_for_reconciliation(self):
        (self.root / 'a').write_bytes(b'move me')
        a = self.action('MOVE_FILE', destination=self.root / 'b'); p = self.m.RuntimePayload('a')
        with patch.object(self.m.os, 'fsync', side_effect=OSError('synthetic')):
            out = self.execute(a, p)
        self.assertEqual(out.receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(self.binding.reconcile(a, p).final_disposition, 'RECONCILED_SUCCESS')

    def test_chain_failure_blocks_retry_with_current_receipt(self):
        a = self.action('CREATE_FILE'); p = self.m.RuntimePayload('a', content_bytes=b'new')
        with patch.object(self.chain, 'append', side_effect=OSError('synthetic')):
            out = self.execute(a, p)
        self.assertEqual(out.boundary_status, 'SECURITY_BOUNDARY_FAILURE')
        self.assertEqual((self.root / 'a').read_bytes(), b'new')
        self.assertEqual(self.execute(a, p).receipt.policy_reason, 'UNKNOWN_OUTCOME_PENDING')

    def test_actual_extra_effect_divergence_is_recorded(self):
        original = self.fs.run
        def extra(action, payload, context, now):
            out = original(action, payload, context, now)
            extra_event = self.m._event(action, context, now, self.c.CriticalEventType.FILE_WRITE)
            return replace(out, events=out.events + (extra_event,))
        (self.root / 'a').write_bytes(b'one')
        with patch.object(self.fs, 'run', side_effect=extra):
            out = self.execute(self.action())
        self.assertEqual(out.boundary_status, 'TRACE_DIVERGENCE')
        self.assertEqual(out.divergences[0].divergence_type.value, 'UNDECLARED_WRITE')
        self.assertTrue(any(r.event_type == 'TRACE_DIVERGENCE' for r in self.chain.records()))

    def test_unsupported_platform_and_no_capability_fail_closed(self):
        (self.root / 'a').write_bytes(b'one')
        with patch.object(self.m.os, 'supports_dir_fd', set()):
            out = self.execute(self.action())
        self.assertEqual(out.evidence.reason, 'PLATFORM_UNSUPPORTED')
        self.broker = self.r.CapabilityBroker()
        out = self.execute(self.action(ident='b'))
        self.assertEqual(out.receipt.policy_reason, 'CAPABILITY_MISSING')

    def test_preapproved_map_copied_and_cannot_be_reset_by_execute(self):
        p = self.m.RuntimePayload('a', content_bytes=b'approved')
        approvals = {'a': p.digest()}
        binding = self.m.RuntimeBinding(self.broker, self.journal, self.chain, self.actor, approved_payload_digests=approvals)
        approvals['a'] = self.m.RuntimePayload('a', content_bytes=b'changed').digest()
        self.assertEqual(binding.approved_payload_digests['a'], p.digest())
        with self.assertRaises(TypeError):
            binding.approved_payload_digests['a'] = approvals['a']

    def test_git_editor_pager_signer_and_alias_traps(self):
        self.setup_git(); (self.root / 'a').write_text('a')
        for key in ('core.editor', 'core.pager', 'gpg.program'):
            self.git('config', key, 'touch marker')
        self.git('config', 'commit.gpgSign', 'true')
        self.execute(self.action('GIT_STAGE', self.root), self.m.RuntimePayload('a', git_paths=('a',)))
        out = self.execute(self.action('GIT_COMMIT', self.root, 'b'), self.m.RuntimePayload('b', commit_message='synthetic'))
        self.assertEqual(out.receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertFalse((self.root / 'marker').exists())

        self.git('config', 'alias.add', '!touch marker')
        out = self.execute(self.action('GIT_STAGE', self.root, 'c'), self.m.RuntimePayload('c', git_paths=('a',)))
        self.assertEqual(out.receipt.execution_state, 'KNOWN_FAILURE')
        self.assertFalse((self.root / 'marker').exists())

    def test_process_default_timeout_and_descriptor_cwd(self):
        exe = str(Path(sys.executable).resolve())
        self.broker.register('process.execute', self.m.ProcessAdapter(workspace_root=str(self.root),
            allowed_executables=(exe,), default_timeout=0.05))
        out = self.process('import time; time.sleep(0.2)')
        self.assertEqual(out.receipt.execution_state, 'UNKNOWN_OUTCOME')
        original = self.m.subprocess.Popen
        cwd = self.root / 'cwd'; cwd.mkdir()
        moved = self.root / 'moved'
        with tempfile.TemporaryDirectory() as outside:
            def replaced(*args, **kw):
                cwd.rename(moved)
                cwd.symlink_to(outside, target_is_directory=True)
                return original(*args, **kw)
            with patch.object(self.m.subprocess, 'Popen', side_effect=replaced):
                out = self.process("open('marker','w').write('inside')", 'other', timeout=1, cwd=str(cwd))
            self.assertEqual(out.receipt.execution_state, 'KNOWN_SUCCESS')
            self.assertEqual((moved / 'marker').read_text(), 'inside')
            self.assertFalse((Path(outside) / 'marker').exists())

    def test_write_not_applied_reconciliation(self):
        (self.root / 'a').write_bytes(b'before')
        a = self.action('WRITE_FILE'); p = self.m.RuntimePayload('a', content_bytes=b'after')
        with patch.object(self.m.os, 'ftruncate', side_effect=OSError('synthetic')):
            out = self.execute(a, p)
        self.assertEqual(out.receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(self.binding.reconcile(a, p).final_disposition, 'RECONCILED_NOT_APPLIED')

    def test_chain_installation_mismatch_prevents_effect(self):
        self.chain = self.s.InMemorySecurityChain('chain', 'different-install')
        out = self.execute(self.action('CREATE_FILE'), self.m.RuntimePayload('a', content_bytes=b'new'))
        self.assertEqual(out.boundary_status, 'SECURITY_BOUNDARY_FAILURE')
        self.assertFalse((self.root / 'a').exists())

    def test_process_denied_executable_and_policy_never_launch(self):
        exe = str(Path(sys.executable).resolve())
        self.broker.register('process.execute', self.m.ProcessAdapter(workspace_root=str(self.root), allowed_executables=(exe,)))
        a = self.action('EXECUTE_PROCESS', '/usr/bin/false')
        with patch.object(self.m.subprocess, 'Popen', side_effect=AssertionError('must not launch')):
            out = self.execute(a, self.m.RuntimePayload('a', argv=('/usr/bin/false',)))
        self.assertEqual(out.receipt.execution_state, 'KNOWN_FAILURE')
        deny = self.r.Policy('deny', self.r.PolicyLevel.CORE)
        with patch.object(self.fs, 'run', side_effect=AssertionError('must not execute')):
            out = self.execute(self.action(ident='b'), policy_stack=(deny,))
        self.assertEqual(out.receipt.policy_disposition, 'DENY')

    def test_distinct_actions_and_unknown_create_not_applied(self):
        a = self.action('CREATE_FILE'); p = self.m.RuntimePayload('a', content_bytes=b'a')
        with patch.object(self.m.os, 'ftruncate', side_effect=OSError('synthetic')):
            self.execute(a, p)
        (self.root / 'a').unlink()
        self.assertEqual(self.binding.reconcile(a, p).final_disposition, 'RECONCILED_NOT_APPLIED')
        a2 = self.action('CREATE_FILE', self.root / 'b', 'b'); p2 = self.m.RuntimePayload('b', content_bytes=b'b')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda ap: self.execute(*ap), ((a, p), (a2, p2))))
        self.assertTrue(all(x.receipt.execution_state == 'KNOWN_SUCCESS' for x in results))

    def test_import_no_effects_and_no_registration(self):
        import builtins
        import importlib.util
        import socket
        import threading
        spec = importlib.util.spec_from_file_location('runtime_binding_import_probe', SCRIPTS / 'runtime_binding.py')
        module = importlib.util.module_from_spec(spec)
        # Source is read before guards; importing source itself is loader work.
        code = compile((SCRIPTS / 'runtime_binding.py').read_text(), str(SCRIPTS / 'runtime_binding.py'), 'exec')
        sys.modules[spec.name] = module
        before = dict(os.environ)
        try:
            with patch.object(builtins, 'open', side_effect=AssertionError('file effect')), \
                 patch.object(os, 'open', side_effect=AssertionError('file effect')), \
                 patch.object(subprocess, 'Popen', side_effect=AssertionError('process effect')), \
                 patch.object(socket, 'socket', side_effect=AssertionError('network effect')), \
                 patch.object(threading.Thread, 'start', side_effect=AssertionError('thread effect')):
                exec(code, module.__dict__)
            self.assertEqual(dict(os.environ), before)
            broker = self.r.CapabilityBroker()
            self.assertFalse(any(broker.has(v) for v in self.r.CAPABILITIES.values()))
        finally:
            sys.modules.pop(spec.name, None)

    def test_local_file_boundary_never_opens_socket(self):
        import socket
        (self.root / 'a').write_bytes(b'local')
        with patch.object(socket, 'socket', side_effect=AssertionError('network not permitted')):
            out = self.execute(self.action())
        self.assertEqual(out.content_bytes, b'local')

    def test_out_of_scope_actions_not_bound(self):
        for kind in ('NETWORK_REQUEST', 'SECRET_ACCESS', 'PACKAGE_INSTALL', 'SERVICE_START',
                     'SERVICE_STOP', 'GIT_PUSH', 'PR_CREATE', 'PR_MERGE', 'RELEASE', 'DEPLOY'):
            with self.subTest(kind=kind):
                out = self.execute(self.action(kind, 'https://invalid.example/', kind), self.m.RuntimePayload(kind))
                self.assertEqual(out.boundary_status, 'NOT_BOUND')
                self.assertEqual(out.receipt.execution_state, 'NOT_ATTEMPTED')

    def test_move_outside_and_symlink_parent_denied(self):
        (self.root / 'a').write_bytes(b'source')
        with tempfile.TemporaryDirectory() as outside:
            link = self.root / 'link'; link.symlink_to(outside, target_is_directory=True)
            out = self.execute(self.action('MOVE_FILE', destination=link / 'b'))
            self.assertEqual(out.receipt.execution_state, 'KNOWN_FAILURE')
            self.assertEqual((self.root / 'a').read_bytes(), b'source')
            self.assertFalse((Path(outside) / 'b').exists())
            out = self.execute(self.action('MOVE_FILE', ident='b', destination=Path(outside) / 'b'))
            self.assertEqual(out.receipt.policy_reason, 'PATH_OUT_OF_SCOPE')

    def test_foreign_event_context_fails_boundary(self):
        (self.root / 'a').write_bytes(b'read')
        original = self.fs.run
        def wrong(action, payload, context, now):
            out = original(action, payload, context, now)
            event = replace(out.events[0], context=replace(context, action_id='different'))
            return replace(out, events=(event,))
        with patch.object(self.fs, 'run', side_effect=wrong):
            out = self.execute(self.action())
        self.assertEqual(out.boundary_status, 'SECURITY_BOUNDARY_FAILURE')
        self.assertEqual(self.execute(self.action()).receipt.policy_reason, 'UNKNOWN_OUTCOME_PENDING')

    def test_payload_incompatible_fields_and_timeout_none(self):
        p = self.m.RuntimePayload('a', content_bytes=b'not a read')
        out = self.execute(self.action(), p)
        self.assertEqual(out.boundary_status, 'MALFORMED_RUNTIME_PAYLOAD')
        with self.assertRaises(ValueError):
            self.m.RuntimePayload('a', argv=('/usr/bin/true',), timeout=None)

    def test_payload_approval_change_cannot_reuse_action_identity(self):
        a = self.action('CREATE_FILE'); p = self.m.RuntimePayload('a', content_bytes=b'original')
        self.execute(a, p)
        changed = self.m.RuntimePayload('a', content_bytes=b'changed')
        out = self.execute(a, changed)
        self.assertEqual(out.receipt.policy_reason, 'ACTION_ID_CONFLICT')
        self.assertEqual((self.root / 'a').read_bytes(), b'original')

    def test_environment_unknown_override_and_nonzero_unknown(self):
        out = self.process('print(1)', environment=(('UNAPPROVED', 'value'),))
        self.assertEqual(out.receipt.execution_state, 'KNOWN_FAILURE')
        out = self.process("open('marker','w').write('synthetic'); raise SystemExit(2)", 'b')
        self.assertEqual(out.receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual((self.root / 'marker').read_text(), 'synthetic')

    def test_read_evidence_and_output_raw_bytes_not_in_chain(self):
        out = self.process("import sys; print('SYNTHETIC_STDOUT'); sys.stderr.write('SYNTHETIC_STDERR')")
        self.assertIn(b'SYNTHETIC_STDOUT', out.stdout)
        serialized = json.dumps([asdict(row) for row in self.chain.records()])
        self.assertNotIn('SYNTHETIC_STDOUT', serialized)
        self.assertNotIn('SYNTHETIC_STDERR', serialized)
        self.assertNotIn('MODEL_USAGE', serialized)

    def test_reconcile_retains_evidence_after_chain_failure(self):
        (self.root / 'a').write_bytes(b'move')
        a = self.action('MOVE_FILE', destination=self.root / 'b'); p = self.m.RuntimePayload('a')
        with patch.object(self.chain, 'append', side_effect=OSError('synthetic')):
            out = self.execute(a, p)
        self.assertEqual(out.evidence.content_digest, hashlib.sha256(b'move').hexdigest())
        self.assertEqual(len(out.events), 1)
        self.assertEqual(self.binding.reconcile(a, p).final_disposition, 'RECONCILED_SUCCESS')

    def test_helper_failure_does_not_report_target_start(self):
        exe = self.root / 'fixture'
        shutil.copyfile('/usr/bin/true', exe); exe.chmod(0o700)
        self.broker.register('process.execute', self.m.ProcessAdapter(workspace_root=str(self.root), allowed_executables=(str(exe),)))
        original = self.m.subprocess.Popen
        def changed(*args, **kw):
            exe.unlink()
            return original(*args, **kw)
        with patch.object(self.m.subprocess, 'Popen', side_effect=changed):
            out = self.execute(self.action('EXECUTE_PROCESS', exe), self.m.RuntimePayload('a', argv=(str(exe),)))
        self.assertEqual(out.receipt.execution_state, 'KNOWN_FAILURE')
        self.assertEqual(out.events, ())

    def test_launcher_has_minimal_env_but_target_gets_approved_env(self):
        exe = str(Path(sys.executable).resolve())
        self.broker.register('process.execute', self.m.ProcessAdapter(workspace_root=str(self.root),
            allowed_executables=(exe,), base_env={'SYNTHETIC_ALLOWED': 'approved'}))
        original = self.m.subprocess.Popen
        def minimal(*args, **kw):
            self.assertEqual(kw['env'], {})
            return original(*args, **kw)
        with patch.object(self.m.subprocess, 'Popen', side_effect=minimal):
            out = self.process("import os; print(os.getenv('SYNTHETIC_ALLOWED'))")
        self.assertEqual(out.stdout, b'approved\n')

    def test_all_eight_effects_have_attempted_journal_before_adapter(self):
        self.setup_git()
        exe = str(Path(sys.executable).resolve())
        process = self.m.ProcessAdapter(workspace_root=str(self.root), allowed_executables=(exe,))
        self.broker.register('process.execute', process)
        seen = []
        def guard(adapter):
            original = adapter.run
            def run(action, *args):
                self.assertEqual(self.journal.latest(action.action_id).state, self.r.JournalState.ATTEMPTED)
                seen.append(action.action_class.value)
                return original(action, *args)
            return patch.object(adapter, 'run', side_effect=run)
        git_adapter = self.broker.get('git.stage')
        with guard(self.fs), guard(process), guard(git_adapter):
            fixtures = [
                (self.action('CREATE_FILE', ident='create'), self.m.RuntimePayload('create', content_bytes=b'one')),
                (self.action('READ_FILE', ident='read'), self.m.RuntimePayload('read')),
                (self.action('WRITE_FILE', ident='write'), self.m.RuntimePayload('write', content_bytes=b'two')),
                (self.action('MOVE_FILE', ident='move', destination=self.root / 'b'), self.m.RuntimePayload('move')),
                (self.action('DELETE_FILE', self.root / 'b', 'delete'), self.m.RuntimePayload('delete')),
                (self.action('EXECUTE_PROCESS', exe, 'process'), self.m.RuntimePayload('process', argv=(exe, '-c', 'pass'))),
            ]
            for action, payload in fixtures:
                self.assertEqual(self.execute(action, payload).receipt.execution_state, 'KNOWN_SUCCESS')
            (self.root / 'stage-file').write_text('synthetic')
            for kind, ident, kwargs in [('GIT_STAGE', 'stage', {'git_paths': ('stage-file',)}),
                                       ('GIT_COMMIT', 'commit', {'commit_message': 'synthetic'})]:
                out = self.execute(self.action(kind, self.root, ident), self.m.RuntimePayload(ident, **kwargs))
                self.assertEqual(out.receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertEqual(set(seen), {'CREATE_FILE', 'READ_FILE', 'WRITE_FILE', 'MOVE_FILE', 'DELETE_FILE',
            'EXECUTE_PROCESS', 'GIT_STAGE', 'GIT_COMMIT'})

    def test_stage_authority_does_not_commit_and_subprocess_never_pushes(self):
        self.setup_git(); (self.root / 'a').write_text('a')
        original = self.m.subprocess.Popen
        observed = []
        def capture(*args, **kw):
            observed.append(json.loads(args[0][7]))
            return original(*args, **kw)
        with patch.object(self.m.subprocess, 'Popen', side_effect=capture):
            self.execute(self.action('GIT_STAGE', self.root), self.m.RuntimePayload('a', git_paths=('a',)))
            only_stage = self.r.Authorization('auth', 'task', frozenset({self.r.ActionClass.GIT_STAGE}),
                (str(self.root),), frozenset({'git.stage'}), 100)
            out = self.execute(self.action('GIT_COMMIT', self.root, 'b'),
                self.m.RuntimePayload('b', commit_message='synthetic'), authorization=only_stage)
        self.assertEqual(out.receipt.policy_reason, 'AUTHORIZATION_MISSING')
        self.assertEqual(self.git('rev-list', '--count', '--all').stdout, b'0\n')
        self.assertTrue(observed)
        self.assertFalse(any('push' in argv for argv in observed))


if __name__ == '__main__':
    unittest.main()
