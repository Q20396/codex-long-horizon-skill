"""Explicit, provider-independent proposal bridge; inactive on import.

Host code supplies identity, immutable preauthorization commitments and existing
bindings. This is a same-process lifecycle guard, not a Python or OS sandbox.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace
from enum import Enum
import hashlib
import json
import math
from threading import RLock
from types import MappingProxyType
import uuid

import runtime_binding as local
import remote_runtime_binding as remote
import runtime_safety_envelope as rse
import critical_execution_trace as cet
import security_authority_chain as sc

_CAPABILITIES = MappingProxyType({a: rse.CAPABILITIES[a] for a in local.BOUND_ACTIONS | remote.BOUND_ACTIONS})
_MAX_PENDING = 1024


def _require(ok, reason='MALFORMED_PROPOSAL'):
    if not ok:
        raise ValueError(reason)


def _freeze(value, budget=None, depth=0):
    """Copy only bounded primitive data; never retain caller containers."""
    budget = [4096, 10 * 1024 * 1024] if budget is None else budget
    budget[0] -= 1
    _require(budget[0] >= 0 and depth <= 16)
    if value is None or type(value) is bool:
        return value
    if type(value) in (str, bytes):
        size = len(value.encode('utf-8')) if type(value) is str else len(value)
        budget[1] -= size
        _require(budget[1] >= 0)
        return value
    if type(value) in (int, float):
        _require(math.isfinite(value) and abs(value) <= 2**53)
        return value
    if type(value) in (dict, MappingProxyType):
        _require(len(value) <= 256 and all(type(k) is str and len(k) <= 128 for k in value))
        return MappingProxyType({k: _freeze(value[k], budget, depth + 1) for k in sorted(value)})
    if type(value) in (tuple, list, set, frozenset):
        _require(len(value) <= 256)
        items = tuple(_freeze(v, budget, depth + 1) for v in value)
        return tuple(sorted(items, key=lambda v: json.dumps(_canonical(v), sort_keys=True))) if type(value) in (set, frozenset) else items
    raise ValueError('MALFORMED_PROPOSAL')


def _canonical(value):
    if isinstance(value, Enum):
        return value.value
    if type(value) is bytes:
        return {'bytes_sha256': hashlib.sha256(value).hexdigest(), 'size': len(value)}
    if is_dataclass(value):
        return {f.name: _canonical(getattr(value, f.name)) for f in fields(value)}
    if type(value) in (dict, MappingProxyType):
        return {k: _canonical(v) for k, v in value.items()}
    if type(value) is tuple:
        return [_canonical(v) for v in value]
    return value


def _digest(value):
    return hashlib.sha256(json.dumps(_canonical(value), sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True, repr=False)
class AgentActionProposal:
    proposal_id: str
    requested_action_class: str
    requested_target: str
    requested_parameters: object = None
    declared_effects: object = None
    reason_text: str = ''
    untrusted_agent_ref: str | None = None
    untrusted_provider_ref: str | None = None
    untrusted_model_ref: str | None = None
    correlation_ref: str | None = None
    action_id: str | None = None  # untrusted correlation only

    def __post_init__(self):
        _require(all(type(getattr(self, n)) is str and 0 < len(getattr(self, n).encode()) <= 4096
            for n in ('proposal_id', 'requested_action_class', 'requested_target')))
        _require(type(self.reason_text) is str and len(self.reason_text.encode()) <= 8192)
        _require(all(getattr(self, n) is None or (type(getattr(self, n)) is str and len(getattr(self, n).encode()) <= 1024)
            for n in ('untrusted_agent_ref', 'untrusted_provider_ref', 'untrusted_model_ref', 'correlation_ref', 'action_id')))
        params = {} if self.requested_parameters is None else self.requested_parameters
        _require(type(params) in (dict, MappingProxyType))
        object.__setattr__(self, 'requested_parameters', _freeze(params))
        _require(self.declared_effects is None or type(self.declared_effects) in (dict, MappingProxyType))
        object.__setattr__(self, 'declared_effects', _freeze(self.declared_effects))


@dataclass(frozen=True, repr=False)
class PreparedAgentAction:
    proposal_digest: str
    proposal_ref: str
    trusted_agent_id: str
    context: cet.TraceContext
    action_request: rse.ActionRequest
    payload_kind: str
    normalized_payload: local.RuntimePayload | remote.RemoteRuntimePayload
    payload_digest: str
    material_effect_identity: str
    trusted_capability_name: str
    declared_effects: cet.DeclaredEffects | None
    declaration_status: str
    prepared_at: float
    expires_at: float | None
    prepared_digest: str = ''


@dataclass(frozen=True, repr=False)
class AgentRuntimePrepareResult:
    status: str
    prepared: PreparedAgentAction | None = None


@dataclass(frozen=True, repr=False)
class AgentRuntimeExecutionResult:
    status: str
    receipt: rse.SecurityReceipt
    runtime_result: object = None
    events: tuple = ()
    causal_refs: tuple = ()
    token_usage_status: str = 'UNKNOWN'


def _prepared_digest(p):
    return _digest({f.name: getattr(p, f.name) for f in fields(p) if f.name != 'prepared_digest'})


def _material(action, payload):
    """Effect semantics exclude attribution, action IDs and execution limits."""
    kind = action.action_class
    common = (kind, action.target, action.destination)
    names = {
        rse.ActionClass.READ_FILE: (), rse.ActionClass.DELETE_FILE: (), rse.ActionClass.MOVE_FILE: (),
        rse.ActionClass.CREATE_FILE: ('content_bytes',), rse.ActionClass.WRITE_FILE: ('content_bytes',),
        rse.ActionClass.EXECUTE_PROCESS: ('argv', 'cwd', 'environment'),
        rse.ActionClass.GIT_STAGE: ('git_paths',),
        rse.ActionClass.GIT_COMMIT: ('expected_git_tree', 'expected_git_parent', 'commit_message'),
        rse.ActionClass.NETWORK_REQUEST: ('method', 'query', 'headers', 'body', 'request_identity'),
        rse.ActionClass.GIT_PUSH: ('repository', 'remote_ref', 'expected_remote_oid', 'expected_local_oid'),
        rse.ActionClass.PR_CREATE: ('provider', 'repository', 'head', 'base', 'title', 'body', 'draft', 'request_identity'),
    }[kind]
    return _digest((common, tuple((n, getattr(payload, n)) for n in names)))


def _mutation(p):
    return p.action_request.action_class != rse.ActionClass.READ_FILE and not (
        p.action_request.action_class == rse.ActionClass.NETWORK_REQUEST and p.normalized_payload.method in ('GET', 'HEAD'))


class AgentRuntimeBridge:
    """Small bounded reservations; no new authority, adapter or durable ledger.

    Host must retain expected_prepared_digest AND expected_payload_digest before
    authorizing, and pass those saved values, never derive them from execute input.
    The bridge pins binding lifecycle components on first execution per kind.
    """
    def __init__(self):
        self._lock = RLock()
        self._pending = {}
        self._lifecycles = {}

    def prepare(self, proposal, *, context, trusted_agent_id, authorization_ref,
                data_classification, now, expires_at=None):
        try:
            if type(proposal) is dict:
                _require(set(proposal) <= {f.name for f in fields(AgentActionProposal)})
                proposal = AgentActionProposal(**proposal)
            _require(type(proposal) is AgentActionProposal)
            # Revalidate even a forcibly modified frozen instance.
            proposal = AgentActionProposal(**{f.name: getattr(proposal, f.name) for f in fields(proposal)})
            try:
                kind = rse.ActionClass(proposal.requested_action_class)
            except ValueError:
                return AgentRuntimePrepareResult('NOT_SUPPORTED')
            if kind not in _CAPABILITIES:
                return AgentRuntimePrepareResult('NOT_SUPPORTED')
            _require(type(context) is cet.TraceContext and cet._text(trusted_agent_id) and rse._time(now))
            context = cet.TraceContext(**{f.name: getattr(context, f.name) for f in fields(context)})
            _require(expires_at is None or (rse._time(expires_at) and expires_at > now))
            params = dict(proposal.requested_parameters)
            _require(not {'action_id', 'action_class', 'target'} & params.keys())
            destination = params.pop('destination', None)
            _require((kind == rse.ActionClass.MOVE_FILE) == (destination is not None))
            if kind in local.BOUND_ACTIONS:
                target = rse._path(proposal.requested_target)
                if destination is not None:
                    destination = rse._path(destination)
                if type(params.get('environment')) is MappingProxyType:
                    params['environment'] = tuple(sorted(params['environment'].items()))
                if params.get('cwd') is not None:
                    params['cwd'] = rse._path(params['cwd'])
                payload = local.RuntimePayload(context.action_id, **params)
                _require(kind != rse.ActionClass.EXECUTE_PROCESS or payload.cwd is not None)
                if payload.environment is not None:
                    payload = replace(payload, environment=tuple(sorted(payload.environment)) or None)
                if payload.git_paths is not None:
                    payload = replace(payload, git_paths=tuple(sorted(payload.git_paths)))
                payload_kind = 'LOCAL'
            else:
                payload = remote.RemoteRuntimePayload(context.action_id, kind, proposal.requested_target, **params)
                payload = replace(payload, query=remote._url(remote._endpoint(payload.target, payload.query))[2])
                if kind == rse.ActionClass.GIT_PUSH:
                    payload = replace(payload, repository=rse._path(payload.repository))
                target = payload.target
                payload_kind = 'REMOTE'
            proposal_digest = _digest(proposal)
            action = rse.ActionRequest(context.action_id, context.run_id, context.task_id, kind, target,
                context.provider, context.runtime, data_classification, authorization_ref, _CAPABILITIES[kind],
                'agent-proposal:' + proposal_digest, getattr(payload, 'request_identity', None), destination)
            _require(rse._valid_action(action))
            payload.validate_for(action)
            declared = None
            declaration_status = 'UNKNOWN'
            if proposal.declared_effects:
                declared = cet.DeclaredEffects(context, **dict(proposal.declared_effects))
                if cet.effect_count(declared):
                    requested = cet.declared_from_action(action, context)
                    comparison = cet.compare_effects(declared, cet.ObservedEffects(context,
                        **{n: getattr(requested, n) for n in cet._CATEGORIES}))
                    declaration_status = 'DECLARATION_ACTION_MISMATCH' if comparison.divergences else 'DECLARED'
                else:
                    declared = None
            p = PreparedAgentAction(proposal_digest, rse._ref(proposal.proposal_id), trusted_agent_id, context,
                action, payload_kind, payload, payload.digest(), _material(action, payload), _CAPABILITIES[kind],
                declared, declaration_status, now, expires_at)
            return AgentRuntimePrepareResult('PREPARED', replace(p, prepared_digest=_prepared_digest(p)))
        except (ValueError, TypeError, AttributeError, OverflowError, RecursionError):
            return AgentRuntimePrepareResult('MALFORMED_PROPOSAL')

    def _validate(self, p, binding, expected_payload_digest, expected_prepared_digest, context, now, *, reconciliation=False):
        _require(type(p) is PreparedAgentAction, 'INVALID_PREPARED_ACTION')
        a = p.action_request
        _require(type(a) is rse.ActionRequest, 'INVALID_PREPARED_ACTION')
        _require(p.trusted_capability_name == a.capability,
            'CAPABILITY_ACTION_MISMATCH')
        payload_type = local.RuntimePayload if a.action_class in local.BOUND_ACTIONS else remote.RemoteRuntimePayload
        _require(type(p.normalized_payload) is payload_type, 'INVALID_PREPARED_ACTION')
        _require(p.normalized_payload.digest() == p.payload_digest == expected_payload_digest,
            'PREPARED_PAYLOAD_MISMATCH')
        _require(p.prepared_digest == expected_prepared_digest == _prepared_digest(p), 'INVALID_PREPARED_ACTION')
        _require(_CAPABILITIES.get(a.action_class) == a.capability, 'CAPABILITY_ACTION_MISMATCH')
        _require(context == p.context and type(context) is cet.TraceContext and rse._time(now)
            and now >= p.prepared_at, 'INVALID_PREPARED_ACTION')
        # Expiry limits new execution, not observation of an unresolved effect.
        # Reconciliation still evaluates current policy/authorization below.
        _require(reconciliation or p.expires_at is None or now < p.expires_at, 'INVALID_PREPARED_ACTION')
        cet._match_action(a, context)
        p.normalized_payload.validate_for(a)
        _require(p.material_effect_identity == _material(a, p.normalized_payload), 'INVALID_PREPARED_ACTION')
        expected_binding = local.RuntimeBinding if payload_type is local.RuntimePayload else remote.RemoteRuntimeBinding
        _require(type(binding) is expected_binding and p.payload_kind == ('LOCAL' if payload_type is local.RuntimePayload else 'REMOTE'),
            'INVALID_RUNTIME_BINDING')
        _require(binding.approved_payload_digests.get(a.action_id) == expected_payload_digest, 'PREPARED_PAYLOAD_MISMATCH')
        with self._lock:
            lifecycle = (binding.journal, binding.chain, binding.broker, binding.actor)
            previous = self._lifecycles.get(p.payload_kind)
            _require(previous is None or all(x is y for x, y in zip(previous, lifecycle)), 'BINDING_LIFECYCLE_MISMATCH')
            self._lifecycles[p.payload_kind] = lifecycle

    def _refs(self, p):
        return (p.proposal_digest, p.prepared_digest, p.material_effect_identity,
            _digest(('agent', p.trusted_agent_id)), _digest(('context', p.context)))

    def _denied(self, p, reason):
        action = p.action_request if type(p) is PreparedAgentAction else None
        receipt = rse._receipt(action, rse.PolicyDecision('DENY', reason))
        return AgentRuntimeExecutionResult(reason, receipt)

    def _uncertain(self, p, binding):
        # Match binding failure-closed semantics in the existing RSE journal so
        # a post-effect causal-evidence failure can still use binding reconcile.
        try:
            rse._append(binding.journal, binding._bound(p.action_request, p.normalized_payload),
                rse.JournalState.RECONCILIATION_REQUIRED)
        except Exception:
            pass  # Keep the bridge reservation even if the authoritative journal failed.
        receipt = rse._receipt(p.action_request, rse.PolicyDecision('REQUIRE_RECONCILIATION', 'SECURITY_BOUNDARY_FAILURE'),
            execution='UNKNOWN_OUTCOME', reconciliation='RECONCILIATION_REQUIRED', final='REQUIRE_RECONCILIATION')
        return AgentRuntimeExecutionResult('RECONCILIATION_REQUIRED', receipt, causal_refs=self._refs(p))

    def _result(self, p, binding, runtime, context, now, *, reconciliation=False):
        receipt = runtime if type(runtime) is rse.SecurityReceipt else runtime.receipt
        refs = self._refs(p)
        receipt = replace(receipt, evidence_refs=receipt.evidence_refs + refs)
        events = list(getattr(runtime, 'events', ()))
        additions = []
        if not reconciliation and p.declared_effects is not None:
            kinds = ('FILE_READ', 'FILE_WRITE', 'FILE_CREATE', 'FILE_DELETE', 'FILE_MOVE',
                'PROCESS_START', 'NETWORK_REQUEST', 'SECRET_ACCESS', None, None)
            for category, kind in zip(cet._CATEGORIES, kinds):
                for value in getattr(p.declared_effects, category):
                    destination = None
                    if category == 'moves':
                        target, destination = value
                    elif kind is None:
                        event_kind, target = value
                    else:
                        target = value
                    additions.append(cet.CriticalEvent(uuid.uuid4().hex,
                        cet.CriticalEventType(kind or event_kind), context, cet.ObservationSource.DECLARED,
                        now, target, p.action_request.data_classification, evidence_refs=refs, destination=destination))
        if reconciliation and (getattr(runtime, 'evidence', None) is not None or
                receipt.final_disposition in ('RECONCILED_SUCCESS', 'RECONCILED_NOT_APPLIED')):
            additions.append(cet.CriticalEvent(uuid.uuid4().hex, cet.CriticalEventType.CAPABILITY_USE, context,
                cet.ObservationSource.RECONCILIATION_OBSERVED, now, 'sha256:' + p.material_effect_identity,
                p.action_request.data_classification, capability=p.trusted_capability_name, evidence_refs=refs))
        sc.record_receipt(binding.chain, binding.actor, receipt, event_id=uuid.uuid4().hex, now=now,
            project_id=context.project_id, task_id=context.task_id)
        for event in additions:
            cet.record_critical_event(binding.chain, binding.actor, event, now=now)
        events.extend(additions)
        return AgentRuntimeExecutionResult(receipt.final_disposition, receipt, runtime, tuple(events), refs)

    def execute(self, prepared, *, binding, expected_payload_digest, expected_prepared_digest,
                policy_stack, authorization, context, now):
        p = prepared
        try:
            self._validate(p, binding, expected_payload_digest, expected_prepared_digest, context, now)
        except Exception as error:
            reason = str(error) if type(error) is ValueError and str(error) in (
                'INVALID_PREPARED_ACTION', 'CAPABILITY_ACTION_MISMATCH', 'PREPARED_PAYLOAD_MISMATCH',
                'INVALID_RUNTIME_BINDING', 'BINDING_LIFECYCLE_MISMATCH') else 'INVALID_PREPARED_ACTION'
            return self._denied(p, reason)
        key = p.material_effect_identity
        with self._lock:
            if _mutation(p):
                if key in self._pending:
                    return self._denied(p, 'RECONCILIATION_REQUIRED')
                if len(self._pending) >= _MAX_PENDING:
                    return self._denied(p, 'RESERVATION_LIMIT')
                self._pending[key] = (p.prepared_digest, binding, 'EXECUTING')
        try:
            runtime = binding.execute(p.action_request, p.normalized_payload, policy_stack=policy_stack,
                authorization=authorization, context=context, now=now)
            out = self._result(p, binding, runtime, context, now)
        except BaseException as error:
            # Keep EXECUTING until the authoritative uncertainty update finishes:
            # reconciliation must not clear a reservation before a late append.
            try:
                out = self._uncertain(p, binding)
            finally:
                with self._lock:
                    if _mutation(p):
                        self._pending[key] = (p.prepared_digest, binding, 'UNKNOWN')
            if not isinstance(error, Exception):
                raise
            return out
        with self._lock:
            if _mutation(p):
                if out.receipt.execution_state == 'UNKNOWN_OUTCOME' or out.receipt.reconciliation_state == 'RECONCILIATION_REQUIRED':
                    self._pending[key] = (p.prepared_digest, binding, 'UNKNOWN')
                else:
                    self._pending.pop(key, None)
        return out

    def reconcile(self, prepared, *, binding, expected_payload_digest, expected_prepared_digest,
                  policy_stack, authorization, context, now):
        p = prepared
        out = None
        acquired = False
        try:
            self._validate(p, binding, expected_payload_digest, expected_prepared_digest, context, now, reconciliation=True)
            key = p.material_effect_identity
            with self._lock:
                reservation = self._pending.get(key)
                _require(not _mutation(p) or reservation == (p.prepared_digest, binding, 'UNKNOWN'), 'RECONCILIATION_REQUIRED')
                if _mutation(p):
                    self._pending[key] = (p.prepared_digest, binding, 'RECONCILING')
                    acquired = True
            # Phase 2A reconcile predates context/authorization parameters. Apply
            # existing validators before delegating its read-only inspection.
            decision = rse.evaluate_policy(p.action_request, policy_stack, authorization, now)
            if decision.disposition != 'ALLOW':
                runtime = rse._receipt(p.action_request, decision)
            else:
                _require(binding.chain._installation_id == context.installation_id and binding.chain.verify().valid
                    and sc.authorize_management_change(binding.actor, sc.ManagementAction.RSE_RECEIPT_RECORD,
                        installation_id=context.installation_id, project_id=context.project_id,
                        task_id=context.task_id, now=now).disposition == 'ALLOW', 'SECURITY_BOUNDARY_FAILURE')
                if p.payload_kind == 'LOCAL':
                    runtime = binding.reconcile(p.action_request, p.normalized_payload)
                else:
                    runtime = binding.reconcile(p.action_request, p.normalized_payload, policy_stack=policy_stack,
                        authorization=authorization, context=context, now=now)
            out = self._result(p, binding, runtime, context, now, reconciliation=True)
        except Exception:
            out = self._uncertain(p, binding) if acquired else self._denied(p, 'RECONCILIATION_REQUIRED')
        finally:
            if acquired:
                with self._lock:
                    reservation = self._pending.get(p.material_effect_identity)
                    if reservation == (p.prepared_digest, binding, 'RECONCILING'):
                        if out is not None and out.receipt.final_disposition in ('RECONCILED_SUCCESS', 'RECONCILED_NOT_APPLIED'):
                            self._pending.pop(p.material_effect_identity, None)
                        else:
                            self._pending[p.material_effect_identity] = (p.prepared_digest, binding, 'UNKNOWN')
        return out
