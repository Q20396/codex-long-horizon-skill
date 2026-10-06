"""Pure comparison of trusted-caller normalized evidence for one action.

This module authenticates no source and collects no evidence. A caller must keep
source authority, coverage and material identity semantics intact before entry.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

__all__ = ('VerificationInput', 'VerificationFinding', 'CrossLayerVerifier')
_LAYERS = ('DECLARED', 'AUTHORIZED', 'ADAPTER_OBSERVED', 'HOST_OBSERVED', 'TARGET_REALITY')
_RESULTS = ('MATCH', 'MISSING', 'EXTRA', 'DIVERGED', 'UNKNOWN', 'NOT_OBSERVED')
_COVERAGE = ('SCOPED_COMPLETE', 'PARTIAL', 'UNKNOWN')
_CORRELATION = ('CORRELATED', 'UNCORRELATED', 'UNRESOLVED_LINK')
_REASONS = ('EFFECT_MATCH', 'EXPECTED_EFFECT_NOT_OBSERVED', 'UNEXPECTED_EFFECT_OBSERVED',
            'MATERIAL_EFFECT_DIFFERENCE', 'INSUFFICIENT_COVERAGE', 'UNRESOLVED_CORRELATION',
            'TARGET_REALITY_UNKNOWN', 'SEMANTICS_NOT_COMPARABLE', 'AMBIGUOUS_EFFECT_IDENTITY',
            'SOURCE_UNAVAILABLE')
# Existing CET semantic classes; PROCESS_START and PROCESS_EXEC stay distinct.
_CLASSES = frozenset(('FILE_READ', 'FILE_WRITE', 'FILE_CREATE', 'FILE_DELETE', 'FILE_MOVE',
    'PROCESS_START', 'PROCESS_EXEC', 'PROCESS_EXIT', 'NETWORK_REQUEST', 'SECRET_ACCESS',
    'PACKAGE_INSTALL', 'CONFIG_CHANGE', 'SERVICE_START', 'SERVICE_STOP', 'GIT_STAGE',
    'GIT_COMMIT', 'GIT_PUSH', 'GIT_EFFECT', 'REMOTE_EFFECT', 'PR_CREATE', 'PR_MERGE',
    'RELEASE', 'DEPLOY'))


def _require(condition):
    if not condition:
        raise ValueError('VERIFICATION_INPUT_INVALID')


def _ref(value):
    return type(value) is str and re.fullmatch(
        r'(?:ref:[A-Za-z0-9_.-]{1,128}|sha256:[0-9a-f]{64})', value) is not None


def _sequence(values, limit):
    # Accept only inert bounded containers, not iterators or arbitrary callbacks.
    _require(type(values) in (list, tuple) and len(values) <= limit)
    return tuple(values)


def _refs(values, limit=16):
    result = _sequence(values, limit)
    _require(all(_ref(ref) for ref in result))
    return tuple(sorted(set(result)))


def _effects(values):
    if values is None:
        return None  # Unavailable is distinct from a supplied empty source.
    result = []
    for raw in _sequence(values, 128):
        effect = _sequence(raw, 5)
        _require(len(effect) == 5)
        kind, material, action, evidence, correlation = effect
        _require(type(kind) is str and re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', kind) is not None)
        _require(material is None or _ref(material))
        _require(action is None or _ref(action))
        _require(type(correlation) is str and correlation in _CORRELATION)
        _require(correlation != 'CORRELATED' or action is not None)
        result.append((kind, material, action, _refs(evidence), correlation))
    return tuple(result)  # Never deduplicate: repeated identity may be ambiguous.


@dataclass(frozen=True, repr=False)
class VerificationInput:
    action_id: str
    declared_effects: tuple | None = None
    authorized_effects: tuple | None = None
    adapter_observed_effects: tuple | None = None
    host_observed_effects: tuple | None = None
    target_reality_effects: tuple | None = None
    adapter_coverage: str = 'UNKNOWN'
    host_coverage: str = 'UNKNOWN'
    target_reality_status: str = 'UNKNOWN'
    host_gap: bool = False

    def __post_init__(self):
        _require(_ref(self.action_id))
        _require(all(type(value) is str and value in _COVERAGE
                     for value in (self.adapter_coverage, self.host_coverage)))
        _require(type(self.target_reality_status) is str
                 and self.target_reality_status in ('VERIFIED', 'UNKNOWN'))
        _require(type(self.host_gap) is bool)
        for name in ('declared_effects', 'authorized_effects', 'adapter_observed_effects',
                     'host_observed_effects', 'target_reality_effects'):
            object.__setattr__(self, name, _effects(getattr(self, name)))


@dataclass(frozen=True)
class VerificationFinding:
    action_id: str
    layer_a: str
    layer_b: str
    result: str
    effect_class: str | None
    effect_ref: str | None
    reason: str
    evidence_refs: tuple
    coverage_status: str
    compared_effect_ref: str | None = None

    def __post_init__(self):
        _require(_ref(self.action_id))
        _require((self.layer_a, self.layer_b) in tuple(zip(_LAYERS, _LAYERS[1:])))
        _require(type(self.result) is str and self.result in _RESULTS)
        _require(type(self.reason) is str and self.reason in _REASONS)
        _require(type(self.coverage_status) is str and self.coverage_status in _COVERAGE)
        _require(self.effect_class is None or (type(self.effect_class) is str
                 and re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', self.effect_class) is not None))
        _require(all(value is None or _ref(value) for value in
                     (self.effect_ref, self.compared_effect_ref)))
        object.__setattr__(self, 'evidence_refs', _refs(self.evidence_refs, 32))


def _finding(value, a, b, result, reason, coverage, left=None, right=None):
    effect = left if left is not None else right
    evidence = tuple(sorted(set((left[3] if left else ()) + (right[3] if right else ()))))
    return VerificationFinding(value.action_id, a, b, result, effect[0] if effect else None,
        effect[1] if effect else None, reason, evidence, coverage, right[1] if left and right else None)


def _scoped(effects, action):
    return tuple(e for e in effects if e[2] == action and e[4] == 'CORRELATED')


def _compare(value, a, b, source_a, source_b, coverage_a, coverage_b):
    if b == 'TARGET_REALITY' and value.target_reality_status != 'VERIFIED':
        return (_finding(value, a, b, 'UNKNOWN', 'TARGET_REALITY_UNKNOWN', 'UNKNOWN'),)
    if source_a is None or source_b is None:
        return (_finding(value, a, b, 'UNKNOWN', 'SOURCE_UNAVAILABLE', 'UNKNOWN'),)
    left, right = _scoped(source_a, value.action_id), _scoped(source_b, value.action_id)
    if not left and not right and any(e[4] == 'UNRESOLVED_LINK' for e in source_a + source_b):
        return (_finding(value, a, b, 'UNKNOWN', 'UNRESOLVED_CORRELATION', 'UNKNOWN'),)
    unresolved_b = any(e[4] != 'CORRELATED' and (e[2] is None or e[2] == value.action_id
                         or e[4] == 'UNRESOLVED_LINK') for e in source_b)
    unresolved_a = any(e[4] != 'CORRELATED' and (e[2] is None or e[2] == value.action_id
                         or e[4] == 'UNRESOLVED_LINK') for e in source_a)
    findings = []
    for kind in sorted({e[0] for e in left + right}):
        aa, bb = tuple(e for e in left if e[0] == kind), tuple(e for e in right if e[0] == kind)
        if kind not in _CLASSES:
            findings.extend(_finding(value, a, b, 'UNKNOWN', 'SEMANTICS_NOT_COMPARABLE', coverage_b,
                                     left=e) for e in aa + bb)
            continue
        # A missing identity or repeated material identity can hide an alternative
        # candidate even beside an exact match; do not guess within that class.
        if any(e[1] is None for e in aa + bb) or any(
                len({e[1] for e in group}) != len(group) for group in (aa, bb)):
            findings.extend(_finding(value, a, b, 'UNKNOWN', 'AMBIGUOUS_EFFECT_IDENTITY', coverage_b,
                                     left=e) for e in aa + bb)
            continue
        ma, mb = {e[1]: e for e in aa}, {e[1]: e for e in bb}
        for ref in sorted(ma.keys() & mb.keys()):
            findings.append(_finding(value, a, b, 'MATCH', 'EFFECT_MATCH', coverage_b, ma[ref], mb[ref]))
        aa = tuple(ma[ref] for ref in sorted(ma.keys() - mb.keys()))
        bb = tuple(mb[ref] for ref in sorted(mb.keys() - ma.keys()))
        if aa and bb:
            if (len(aa) == len(bb) == 1 and coverage_a == coverage_b == 'SCOPED_COMPLETE'
                    and not (unresolved_a or unresolved_b)):
                findings.append(_finding(value, a, b, 'DIVERGED', 'MATERIAL_EFFECT_DIFFERENCE',
                                         coverage_b, aa[0], bb[0]))
            else:
                findings.extend(_finding(value, a, b, 'UNKNOWN', 'AMBIGUOUS_EFFECT_IDENTITY', coverage_b,
                                         left=e) for e in aa + bb)
        else:
            for effect in aa:
                if unresolved_b:
                    result, reason = 'UNKNOWN', 'UNRESOLVED_CORRELATION'
                elif coverage_b == 'SCOPED_COMPLETE':
                    result, reason = 'MISSING', 'EXPECTED_EFFECT_NOT_OBSERVED'
                else:
                    result = 'NOT_OBSERVED' if coverage_b == 'PARTIAL' else 'UNKNOWN'
                    reason = 'INSUFFICIENT_COVERAGE'
                findings.append(_finding(value, a, b, result, reason, coverage_b, left=effect))
            for effect in bb:
                if unresolved_a:
                    result, reason = 'UNKNOWN', 'UNRESOLVED_CORRELATION'
                elif coverage_a == 'SCOPED_COMPLETE':
                    result, reason = 'EXTRA', 'UNEXPECTED_EFFECT_OBSERVED'
                else:
                    result, reason = 'UNKNOWN', 'INSUFFICIENT_COVERAGE'
                findings.append(_finding(value, a, b, result, reason, coverage_a, right=effect))
    return tuple(sorted(set(findings), key=lambda f: (
        f.effect_class or '', f.effect_ref or '', f.result, f.compared_effect_ref or '', f.evidence_refs)))


class CrossLayerVerifier:
    """Four fixed directional comparisons; no pair selection or authority API."""

    @staticmethod
    def verify(value: VerificationInput) -> tuple[VerificationFinding, ...]:
        _require(type(value) is VerificationInput)
        host_coverage = 'UNKNOWN' if value.host_gap else value.host_coverage
        return (
            _compare(value, 'DECLARED', 'AUTHORIZED', value.declared_effects,
                     value.authorized_effects, 'SCOPED_COMPLETE', 'SCOPED_COMPLETE')
            + _compare(value, 'AUTHORIZED', 'ADAPTER_OBSERVED', value.authorized_effects,
                       value.adapter_observed_effects, 'SCOPED_COMPLETE', value.adapter_coverage)
            + _compare(value, 'ADAPTER_OBSERVED', 'HOST_OBSERVED', value.adapter_observed_effects,
                       value.host_observed_effects, value.adapter_coverage, host_coverage)
            + _compare(value, 'HOST_OBSERVED', 'TARGET_REALITY', value.host_observed_effects,
                       value.target_reality_effects, host_coverage, 'UNKNOWN'))
