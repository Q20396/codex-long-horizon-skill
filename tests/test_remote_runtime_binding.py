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
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/long-horizon-engineering/scripts'


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


if __name__ == '__main__':
    unittest.main()
