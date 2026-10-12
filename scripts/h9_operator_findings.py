"""Repository-only inert presentation; caller supplies the existing core module.

No CLI, collection, persistence or authority. Normal Python module loading is
not an isolation boundary. Use only safe, synthetic opaque references.
"""
import json

from cross_layer_verification import VerificationFinding

__all__ = ('render_findings',)
_FIELDS = ('action_id', 'layer_a', 'layer_b', 'result', 'effect_class',
           'effect_ref', 'reason', 'evidence_refs', 'coverage_status',
           'compared_effect_ref')
_OPTIONAL = ('effect_class', 'effect_ref', 'compared_effect_ref')
_HEADER = '''READ_ONLY_PRESENTATION
SOURCE_TRUST_NOT_ESTABLISHED
NOT_EXECUTION_OR_RETRY_AUTHORITY
MATCH is scoped agreement, not all-effects proof.
MISSING is expected evidence absent under the verifier's scoped coverage.
EXTRA is unexpected evidence under the verifier's scoped coverage.
DIVERGED is the verifier's unique material difference, not intent or causality.
UNKNOWN is missing or ambiguous evidence, not success.
NOT_OBSERVED is partial observation, not proof of no effect.
SCOPED_COMPLETE is scoped supplied coverage, not universal completeness.
PARTIAL and UNKNOWN coverage retain their original limits.
References are supplied opaque identifiers, not authenticated sources or freshness.
'''


def _reject():
    raise ValueError('H9_PRESENTATION_INPUT_INVALID') from None


def _row(finding):
    if type(finding) is not VerificationFinding:
        _reject()
    try:
        row = {name: object.__getattribute__(finding, name) for name in _FIELDS}
    except AttributeError:
        _reject()
    # Check exact primitive types BEFORE calling the existing core validator;
    # it must never compare, iterate, stringify or sort caller-defined objects.
    for name, value in row.items():
        if name == 'evidence_refs':
            if type(value) is not tuple or len(value) > 32:
                _reject()
            if any(type(ref) is not str or len(ref) > 132 for ref in value):
                _reject()
        elif value is None and name in _OPTIONAL:
            continue
        elif type(value) is not str or len(value) > 132:
            _reject()
    try:
        checked = VerificationFinding(**row)
    except (ValueError, TypeError):
        _reject()
    # Existing findings have canonical refs. Reject tampered/noncanonical values
    # rather than silently sorting/deduplicating or losing caller information.
    if checked.evidence_refs != row['evidence_refs']:
        _reject()
    return row


def render_findings(findings) -> str:
    """Return all ten fields in escaped JSON text rows, or one fixed error.

    One action; at most1024 rows and1MiB UTF-8. No partial output is returned.
    Input order and repeated findings are retained. No inference is added.
    """
    if (type(findings) is not list and type(findings) is not tuple) or len(findings) > 1024:
        _reject()
    parts = [_HEADER]
    size = len(_HEADER.encode('utf-8'))
    action = None
    for finding in findings:
        row = _row(finding)
        if action is not None and row['action_id'] != action:
            _reject()
        action = row['action_id']
        line = 'FINDING ' + json.dumps(row, ensure_ascii=True, separators=(',', ':')) + '\n'
        size += len(line.encode('utf-8'))
        if size > 1024 * 1024:
            _reject()
        parts.append(line)
    if not findings:
        parts.append('NO_FINDINGS_SUPPLIED\n')
    return ''.join(parts)
