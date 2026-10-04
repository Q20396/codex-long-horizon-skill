"""Inactive checkpoint/anchor contracts. Crypto and independent retention are host supplied.

No keys, crypto algorithms, storage, network adapters or import-time I/O. Python
callers and adapters are trusted: this is not a hostile-process security boundary.
"""
from dataclasses import dataclass, fields, replace
from enum import Enum
import hashlib
import json
import math
import re
from typing import Protocol

import security_authority_chain as sc

SCHEMA = '20396-security-checkpoint/v1'
GENESIS_CHECKPOINT_HASH = '0' * 64
MAX_SIGNATURE_BYTES = 1024
MAX_CHECKPOINTS = 1024
MAX_ARTIFACT_BYTES = 8192


class SignatureAlgorithm(str, Enum):
    ED25519 = 'ED25519'
    ECDSA_P256_SHA256 = 'ECDSA_P256_SHA256'
    RSA_PSS_SHA256 = 'RSA_PSS_SHA256'


def _text(value):
    return (type(value) is str and 0 < len(value) <= 256 and value.strip() == value
            and all(32 <= ord(c) < 127 for c in value))


def _opaque(value):
    return _text(value) and re.fullmatch(r'[A-Za-z0-9_.-]+', value) is not None


def _hash(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _time(value):
    return type(value) in (int, float) and 0 <= value <= 2**53 and math.isfinite(value)


def _sequence(value):
    return type(value) is int and 1 <= value <= sc.MAX_RECORDS


def _ref(value):
    if not sc._text(value):
        raise ValueError('IDENTITY_INVALID')
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


@dataclass(frozen=True, repr=False)
class SignatureEnvelope:
    algorithm: SignatureAlgorithm
    key_id: str
    signature: bytes

    def __post_init__(self):
        if (type(self.algorithm) is not SignatureAlgorithm or not _opaque(self.key_id)
                or type(self.signature) is not bytes or not 0 < len(self.signature) <= MAX_SIGNATURE_BYTES):
            raise ValueError('SIGNATURE_ENVELOPE_INVALID')


@dataclass(frozen=True, repr=False)
class SignatureVerification:
    """Host must return the actual trusted algorithm/key binding used to verify."""
    valid: bool
    reason: str
    algorithm: SignatureAlgorithm = None
    key_id: str = None


class CheckpointSigner(Protocol):
    def sign(self, message_bytes: bytes) -> SignatureEnvelope: ...


class CheckpointVerifier(Protocol):
    def verify(self, message_bytes: bytes, envelope: SignatureEnvelope) -> SignatureVerification: ...


@dataclass(frozen=True, repr=False)
class SignedCheckpoint:
    """Candidate artifact; construction alone is NOT evidence of verified signing."""
    schema_version: str
    checkpoint_id: str
    chain_id_ref: str
    installation_ref: str
    sequence: int
    chain_head_hash: str
    created_at: float
    key_id: str
    algorithm: SignatureAlgorithm
    previous_checkpoint_hash: str
    signature: bytes

    def __post_init__(self):
        if (type(self.schema_version) is not str or self.schema_version != SCHEMA
                or not _opaque(self.checkpoint_id) or not _sequence(self.sequence)
                or not _time(self.created_at)
                or not all(_hash(v) for v in (self.chain_id_ref,self.installation_ref,
                                             self.chain_head_hash,self.previous_checkpoint_hash))):
            raise ValueError('MALFORMED_CHECKPOINT')
        try:
            SignatureEnvelope(self.algorithm,self.key_id,self.signature)
        except ValueError:
            raise ValueError('MALFORMED_CHECKPOINT') from None
        object.__setattr__(self,'created_at',float(self.created_at))


def _valid_checkpoint(cp):
    if type(cp) is not SignedCheckpoint:
        return False
    try:
        replace(cp)
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def canonical_payload(checkpoint):
    if not _valid_checkpoint(checkpoint):
        raise ValueError('MALFORMED_CHECKPOINT')
    values = {f.name:getattr(checkpoint,f.name) for f in fields(SignedCheckpoint) if f.name != 'signature'}
    values['algorithm'] = checkpoint.algorithm.value
    # Normalize numeric representation even for a deserialized candidate.
    values['created_at'] = float(checkpoint.created_at)
    return _json(values)


def checkpoint_to_json(checkpoint):
    values = json.loads(canonical_payload(checkpoint))
    values['signature'] = checkpoint.signature.hex()
    return _json(values).decode('utf-8')


def checkpoint_hash(checkpoint):
    return hashlib.sha256(checkpoint_to_json(checkpoint).encode('utf-8')).hexdigest()


def checkpoint_from_json(text):
    def pairs(items):
        result = {}
        for k,v in items:
            if k in result: raise ValueError('MALFORMED_CHECKPOINT')
            result[k] = v
        return result
    try:
        if type(text) is not str or len(text.encode('utf-8')) > MAX_ARTIFACT_BYTES:
            raise ValueError()
        obj = json.loads(text,object_pairs_hook=pairs)
        if type(obj) is not dict or set(obj) != {f.name for f in fields(SignedCheckpoint)}:
            raise ValueError()
        signature = obj['signature']
        if (type(signature) is not str or not 2 <= len(signature) <= 2*MAX_SIGNATURE_BYTES
                or len(signature)%2 or re.fullmatch('[0-9a-f]+',signature) is None):
            raise ValueError()
        obj['signature'] = bytes.fromhex(signature)
        obj['algorithm'] = SignatureAlgorithm(obj['algorithm'])
        return SignedCheckpoint(**obj)
    except (ValueError,TypeError,KeyError,UnicodeError,RecursionError):
        raise ValueError('MALFORMED_CHECKPOINT') from None


@dataclass(frozen=True)
class CheckpointVerification:
    valid: bool
    reason: str
    chain_valid: bool = None
    signature_valid: bool = None
    prefix_valid: bool = None
    continuity_valid: bool = None
    anchor_valid: bool = None
    checkpoint_sequence: int = None
    chain_sequence: int = None
    trust_level: str = 'UNVERIFIED'


def verify_checkpoint(checkpoint, verifier, *, expected_chain_id, expected_installation_id, expected_hash=None):
    if not _valid_checkpoint(checkpoint):
        return CheckpointVerification(False,'MALFORMED_CHECKPOINT')
    cp = checkpoint
    try:
        chain_ref, install_ref = _ref(expected_chain_id), _ref(expected_installation_id)
    except ValueError:
        return CheckpointVerification(False,'IDENTITY_INVALID')
    if cp.chain_id_ref != chain_ref:
        return CheckpointVerification(False,'CHAIN_ID_MISMATCH')
    if cp.installation_ref != install_ref:
        return CheckpointVerification(False,'INSTALLATION_MISMATCH')
    if expected_hash is not None and (not _hash(expected_hash) or checkpoint_hash(cp) != expected_hash):
        return CheckpointVerification(False,'CHECKPOINT_HASH_MISMATCH')
    try:
        envelope = SignatureEnvelope(cp.algorithm,cp.key_id,cp.signature)
        result = verifier.verify(canonical_payload(cp),envelope)
    except Exception:
        result = None
    valid = (type(result) is SignatureVerification and result.valid is True and result.reason == 'VALID'
             and type(result.algorithm) is SignatureAlgorithm and result.algorithm == cp.algorithm
             and type(result.key_id) is str and result.key_id == cp.key_id)
    reason = 'VALID' if valid else 'SIGNATURE_INVALID'
    if type(result) is SignatureVerification and result.valid is False and result.reason == 'KEY_NOT_TRUSTED':
        reason = 'KEY_NOT_TRUSTED'
    return CheckpointVerification(valid,reason,signature_valid=valid,checkpoint_sequence=cp.sequence,
                                  trust_level='SIGNED_CHECKPOINT' if valid else 'UNVERIFIED')


def _snapshot(chain):
    """One bounded snapshot; never verify one records read and compare a second."""
    if not isinstance(chain,sc.InMemorySecurityChain):
        raise ValueError('CHAIN_INVALID')
    records = chain.records()
    result = sc.verify_chain(records,chain._chain_id,chain._installation_id)
    return records, result, chain._chain_id, chain._installation_id


def _prefix(records, chain_result, cp, verifier, chain_id, installation_id):
    result = verify_checkpoint(cp,verifier,expected_chain_id=chain_id,expected_installation_id=installation_id)
    result = replace(result,chain_valid=chain_result.valid,chain_sequence=chain_result.head_sequence)
    if not result.valid: return result
    if not chain_result.valid:
        return replace(result,valid=False,reason='CHAIN_INVALID',trust_level='UNVERIFIED')
    if len(records) < cp.sequence:
        return replace(result,valid=False,reason='CHECKPOINT_AHEAD_OF_CHAIN',prefix_valid=False,trust_level='UNVERIFIED')
    if records[cp.sequence-1].record_hash != cp.chain_head_hash:
        return replace(result,valid=False,reason='CHAIN_DIVERGENCE',prefix_valid=False,trust_level='UNVERIFIED')
    return replace(result,prefix_valid=True)


def verify_chain_against_checkpoint(chain, checkpoint, verifier):
    try:
        records,result,chain_id,installation_id = _snapshot(chain)
    except Exception:
        return CheckpointVerification(False,'CHAIN_INVALID',chain_valid=False)
    return _prefix(records,result,checkpoint,verifier,chain_id,installation_id)


def _authorized(actor, action, installation_id, now):
    return sc.authorize_management_change(actor,action,installation_id=installation_id,now=now).disposition == 'ALLOW'


def create_checkpoint(chain, actor, signer, verifier, *, checkpoint_id, now, algorithm, key_id,
                      previous_checkpoint=None):
    try:
        records,result,chain_id,installation_id = _snapshot(chain)
    except Exception:
        raise ValueError('CHAIN_INVALID') from None
    if not _authorized(actor,sc.ManagementAction.CHECKPOINT_CREATE,installation_id,now):
        raise ValueError('AUTHORITY_DENIED')
    if not result.valid: raise ValueError('CHAIN_INVALID')
    if not records: raise ValueError('EMPTY_CHAIN_NOT_SUPPORTED')
    previous_hash = GENESIS_CHECKPOINT_HASH
    if previous_checkpoint is not None:
        previous = _prefix(records,result,previous_checkpoint,verifier,chain_id,installation_id)
        if not previous.valid: raise ValueError('PREVIOUS_CHECKPOINT_INVALID')
        if (result.head_sequence <= previous_checkpoint.sequence or now < previous_checkpoint.created_at
                or checkpoint_id == previous_checkpoint.checkpoint_id):
            raise ValueError('CHECKPOINT_CONTINUITY_INVALID')
        previous_hash = checkpoint_hash(previous_checkpoint)
    # Temporary nonempty bytes only construct the unsigned payload, never returned.
    candidate = SignedCheckpoint(SCHEMA,checkpoint_id,_ref(chain_id),_ref(installation_id),
        result.head_sequence,result.head_hash,now,key_id,algorithm,previous_hash,b'unsigned')
    try:
        envelope = signer.sign(canonical_payload(candidate))
    except Exception:
        raise ValueError('SIGNER_FAILED') from None
    if (type(envelope) is not SignatureEnvelope or envelope.algorithm != algorithm or envelope.key_id != key_id):
        raise ValueError('SIGNATURE_ENVELOPE_INVALID')
    candidate = replace(candidate,signature=envelope.signature)
    verified = verify_checkpoint(candidate,verifier,expected_chain_id=chain_id,expected_installation_id=installation_id)
    if not verified.valid: raise ValueError(verified.reason)
    return candidate


def verify_checkpoint_sequence(checkpoints, verifier, *, expected_chain_id, expected_installation_id):
    if type(checkpoints) not in (tuple,list) or not 0 < len(checkpoints) <= MAX_CHECKPOINTS:
        return CheckpointVerification(False,'CHECKPOINT_CONTINUITY_INVALID',continuity_valid=False)
    previous = None
    seen = set()
    for cp in checkpoints:
        result = verify_checkpoint(cp,verifier,expected_chain_id=expected_chain_id,
                                   expected_installation_id=expected_installation_id)
        if not result.valid: return replace(result,continuity_valid=False)
        expected = GENESIS_CHECKPOINT_HASH if previous is None else checkpoint_hash(previous)
        if (cp.checkpoint_id in seen or cp.previous_checkpoint_hash != expected
                or (previous is not None and (cp.sequence <= previous.sequence or cp.created_at < previous.created_at))):
            return replace(result,valid=False,reason='CHECKPOINT_CONTINUITY_INVALID',
                           continuity_valid=False,trust_level='UNVERIFIED')
        previous = cp
        seen.add(cp.checkpoint_id)
    return replace(result,continuity_valid=True)


@dataclass(frozen=True, repr=False)
class ExternalAnchor:
    """Caller-attested retained evidence, NOT proof of external independence."""
    anchor_id: str
    checkpoint_hash: str
    checkpoint_sequence: int
    chain_id_ref: str
    installation_ref: str
    anchored_at: float
    location_ref: str
    receipt_ref: str = None

    def __post_init__(self):
        if (not _opaque(self.anchor_id) or not _opaque(self.location_ref)
                or (self.receipt_ref is not None and not _opaque(self.receipt_ref))
                or not _sequence(self.checkpoint_sequence) or not _time(self.anchored_at)
                or not all(_hash(v) for v in (self.checkpoint_hash,self.chain_id_ref,self.installation_ref))):
            raise ValueError('MALFORMED_ANCHOR')
        object.__setattr__(self,'anchored_at',float(self.anchored_at))


class AnchorPublisher(Protocol):
    """Host must deduplicate stable request ID, reject conflicting reuse, retain ID mapping.

    Never change request ID after uncertain publication. Return value attests
    publication only; storage independence is not established by this protocol.
    """
    def publish(self, anchor_request_id: str, checkpoint: SignedCheckpoint) -> ExternalAnchor: ...


class AnchorReader(Protocol):
    def read(self, anchor_request_id: str) -> ExternalAnchor: ...


def verify_checkpoint_against_anchor(checkpoint, external_anchor):
    """Artifact equality only; does NOT verify signature or authenticate an anchor."""
    if not _valid_checkpoint(checkpoint): return CheckpointVerification(False,'MALFORMED_CHECKPOINT')
    try:
        if type(external_anchor) is not ExternalAnchor: raise ValueError()
        a = replace(external_anchor)
    except (ValueError,TypeError,AttributeError):
        return CheckpointVerification(False,'MALFORMED_ANCHOR',anchor_valid=False)
    cp = checkpoint
    valid = (a.checkpoint_hash == checkpoint_hash(cp) and a.checkpoint_sequence == cp.sequence
             and a.chain_id_ref == cp.chain_id_ref and a.installation_ref == cp.installation_ref
             and a.anchored_at >= cp.created_at)
    return CheckpointVerification(valid,'VALID' if valid else 'ANCHOR_MISMATCH',anchor_valid=valid,
                                  checkpoint_sequence=cp.sequence)


@dataclass(frozen=True, repr=False)
class AnchorOutcome:
    valid: bool
    reason: str
    trust: str = 'UNVERIFIED'
    anchor: ExternalAnchor = None


def publish_anchor(checkpoint, verifier, actor, publisher, *, anchor_request_id, installation_id, chain_id, now):
    if not _authorized(actor,sc.ManagementAction.ANCHOR_PUBLISH,installation_id,now):
        return AnchorOutcome(False,'AUTHORITY_DENIED')
    if not _opaque(anchor_request_id): return AnchorOutcome(False,'REQUEST_INVALID')
    result = verify_checkpoint(checkpoint,verifier,expected_chain_id=chain_id,expected_installation_id=installation_id)
    if not result.valid: return AnchorOutcome(False,result.reason)
    if now < checkpoint.created_at: return AnchorOutcome(False,'TIMESTAMP_INVALID')
    try:
        anchor = publisher.publish(anchor_request_id,checkpoint)
    except Exception:
        return AnchorOutcome(False,'ANCHOR_OUTCOME_UNKNOWN')
    result = verify_checkpoint_against_anchor(checkpoint,anchor)
    if not result.valid:
        # Publication may have happened even if its returned receipt is bad.
        return AnchorOutcome(False,'ANCHOR_OUTCOME_UNKNOWN')
    return AnchorOutcome(True,'VALID','PUBLISHER_ATTESTED',anchor)


def reconcile_anchor(checkpoint, verifier, reader, *, anchor_request_id, expected_chain_id, expected_installation_id):
    if not _opaque(anchor_request_id): return AnchorOutcome(False,'REQUEST_INVALID')
    result = verify_checkpoint(checkpoint,verifier,expected_chain_id=expected_chain_id,
                               expected_installation_id=expected_installation_id)
    if not result.valid: return AnchorOutcome(False,result.reason)
    try:
        anchor = reader.read(anchor_request_id)
    except Exception:
        return AnchorOutcome(False,'ANCHOR_OUTCOME_UNKNOWN')
    if anchor is None: return AnchorOutcome(False,'NOT_FOUND')
    result = verify_checkpoint_against_anchor(checkpoint,anchor)
    if not result.valid: return AnchorOutcome(False,result.reason)
    return AnchorOutcome(True,'VALID','READBACK_VERIFIED',anchor)


def verify_security_history(chain, checkpoint=None, verifier=None, *, external_anchor=None):
    """Trust levels describe supplied evidence, never host trust or retention proof.

    external_anchor must be obtained independently by a trusted caller, not
    promoted from a local test store or publisher receipt without that evidence.
    """
    if checkpoint is None:
        try:
            _,result,_,_ = _snapshot(chain)
        except Exception:
            return CheckpointVerification(False,'CHAIN_INVALID',chain_valid=False)
        if external_anchor is not None:
            return CheckpointVerification(False,'CHECKPOINT_MISSING',chain_valid=result.valid,anchor_valid=False)
        return CheckpointVerification(result.valid,'VALID' if result.valid else 'CHAIN_INVALID',
            chain_valid=result.valid,chain_sequence=result.head_sequence,
            trust_level='CHAIN_ONLY' if result.valid else 'UNVERIFIED')
    result = verify_chain_against_checkpoint(chain,checkpoint,verifier)
    if not result.valid or external_anchor is None: return result
    anchor = verify_checkpoint_against_anchor(checkpoint,external_anchor)
    return replace(result,valid=anchor.valid,reason=anchor.reason,anchor_valid=anchor.valid,
                   trust_level='SIGNED_AND_ANCHORED' if anchor.valid else 'UNVERIFIED')
