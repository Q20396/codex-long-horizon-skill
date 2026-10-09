"""SYNTHETIC_SERVICE only: stored-byte HTTP service and fresh Python recovery."""
from dataclasses import replace
import base64
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import json
import os
from pathlib import Path
import subprocess
import stat
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / '.agents/skills/long-horizon-engineering/scripts'


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def git_blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


class Service:
    """Reader obtains service storage, never a publisher's in-memory receipt."""
    def __init__(self):
        self.creates, self.gets, self.objects = 0, [], {}
        self.user_agents = []
        self.mode, self.mutation = 'ok', None
        self.commit, self.ready = 'a' * 40, threading.Event()
        service = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def reply(self, status, value):
                data = encoded(value) if not isinstance(value, bytes) else value
                self.send_response(status)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            def do_PUT(self):
                service.user_agents.append(('PUT', self.headers.get('User-Agent')))
                service.creates += 1
                if self.headers.get('X-GitHub-Api-Version') != '2026-03-10':
                    return self.reply(422, {})
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if set(body) != {'message', 'content', 'branch'} or body['branch'] != 'anchor':
                    return self.reply(422, {})
                path = self.path.split('/contents/')[1]
                if path in service.objects:
                    return self.reply(422, {})
                data = base64.b64decode(body['content'], validate=True)
                service.objects[path] = data
                service.ready.set()
                if service.mode == 'drop':
                    self.connection.shutdown(2)
                    return
                if service.mode == 'hold':
                    time.sleep(2)
                status = 200 if service.mode == 'update' else 201
                return self.reply(status, {'content': {'path': path, 'sha': git_blob(data)},
                                           'commit': {'sha': service.commit}})
            def do_GET(self):
                service.user_agents.append(('GET', self.headers.get('User-Agent')))
                service.gets.append(self.path)
                if service.mode in ('401', '403', '503'):
                    return self.reply(int(service.mode), {})
                if service.mode == 'malformed':
                    return self.reply(200, b'{broken')
                if service.mode == 'oversize':
                    return self.reply(200, b'x' * 40000)
                if self.path == '/repos/synthetic/anchor':
                    value = {'id': 17, 'full_name': 'synthetic/anchor'}
                elif self.path.endswith('/git/ref/heads/anchor'):
                    value = {'ref': 'refs/heads/anchor', 'object': {'type': 'commit', 'sha': service.commit}}
                elif '/git/commits/' in self.path:
                    value = {'sha': self.path.rsplit('/', 1)[1], 'tree': {'sha': 'b' * 40}}
                elif '/git/trees/' in self.path:
                    oid = self.path.rsplit('/', 1)[1]
                    if oid == 'b' * 40:
                        entries = [{'path': 'checkpoints', 'mode': '040000', 'type': 'tree', 'sha': 'c' * 40}]
                    else:
                        entries = [{'path': path.split('/')[1], 'mode': '100644', 'type': 'blob',
                                    'sha': git_blob(data)} for path, data in service.objects.items()]
                    value = {'sha': oid, 'truncated': False, 'tree': entries}
                elif '/git/blobs/' in self.path:
                    sha = self.path.rsplit('/', 1)[1]
                    data = next((data for data in service.objects.values() if git_blob(data) == sha), None)
                    if data is None:
                        return self.reply(404, {})
                    value = {'sha': sha, 'encoding': 'base64', 'size': len(data),
                             'content': base64.b64encode(data).decode()}
                else:
                    return self.reply(404, {})
                if service.mutation:
                    value = service.mutation(self.path, value)
                return self.reply(200, value)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)


class LocalTransport:
    evidence_kind = 'SYNTHETIC_SERVICE'
    def __init__(self, port):
        self.port = port
    def request(self, method, url, headers, body, *, timeout, response_limit):
        parsed = urlsplit(url)
        if parsed.netloc != 'api.github.com' or parsed.scheme != 'https':
            raise ValueError('wrong fixed origin')
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=timeout)
        try:
            connection.request(method, parsed.path + ('?' + parsed.query if parsed.query else ''),
                               body=body, headers=dict(headers))
            response = connection.getresponse()
            return response.status, tuple(response.getheaders()), response.read(response_limit + 1)
        finally:
            connection.close()


class AnchorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global crypto, checkpoints
        cls.old_path = sys.path[:]
        cls.old_modules = {name: sys.modules.get(name) for name in ('checkpoint_anchor', 'checkpoint_crypto',
            'signed_checkpoints', 'security_authority_chain', 'runtime_safety_envelope')}
        sys.path[:0] = [str(ROOT / 'scripts'), str(CORE)]
        crypto = importlib.import_module('checkpoint_crypto')
        checkpoints = importlib.import_module('signed_checkpoints')
        cls.m = importlib.import_module('checkpoint_anchor') if (ROOT / 'scripts/checkpoint_anchor.py').exists() else None
        cls.key_dir = tempfile.TemporaryDirectory(prefix='h5-synthetic-key-')
        root = Path(cls.key_dir.name)
        key = root / 'key'
        result = subprocess.run(['/usr/bin/ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)],
            env={'PATH': '/usr/bin:/bin', 'LANG': 'C'}, capture_output=True, timeout=5)
        if result.returncode:
            raise AssertionError('required synthetic OpenSSH key failed')
        public = ' '.join(key.with_suffix('.pub').read_text().split()[:2])
        fingerprint = 'SHA256:' + base64.b64encode(hashlib.sha256(base64.b64decode(public.split()[1])).digest()).decode().rstrip('=')
        cls.policy_data = dict(schema_version=crypto.POLICY_SCHEMA, policy_version='synthetic-policy', keys=[dict(
            key_id='key', principal='synthetic', public_key=public, fingerprint=fingerprint,
            purpose=crypto.NAMESPACE, status='ACTIVE')])
        cls.policy = crypto.load_policy(encoded(cls.policy_data))
        cls.verifier = crypto.OpenSSHCheckpointVerifier(crypto.OpenSSHBackend('/usr/bin/ssh-keygen'), cls.policy)
        signer = crypto.OpenSSHCheckpointSigner(crypto.OpenSSHBackend('/usr/bin/ssh-keygen'), 'key', str(key))
        cp = checkpoints.SignedCheckpoint(checkpoints.SCHEMA, 'checkpoint', checkpoints._ref('chain'),
            checkpoints._ref('installation'), 1, 'd' * 64, 100, 'key',
            checkpoints.SignatureAlgorithm.ED25519, '0' * 64, b'unsigned')
        cls.cp = replace(cp, signature=signer.sign(checkpoints.canonical_payload(cp)).signature)
        cls.data = checkpoints.checkpoint_to_json(cls.cp).encode()
    @classmethod
    def tearDownClass(cls):
        cls.key_dir.cleanup()
        sys.path[:] = cls.old_path
        for name, value in cls.old_modules.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
    def setUp(self):
        self.assertIsNotNone(self.m, 'H5 bounded anchor capability missing')
        self.tmp = tempfile.TemporaryDirectory(prefix='h5-capsule-')
        self.addCleanup(self.tmp.cleanup)
        self.directory = os.path.realpath(self.tmp.name)
        self.service = Service()
        self.addCleanup(self.service.close)
        self.target = self.m.GitHubTarget('https://api.github.com', 17, 'synthetic/anchor', 'anchor', 'checkpoints')
        self.request = self.m.AnchorRequest('request', self.data, 'chain', 'installation',
            hashlib.sha256(self.data).hexdigest(), 1, 'key', self.policy.reference)
        transport = LocalTransport(self.service.server.server_port)
        self.adapter = self.m.GitHubAnchor(self.target, self.directory, verifier=self.verifier,
                                          write_transport=transport, read_transport=transport)
    def test_single_create_then_independent_stored_bytes_get(self):
        sent = self.adapter.publish(self.request)
        self.assertEqual((sent.send_state, sent.publication, sent.readback),
            ('CREATE_ATTEMPTED', 'PUBLICATION_CONFIRMED_BY_PROVIDER', 'NOT_OBSERVED'))
        self.assertEqual(self.service.gets, ['/repos/synthetic/anchor'])
        read = self.adapter.read(self.request)
        self.assertEqual(read.readback, 'READBACK_OBSERVED')
        self.assertEqual(read.version, 'a' * 40)
        self.assertEqual((read.independent_retention, read.freshness), ('NOT_VALIDATED', 'UNKNOWN'))
        self.assertEqual(self.service.creates, 1)
        self.assertTrue(any('/git/blobs/' in path for path in self.service.gets))

    def test_fixed_application_user_agent_reaches_actual_get_and_put_requests(self):
        self.assertEqual(self.adapter.publish(self.request).publication, 'PUBLICATION_CONFIRMED_BY_PROVIDER')
        self.assertEqual(self.adapter.read(self.request).readback, 'READBACK_OBSERVED')
        self.assertEqual({method for method, value in self.service.user_agents}, {'GET', 'PUT'})
        self.assertTrue(all(value == '20396-checkpoint-anchor/1' for method, value in self.service.user_agents),
                        self.service.user_agents)
    def test_receipt_never_proves_readback(self):
        self.assertEqual(self.adapter.publish(self.request).publication, 'PUBLICATION_CONFIRMED_BY_PROVIDER')
        self.service.objects.clear()
        result = self.adapter.read(self.request)
        self.assertEqual((result.readback, result.reason), ('NOT_OBSERVED', 'NOT_OBSERVED'))
        self.assertEqual(result.publication, 'PUBLICATION_CONFIRMED_BY_PROVIDER')
    def test_dropped_reply_fresh_interpreter_recovers_without_second_create(self):
        self.service.mode = 'drop'
        sent = self.adapter.publish(self.request)
        self.assertEqual((sent.publication, sent.version), ('OUTCOME_UNKNOWN', 'UNKNOWN'))
        child = self.child('recover')
        output, error = child.communicate(timeout=10)
        self.assertEqual(child.returncode, 0, error.decode())
        self.assertEqual(json.loads(output)['readback'], 'READBACK_OBSERVED')
        self.assertEqual(self.service.creates, 1)
    def test_same_id_conflict_and_new_id_cannot_bypass_unresolved_capsule(self):
        self.service.mode = 'drop'
        self.adapter.publish(self.request)
        self.assertEqual(self.adapter.publish(replace(self.request, sequence=2)).reason, 'CONFLICT')
        self.assertEqual(self.adapter.publish(replace(self.request, request_id='new')).reason, 'DUPLICATE_CHECKPOINT_TARGET')
        self.assertEqual(self.adapter.publish(self.request).readback, 'READBACK_OBSERVED')
        self.assertEqual(self.service.creates, 1)
    def test_same_bytes_at_another_commit_rejected_after_persisted_pin(self):
        self.adapter.publish(self.request)
        self.service.commit = 'e' * 40
        self.assertEqual(self.adapter.read(self.request).reason, 'BINDING_MISMATCH')
        child = self.child('recover')
        out, _ = child.communicate(timeout=10)
        self.assertEqual(json.loads(out)['reason'], 'BINDING_MISMATCH')
    def test_each_checkpoint_binding_or_signature_is_rejected_before_send(self):
        changes = [dict(checkpoint_hash='f' * 64), dict(chain_id='other'), dict(installation_id='other'),
                   dict(sequence=2), dict(key_id='other'), dict(policy_reference='other')]
        bad_cp = replace(self.cp, signature=self.cp.signature[:-1] + bytes([self.cp.signature[-1] ^ 1]))
        bad_data = checkpoints.checkpoint_to_json(bad_cp).encode()
        changes.append(dict(checkpoint_bytes=bad_data, checkpoint_hash=hashlib.sha256(bad_data).hexdigest()))
        for change in changes:
            with self.subTest(field=list(change)[0]):
                result = self.adapter.publish(replace(self.request, **change))
                self.assertEqual(result.send_state, 'NOT_SENT_THIS_INVOCATION')
                self.assertEqual(result.reason, 'BINDING_MISMATCH')
        self.assertEqual(self.service.creates, 0)
    def test_repository_path_blob_and_regular_file_binding(self):
        self.adapter.publish(self.request)
        mutations = [lambda path, obj: {**obj, 'id': 18} if path == '/repos/synthetic/anchor' else obj,
                     lambda path, obj: {**obj, 'full_name': 'other/repo'} if path == '/repos/synthetic/anchor' else obj,
                     lambda path, obj: {**obj, 'ref': 'refs/heads/other'} if '/git/ref/' in path else obj,
                     lambda path, obj: {**obj, 'sha': 'f' * 40} if '/git/commits/' in path else obj,
                     lambda path, obj: {**obj, 'tree': [{**e, 'mode': '120000', 'type': 'blob'} for e in obj['tree']]} if '/git/trees/' in path else obj,
                     lambda path, obj: {**obj, 'tree': [{**e, 'path': 'other'} for e in obj['tree']]} if '/git/trees/' in path else obj,
                     lambda path, obj: {**obj, 'content': base64.b64encode(b'wrong').decode(), 'size': 5} if '/git/blobs/' in path else obj]
        for mutation in mutations:
            self.service.mutation = mutation
            with self.subTest(mutation=mutations.index(mutation)):
                self.assertIn(self.adapter.read(self.request).reason, ('BINDING_MISMATCH', 'NOT_OBSERVED'))
        self.service.mutation = None
        self.assertEqual(self.adapter.read(self.request).readback, 'READBACK_OBSERVED')

    def test_valid_unrelated_git_tree_names_do_not_block_exact_checkpoint(self):
        self.adapter.publish(self.request)
        for sibling in ('.github', '.gitignore', '说明文档'):
            def add_sibling(path, value):
                if path.endswith('/git/trees/' + 'b' * 40):
                    return {**value, 'tree': value['tree'] + [dict(path=sibling, mode='100644', type='blob', sha='f' * 40)]}
                return value
            self.service.mutation = add_sibling
            with self.subTest(sibling=sibling):
                self.assertEqual(self.adapter.read(self.request).readback, 'READBACK_OBSERVED')

    def test_malformed_unrelated_tree_name_type_or_sha_is_rejected(self):
        self.adapter.publish(self.request)
        for change in (dict(path=''), dict(path='.'), dict(path='..'), dict(path='other/path'),
                       dict(path='bad\0name'), dict(path='x' * 257), dict(type='bogus'),
                       dict(mode='bogus'), dict(sha='not-an-oid')):
            sibling = {**dict(path='other', mode='100644', type='blob', sha='f' * 40), **change}
            def add_bad_sibling(path, value):
                if path.endswith('/git/trees/' + 'b' * 40):
                    return {**value, 'tree': value['tree'] + [sibling]}
                return value
            self.service.mutation = add_bad_sibling
            with self.subTest(change=change):
                self.assertEqual(self.adapter.read(self.request).reason, 'RESPONSE_INVALID')
    def test_stale_head_clock_and_absent_freshness_inputs(self):
        self.adapter.publish(self.request)
        self.assertEqual(self.adapter.read(self.request).freshness, 'UNKNOWN')
        self.assertEqual(self.adapter.read(self.request, expected_head=(2, 'f' * 64)).freshness, 'STALE')
        self.assertEqual(self.adapter.read(self.request, trusted_clock=200, max_age=10).freshness, 'STALE')
        self.assertEqual(self.adapter.read(self.request, expected_head=(1, 'd' * 64), trusted_clock=105, max_age=10).freshness,
                         'FRESH_RELATIVE_TO_TRUSTED_INPUTS')
    def test_fsync_and_corrupt_capsule_prevent_send(self):
        with patch.object(self.m.os, 'fsync', side_effect=OSError('synthetic')):
            result = self.adapter.publish(self.request)
        self.assertEqual(result.send_state, 'NOT_SENT_THIS_INVOCATION')
        self.assertEqual(self.service.creates, 0)
        self.assertEqual(self.service.gets, [])
        self.assertEqual(self.adapter.publish(self.request).readback, 'NOT_OBSERVED')
        capsule = next(Path(self.directory).glob('*.capsule'))
        capsule.write_bytes(b'{broken')
        self.assertEqual(self.adapter.publish(self.request).reason, 'PERSISTENCE_INVALID')
        self.assertEqual(self.service.creates, 0)
    def test_read_missing_capsule_does_not_create_or_claim_historic_absence(self):
        result = self.adapter.read(self.request)
        self.assertEqual((result.send_state, result.publication, result.reason),
                         ('NOT_SENT_THIS_INVOCATION', 'OUTCOME_UNKNOWN', 'CAPSULE_MISSING'))
        self.assertEqual(self.service.creates, 0)
        self.assertEqual(self.service.gets, [])
    def test_orphan_observation_prevents_new_create(self):
        self.adapter.publish(self.request)
        next(Path(self.directory).glob('*.capsule')).unlink()
        self.assertEqual(self.adapter.publish(self.request).reason, 'PERSISTENCE_INVALID')
        self.assertEqual(self.service.creates, 1)
    def test_http_diagnostics_and_malformed_limits_preserve_unknown(self):
        self.service.mode = 'drop'
        self.adapter.publish(self.request)
        for mode, reason in [('401', 'HTTP_401'), ('403', 'HTTP_403'), ('503', 'HTTP_503'),
                             ('oversize', 'RESPONSE_LIMIT'), ('malformed', 'RESPONSE_INVALID')]:
            self.service.mode = mode
            with self.subTest(mode=mode):
                result = self.adapter.read(self.request)
                self.assertEqual((result.publication, result.readback, result.reason),
                                 ('OUTCOME_UNKNOWN', 'NOT_OBSERVED', reason))
    def test_contents_200_not_create_confirmation(self):
        self.service.mode = 'update'
        result = self.adapter.publish(self.request)
        self.assertEqual((result.publication, result.version), ('OUTCOME_UNKNOWN', 'UNKNOWN'))
    def test_real_process_termination_in_capsule_send_receipt_observation_windows(self):
        for stage in ('partial', 'durable', 'send', 'receipt', 'observation_partial', 'observation'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory(prefix='h5-crash-') as directory:
                ready = Path(directory) / 'ready'
                self.service.ready.clear()
                self.service.mode = 'hold' if stage == 'send' else 'ok'
                child = self.child(stage, os.path.realpath(directory), str(ready))
                deadline = time.monotonic() + 8
                reached = lambda: self.service.ready.is_set() if stage == 'send' else ready.exists()
                while not reached() and child.poll() is None and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(reached(), 'crash window not reached')
                child.kill()
                child.communicate(timeout=5)
                before = self.service.creates
                # Marker is outside capsule storage: remove before recovery scan.
                if ready.exists():
                    ready.unlink()
                self.service.mode = 'ok'
                recovery = self.child('recover', os.path.realpath(directory))
                out, error = recovery.communicate(timeout=10)
                self.assertEqual(recovery.returncode, 0, error.decode())
                result = json.loads(out)
                self.assertEqual(self.service.creates, before)
                self.assertEqual(result['send_state'], 'NOT_SENT_THIS_INVOCATION')
                if stage in ('partial', 'observation_partial'):
                    self.assertEqual(result['reason'], 'PERSISTENCE_INVALID')
                elif stage == 'durable':
                    self.assertEqual(result['readback'], 'NOT_OBSERVED')
                else:
                    self.assertEqual(result['readback'], 'READBACK_OBSERVED')
                print('H5_SYNTHETIC_CRASH window=' + stage + ' recovery=' + result['reason']
                      + ' create_count_unchanged=' + str(self.service.creates == before))
                self.service.objects.clear()
    def child(self, mode, directory=None, marker=''):
        config = encoded(dict(mode=mode, directory=directory or self.directory, marker=marker,
            port=self.service.server.server_port, checkpoint=self.data.decode(), policy=self.policy_data))
        process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--child'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={'PATH': '/usr/bin:/bin', 'LANG': 'C'}, start_new_session=True)
        process.stdin.write(config)
        process.stdin.close()
        process.stdin = None
        return process
    def test_multiprocess_duplicate_admission_only_one_create(self):
        children = [self.child('publish') for _ in range(4)]
        results = []
        for child in children:
            out, error = child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0, error.decode())
            results.append(json.loads(out))
        self.assertEqual(self.service.creates, 1)
        # APFS concurrent O_CREAT may fail ENOENT before flock; fail closed with
        # the existing owner's explicit acquisition diagnostic, never retry.
        self.assertTrue(all(r['reason'] in ('VALID', 'OWNERSHIP_CONTENDED', 'OWNERSHIP_ACQUISITION_FAILED') for r in results), results)
        self.assertEqual(sum(r['send_state'] == 'CREATE_ATTEMPTED' for r in results), 1)
        recovery = self.child('recover')
        out, error = recovery.communicate(timeout=10)
        self.assertEqual(recovery.returncode, 0, error.decode())
        self.assertEqual(json.loads(out)['readback'], 'READBACK_OBSERVED')
        self.assertEqual(self.service.creates, 1)
    def test_import_inactive_and_no_credential_discovery(self):
        code = "import sys\ndef audit(e,a):\n if e in ('subprocess.Popen','socket.connect','os.mkdir','os.remove'): raise RuntimeError(e)\nsys.addaudithook(audit)\nimport checkpoint_anchor"
        result = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, timeout=5,
            env={'PATH': '/usr/bin:/bin', 'PYTHONPATH': str(ROOT / 'scripts') + os.pathsep + str(CORE)})
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'synthetic-do-not-use'}):
            self.adapter.publish(self.request)
        self.assertNotIn(b'synthetic-do-not-use', b''.join(path.read_bytes() for path in Path(self.directory).glob('*.capsule')))
    def test_unresolved_rse_state_is_unchanged_by_anchor_success(self):
        import runtime_safety_envelope as rse
        journal = rse.InMemorySecurityJournal()
        for state in (rse.JournalState.PROPOSED, rse.JournalState.AUTHORIZED,
                      rse.JournalState.ATTEMPTED, rse.JournalState.UNKNOWN_OUTCOME,
                      rse.JournalState.RECONCILIATION_REQUIRED):
            journal.append(rse.JournalEntry(rse._ref('unresolved'), 'synthetic-request', state))
        before = journal.history('unresolved')
        self.adapter.publish(self.request)
        self.assertEqual(self.adapter.read(self.request).readback, 'READBACK_OBSERVED')
        self.assertEqual(journal.history('unresolved'), before)
        self.assertEqual(journal.latest('unresolved').state, rse.JournalState.RECONCILIATION_REQUIRED)

    def test_short_writes_complete_and_midwrite_failure_blocks_transport(self):
        real_write = self.m.os.write
        def short(fd, data):
            return real_write(fd, data[:11] if stat.S_ISREG(os.fstat(fd).st_mode) else data)
        with patch.object(self.m.os, 'write', side_effect=short):
            self.assertEqual(self.adapter.publish(self.request).publication, 'PUBLICATION_CONFIRMED_BY_PROVIDER')
        self.assertEqual(self.adapter.read(self.request).readback, 'READBACK_OBSERVED')
        with tempfile.TemporaryDirectory(prefix='h5-midwrite-') as directory:
            adapter = self.m.GitHubAnchor(self.target, os.path.realpath(directory), verifier=self.verifier,
                write_transport=LocalTransport(self.service.server.server_port), read_transport=LocalTransport(self.service.server.server_port))
            writes = []
            def fail_midwrite(fd, data):
                if stat.S_ISREG(os.fstat(fd).st_mode):
                    writes.append(fd)
                    if len(writes) > 1:
                        raise OSError('synthetic interrupted write')
                    return real_write(fd, data[:7])
                return real_write(fd, data)
            before = (self.service.creates, len(self.service.gets))
            with patch.object(self.m.os, 'write', side_effect=fail_midwrite):
                self.assertEqual(adapter.publish(self.request).reason, 'PERSISTENCE_INVALID')
            self.assertEqual(adapter.publish(self.request).reason, 'PERSISTENCE_INVALID')
            self.assertEqual((self.service.creates, len(self.service.gets)), before)

    def test_directory_fsync_failure_and_owner_identity_loss_block_send(self):
        real_fsync = self.m.os.fsync
        def fail_directory(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError('synthetic directory fsync failure')
            return real_fsync(fd)
        with patch.object(self.m.os, 'fsync', side_effect=fail_directory):
            self.assertEqual(self.adapter.publish(self.request).reason, 'PERSISTENCE_INVALID')
        self.assertEqual((self.service.creates, self.service.gets), (0, []))
        with tempfile.TemporaryDirectory(prefix='h5-owner-loss-') as directory:
            directory = os.path.realpath(directory)
            adapter = self.m.GitHubAnchor(self.target, directory, verifier=self.verifier,
                write_transport=LocalTransport(self.service.server.server_port), read_transport=LocalTransport(self.service.server.server_port))
            def lose_owner(fd):
                if stat.S_ISREG(os.fstat(fd).st_mode):
                    Path(directory, '.h2-owner').unlink()
                return real_fsync(fd)
            with patch.object(self.m.os, 'fsync', side_effect=lose_owner):
                self.assertEqual(adapter.publish(self.request).reason, 'OWNERSHIP_IDENTITY_INVALID')
            self.assertEqual((self.service.creates, self.service.gets), (0, []))

    def test_owner_contention_private_directory_and_linked_capsule_fail_closed(self):
        owner = self.m.CrossProcessOwner(self.directory)
        try:
            self.assertEqual(self.adapter.publish(self.request).reason, 'OWNERSHIP_CONTENDED')
        finally:
            owner.close()
        os.chmod(self.directory, 0o755)
        self.assertEqual(self.adapter.publish(self.request).reason, 'PERSISTENCE_INVALID')
        os.chmod(self.directory, 0o700)
        self.adapter.publish(self.request)
        capsule = next(Path(self.directory).glob('*.capsule'))
        with tempfile.TemporaryDirectory(prefix='h5-link-') as elsewhere:
            copied = Path(elsewhere) / 'data'
            copied.write_bytes(capsule.read_bytes())
            capsule.unlink()
            capsule.symlink_to(copied)
            self.assertEqual(self.adapter.read(self.request).reason, 'PERSISTENCE_INVALID')

    def test_known_owner_acquisition_failure_has_explicit_diagnostic(self):
        with patch.object(self.m, 'CrossProcessOwner', side_effect=ValueError('OWNERSHIP_ACQUISITION_FAILED')):
            result = self.adapter.publish(self.request)
        self.assertEqual(result.reason, 'OWNERSHIP_ACQUISITION_FAILED')
        self.assertEqual((result.send_state, self.service.creates, self.service.gets), ('NOT_SENT_THIS_INVOCATION', 0, []))

    def test_corrupt_observation_is_not_repaired(self):
        self.adapter.publish(self.request)
        observation = next(Path(self.directory).glob('*.observation'))
        observation.write_bytes(b'{broken')
        self.assertEqual(self.adapter.read(self.request).reason, 'PERSISTENCE_INVALID')
        self.assertEqual(observation.read_bytes(), b'{broken')
        self.assertEqual(self.service.creates, 1)

    def test_strict_config_rejects_path_origin_and_request_escape(self):
        for change in (dict(origin='https://example.test'), dict(repository_id=True), dict(repository='../repo'),
                       dict(branch='a/../b'), dict(prefix='../escape'), dict(prefix='a/%2e'),
                       dict(prefix='a//b'), dict(prefix='a/' * 9 + 'b')):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(self.target, **change)
        for request_id in ('../bad', 'bad/path', 'bad%2fpath', '.', 'a' * 65):
            self.assertEqual(self.adapter.publish(replace(self.request, request_id=request_id)).send_state,
                             'NOT_SENT_THIS_INVOCATION')
        self.assertEqual((self.service.creates, self.service.gets), (0, []))

    def test_policy_replacement_cannot_trust_a_caller_reference(self):
        other = crypto.load_policy(encoded({**self.policy_data, 'policy_version': 'replacement'}))
        self.verifier.policy = other
        try:
            self.assertEqual(self.adapter.publish(self.request).reason, 'BINDING_MISMATCH')
            self.assertEqual(self.service.creates, 0)
        finally:
            self.verifier.policy = self.policy

    def test_h4_backend_unknown_before_publish_preserves_diagnostic_and_zero_transport(self):
        for reason in ('BACKEND_UNAVAILABLE', 'BACKEND_TIMEOUT', 'CLEANUP_UNKNOWN'):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory(prefix='h5-h4-unknown-') as directory:
                directory = os.path.realpath(directory)
                executable = directory + '/missing-executable' if reason == 'BACKEND_UNAVAILABLE' else '/usr/bin/ssh-keygen'
                backend = crypto.OpenSSHBackend(executable)
                verifier = crypto.OpenSSHCheckpointVerifier(backend, self.policy)
                adapter = self.m.GitHubAnchor(self.target, directory, verifier=verifier,
                    write_transport=self.adapter.write_transport, read_transport=self.adapter.read_transport)
                if reason == 'BACKEND_UNAVAILABLE':
                    result = adapter.publish(self.request)
                else:
                    with patch.object(backend, '_run', side_effect=crypto.BackendFailure(reason)):
                        result = adapter.publish(self.request)
                self.assertEqual((result.reason, result.send_state, result.publication, result.readback),
                    (reason, 'NOT_SENT_THIS_INVOCATION', 'OUTCOME_UNKNOWN', 'NOT_OBSERVED'))
                self.assertEqual((self.service.creates, self.service.gets), (0, []))

    def test_existing_capsule_h4_backend_unknown_retains_get_only_recovery(self):
        self.adapter.publish(self.request)
        before = (self.service.creates, len(self.service.gets))
        for reason in ('BACKEND_UNAVAILABLE', 'BACKEND_TIMEOUT', 'CLEANUP_UNKNOWN'):
            with self.subTest(reason=reason):
                executable = self.directory + '/missing-executable' if reason == 'BACKEND_UNAVAILABLE' else '/usr/bin/ssh-keygen'
                backend = crypto.OpenSSHBackend(executable)
                verifier = crypto.OpenSSHCheckpointVerifier(backend, self.policy)
                adapter = self.m.GitHubAnchor(self.target, self.directory, verifier=verifier,
                    write_transport=self.adapter.write_transport, read_transport=self.adapter.read_transport)
                if reason == 'BACKEND_UNAVAILABLE':
                    result, read = adapter.publish(self.request), adapter.read(self.request)
                else:
                    with patch.object(backend, '_run', side_effect=crypto.BackendFailure(reason)):
                        result, read = adapter.publish(self.request), adapter.read(self.request)
                for outcome in (result, read):
                    self.assertEqual((outcome.reason, outcome.send_state, outcome.publication, outcome.readback),
                        (reason, 'NOT_SENT_THIS_INVOCATION', 'PUBLICATION_CONFIRMED_BY_PROVIDER', 'NOT_OBSERVED'))
                self.assertEqual((self.service.creates, len(self.service.gets)), before)
        # Restored H4 availability reads existing capsule; it never recreates.
        recovery = self.adapter.publish(self.request)
        self.assertEqual((recovery.readback, recovery.send_state, self.service.creates),
                         ('READBACK_OBSERVED', 'NOT_SENT_THIS_INVOCATION', 1))

    def test_production_transport_bounds_deadline_output_and_closes_resources(self):
        real_popen = self.m.subprocess.Popen
        for worker, reason in [('import time; time.sleep(10)', 'TRANSPORT_TIMEOUT'),
                               ('import os; os.write(1,b"x"*100000)', 'RESPONSE_LIMIT')]:
            processes = []
            def local_worker(*args, **kwargs):
                process = real_popen([sys.executable, '-B', '-c', worker], **kwargs)
                processes.append(process)
                return process
            started = time.monotonic()
            with patch.object(self.m.subprocess, 'Popen', side_effect=local_worker), self.assertRaises(ValueError) as error:
                self.m.GitHubHTTPS().request('GET', 'https://api.github.com/repos/synthetic/anchor', (), b'',
                                             timeout=.2, response_limit=32768)
            self.assertEqual(str(error.exception), reason)
            self.assertLess(time.monotonic() - started, 2)
            self.assertIsNotNone(processes[0].poll())
            self.assertTrue(all(stream.closed for stream in (processes[0].stdin, processes[0].stdout, processes[0].stderr)))

    def test_unavailable_reader_does_not_regain_create_eligibility(self):
        self.service.mode = 'drop'
        self.adapter.publish(self.request)
        with patch.object(self.adapter.read_transport, 'request', side_effect=OSError('synthetic unavailable')):
            result = self.adapter.publish(self.request)
        self.assertEqual((result.send_state, result.publication, result.reason),
                         ('NOT_SENT_THIS_INVOCATION', 'OUTCOME_UNKNOWN', 'TRANSPORT_UNAVAILABLE'))
        self.assertEqual(self.service.creates, 1)

    def test_transport_caller_label_cannot_claim_real_https(self):
        transport = LocalTransport(self.service.server.server_port)
        transport.evidence_kind = 'REAL_HTTPS_IO'
        with self.assertRaises(ValueError):
            self.m.GitHubAnchor(self.target, self.directory, verifier=self.verifier,
                                write_transport=transport, read_transport=transport)

    def test_file_replacement_between_descriptor_read_and_owner_bind_rejected(self):
        self.adapter.publish(self.request)
        real_read, changed = self.m.os.read, []
        capsule = next(Path(self.directory).glob('*.capsule'))
        original = capsule.read_bytes()
        def swap_after_read(fd, count):
            result = real_read(fd, count)
            if result == original and not changed:
                replacement = Path(self.directory, 'replacement')
                replacement.write_bytes(original)
                replacement.chmod(0o600)
                os.replace(replacement, capsule)
                changed.append(True)
            return result
        with patch.object(self.m.os, 'read', side_effect=swap_after_read):
            self.assertNotEqual(self.adapter.read(self.request).readback, 'READBACK_OBSERVED')
        self.assertEqual(changed, [True])

    def test_persistence_replacement_of_open_file_is_rejected_before_send(self):
        real_write, changed = self.m.os.write, []
        def swap_after_write(fd, data):
            result = real_write(fd, data)
            if stat.S_ISREG(os.fstat(fd).st_mode) and not changed:
                capsule = next(Path(self.directory).glob('*.capsule'))
                replacement = Path(self.directory, 'replacement')
                replacement.write_bytes(data)
                replacement.chmod(0o600)
                os.replace(replacement, capsule)
                changed.append(True)
            return result
        with patch.object(self.m.os, 'write', side_effect=swap_after_write):
            result = self.adapter.publish(self.request)
        self.assertEqual(result.send_state, 'NOT_SENT_THIS_INVOCATION')
        self.assertEqual((self.service.creates, self.service.gets), (0, []))
        self.assertEqual(changed, [True])

    def test_timeout_kills_worker_descendants_after_leader_exits(self):
        with tempfile.TemporaryDirectory(prefix='h5-worker-child-') as directory:
            marker = Path(directory, 'late-effect')
            code = ('import os,time\nif os.fork()==0:\n time.sleep(.6)\n open(' + repr(str(marker))
                    + ',"w").write("bad")\nelse: os._exit(0)\n')
            real_popen = self.m.subprocess.Popen
            def worker(*args, **kwargs):
                return real_popen([sys.executable, '-B', '-c', code], **kwargs)
            with patch.object(self.m.subprocess, 'Popen', side_effect=worker), self.assertRaises(ValueError):
                self.m.GitHubHTTPS().request('GET', 'https://api.github.com/repos/synthetic/anchor', (), b'',
                                             timeout=.2, response_limit=32768)
            time.sleep(.7)
            self.assertFalse(marker.exists(), 'timed-out request worker descendant survived')

    def test_malformed_unrelated_capsule_cannot_be_ignored_in_admission_scan(self):
        self.adapter.publish(self.request)
        original = json.loads(next(Path(self.directory).glob('*.capsule')).read_bytes())
        other_id = 'other-request'
        path = Path(self.directory, hashlib.sha256(other_id.encode()).hexdigest() + '.capsule')
        for field, bad in (('sequence', True), ('policy_reference', True), ('policy_reference', 'unbound'),
                           ('key_id', False), ('checkpoint_hash', 'unbound')):
            value = json.loads(json.dumps(original))
            value['request'].update(request_id=other_id)
            value['request'][field] = bad
            path.write_bytes(encoded(value))
            path.chmod(0o600)
            with self.subTest(field=field, bad=bad):
                self.assertEqual(self.adapter.publish(self.request).reason, 'PERSISTENCE_INVALID')
            path.unlink()

    def test_readback_each_checkpoint_field_and_signature_replacement_rejected(self):
        self.adapter.publish(self.request)
        path = 'checkpoints/request.json'
        mutations = dict(chain_id_ref='f' * 64, installation_ref='f' * 64, sequence=2,
                         key_id='other', chain_head_hash='f' * 64,
                         signature=self.cp.signature[:-1] + bytes([self.cp.signature[-1] ^ 1]))
        for field, value in mutations.items():
            self.service.objects[path] = checkpoints.checkpoint_to_json(replace(self.cp, **{field: value})).encode()
            with self.subTest(field=field):
                self.assertEqual(self.adapter.read(self.request).reason, 'BINDING_MISMATCH')
        self.service.objects[path] = self.data
        self.assertEqual(self.adapter.read(self.request).readback, 'READBACK_OBSERVED')


def run_child():
    global crypto, checkpoints
    sys.path[:0] = [str(ROOT / 'scripts'), str(CORE)]
    crypto = importlib.import_module('checkpoint_crypto')
    checkpoints = importlib.import_module('signed_checkpoints')
    import checkpoint_anchor as m
    config = json.loads(sys.stdin.buffer.read(20000))
    policy = crypto.load_policy(encoded(config['policy']))
    verifier = crypto.OpenSSHCheckpointVerifier(crypto.OpenSSHBackend('/usr/bin/ssh-keygen'), policy)
    data = config['checkpoint'].encode()
    request = m.AnchorRequest('request', data, 'chain', 'installation', hashlib.sha256(data).hexdigest(),
                              1, 'key', policy.reference)
    target = m.GitHubTarget('https://api.github.com', 17, 'synthetic/anchor', 'anchor', 'checkpoints')
    transport = LocalTransport(config['port'])
    adapter = m.GitHubAnchor(target, config['directory'], verifier=verifier,
                             write_transport=transport, read_transport=transport)
    def pause():
        Path(config['marker']).write_text('ready')
        time.sleep(30)
    if config['mode'] == 'partial':
        real_write = m.os.write
        def partial(fd, data):
            regular = stat.S_ISREG(os.fstat(fd).st_mode)
            result = real_write(fd, data[:9] if regular else data)
            if regular:
                pause()
            return result
        m.os.write = partial
    elif config['mode'] == 'durable':
        real_request = transport.request
        def before_send(method, *args, **kwargs):
            if method == 'GET':
                pause()
            return real_request(method, *args, **kwargs)
        transport.request = before_send
    elif config['mode'] in ('receipt', 'observation', 'observation_partial'):
        real_observe = adapter._observe
        def observation(*args, **kwargs):
            if config['mode'] == 'receipt':
                pause()
            if config['mode'] == 'observation_partial':
                real_write = m.os.write
                def partial_observation(fd, data):
                    result = real_write(fd, data[:9])
                    pause()
                    return result
                m.os.write = partial_observation
            result = real_observe(*args, **kwargs)
            pause()
            return result
        adapter._observe = observation
    result = adapter.publish(request)
    print(json.dumps(vars(result), sort_keys=True))


if __name__ == '__main__':
    if '--child' in sys.argv:
        run_child()
    else:
        unittest.main()
