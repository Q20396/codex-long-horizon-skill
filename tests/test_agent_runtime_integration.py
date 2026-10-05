"""Bridge contracts against real governed bindings and synthetic effects."""
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import asdict, replace
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from test_remote_runtime_binding import Service, PRService, GitService

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/long-horizon-engineering/scripts'


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_path = sys.path[:]
        sys.path.insert(0, str(SCRIPTS))
        cls.m = importlib.import_module('agent_runtime_integration') if (SCRIPTS / 'agent_runtime_integration.py').exists() else None

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = cls.saved_path

    def setUp(self):
        self.assertIsNotNone(self.m, 'governed agent bridge implementation missing')
        self.r, self.c, self.s = self.m.rse, self.m.cet, self.m.sc
        self.local, self.remote = self.m.local, self.m.remote
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.bridge = self.m.AgentRuntimeBridge()
        self.broker = self.r.CapabilityBroker()
        self.journal = self.r.InMemorySecurityJournal()
        self.chain = self.s.InMemorySecurityChain('chain', 'install')
        self.actor = self.s.SecurityAuthority('runtime', self.s.AuthorityRole.RUNTIME, 'install')
        self.fs = self.local.FilesystemAdapter(workspace_root=str(self.root))
        for cap in ('filesystem.read', 'filesystem.write'):
            self.broker.register(cap, self.fs)
        self.service = Service()
        self.broker.register('network.request', self.remote.NetworkRequestAdapter(
            transport=self.service, allowed_origins=('https://api.example.invalid',)))
        self.provider = PRService()
        self.broker.register(self.r.CAPABILITIES[self.r.ActionClass.PR_CREATE], self.remote.PullRequestCreateAdapter(
            transport=self.provider, allowed_origins=('https://api.example.invalid',)))
        self.policy = self.r.Policy('core', self.r.PolicyLevel.CORE, frozenset(self.r.ActionClass),
            read_roots=(str(self.root),), write_roots=(str(self.root),),
            network_mode=self.r.NetworkMode.ALLOWLIST, network_allowlist=('https://api.example.invalid',),
            allowed_egress_classes=frozenset({self.r.DataClass.NON_SENSITIVE}),
            allowed_capabilities=frozenset(self.r.CAPABILITIES.values()))
        self.addCleanup(patch.stopall)
        patch('socket.create_connection', side_effect=AssertionError('PUBLIC_NETWORK_FORBIDDEN')).start()

    def proposal(self, kind='CREATE_FILE', **changes):
        value = dict(proposal_id='proposal', requested_action_class=kind,
            requested_target=str(self.root / 'file'), requested_parameters={'content_bytes': b'content'})
        if kind == 'READ_FILE': value['requested_parameters'] = {}
        if kind == 'NETWORK_REQUEST':
            value.update(requested_target='https://api.example.invalid/resource',
                requested_parameters=dict(method='POST', body=b'content', request_identity='request-1'))
        if kind == 'PR_CREATE':
            value.update(requested_target='https://api.example.invalid/repos/team/repo/pulls',
                requested_parameters=dict(provider='github', repository='team/repo', head='feature', base='main',
                    title='Title', body=b'body', draft=True, request_identity='request-1'))
        value.update(changes)
        return value

    def prepare(self, proposal=None, ident='host-1', **kw):
        context = self.c.TraceContext('trace', 'install', 'project', 'task', 'run', ident,
            None, 'host-provider', 'host-model', 'runtime')
        args = dict(context=context, trusted_agent_id='host-agent', authorization_ref='auth',
            data_classification=self.r.DataClass.NON_SENSITIVE, now=1)
        args.update(kw)
        return self.bridge.prepare(proposal or self.proposal(), **args)

    def bind(self, *prepared):
        snapshot = {p.action_request.action_id: p.payload_digest for p in prepared}
        cls = self.remote.RemoteRuntimeBinding if prepared[0].payload_kind == 'REMOTE' else self.local.RuntimeBinding
        self.binding = cls(self.broker, self.journal, self.chain, self.actor, approved_payload_digests=snapshot)

    def execute(self, p, reconcile=False, **kw):
        a = p.action_request
        auth = self.r.Authorization('auth', 'task', frozenset({a.action_class}),
            tuple(x for x in (a.target, a.destination) if x), frozenset({a.capability}), 100)
        args = dict(binding=self.binding, expected_payload_digest=p.payload_digest,
            expected_prepared_digest=p.prepared_digest, policy_stack=(self.policy,), authorization=auth,
            context=p.context, now=2)
        args.update(kw)
        return (self.bridge.reconcile if reconcile else self.bridge.execute)(p, **args)

    def test_authority_and_capability_fields_rejected(self):
        for field in ('approved', 'authorized', 'authorization_id', 'role', 'authority', 'policy_level',
                'root_owner', 'installation_admin', 'task_authority', 'break_glass', 'trusted',
                'capability_grant', 'requested_capability', 'emergency_override', 'admin_override'):
            with self.subTest(field=field):
                self.assertEqual(self.prepare(self.proposal(**{field: 'pr.create'})).status, 'MALFORMED_PROPOSAL')
        self.assertEqual(self.chain.records(), ())

    def test_unknown_action_never_falls_back_to_process(self):
        self.assertEqual(self.prepare(self.proposal('shell')).status, 'NOT_SUPPORTED')
        self.assertEqual(self.prepare(self.proposal('PR_MERGE')).status, 'NOT_SUPPORTED')

    def test_prepare_pure_and_import_inactive(self):
        with ExitStack() as stack:
            for target in ('os.open', 'builtins.open', 'subprocess.Popen', 'socket.socket', 'threading.Thread.start'):
                stack.enter_context(patch(target, side_effect=AssertionError('EFFECT_DURING_PREPARE')))
            for cls in (self.local.FilesystemAdapter, self.local.ProcessAdapter, self.local.LocalGitAdapter,
                    self.remote.NetworkRequestAdapter, self.remote.GitPushAdapter, self.remote.PullRequestCreateAdapter):
                stack.enter_context(patch.object(cls, 'run' if hasattr(cls, 'run') else '_run', side_effect=AssertionError('ADAPTER_DURING_PREPARE')))
            stack.enter_context(patch.object(self.chain, 'append', side_effect=AssertionError('CHAIN_DURING_PREPARE')))
            stack.enter_context(patch.object(self.r.CapabilityBroker, 'register', side_effect=AssertionError('REGISTRATION')))
            before = dict(os.environ)
            self.assertEqual(self.prepare().status, 'PREPARED')
            importlib.reload(self.m)
            self.assertEqual(dict(os.environ), before)

    def test_deep_immutable_nested_input_and_redacted_repr(self):
        params = {'argv': ['/usr/bin/true'], 'environment': {'LANG': 'C'}, 'cwd': str(self.root)}
        data = self.proposal('EXECUTE_PROCESS', requested_target='/usr/bin/true', requested_parameters=params,
            reason_text='PRIVATE_MARKER', untrusted_model_ref='PRIVATE_MARKER')
        proposal = self.m.AgentActionProposal(**data)
        p = self.prepare(proposal).prepared
        params['argv'].append('PRIVATE_MARKER'); params['environment']['LANG'] = 'PRIVATE_MARKER'
        self.assertEqual(p.normalized_payload.argv, ('/usr/bin/true',))
        self.assertEqual(p.normalized_payload.environment, (('LANG', 'C'),))
        self.assertNotIn('PRIVATE_MARKER', repr(p) + repr(proposal))
        with self.assertRaises((AttributeError, TypeError)):
            p.normalized_payload.argv += ('changed',)

    def test_trusted_action_identity_and_provider_independence(self):
        for provider in ('OpenAI', 'Anthropic', 'human'):
            p = self.prepare(self.proposal(action_id='model-choice', untrusted_agent_ref='ROOT_OWNER',
                untrusted_provider_ref=provider)).prepared
            self.assertEqual(p.action_request.action_id, 'host-1')
            self.assertEqual(p.action_request.provider, 'host-provider')
            self.assertEqual(p.trusted_agent_id, 'host-agent')

    def test_tamper_target_class_capability_payload_prebinding(self):
        p = self.prepare().prepared; self.bind(p)
        for changes in (dict(action_request=replace(p.action_request, target=str(self.root / 'other'))),
                dict(action_request=replace(p.action_request, action_class=self.r.ActionClass.READ_FILE)),
                dict(trusted_agent_id='different'), dict(prepared_digest='0' * 64)):
            result = self.execute(replace(p, **changes), expected_prepared_digest=p.prepared_digest)
            self.assertEqual(result.status, 'INVALID_PREPARED_ACTION')
        self.assertEqual(self.execute(p, expected_payload_digest='0' * 64).status, 'PREPARED_PAYLOAD_MISMATCH')
        altered = replace(p, normalized_payload=replace(p.normalized_payload, content_bytes=b'evil'))
        self.assertEqual(self.execute(altered, expected_payload_digest=p.payload_digest).status, 'PREPARED_PAYLOAD_MISMATCH')
        altered = replace(p, trusted_capability_name='pr.create')
        self.assertEqual(self.execute(altered).status, 'CAPABILITY_ACTION_MISMATCH')
        self.assertFalse((self.root / 'file').exists())

    def test_declaration_unknown_and_mismatch(self):
        self.assertEqual(self.prepare().prepared.declaration_status, 'UNKNOWN')
        out = self.prepare(self.proposal(declared_effects={'reads': [str(self.root / 'file')]}))
        self.assertEqual(out.status, 'PREPARED')
        self.assertEqual(out.prepared.declaration_status, 'DECLARATION_ACTION_MISMATCH')
        self.assertEqual(out.prepared.declared_effects.reads, (str(self.root / 'file'),))

    def test_valid_local_read_create_and_success_replay(self):
        p = self.prepare().prepared; self.bind(p)
        self.assertEqual(self.execute(p).receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertEqual(self.execute(p).receipt.final_disposition, 'ALREADY_COMPLETED')
        p = self.prepare(self.proposal('READ_FILE'), 'read').prepared; self.bind(p)
        out = self.execute(p)
        self.assertEqual(out.runtime_result.content_bytes, b'content')
        self.assertEqual(out.events[0].source, self.c.ObservationSource.ADAPTER_OBSERVED)

    def test_missing_authorization_capability_policy_and_scope_denied(self):
        p = self.prepare().prepared; self.bind(p)
        self.assertEqual(self.execute(p, authorization=None).receipt.policy_reason, 'AUTHORIZATION_MISSING')
        denied = replace(self.policy, allowed_actions=frozenset())
        self.assertEqual(self.execute(p, policy_stack=(denied,)).receipt.policy_disposition, 'DENY')
        wrong = self.r.Authorization('auth', 'wrong-task', frozenset({p.action_request.action_class}),
            (p.action_request.target,), frozenset({p.trusted_capability_name}), 100)
        self.assertEqual(self.execute(p, authorization=wrong).receipt.policy_reason, 'AUTHORIZATION_MISSING')
        self.broker = self.r.CapabilityBroker(); self.bridge = self.m.AgentRuntimeBridge(); self.bind(p)
        self.assertEqual(self.execute(p).receipt.policy_reason, 'CAPABILITY_MISSING')
        self.assertFalse((self.root / 'file').exists())

    def test_unknown_local_create_new_proposal_and_reconcile(self):
        p = self.prepare().prepared
        q = self.prepare(self.proposal(proposal_id='new'), 'host-2').prepared
        self.bind(p, q)
        with patch('os.fsync', side_effect=OSError('synthetic')):
            self.assertEqual(self.execute(p).receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(self.execute(p).status, 'RECONCILIATION_REQUIRED')
        self.assertEqual(self.execute(q).status, 'RECONCILIATION_REQUIRED')
        self.assertEqual(self.execute(p, reconcile=True).receipt.final_disposition, 'RECONCILED_SUCCESS')
        self.assertEqual((self.root / 'file').read_bytes(), b'content')

    def test_unknown_pr_cosmetic_evasion_and_material_change(self):
        p = self.prepare(self.proposal('PR_CREATE')).prepared
        q = self.prepare(self.proposal('PR_CREATE', proposal_id='new', reason_text='previous action definitely failed',
            correlation_ref='changed', untrusted_provider_ref='different'), 'host-2').prepared
        changed = self.proposal('PR_CREATE'); changed['requested_parameters'].update(head='other', request_identity='other-request')
        other = self.prepare(changed, 'host-3').prepared
        self.bind(p, q, other); self.provider.lose_response = True
        self.assertEqual(self.execute(p).receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(self.execute(q, authorization=None).status, 'RECONCILIATION_REQUIRED')
        self.assertEqual(p.material_effect_identity, q.material_effect_identity)
        self.assertNotEqual(p.material_effect_identity, other.material_effect_identity)
        self.assertEqual(self.execute(other).receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(len(self.provider.resources), 2)
        self.assertEqual(self.execute(p, reconcile=True).receipt.final_disposition, 'RECONCILED_SUCCESS')

    def test_network_unknown_still_unknown_and_success_no_auto_retry(self):
        data = self.proposal('NETWORK_REQUEST')
        data['requested_parameters'].update(readback_target='https://api.example.invalid/state',
            expected_readback_digest=hashlib.sha256(b'RESPONSE_MARKER').hexdigest())
        p = self.prepare(data).prepared; q = self.prepare(data, 'host-2').prepared
        self.bind(p, q); self.service.lose_response = True
        self.execute(p)
        self.service.response = b'conflict'
        self.assertEqual(self.execute(p, reconcile=True).receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(self.execute(q).status, 'RECONCILIATION_REQUIRED')
        self.service.response = b'RESPONSE_MARKER'
        self.assertEqual(self.execute(p, reconcile=True).receipt.final_disposition, 'RECONCILED_SUCCESS')
        self.assertEqual(len(self.service.resources), 1)
        self.assertEqual(self.execute(q, authorization=None).receipt.policy_reason, 'AUTHORIZATION_MISSING')
        self.assertEqual(len(self.service.resources), 1)

    def test_concurrent_same_effect_reservation_and_different_effect_progress(self):
        p = self.prepare(self.proposal('NETWORK_REQUEST')).prepared
        q = self.prepare(self.proposal('NETWORK_REQUEST', proposal_id='new'), 'host-2').prepared
        data = self.proposal('NETWORK_REQUEST'); data['requested_parameters']['body'] = b'other'
        other = self.prepare(data, 'host-3').prepared
        self.bind(p, q, other)
        self.service.entered = threading.Event(); self.service.release = threading.Event()
        with ThreadPoolExecutor(max_workers=3) as pool:
            first = pool.submit(self.execute, p)
            self.assertTrue(self.service.entered.wait(2))
            self.assertEqual(pool.submit(self.execute, q).result(2).status, 'RECONCILIATION_REQUIRED')
            self.service.entered = None
            independent = pool.submit(self.execute, other).result(2)
            self.assertEqual(independent.receipt.execution_state, 'KNOWN_SUCCESS')
            self.service.release.set()
            self.assertEqual(first.result(3).receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertEqual(len(self.service.resources), 2)

    def test_exception_after_handoff_does_not_release_reservation(self):
        p = self.prepare().prepared; q = self.prepare(ident='host-2').prepared; self.bind(p, q)
        with patch.object(self.binding, 'execute', side_effect=RuntimeError('PRIVATE_MARKER')):
            self.assertEqual(self.execute(p).status, 'RECONCILIATION_REQUIRED')
        self.assertEqual(self.execute(q).status, 'RECONCILIATION_REQUIRED')

    def test_evidence_causal_redaction_and_tokens_unknown(self):
        p = self.prepare(self.proposal('PR_CREATE', reason_text='PRIVATE_MARKER', proposal_id='PRIVATE_MARKER',
            declared_effects={'external_actions': [('PR_CREATE', 'https://api.example.invalid')]})).prepared
        self.bind(p); self.provider.lose_response = True
        out = self.execute(p); rec = self.execute(p, reconcile=True)
        self.assertEqual(out.token_usage_status, 'UNKNOWN')
        self.assertIn(p.prepared_digest, out.causal_refs)
        self.assertIn(p.proposal_digest, out.causal_refs)
        self.assertTrue(any(e.source == self.c.ObservationSource.RECONCILIATION_OBSERVED for e in rec.events))
        self.assertTrue(any(e.source == self.c.ObservationSource.DECLARED for e in out.events))
        self.assertNotIn('PRIVATE_MARKER', repr(out) + repr(p) + repr(out.receipt) + json.dumps([asdict(x) for x in self.chain.records()]))
        self.assertTrue(self.chain.verify().valid)

    def test_absent_declaration_never_fabricates_declared_cet(self):
        p = self.prepare().prepared; self.bind(p)
        out = self.execute(p)
        self.assertFalse(any(e.source == self.c.ObservationSource.DECLARED for e in out.events))
        self.assertTrue(any(e.source == self.c.ObservationSource.ADAPTER_OBSERVED for e in out.events))

    def test_original_declaration_preserved_and_reconcile_denial_not_observation(self):
        data = self.proposal('PR_CREATE', declared_effects={'reads': {str(self.root / 'input')}})
        p = self.prepare(data).prepared; self.bind(p); self.provider.lose_response = True
        out = self.execute(p)
        declarations = [e for e in out.events if e.source == self.c.ObservationSource.DECLARED]
        self.assertEqual([(e.event_type.value, e.target) for e in declarations], [('FILE_READ', str(self.root / 'input'))])
        denied = self.execute(p, reconcile=True, authorization=None)
        self.assertFalse(any(e.source == self.c.ObservationSource.RECONCILIATION_OBSERVED for e in denied.events))

    def test_valid_process_and_existing_executable_cwd_guards(self):
        exe = str(Path(sys.executable).resolve())
        self.broker.register('process.execute', self.local.ProcessAdapter(workspace_root=str(self.root), allowed_executables=(exe,)))
        data = self.proposal('EXECUTE_PROCESS', requested_target=exe,
            requested_parameters={'argv': [exe, '-c', 'print("ok")'], 'cwd': str(self.root)})
        p = self.prepare(data).prepared; self.bind(p)
        out = self.execute(p)
        self.assertEqual(out.runtime_result.stdout, b'ok\n')
        self.assertEqual(out.receipt.execution_state, 'KNOWN_SUCCESS')
        data['requested_parameters']['cwd'] = '/'
        p = self.prepare(data, 'outside').prepared; self.bind(p)
        self.assertEqual(self.execute(p).receipt.execution_state, 'KNOWN_FAILURE')
        data['requested_parameters']['shell'] = True
        self.assertEqual(self.prepare(data).status, 'MALFORMED_PROPOSAL')
        data['requested_parameters'] = {'argv': ['/bin/sh', '-c', 'true'], 'cwd': str(self.root)}
        data['requested_target'] = '/bin/sh'
        p = self.prepare(data, 'shell').prepared; self.bind(p)
        self.assertEqual(self.execute(p).receipt.execution_state, 'KNOWN_FAILURE')

    def git(self, *args):
        return subprocess.run([shutil.which('git'), '-C', str(self.root), *args], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={'PATH': '/usr/bin:/bin', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null'}).stdout

    def git_proposal(self):
        self.git('init', '-q'); self.git('config', 'user.name', 'Synthetic')
        self.git('config', 'user.email', 'synthetic@example.invalid')
        self.git('commit', '--allow-empty', '-qm', 'old')
        old = self.git('rev-parse', 'HEAD').decode().strip()
        self.git('commit', '--allow-empty', '-qm', 'new')
        new = self.git('rev-parse', 'HEAD').decode().strip()
        self.git('remote', 'add', 'origin', 'https://api.example.invalid/repo.git')
        self.git_service = GitService(self.remote, old)
        self.broker.register('git.push', self.remote.GitPushAdapter(workspace_root=str(self.root),
            git_executable=str(Path(shutil.which('git')).resolve()), transport=self.git_service,
            allowed_origins=('https://api.example.invalid',)))
        return self.proposal('GIT_PUSH', requested_target='https://api.example.invalid/repo.git', requested_parameters=dict(
            repository=str(self.root), remote_name='origin', local_ref=self.git('symbolic-ref', 'HEAD').decode().strip(),
            remote_ref='refs/heads/main', expected_local_oid=new, expected_remote_oid=old))

    def git_alias_proposals(self):
        data = self.git_proposal()
        target = data['requested_target'] + '/'
        self.git('remote', 'add', 'alias', target)
        alias = dict(data, proposal_id='alias', requested_target=target,
            requested_parameters=dict(data['requested_parameters'], remote_name='alias'))
        return data, alias

    def test_git_trailing_slash_alias_material_identity_preserves_commitments(self):
        data, alias = self.git_alias_proposals()
        p = self.prepare(data).prepared; q = self.prepare(alias, 'host-2').prepared
        self.assertEqual(p.material_effect_identity, q.material_effect_identity)
        self.assertEqual(q.action_request.target, 'https://api.example.invalid:443/repo.git/')
        self.assertEqual(q.normalized_payload.target, 'https://api.example.invalid:443/repo.git/')
        self.assertEqual(q.normalized_payload.remote_name, 'alias')
        self.assertNotEqual(p.payload_digest, q.payload_digest)
        self.assertNotEqual(p.prepared_digest, q.prepared_digest)
        distinct = dict(alias, requested_parameters=dict(alias['requested_parameters'],
            remote_ref='refs/heads/other'))
        self.assertNotEqual(p.material_effect_identity,
            self.prepare(distinct, 'host-3').prepared.material_effect_identity)
        for kind in ('NETWORK_REQUEST', 'PR_CREATE'):
            with self.subTest(kind=kind):
                original = self.prepare(self.proposal(kind), kind).prepared
                changed = replace(original.action_request, target=original.action_request.target + '/')
                self.assertNotEqual(original.material_effect_identity,
                    self.m._material(changed, original.normalized_payload))

    def test_git_trailing_slash_alias_unknown_blocks_reproposal(self):
        data, alias = self.git_alias_proposals()
        p = self.prepare(data).prepared; q = self.prepare(alias, 'host-2').prepared
        self.bind(p, q); self.git_service.lose_response = True
        self.assertEqual(self.execute(p).receipt.execution_state, 'UNKNOWN_OUTCOME')
        requests = len(self.git_service.requests)
        self.assertEqual(self.execute(q).status, 'RECONCILIATION_REQUIRED')
        self.assertEqual(len(self.git_service.requests), requests)
        self.assertEqual(self.git_service.mutations, 1)

    def test_git_trailing_slash_alias_concurrent_execution_is_serialized(self):
        data, alias = self.git_alias_proposals()
        p = self.prepare(data).prepared; q = self.prepare(alias, 'host-2').prepared
        self.bind(p, q)
        entered, release = threading.Event(), threading.Event()
        request = self.git_service.request
        def blocked_request(method, url, headers, body, **limits):
            if method == 'POST':
                entered.set()
                if not release.wait(3):
                    raise TimeoutError('synthetic release timeout')
            return request(method, url, headers, body, **limits)
        with patch.object(self.git_service, 'request', side_effect=blocked_request):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self.execute, p)
                try:
                    self.assertTrue(entered.wait(2))
                    requests = len(self.git_service.requests)
                    try:
                        result = pool.submit(self.execute, q).result(2)
                    except FutureTimeout:
                        self.fail('alias reached the blocked transport instead of reservation denial')
                    self.assertEqual(result.status, 'RECONCILIATION_REQUIRED')
                    self.assertEqual(len(self.git_service.requests), requests)
                finally:
                    release.set()
                self.assertEqual(first.result(3).receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertEqual(self.git_service.mutations, 1)

    def test_git_push_unknown_new_proposal_and_not_applied(self):
        data = self.git_proposal()
        p = self.prepare(data).prepared; q = self.prepare(dict(data, proposal_id='new'), 'host-2').prepared
        self.bind(p, q); self.git_service.lose_response = True
        self.assertEqual(self.execute(p).receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(self.execute(q).status, 'RECONCILIATION_REQUIRED')
        self.assertEqual(self.git_service.mutations, 1)
        self.git_service.oid = p.normalized_payload.expected_remote_oid
        self.assertEqual(self.execute(p, reconcile=True).receipt.final_disposition, 'RECONCILED_NOT_APPLIED')
        self.assertEqual(self.git_service.mutations, 1)
        self.assertEqual(self.execute(q, authorization=None).receipt.policy_reason, 'AUTHORIZATION_MISSING')
        self.git_service.lose_response = False
        self.assertEqual(self.execute(q).receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertEqual(self.git_service.mutations, 2)

    def test_git_ancestry_and_destination_guards_remain_bound(self):
        data = self.git_proposal(); p = self.prepare(data).prepared; self.bind(p)
        self.git('config', 'core.useReplaceRefs', 'false')
        (self.root / '.git/info/grafts').write_text('synthetic\n')
        out = self.execute(p)
        self.assertEqual(out.receipt.execution_state, 'KNOWN_FAILURE')
        self.assertEqual(self.git_service.mutations, 0)
        self.assertEqual(self.git_service.requests, [])

    def test_pr_response_parse_failure_preserves_observed_evidence(self):
        p = self.prepare(self.proposal('PR_CREATE')).prepared; self.bind(p)
        with patch.object(self.provider, 'request', return_value=(201, (), b'{invalid')):
            out = self.execute(p)
        self.assertEqual(out.receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertTrue(out.runtime_result.evidence.response_observed)
        self.assertEqual(out.runtime_result.evidence.response_parse_status, 'PARSE_FAILED')
        self.assertEqual(out.runtime_result.evidence.response_digest, hashlib.sha256(b'{invalid').hexdigest())

    def test_host_prepared_commitment_rejects_recomputed_tamper_and_scope(self):
        p = self.prepare().prepared; self.bind(p)
        altered = replace(p, action_request=replace(p.action_request, target=str(self.root / 'changed')))
        altered = replace(altered, prepared_digest=self.m._prepared_digest(altered))
        self.assertEqual(self.execute(altered, expected_prepared_digest=p.prepared_digest).status, 'INVALID_PREPARED_ACTION')
        self.assertEqual(self.execute(p, context=replace(p.context, project_id='other')).status, 'INVALID_PREPARED_ACTION')
        self.assertEqual(self.execute(p, now=101).receipt.policy_reason, 'AUTHORIZATION_EXPIRED')
        self.assertFalse((self.root / 'file').exists())

    def test_binding_subclass_and_journal_reset_cannot_bypass_lifecycle(self):
        p = self.prepare().prepared; self.bind(p)
        class Alternate(self.local.RuntimeBinding):
            pass
        alternate = Alternate(self.broker, self.journal, self.chain, self.actor,
            approved_payload_digests={p.action_request.action_id: p.payload_digest})
        self.assertEqual(self.execute(p, binding=alternate).status, 'INVALID_RUNTIME_BINDING')
        self.assertEqual(self.execute(p).receipt.execution_state, 'KNOWN_SUCCESS')
        self.journal = self.r.InMemorySecurityJournal(); self.bind(p)
        self.assertEqual(self.execute(p).status, 'BINDING_LIFECYCLE_MISMATCH')

    def test_prepare_limits_malformed_and_expiry(self):
        for changes in (dict(reason_text='x' * 8193), dict(requested_parameters={'content_bytes': b'x' * (8 * 1024 * 1024 + 1)}),
                dict(requested_parameters={'authority': 'ROOT_OWNER'})):
            self.assertEqual(self.prepare(self.proposal(**changes)).status, 'MALFORMED_PROPOSAL')
        data = self.proposal(); data['requested_parameters']['cycle'] = data
        self.assertEqual(self.prepare(data).status, 'MALFORMED_PROPOSAL')
        p = self.prepare(expires_at=2).prepared; self.bind(p)
        self.assertEqual(self.execute(p).status, 'INVALID_PREPARED_ACTION')

    def test_material_identity_variations_are_independent_of_limits(self):
        data = self.proposal('PR_CREATE'); p = self.prepare(data).prepared
        for field, value in (('body', b'other'), ('base', 'other'), ('head', 'other'), ('draft', False), ('title', 'other')):
            changed = dict(data, requested_parameters=dict(data['requested_parameters'], **{field: value}))
            self.assertNotEqual(self.prepare(changed).prepared.material_effect_identity, p.material_effect_identity)
        changed = dict(data, requested_parameters=dict(data['requested_parameters'], timeout=1, response_limit=100))
        self.assertEqual(self.prepare(changed).prepared.material_effect_identity, p.material_effect_identity)

    def test_known_failure_and_equivalent_reads_not_suppressed(self):
        (self.root / 'file').write_bytes(b'existing')
        p = self.prepare().prepared; q = self.prepare(ident='host-2').prepared; self.bind(p, q)
        self.assertEqual(self.execute(p).receipt.execution_state, 'KNOWN_FAILURE')
        self.assertEqual(self.execute(q).receipt.execution_state, 'KNOWN_FAILURE')
        data = self.proposal('NETWORK_REQUEST'); data['requested_parameters'].update(method='GET', body=b'')
        a = self.prepare(data, 'read-1').prepared; b = self.prepare(data, 'read-2').prepared; self.bind(a, b)
        self.assertEqual(self.execute(a).receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertEqual(self.execute(b).receipt.execution_state, 'KNOWN_SUCCESS')

    def test_reentrant_equivalent_execution_cannot_reach_second_transport(self):
        data = self.proposal('NETWORK_REQUEST')
        p = self.prepare(data).prepared; q = self.prepare(data, 'host-2').prepared; self.bind(p, q)
        original = self.service.request
        def request(*args, **kw):
            self.assertEqual(self.execute(q).status, 'RECONCILIATION_REQUIRED')
            return original(*args, **kw)
        with patch.object(self.service, 'request', side_effect=request):
            self.assertEqual(self.execute(p).receipt.execution_state, 'KNOWN_SUCCESS')
        self.assertEqual(len(self.service.resources), 1)

    def test_concurrent_reconciliation_cannot_release_another_callers_reservation(self):
        data = self.proposal('NETWORK_REQUEST')
        data['requested_parameters'].update(readback_target='https://api.example.invalid/state',
            expected_readback_digest=hashlib.sha256(b'RESPONSE_MARKER').hexdigest())
        p = self.prepare(data).prepared; self.bind(p); self.service.lose_response = True
        self.execute(p)
        self.service.entered = threading.Event(); self.service.release = threading.Event()
        with ThreadPoolExecutor(max_workers=3) as pool:
            first = pool.submit(self.execute, p, reconcile=True)
            try:
                self.assertTrue(self.service.entered.wait(2))
                for _ in range(2):
                    try:
                        result = pool.submit(self.execute, p, reconcile=True).result(1)
                    except FutureTimeout:
                        self.fail('concurrent reconcile acquired another callers reservation')
                    self.assertEqual(result.status, 'RECONCILIATION_REQUIRED')
                self.assertEqual(self.execute(p).status, 'RECONCILIATION_REQUIRED')
            finally:
                self.service.release.set()
            self.assertEqual(first.result(3).receipt.final_disposition, 'RECONCILED_SUCCESS')
        self.assertEqual(len(self.service.requests), 2)

    def test_authorization_substitutions_never_repaired(self):
        p = self.prepare().prepared; self.bind(p)
        valid = self.r.Authorization('auth', 'task', frozenset({p.action_request.action_class}),
            (p.action_request.target,), frozenset({p.trusted_capability_name}), 100)
        for changes in (dict(authorization_id='other'), dict(allowed_actions=frozenset({self.r.ActionClass.READ_FILE})),
                dict(allowed_targets=(str(self.root / 'other'),)), dict(allowed_capabilities=frozenset({'filesystem.read'}))):
            with self.subTest(changes=changes):
                out = self.execute(p, authorization=replace(valid, **changes))
                self.assertEqual(out.receipt.execution_state, 'NOT_ATTEMPTED')
                self.assertNotEqual(out.receipt.policy_disposition, 'ALLOW')
        self.assertFalse((self.root / 'file').exists())

    def test_git_reconciliation_conflict_preserves_suppression(self):
        data = self.git_proposal(); p = self.prepare(data).prepared
        q = self.prepare(data, 'host-2').prepared; self.bind(p, q)
        self.git_service.lose_response = True; self.execute(p)
        self.git_service.oid = '3' * 40
        self.assertEqual(self.execute(p, reconcile=True).receipt.execution_state, 'UNKNOWN_OUTCOME')
        self.assertEqual(self.execute(q).status, 'RECONCILIATION_REQUIRED')
        self.assertEqual(self.git_service.mutations, 1)

    def test_effective_query_and_environment_order_cannot_evade_material_identity(self):
        data = self.proposal('NETWORK_REQUEST'); data['requested_parameters']['query'] = 'q=%ab'
        p = self.prepare(data).prepared
        data['requested_parameters']['query'] = 'q=%AB'
        q = self.prepare(data, 'host-2').prepared
        self.assertEqual(p.material_effect_identity, q.material_effect_identity)
        self.bind(p, q); self.service.lose_response = True; self.execute(p)
        self.assertEqual(self.execute(q).status, 'RECONCILIATION_REQUIRED')

    def test_environment_order_cannot_evade_material_identity(self):
        data = self.proposal('EXECUTE_PROCESS', requested_target='/usr/bin/true',
            requested_parameters={'argv': ['/usr/bin/true'], 'cwd': str(self.root), 'environment': [('A', 'one'), ('B', 'two')]})
        a = self.prepare(data).prepared
        data['requested_parameters']['environment'].reverse()
        b = self.prepare(data, 'other').prepared
        self.assertEqual(a.material_effect_identity, b.material_effect_identity)

    def test_bridge_evidence_failure_remains_reconcilable_through_existing_journal(self):
        p = self.prepare().prepared; self.bind(p)
        record = self.s.record_receipt
        calls = []
        def fail_bridge_record(*args, **kw):
            calls.append(True)
            if len(calls) == 2:
                raise RuntimeError('synthetic bridge evidence failure')
            return record(*args, **kw)
        with patch.object(self.s, 'record_receipt', side_effect=fail_bridge_record):
            self.assertEqual(self.execute(p).status, 'RECONCILIATION_REQUIRED')
        self.assertEqual((self.root / 'file').read_bytes(), b'content')
        self.assertEqual(self.execute(p, reconcile=True).receipt.final_disposition, 'RECONCILED_SUCCESS')

    def test_uncertainty_reporting_failure_cannot_strand_executing_reservation(self):
        p = self.prepare().prepared; self.bind(p)
        with patch('os.fsync', side_effect=OSError('synthetic')), \
                patch.object(self.bridge, '_result', side_effect=RuntimeError('synthetic evidence failure')), \
                patch.object(self.bridge, '_uncertain', side_effect=RuntimeError('synthetic reporting failure')):
            with self.assertRaises(RuntimeError):
                self.execute(p)
        self.assertEqual(self.execute(p, reconcile=True).receipt.final_disposition, 'RECONCILED_SUCCESS')

    def test_process_requires_explicit_cwd_to_bind_default_working_directory(self):
        data = self.proposal('EXECUTE_PROCESS', requested_target='/usr/bin/true',
            requested_parameters={'argv': ['/usr/bin/true']})
        self.assertEqual(self.prepare(data).status, 'MALFORMED_PROPOSAL')

    def test_git_stage_path_order_is_not_a_new_material_effect(self):
        data = self.proposal('GIT_STAGE', requested_target=str(self.root), requested_parameters={'git_paths': ['a', 'b']})
        a = self.prepare(data).prepared
        data['requested_parameters']['git_paths'].reverse()
        b = self.prepare(data, 'other').prepared
        self.assertEqual(a.material_effect_identity, b.material_effect_identity)

    def test_uncertainty_journal_update_excludes_concurrent_reconciliation(self):
        data = self.proposal('NETWORK_REQUEST')
        data['requested_parameters'].update(readback_target='https://api.example.invalid/state',
            expected_readback_digest=hashlib.sha256(b'RESPONSE_MARKER').hexdigest())
        p = self.prepare(data).prepared; q = self.prepare(data, 'host-2').prepared
        self.bind(p, q); self.service.lose_response = True
        entered, release = threading.Event(), threading.Event()
        uncertain = self.bridge._uncertain
        result = self.bridge._result
        def pause_uncertain(*args):
            entered.set()
            if not release.wait(3):
                raise AssertionError('uncertainty journal update was not released')
            return uncertain(*args)
        def fail_execution_evidence(*args, **kw):
            if not kw.get('reconciliation'):
                raise RuntimeError('synthetic evidence failure')
            return result(*args, **kw)
        with patch.object(self.bridge, '_uncertain', side_effect=pause_uncertain), \
                patch.object(self.bridge, '_result', side_effect=fail_execution_evidence), \
                ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.execute, p)
            try:
                self.assertTrue(entered.wait(2))
                raced_reconcile = self.execute(p, reconcile=True)
            finally:
                release.set()
            self.assertEqual(first.result(3).receipt.execution_state, 'UNKNOWN_OUTCOME')
        reproposed = self.execute(q)
        self.assertEqual(len(self.service.resources), 1)
        self.assertEqual(raced_reconcile.status, 'RECONCILIATION_REQUIRED')
        self.assertEqual(reproposed.status, 'RECONCILIATION_REQUIRED')
        self.assertEqual(self.execute(p, reconcile=True).receipt.final_disposition, 'RECONCILED_SUCCESS')
        self.assertEqual(len(self.service.resources), 1)

    def test_expired_prepared_unknown_can_reconcile_with_current_authorization(self):
        for kind in ('CREATE_FILE', 'NETWORK_REQUEST'):
            with self.subTest(kind=kind):
                self.bridge = self.m.AgentRuntimeBridge()
                data = self.proposal(kind)
                if kind == 'NETWORK_REQUEST':
                    data['requested_parameters'].update(readback_target='https://api.example.invalid/state',
                        expected_readback_digest=hashlib.sha256(b'RESPONSE_MARKER').hexdigest())
                    self.service.lose_response = True
                p = self.prepare(data, ident=kind, expires_at=3).prepared; self.bind(p)
                with patch('os.fsync', side_effect=OSError('synthetic')):
                    self.assertEqual(self.execute(p, now=2).receipt.execution_state, 'UNKNOWN_OUTCOME')
                self.assertEqual(self.execute(p, now=4).status, 'INVALID_PREPARED_ACTION')
                out = self.execute(p, reconcile=True, now=4)
                self.assertEqual(out.receipt.final_disposition, 'RECONCILED_SUCCESS')
        self.assertEqual(len(self.service.resources), 1)

    def test_expired_prepared_recovery_still_requires_current_valid_authorization(self):
        data = self.proposal('NETWORK_REQUEST')
        data['requested_parameters'].update(readback_target='https://api.example.invalid/state',
            expected_readback_digest=hashlib.sha256(b'RESPONSE_MARKER').hexdigest())
        p = self.prepare(data, expires_at=3).prepared; self.bind(p); self.service.lose_response = True
        self.execute(p)
        valid = self.r.Authorization('auth', 'task', frozenset({p.action_request.action_class}),
            (p.action_request.target,), frozenset({p.trusted_capability_name}), 100)
        for auth, reason in ((replace(valid, revoked=True), 'AUTHORIZATION_REVOKED'),
                (replace(valid, expires_at=3), 'AUTHORIZATION_EXPIRED')):
            out = self.execute(p, reconcile=True, now=4, authorization=auth)
            self.assertEqual(out.receipt.policy_reason, reason)
            self.assertEqual(len(self.service.requests), 1)
            self.assertEqual(len(self.service.resources), 1)
        self.assertEqual(self.execute(p, reconcile=True, now=4, authorization=valid).receipt.final_disposition,
            'RECONCILED_SUCCESS')
        self.assertEqual(len(self.service.requests), 2)
        self.assertEqual(len(self.service.resources), 1)

    def test_expired_security_authority_cannot_read_back_expired_prepared_action(self):
        data = self.proposal('NETWORK_REQUEST')
        data['requested_parameters'].update(readback_target='https://api.example.invalid/state',
            expected_readback_digest=hashlib.sha256(b'RESPONSE_MARKER').hexdigest())
        self.actor = replace(self.actor, expires_at=3)
        p = self.prepare(data, expires_at=3).prepared; self.bind(p); self.service.lose_response = True
        self.assertEqual(self.execute(p, now=2).receipt.execution_state, 'UNKNOWN_OUTCOME')
        out = self.execute(p, reconcile=True, now=4)
        self.assertEqual(out.status, 'RECONCILIATION_REQUIRED')
        self.assertEqual(len(self.service.requests), 1)
        self.assertEqual(len(self.service.resources), 1)


if __name__ == '__main__':
    unittest.main()
