"""Synthetic contract tests. FakeSigner/FakeVerifier are NOT cryptography."""
from dataclasses import replace
import importlib
import json
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/long-horizon-engineering/scripts'


class FakeSigner:
    """TEST ONLY: records exact messages under arbitrary tokens; no security."""
    def __init__(self, m, key='key1', algorithm=None):
        self.m = m
        self.key = key
        self.algorithm = algorithm or m.SignatureAlgorithm.ED25519
        self.messages = {}

    def sign(self, message):
        token = ('TEST_ONLY_%d' % len(self.messages)).encode()
        self.messages[token] = message
        return self.m.SignatureEnvelope(self.algorithm, self.key, token)


class FakeVerifier:
    """TEST ONLY: exact-message lookup, not digital signature verification."""
    def __init__(self, signer):
        self.signer = signer

    def verify(self, message, envelope):
        m = self.signer.m
        if envelope.key_id != self.signer.key:
            return m.SignatureVerification(False, 'KEY_NOT_TRUSTED')
        valid = (envelope.algorithm == self.signer.algorithm
                 and self.signer.messages.get(envelope.signature) == message)
        return m.SignatureVerification(valid, 'VALID' if valid else 'SIGNATURE_INVALID',
                                       envelope.algorithm, envelope.key_id)


class CheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = sys.path[:]
        cls.modules = {n: sys.modules.get(n) for n in ('signed_checkpoints','security_authority_chain')}
        sys.path.insert(0, str(SCRIPTS))
        cls.m = importlib.import_module('signed_checkpoints') if (SCRIPTS/'signed_checkpoints.py').exists() else None

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = cls.path
        for n, v in cls.modules.items():
            if v is None: sys.modules.pop(n, None)
            else: sys.modules[n] = v

    def setUp(self):
        self.assertIsNotNone(self.m, 'signed checkpoint implementation missing')
        self.s = self.m.sc
        self.signer = FakeSigner(self.m)
        self.verifier = FakeVerifier(self.signer)
        self.actor = self.s.SecurityAuthority('admin', self.s.AuthorityRole.INSTALLATION_ADMIN, 'i')
        self.chain = self.make_chain(3)

    def make_chain(self, count, prefix='event', chain_id='c', install='i'):
        c = self.s.InMemorySecurityChain(chain_id, install)
        for i in range(count):
            c.append(self.s.SecurityEventDraft(prefix+str(i), self.s.EventType.SECURITY_ALERT,
                i, install, self.s.AuthorityRole.ROOT_OWNER, 'owner', 'synthetic'))
        return c

    def cp(self, chain=None, **kw):
        args = dict(checkpoint_id='cp1', now=10, algorithm=self.signer.algorithm, key_id=self.signer.key)
        args.update(kw)
        return self.m.create_checkpoint(chain or self.chain, self.actor, self.signer, self.verifier, **args)

    def verify(self, cp, **kw):
        return self.m.verify_checkpoint(cp, self.verifier, expected_chain_id='c', expected_installation_id='i', **kw)

    def anchor(self, cp, **kw):
        args = dict(anchor_id='anchor1', checkpoint_hash=self.m.checkpoint_hash(cp),
            checkpoint_sequence=cp.sequence, chain_id_ref=cp.chain_id_ref,
            installation_ref=cp.installation_ref, anchored_at=11, location_ref='opaque-object', receipt_ref=None)
        args.update(kw)
        return self.m.ExternalAnchor(**args)

    def test_current_and_extended_prefix(self):
        cp = self.cp()
        for c in (self.chain, self.make_chain(5)):
            result = self.m.verify_security_history(c, cp, self.verifier)
            self.assertTrue(result.valid)
            self.assertTrue(result.chain_valid and result.signature_valid and result.prefix_valid)
            self.assertIsNone(result.anchor_valid)
            self.assertEqual(result.trust_level, 'SIGNED_CHECKPOINT')

    def test_rollback_and_rebuilt_valid_history(self):
        cp = self.cp(self.make_chain(100))
        for count, prefix, reason in ((80,'event','CHECKPOINT_AHEAD_OF_CHAIN'),
                                     (100,'rebuild','CHAIN_DIVERGENCE')):
            c = self.make_chain(count, prefix)
            self.assertTrue(c.verify().valid)
            self.assertEqual(self.m.verify_chain_against_checkpoint(c,cp,self.verifier).reason, reason)
        # Mutate an old event while rebuilding every following record hash.
        c = self.make_chain(100)
        records = list(c.records())
        previous = self.s.GENESIS
        for i, r in enumerate(records):
            from dataclasses import asdict
            p = asdict(r)
            p.pop('record_hash')
            p['previous_hash'] = previous
            if i == 2: p['reason_ref'] = 'a'*64
            records[i] = self.s.SecurityRecord(**p, record_hash=self.s.artifact_digest(p))
            previous = records[i].record_hash
        c._records = records
        self.assertTrue(c.verify().valid)
        self.assertEqual(self.m.verify_chain_against_checkpoint(c,cp,self.verifier).reason,'CHAIN_DIVERGENCE')

    def test_canonical_and_roundtrip(self):
        cp = self.cp()
        payload = self.m.canonical_payload(cp)
        obj = json.loads(payload)
        self.assertNotIn('signature', obj)
        self.assertEqual(payload, json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
        self.assertEqual(obj['schema_version'],'20396-security-checkpoint/v1')
        self.assertEqual(obj['sequence'],3)
        serialized = self.m.checkpoint_to_json(cp)
        self.assertEqual(self.m.checkpoint_from_json(serialized),cp)
        reversed_json = json.dumps(dict(reversed(list(json.loads(serialized).items()))))
        self.assertEqual(self.m.canonical_payload(self.m.checkpoint_from_json(reversed_json)),payload)

    def test_every_signed_field_is_bound(self):
        cp = self.cp()
        mutations = dict(checkpoint_id='other',chain_id_ref='a'*64,installation_ref='b'*64,
            sequence=2,chain_head_hash='c'*64,created_at=11,key_id='key2',
            algorithm=self.m.SignatureAlgorithm.RSA_PSS_SHA256,previous_checkpoint_hash='d'*64)
        for field,value in mutations.items():
            with self.subTest(field=field):
                changed = replace(cp,**{field:value})
                self.assertFalse(self.verify(changed).valid)
                self.assertFalse(self.verifier.verify(self.m.canonical_payload(changed),
                    self.m.SignatureEnvelope(changed.algorithm,changed.key_id,changed.signature)).valid)
        self.assertEqual(self.verify(replace(cp,signature=b'changed')).reason,'SIGNATURE_INVALID')
        self.assertEqual(self.verify(replace(cp,key_id='unknown')).reason,'KEY_NOT_TRUSTED')
        self.assertFalse(self.verify(cp,expected_hash='f'*64).valid)

    def test_cross_scope(self):
        cp = self.cp()
        for c,reason in ((self.make_chain(3,chain_id='other'),'CHAIN_ID_MISMATCH'),
                         (self.make_chain(3,install='other'),'INSTALLATION_MISMATCH')):
            self.assertEqual(self.m.verify_chain_against_checkpoint(c,cp,self.verifier).reason,reason)

    def test_history_continuity_and_removal(self):
        a = self.cp()
        b = self.cp(self.make_chain(4), checkpoint_id='cp2',now=11,previous_checkpoint=a)
        c = self.cp(self.make_chain(5), checkpoint_id='cp3',now=12,previous_checkpoint=b)
        history = (a,b,c)
        check = lambda h: self.m.verify_checkpoint_sequence(h,self.verifier,expected_chain_id='c',expected_installation_id='i')
        self.assertTrue(check(history).valid)
        for bad in ((b,a,c),(a,c),(a,a),(),(replace(a,signature=b'bad'),b,c)):
            self.assertFalse(check(bad).valid)
        self.assertTrue(check((a,b)).valid) # Tail loss alone is not detectable.
        self.assertFalse(self.m.verify_checkpoint_against_anchor(b,self.anchor(c)).valid)

    def test_creation_sequence_time_and_empty_policy(self):
        a = self.cp()
        for c,kw in ((self.make_chain(0),{}),(self.make_chain(2),{'previous_checkpoint':a}),
                     (self.chain,{'previous_checkpoint':a}),
                     (self.make_chain(4),{'previous_checkpoint':a,'now':9}),
                     (self.make_chain(4,'replacement'),{'previous_checkpoint':a}),
                     (self.make_chain(4),{'previous_checkpoint':a,'checkpoint_id':'cp1'})):
            with self.assertRaises(ValueError): self.cp(c,**kw)

    def test_key_rotation_with_host_trust(self):
        a=self.cp()
        old=self.verifier
        self.signer=FakeSigner(self.m,key='key2')
        new=FakeVerifier(self.signer)
        class RotationVerifier:
            def verify(_,message,envelope):
                return (old if envelope.key_id=='key1' else new).verify(message,envelope)
        self.verifier=RotationVerifier()
        b=self.cp(self.make_chain(4),checkpoint_id='cp2',previous_checkpoint=a)
        self.assertTrue(self.m.verify_checkpoint_sequence((a,b),self.verifier,
            expected_chain_id='c',expected_installation_id='i').valid)

    def test_authority_creation_and_publication(self):
        cp=self.cp()
        for role in self.s.AuthorityRole:
            kw={'project_id':'p','task_id':'t'} if role==self.s.AuthorityRole.TASK_AUTHORITY else (
                {'project_id':'p'} if role==self.s.AuthorityRole.PROJECT_AUTHORITY else {})
            self.actor=self.s.SecurityAuthority('actor',role,'i',**kw)
            allowed=role in (self.s.AuthorityRole.ROOT_OWNER,self.s.AuthorityRole.INSTALLATION_ADMIN)
            if allowed: self.assertTrue(self.verify(self.cp()).valid)
            else:
                with self.assertRaisesRegex(ValueError,'AUTHORITY_DENIED'): self.cp()
            result=self.m.publish_anchor(cp,self.verifier,self.actor,None,anchor_request_id='req',
                installation_id='i',chain_id='c',now=12)
            self.assertEqual(result.reason=='AUTHORITY_DENIED',not allowed)
        for actor in (replace(self.actor,revoked=True),replace(self.actor,expires_at=1),
                      replace(self.actor,installation_id='wrong')):
            self.actor=actor
            with self.assertRaises(ValueError): self.cp()

    def test_anchor_match_and_metadata_mismatch(self):
        cp=self.cp(); a=self.anchor(cp)
        self.assertTrue(self.m.verify_checkpoint_against_anchor(cp,a).valid)
        for kw in ({'checkpoint_hash':'f'*64},{'checkpoint_sequence':2},
                   {'chain_id_ref':'f'*64},{'installation_ref':'f'*64},{'anchored_at':9}):
            self.assertFalse(self.m.verify_checkpoint_against_anchor(cp,replace(a,**kw)).valid)
        report=self.m.verify_security_history(self.chain,cp,self.verifier,external_anchor=a)
        self.assertEqual(report.trust_level,'SIGNED_AND_ANCHORED')
        self.assertTrue(report.anchor_valid)
        self.assertEqual(self.m.verify_security_history(self.chain).trust_level,'CHAIN_ONLY')
        self.assertFalse(self.m.verify_security_history(self.chain,replace(cp,signature=b'bad'),
            self.verifier,external_anchor=a).valid)

    def test_unknown_publication_and_readback_no_retry(self):
        cp=self.cp(); a=self.anchor(cp); calls=[]
        class Publisher:
            def publish(_,request_id,checkpoint):
                calls.append(request_id)
                raise RuntimeError('SYNTHETIC_PRIVATE_MARKER')
        result=self.m.publish_anchor(cp,self.verifier,self.actor,Publisher(),anchor_request_id='req',
            installation_id='i',chain_id='c',now=12)
        self.assertEqual(result.reason,'ANCHOR_OUTCOME_UNKNOWN')
        self.assertEqual(calls,['req'])
        self.assertNotIn('SYNTHETIC_PRIVATE_MARKER',repr(result))
        class Reader:
            def read(_,request_id):
                if request_id=='req': return a
        reconciled=self.m.reconcile_anchor(cp,self.verifier,Reader(),anchor_request_id='req',
            expected_chain_id='c',expected_installation_id='i')
        self.assertEqual(reconciled.trust,'READBACK_VERIFIED')
        self.assertTrue(reconciled.valid)
        missing=self.m.reconcile_anchor(cp,self.verifier,Reader(),anchor_request_id='missing',
            expected_chain_id='c',expected_installation_id='i')
        self.assertEqual(missing.reason,'NOT_FOUND')
        self.assertEqual(calls,['req'])
        class SuccessfulPublisher:
            def publish(_,request_id,checkpoint): return a
        result=self.m.publish_anchor(cp,self.verifier,self.actor,SuccessfulPublisher(),anchor_request_id='req',
            installation_id='i',chain_id='c',now=12)
        self.assertEqual(result.trust,'PUBLISHER_ATTESTED')

    def test_signer_and_verifier_fail_closed(self):
        cp=self.cp()
        class Broken:
            def sign(_,message): raise RuntimeError('SYNTHETIC_PRIVATE_MARKER')
            def verify(_,message,envelope): raise RuntimeError('SYNTHETIC_PRIVATE_MARKER')
        self.signer=Broken()
        with self.assertRaisesRegex(ValueError,'SIGNER_FAILED') as exc:
            self.m.create_checkpoint(self.chain,self.actor,self.signer,self.verifier,
                checkpoint_id='cp',now=10,algorithm=self.m.SignatureAlgorithm.ED25519,key_id='key1')
        self.assertIsNone(exc.exception.__cause__)
        self.verifier=Broken()
        self.assertEqual(self.verify(cp).reason,'SIGNATURE_INVALID')
        class WrongBinding:
            def verify(_,message,envelope):
                return self.m.SignatureVerification(True,'VALID',self.m.SignatureAlgorithm.RSA_PSS_SHA256,'key1')
        self.verifier=WrongBinding()
        self.assertFalse(self.verify(cp).valid)

    def test_invalid_values_and_private_repr(self):
        cp=self.cp()
        for field,values in [('created_at',[True,-1,float('nan'),float('inf'),2**54]),
                             ('sequence',[True,0,-1,1.5]),('chain_head_hash',['X'*64,'bad']),
                             ('signature',[b'',b'x'*(self.m.MAX_SIGNATURE_BYTES+1),'text']),
                             ('algorithm',['SHA256','ED25519']),('schema_version',['other'])]:
            for value in values:
                with self.assertRaises(ValueError): replace(cp,**{field:value})
        secret=replace(cp,checkpoint_id='SYNTHETIC_PRIVATE_MARKER')
        self.assertNotIn('SYNTHETIC_PRIVATE_MARKER',repr(secret))
        self.assertNotIn('SYNTHETIC_PRIVATE_MARKER',repr(self.verify(secret)))
        a=self.anchor(cp,location_ref='SYNTHETIC_PRIVATE_MARKER')
        self.assertNotIn('SYNTHETIC_PRIVATE_MARKER',repr(a))
        for location in ('https://x/?token=value','user:password@host','a\nsecret'):
            with self.assertRaises(ValueError): self.anchor(cp,location_ref=location)

    def test_deserialization_rejects_extensions_duplicates_and_bad_encoding(self):
        cp=self.cp(); text=self.m.checkpoint_to_json(cp); data=json.loads(text)
        for bad in (text[:-1]+',"extra":1}',text[:-1]+',"sequence":3}',
                    json.dumps(dict(data,signature='AA')),json.dumps(dict(data,signature='xy')),
                    '[]','{"sequence":NaN}'):
            with self.assertRaisesRegex(ValueError,'MALFORMED_CHECKPOINT'): self.m.checkpoint_from_json(bad)

    def test_signed_but_invalid_history_order(self):
        a=self.cp()
        b=self.cp(self.make_chain(4),checkpoint_id='cp2',now=11,previous_checkpoint=a)
        for kw in ({'created_at':9},{'sequence':2},{'sequence':3},{'checkpoint_id':'cp1'},
                   {'previous_checkpoint_hash':'f'*64}):
            candidate=replace(b,**kw)
            signed=replace(candidate,signature=self.signer.sign(self.m.canonical_payload(candidate)).signature)
            self.assertTrue(self.verify(signed).valid)
            result=self.m.verify_checkpoint_sequence((a,signed),self.verifier,
                expected_chain_id='c',expected_installation_id='i')
            self.assertEqual(result.reason,'CHECKPOINT_CONTINUITY_INVALID')

    def test_malformed_verifier_and_signer_results(self):
        cp=self.cp()
        for value in (True,None,{'valid':True},self.m.SignatureVerification(1,'VALID',cp.algorithm,cp.key_id),
                      self.m.SignatureVerification(True,'VALID',cp.algorithm,'other')):
            class Verifier:
                def verify(_,message,envelope): return value
            self.verifier=Verifier()
            self.assertFalse(self.verify(cp).valid)
        self.verifier=FakeVerifier(self.signer)
        for value in (None,True,self.m.SignatureEnvelope(cp.algorithm,'other',b'x'),
                      self.m.SignatureEnvelope(cp.algorithm,cp.key_id,b'unverifiable')):
            class Signer:
                def sign(_,message): return value
            with self.assertRaises(ValueError):
                self.m.create_checkpoint(self.chain,self.actor,Signer(),self.verifier,checkpoint_id='cp',
                    now=10,algorithm=cp.algorithm,key_id=cp.key_id)

    def test_invalid_chain_and_missing_checkpoint(self):
        cp=self.cp()
        self.chain._records[0]=replace(self.chain._records[0],record_hash='e'*64)
        result=self.m.verify_security_history(self.chain,cp,self.verifier)
        self.assertFalse(result.chain_valid)
        self.assertFalse(result.valid)
        with self.assertRaisesRegex(ValueError,'CHAIN_INVALID'): self.cp()
        self.assertEqual(self.m.verify_security_history(self.make_chain(3),external_anchor=self.anchor(cp)).reason,
                         'CHECKPOINT_MISSING')

    def test_adapter_mismatch_errors_and_denied_no_effect(self):
        cp=self.cp(); calls=[]
        class Adapter:
            def publish(_,request_id,checkpoint): calls.append(request_id); return self.anchor(cp,checkpoint_hash='f'*64)
            def read(_,request_id): raise RuntimeError('PRIVATE_MARKER')
        self.actor=replace(self.actor,revoked=True)
        result=self.m.publish_anchor(cp,self.verifier,self.actor,Adapter(),anchor_request_id='req',
            installation_id='i',chain_id='c',now=12)
        self.assertEqual(result.reason,'AUTHORITY_DENIED')
        self.assertEqual(calls,[])
        self.actor=replace(self.actor,revoked=False)
        result=self.m.publish_anchor(cp,self.verifier,self.actor,Adapter(),anchor_request_id='req',
            installation_id='i',chain_id='c',now=12)
        self.assertEqual(result.reason,'ANCHOR_OUTCOME_UNKNOWN')
        self.assertEqual(self.m.reconcile_anchor(cp,self.verifier,Adapter(),anchor_request_id='req',
            expected_chain_id='c',expected_installation_id='i').reason,'ANCHOR_OUTCOME_UNKNOWN')

    def test_import_has_no_operational_side_effect(self):
        import os
        from unittest.mock import patch
        import socket
        import subprocess
        import threading
        import builtins
        before=dict(os.environ)
        # Import dependency once before guarding operational calls. Importlib's
        # loader reads source as usual; module-level application I/O is forbidden.
        with patch.object(builtins,'open',side_effect=AssertionError('filesystem')), \
             patch.object(socket,'socket',side_effect=AssertionError('network')), \
             patch.object(subprocess,'Popen',side_effect=AssertionError('process')), \
             patch.object(threading.Thread,'start',side_effect=AssertionError('thread')):
            # Execute under a fresh name so existing test classes remain identical.
            spec=importlib.util.spec_from_file_location('checkpoint_import_probe',SCRIPTS/'signed_checkpoints.py')
            module=importlib.util.module_from_spec(spec)
            sys.modules[spec.name]=module
            try: spec.loader.exec_module(module)
            finally: sys.modules.pop(spec.name,None)
        self.assertEqual(dict(os.environ),before)


if __name__=='__main__': unittest.main()
