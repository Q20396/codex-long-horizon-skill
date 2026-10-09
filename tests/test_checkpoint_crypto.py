"""Real OpenSSH integration with temporary synthetic keys; no production custody."""
from dataclasses import replace
import base64
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / '.agents/skills/long-horizon-engineering/scripts'
BACKEND = '/usr/bin/ssh-keygen'
PURPOSE = '20396-security-checkpoint/v1'
ENV = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C',
       'SSH_ASKPASS_REQUIRE': 'never'}


class CheckpointCryptoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_path = sys.path[:]
        cls.old_modules = {n: sys.modules.get(n) for n in
                           ('checkpoint_crypto', 'signed_checkpoints', 'security_authority_chain')}
        sys.path[:0] = [str(ROOT / 'scripts'), str(CORE)]
        cls.m = importlib.import_module('checkpoint_crypto') if (
            ROOT / 'scripts/checkpoint_crypto.py').exists() else None
        cls.c = importlib.import_module('signed_checkpoints')
        if cls.m is not None and Path(BACKEND).is_file():
            identity = hashlib.sha256(Path(BACKEND).read_bytes()).hexdigest()
            companion = subprocess.run(['/usr/bin/ssh', '-V'], env=ENV, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, timeout=5, start_new_session=True)
            version = (companion.stdout + companion.stderr).decode('ascii').strip()
            if companion.returncode != 0 or len(version) > 256:
                raise AssertionError('OpenSSH companion version probe failed')
            print('H4_BACKEND platform=' + platform.platform() + ' executable=' + BACKEND
                  + ' sha256=' + identity + ' companion_ssh_version=' + version
                  + ' version_provenance=COMPANION_NOT_SSH_KEYGEN_IDENTITY')

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = cls.old_path
        for name, value in cls.old_modules.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value

    def setUp(self):
        self.assertIsNotNone(self.m, 'real checkpoint crypto capability missing')
        # Required real cases deliberately fail rather than skip without a backend.
        self.assertTrue(Path(BACKEND).is_file(), 'required OpenSSH backend missing')
        self.tmp = tempfile.TemporaryDirectory(prefix='h4-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        os.chmod(self.root, 0o700)
        self.keys = {}
        for name in ('A', 'B'):
            key = self.root / name
            result = self.direct(['-q', '-t', 'ed25519', '-N', '', '-f', str(key)])
            self.assertEqual(result.returncode, 0)
            public = ' '.join(key.with_suffix('.pub').read_text().split()[:2])
            blob = base64.b64decode(public.split()[1])
            fingerprint = 'SHA256:' + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip('=')
            self.keys[name] = dict(key_id=name, principal='synthetic-' + name,
                                   public_key=public, fingerprint=fingerprint,
                                   purpose=PURPOSE, status='ACTIVE')
        self.backend = self.m.OpenSSHBackend(BACKEND)
        self.policy = self.policy_for('A')
        self.signer = self.m.OpenSSHCheckpointSigner(self.backend, 'A', str(self.root / 'A'))
        self.verifier = self.m.OpenSSHCheckpointVerifier(self.backend, self.policy)

    def direct(self, args, data=None):
        return subprocess.run([BACKEND] + args, input=data, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=ENV, timeout=5, start_new_session=True)

    def policy_text(self, *names, version='policy-1', **changes):
        value = dict(schema_version='20396-checkpoint-trust-policy/v1',
                     policy_version=version, keys=[dict(self.keys[n]) for n in names])
        value.update(changes)
        return json.dumps(value)

    def policy_for(self, *names, **changes):
        return self.m.load_policy(self.policy_text(*names, **changes))

    def checkpoint(self, signer=None, verifier=None, count=1, **changes):
        sc = self.c.sc
        chain = sc.InMemorySecurityChain('chain', 'installation')
        for index in range(count):
            chain.append(sc.SecurityEventDraft('event-' + str(index), sc.EventType.SECURITY_ALERT,
                         index, 'installation', sc.AuthorityRole.ROOT_OWNER, 'owner', 'synthetic'))
        actor = sc.SecurityAuthority('admin', sc.AuthorityRole.INSTALLATION_ADMIN, 'installation')
        args = dict(checkpoint_id='checkpoint-' + str(count), now=10 + count,
                    algorithm=self.c.SignatureAlgorithm.ED25519, key_id='A')
        args.update(changes)
        cp = self.c.create_checkpoint(chain, actor, signer or self.signer,
                                      verifier or self.verifier, **args)
        return chain, cp

    def envelope(self, cp):
        return self.c.SignatureEnvelope(cp.algorithm, cp.key_id, cp.signature)

    def test_real_signature_core_history_and_direct_openssh_acceptance(self):
        chain, cp = self.checkpoint()
        assessment = self.verifier.assess(self.c.canonical_payload(cp), self.envelope(cp))
        self.assertEqual((assessment.cryptographic_validity, assessment.signer_trust), ('VALID', 'TRUSTED'))
        self.assertTrue(assessment.policy_reference.startswith('policy-1:'))
        self.assertTrue(self.c.verify_security_history(chain, cp, self.verifier).valid)
        records = chain.records()
        self.verifier.assess(self.c.canonical_payload(cp), self.envelope(cp))
        self.assertEqual(chain.records(), records)
        self.assertFalse(hasattr(assessment, 'retry_authorized'))
        self.assertLessEqual(len(cp.signature), 1024)
        signature_file = self.root / 'signature'
        armor = b'-----BEGIN SSH SIGNATURE-----\n' + base64.b64encode(cp.signature) + b'\n-----END SSH SIGNATURE-----\n'
        signature_file.write_bytes(armor)
        allowed = self.root / 'allowed'
        allowed.write_text('synthetic-A namespaces="' + PURPOSE + '" ' + self.keys['A']['public_key'] + '\n')
        result = self.direct(['-Y', 'verify', '-f', str(allowed), '-I', 'synthetic-A',
                              '-n', PURPOSE, '-s', str(signature_file)], self.c.canonical_payload(cp))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.c.checkpoint_from_json(self.c.checkpoint_to_json(cp)), cp)
        print('H4_REAL_CRYPTO namespace=' + PURPOSE + ' encoding=RAW_SSHSIG_V1 signature_bytes='
              + str(len(cp.signature)) + ' core=ACCEPTED direct_OpenSSH=PASS')

    def test_signature_carried_public_key_does_not_enroll_unknown_signer(self):
        signer = self.m.OpenSSHCheckpointSigner(self.backend, 'B', str(self.root / 'B'))
        envelope = signer.sign(b'synthetic message')
        assessment = self.verifier.assess(b'synthetic message', envelope)
        self.assertEqual((assessment.cryptographic_validity, assessment.signer_trust), ('VALID', 'UNTRUSTED'))
        self.assertEqual(self.verifier.verify(b'synthetic message', envelope).reason, 'KEY_NOT_TRUSTED')

    def test_key_id_cannot_substitute_another_mathematically_valid_key(self):
        signer = self.m.OpenSSHCheckpointSigner(self.backend, 'A', str(self.root / 'B'))
        envelope = signer.sign(b'synthetic message')
        assessment = self.verifier.assess(b'synthetic message', envelope)
        self.assertEqual((assessment.cryptographic_validity, assessment.signer_trust), ('VALID', 'UNTRUSTED'))
        self.assertEqual(self.verifier.verify(b'synthetic message', envelope).reason, 'KEY_NOT_TRUSTED')

    def test_every_canonical_field_tamper_is_rejected(self):
        _, cp = self.checkpoint()
        fields = dict(checkpoint_id='different', chain_id_ref='a' * 64, installation_ref='b' * 64,
                      sequence=2, chain_head_hash='c' * 64, created_at=99, key_id='B',
                      previous_checkpoint_hash='d' * 64)
        for field, value in fields.items():
            with self.subTest(field=field):
                changed = replace(cp, **{field: value})
                result = self.verifier.assess(self.c.canonical_payload(changed), self.envelope(changed))
                self.assertEqual(result.cryptographic_validity, 'INVALID')
                self.assertFalse(self.verifier.verify(self.c.canonical_payload(changed), self.envelope(changed)).valid)
        changed = replace(cp, algorithm=self.c.SignatureAlgorithm.RSA_PSS_SHA256)
        self.assertEqual(self.verifier.assess(self.c.canonical_payload(changed), self.envelope(changed)).cryptographic_validity,
                         'NOT_ASSESSED')

    def test_strict_binary_signature_encoding_and_no_algorithm_fallback(self):
        envelope = self.signer.sign(b'message')
        bad = (b'TEST_ONLY_0', envelope.signature[:-1], envelope.signature + b'extra',
               b'-----BEGIN SSH SIGNATURE-----\n', b'SSHSIG' + b'\x00\x00\x00\x02' + envelope.signature[10:],
               envelope.signature.replace(PURPOSE.encode(), b'x' * len(PURPOSE)),
               envelope.signature[:-1] + bytes([envelope.signature[-1] ^ 1]))
        for signature in bad:
            with self.subTest(signature_length=len(signature)):
                changed = replace(envelope, signature=signature)
                self.assertEqual(self.verifier.assess(b'message', changed).cryptographic_validity, 'INVALID')
                self.assertFalse(self.verifier.verify(b'message', changed).valid)
        for algorithm in (self.c.SignatureAlgorithm.ECDSA_P256_SHA256, self.c.SignatureAlgorithm.RSA_PSS_SHA256):
            self.assertFalse(self.verifier.verify(b'message', replace(envelope, algorithm=algorithm)).valid)
        with self.assertRaises(ValueError):
            self.c.SignatureEnvelope(self.c.SignatureAlgorithm.ED25519, 'A', b'x' * 1025)

    def test_git_namespace_real_signature_is_rejected(self):
        result = self.direct(['-Y', 'sign', '-f', str(self.root / 'A'), '-n', 'git'], b'message')
        self.assertEqual(result.returncode, 0)
        raw = base64.b64decode(b''.join(result.stdout.splitlines()[1:-1]))
        envelope = self.c.SignatureEnvelope(self.c.SignatureAlgorithm.ED25519, 'A', raw)
        self.assertEqual(self.verifier.assess(b'message', envelope).cryptographic_validity, 'INVALID')

    def test_policy_strict_schema_and_key_fingerprint_purpose_binding(self):
        valid = json.loads(self.policy_text('A'))
        bad = [None, '', '{}', self.policy_text('A', schema_version='v2'),
               self.policy_text('A', extra='field'), self.policy_text('A', policy_version=1),
               self.policy_text('A')[:-1] + ',"keys":[]}', 'x' * 32769]
        for field, value in (('public_key', self.keys['B']['public_key']), ('fingerprint', 'SHA256:bad'),
                             ('purpose', 'git'), ('principal', 'line\nbreak'), ('status', 'UNKNOWN'),
                             ('key_id', True), ('extra', 'unknown'), ('public_key', 'ssh-rsa AAAA')):
            obj = json.loads(json.dumps(valid))
            obj['keys'][0][field] = value
            bad.append(json.dumps(obj))
        bad.append(json.dumps(valid).replace('"status": "ACTIVE"', '"status": "ACTIVE", "status": "ACTIVE"'))
        for text in bad:
            with self.subTest(case=str(text)[:30]):
                with self.assertRaises(self.m.PolicyError):
                    self.m.load_policy(text)
        for identity in ('key_id', 'principal', 'public_key'):
            obj = json.loads(self.policy_text('A', 'B'))
            obj['keys'][1][identity] = obj['keys'][0][identity]
            if identity == 'public_key':
                obj['keys'][1]['fingerprint'] = obj['keys'][0]['fingerprint']
            with self.assertRaises(self.m.PolicyError):
                self.m.load_policy(json.dumps(obj))

    def test_missing_policy_keeps_mathematics_separate_from_unknown_trust(self):
        envelope = self.signer.sign(b'message')
        verifier = self.m.OpenSSHCheckpointVerifier(self.backend, None)
        result = verifier.assess(b'message', envelope)
        self.assertEqual((result.cryptographic_validity, result.signer_trust), ('VALID', 'UNKNOWN'))
        self.assertIsNone(result.policy_reference)
        self.assertFalse(verifier.verify(b'message', envelope).valid)

    def test_immutable_policy_and_explicit_snapshot_replacement(self):
        source = json.loads(self.policy_text('A'))
        policy = self.m.load_policy(json.dumps(source))
        source['keys'][0]['status'] = 'REVOKED'
        with self.assertRaises((AttributeError, TypeError)):
            policy.keys[0].status = 'REVOKED'
        envelope = self.signer.sign(b'message')
        self.assertTrue(self.m.OpenSSHCheckpointVerifier(self.backend, policy).verify(b'message', envelope).valid)
        revoked = self.m.load_policy(json.dumps(source))
        result = self.m.OpenSSHCheckpointVerifier(self.backend, revoked).assess(b'message', envelope)
        self.assertEqual((result.cryptographic_validity, result.signer_trust), ('VALID', 'UNTRUSTED'))

    def test_rotation_retained_history_revocation_and_old_policy_limit(self):
        _, first = self.checkpoint()
        rotated = self.m.OpenSSHCheckpointVerifier(self.backend, self.policy_for('A', 'B', version='policy-2'))
        signer_b = self.m.OpenSSHCheckpointSigner(self.backend, 'B', str(self.root / 'B'))
        _, second = self.checkpoint(signer_b, rotated, count=2, key_id='B', previous_checkpoint=first)
        self.assertTrue(self.c.verify_checkpoint_sequence([first, second], rotated,
                        expected_chain_id='chain', expected_installation_id='installation').valid)
        removed = self.m.OpenSSHCheckpointVerifier(self.backend, self.policy_for('B'))
        self.assertEqual(removed.verify(self.c.canonical_payload(first), self.envelope(first)).reason, 'KEY_NOT_TRUSTED')
        obj = json.loads(self.policy_text('A', 'B', version='policy-3'))
        obj['keys'][0]['status'] = 'REVOKED'
        revoked = self.m.OpenSSHCheckpointVerifier(self.backend, self.m.load_policy(json.dumps(obj)))
        for timestamp in (0, first.created_at, 100):
            candidate = replace(first, created_at=timestamp)
            self.assertEqual(revoked.verify(self.c.canonical_payload(candidate), self.envelope(candidate)).reason,
                             'KEY_NOT_TRUSTED')
        # Supplying an older explicitly ACTIVE snapshot still works: no rollback ledger.
        self.assertTrue(self.verifier.verify(self.c.canonical_payload(first), self.envelope(first)).valid)

    def test_backend_absence_failure_timeout_output_and_cleanup_are_unknown(self):
        envelope = self.signer.sign(b'message')
        missing = self.m.OpenSSHBackend(str(self.root / 'missing'))
        result = self.m.OpenSSHCheckpointVerifier(missing, self.policy).assess(b'message', envelope)
        self.assertEqual(result.cryptographic_validity, 'UNKNOWN')
        for reason in ('BACKEND_TIMEOUT', 'BACKEND_OUTPUT_LIMIT', 'BACKEND_FAILED', 'CLEANUP_UNKNOWN'):
            with self.subTest(reason=reason), patch.object(self.backend, '_run', side_effect=self.m.BackendFailure(reason)):
                result = self.verifier.assess(b'message', envelope)
                self.assertEqual(result.cryptographic_validity, 'UNKNOWN')
                self.assertFalse(self.verifier.verify(b'message', envelope).valid)
                with self.assertRaises(self.m.BackendFailure):
                    self.signer.sign(b'message')
        failed_cleanup_paths = []
        def fail_cleanup(path):
            failed_cleanup_paths.append(path)
            raise OSError('synthetic cleanup failure')
        with patch.object(self.m.shutil, 'rmtree', side_effect=fail_cleanup):
            result = self.verifier.assess(b'message', envelope)
        for path in failed_cleanup_paths:
            self.m.shutil.rmtree(path)
        self.assertEqual((result.cryptographic_validity, result.reason), ('UNKNOWN', 'CLEANUP_UNKNOWN'))

    def test_real_subprocess_output_limit_timeout_and_nonzero_failure(self):
        envelope = self.signer.sign(b'message')
        for body, reason in (("import time; time.sleep(4)", 'BACKEND_TIMEOUT'),
                             ("import os; os.write(1, b'x' * 100000)", 'BACKEND_OUTPUT_LIMIT'),
                             ("import sys; sys.exit(9)", 'BACKEND_FAILED')):
            executable = self.root / 'synthetic-backend'
            executable.write_text('#!' + sys.executable + '\n' + body + '\n')
            executable.chmod(0o700)
            backend = self.m.OpenSSHBackend(str(executable), timeout=2, max_output_bytes=1024)
            result = self.m.OpenSSHCheckpointVerifier(backend, self.policy).assess(b'message', envelope)
            self.assertEqual((result.cryptographic_validity, result.reason), ('UNKNOWN', reason))

    def test_input_limits_and_explicit_paths(self):
        with self.assertRaises(ValueError):
            self.m.OpenSSHBackend('ssh-keygen')
        with self.assertRaises(ValueError):
            self.m.OpenSSHCheckpointSigner(self.backend, 'A', 'relative-key')
        for data in (b'', b'x' * 8193, 'not bytes'):
            with self.assertRaises(ValueError):
                self.signer.sign(data)
        key = self.root / 'A'
        key.chmod(0o644)
        with self.assertRaises(self.m.BackendFailure):
            self.signer.sign(b'message')
        key.chmod(0o600)
        linked_key = self.root / 'key-link'
        linked_key.symlink_to(key)
        with self.assertRaises(self.m.BackendFailure):
            self.m.OpenSSHCheckpointSigner(self.backend, 'A', str(linked_key)).sign(b'message')

    def test_non_ed25519_key_rejected_before_any_sign_operation(self):
        key = self.root / 'rsa'
        result = self.direct(['-q', '-t', 'rsa', '-b', '1024', '-N', '', '-f', str(key)])
        self.assertEqual(result.returncode, 0)
        signer = self.m.OpenSSHCheckpointSigner(self.backend, 'rsa', str(key))
        # Real backend performs public-key inspection; any signing of RSA is a bug.
        real_run = self.backend._run
        def prohibit_other_algorithm_sign(args, data):
            if args[:2] == ['-Y', 'sign']:
                self.fail('unsupported private key reached signing operation')
            return real_run(args, data)
        with patch.object(self.backend, '_run', side_effect=prohibit_other_algorithm_sign):
            with self.assertRaises(self.m.BackendFailure):
                signer.sign(b'message')

    def test_timeout_terminates_descendants_after_direct_child_has_exited(self):
        executable = self.root / 'fork-probe'
        marker = self.root / 'late-effect'
        ready = self.root / 'fork-ready'
        executable.write_text('#!' + sys.executable + '\nimport os,time\n'
            'if os.fork() == 0:\n    time.sleep(3)\n    open(' + repr(str(marker)) + ',"w").write("bad")\n'
            'else:\n    open(' + repr(str(ready)) + ',"w").write("ready")\n    os._exit(0)\n')
        executable.chmod(0o700)
        backend = self.m.OpenSSHBackend(str(executable), timeout=2)
        real_popen, real_killpg = self.m.subprocess.Popen, self.m.os.killpg
        processes, leader_codes_before_kill = [], []
        def observe_popen(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            processes.append(process)
            return process
        def observe_group_kill(*args):
            leader_codes_before_kill.append(processes[0].poll())
            return real_killpg(*args)
        with patch.object(self.m.subprocess, 'Popen', side_effect=observe_popen), \
                patch.object(self.m.os, 'killpg', side_effect=observe_group_kill):
            with self.assertRaises(self.m.BackendFailure):
                backend._run([], b'message')
        self.assertTrue(ready.exists(), 'fixture never established the exited leader')
        self.assertEqual(leader_codes_before_kill, [0], 'leader had not exited before group cleanup')
        time.sleep(3.2)
        self.assertFalse(marker.exists(), 'timeout left child process executing')

    def test_file_close_failure_is_cleanup_unknown(self):
        envelope = self.signer.sign(b'message')
        real_fdopen = self.m.os.fdopen
        class BadClose:
            def __init__(self, fd, mode):
                self.stream = real_fdopen(fd, mode)
            def write(self, data):
                return self.stream.write(data)
            def close(self):
                self.stream.close()
                raise OSError('synthetic close ambiguity')
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.close()
        with patch.object(self.m.os, 'fdopen', side_effect=BadClose):
            result = self.verifier.assess(b'message', envelope)
        self.assertEqual((result.cryptographic_validity, result.reason), ('UNKNOWN', 'CLEANUP_UNKNOWN'))

    def test_nonzero_exited_leader_terminates_children_that_closed_pipes(self):
        executable = self.root / 'nonzero-fork-probe'
        marker = self.root / 'late-effect'
        ready = self.root / 'fork-ready'
        executable.write_text('#!' + sys.executable + '\nimport os,time\n'
            'if os.fork() == 0:\n    os.close(0)\n    os.close(1)\n    os.close(2)\n'
            '    time.sleep(1)\n    open(' + repr(str(marker)) + ',"w").write("bad")\n'
            'else:\n    open(' + repr(str(ready)) + ',"w").write("ready")\n    os._exit(9)\n')
        executable.chmod(0o700)
        code, _, _ = self.m.OpenSSHBackend(str(executable))._run([], b'message')
        self.assertEqual(code, 9)
        self.assertTrue(ready.exists(), 'fixture never established the exited leader')
        time.sleep(1.1)
        self.assertFalse(marker.exists(), 'nonzero exit left child process executing')

    def test_trusted_verification_backend_refusal_cannot_fallback_to_trust(self):
        envelope = self.signer.sign(b'message')
        real_run = self.backend._run
        def reject_allowed_signers(args, data):
            if args[:2] == ['-Y', 'verify']:
                return 255, b'', b'backend refused'
            return real_run(args, data)
        with patch.object(self.backend, '_run', side_effect=reject_allowed_signers):
            result = self.verifier.assess(b'message', envelope)
        self.assertEqual((result.cryptographic_validity, result.signer_trust), ('UNKNOWN', 'UNKNOWN'))

    def test_import_inactive_and_no_agent_environment_discovery(self):
        code = """
import sys
def audit(event, args):
    if event in ('subprocess.Popen', 'os.mkdir', 'os.remove', 'os.rename'):
        raise RuntimeError('unexpected import effect')
sys.addaudithook(audit)
import checkpoint_crypto
"""
        result = subprocess.run([sys.executable, '-B', '-c', code], env={**ENV, 'PYTHONPATH':
                   str(ROOT / 'scripts') + os.pathsep + str(CORE)}, stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        executable = self.root / 'env-probe'
        executable.write_text('#!' + sys.executable + '\nimport os,sys\n'
            'bad=set(os.environ)&{"SSH_AUTH_SOCK","SSH_AGENT_PID","SSH_ASKPASS","HOME","DISPLAY"}\n'
            'sys.exit(8 if bad else 0)\n')
        executable.chmod(0o700)
        with patch.dict(os.environ, {'SSH_AUTH_SOCK': 'synthetic', 'SSH_AGENT_PID': '1',
                                    'SSH_ASKPASS': 'synthetic', 'DISPLAY': 'synthetic'}):
            self.assertEqual(self.m.OpenSSHBackend(str(executable))._run([], b'message')[0], 0)

    def test_encrypted_synthetic_key_fails_without_interaction_or_agent(self):
        key = self.root / 'encrypted'
        self.assertEqual(self.direct(['-q', '-t', 'ed25519', '-N', 'synthetic-test-passphrase',
                                     '-f', str(key)]).returncode, 0)
        signer = self.m.OpenSSHCheckpointSigner(self.backend, 'encrypted', str(key))
        started = time.monotonic()
        with self.assertRaises(self.m.BackendFailure) as result:
            signer.sign(b'message')
        self.assertEqual(str(result.exception), 'SIGNING_KEY_UNAVAILABLE')
        self.assertLess(time.monotonic() - started, 6)


if __name__ == '__main__':
    unittest.main()
