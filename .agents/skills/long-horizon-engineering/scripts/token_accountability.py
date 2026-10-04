"""Experimental caller-invoked accounting. No collection, billing or enforcement.

Hosts supply complete scoped histories, current authority/budget snapshots and
trusted completion/progress facts. Digests anchor artifacts, not their truth.
No import-time I/O. No provider-specific metric arithmetic or implicit prices.
"""
from dataclasses import dataclass
from enum import Enum
import math
import re
import hashlib
import security_authority_chain as sc

MAX_NUMBER = 2**53
METRICS = ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_tokens', 'total_tokens')


def _require(condition):
    if not condition:
        raise ValueError('TOKEN_ACCOUNTABILITY_INVALID')


def _integer(value):
    return type(value) is int and 0 <= value <= MAX_NUMBER


def _time(value):
    return type(value) in (int, float) and 0 <= value <= MAX_NUMBER and math.isfinite(value)


def _text(value):
    return (type(value) is str and 0 < len(value) <= 256 and value.strip() == value
            and all(32 <= ord(c) != 127 and not 0xD800 <= ord(c) <= 0xDFFF for c in value))


def _ids(obj, required, optional=()):
    _require(all(_text(getattr(obj, k)) for k in required))
    _require(all(getattr(obj, k) is None or _text(getattr(obj, k)) for k in optional))


class UsagePurpose(str, Enum):
    PLANNING = 'PLANNING'
    IMPLEMENTATION = 'IMPLEMENTATION'
    DEBUGGING = 'DEBUGGING'
    TEST_ANALYSIS = 'TEST_ANALYSIS'
    REVIEW = 'REVIEW'
    RECOVERY = 'RECOVERY'
    RECONCILIATION = 'RECONCILIATION'
    RESEARCH = 'RESEARCH'
    OTHER = 'OTHER'


class MetricSource(str, Enum):
    PROVIDER_REPORTED = 'PROVIDER_REPORTED'
    RUNTIME_REPORTED = 'RUNTIME_REPORTED'
    UNKNOWN = 'UNKNOWN'


class CostSource(str, Enum):
    PROVIDER_REPORTED = 'PROVIDER_REPORTED'
    EXPLICIT_RATE_DERIVED = 'EXPLICIT_RATE_DERIVED'
    UNKNOWN = 'UNKNOWN'


@dataclass(frozen=True, repr=False)
class TokenUsageRecord:
    usage_id: str
    installation_id: str
    call_id: str
    provider: str
    model: str
    purpose: UsagePurpose
    started_at: float
    finished_at: float
    project_id: str = None
    task_id: str = None
    run_id: str = None
    agent_id: str = None
    parent_call_id: str = None
    retry_group_id: str = None
    attempt_index: int = None
    input_tokens: int = None
    cached_input_tokens: int = None
    output_tokens: int = None
    reasoning_tokens: int = None
    total_tokens: int = None
    metric_source: MetricSource = MetricSource.UNKNOWN
    cost_micros: int = None
    currency: str = None
    cost_source: CostSource = CostSource.UNKNOWN
    pricing_snapshot_ref: str = None

    def __post_init__(self):
        _ids(self, ('usage_id', 'installation_id', 'call_id', 'provider', 'model'),
             ('project_id','task_id','run_id','agent_id','parent_call_id','retry_group_id','pricing_snapshot_ref'))
        _require(type(self.purpose) is UsagePurpose and type(self.metric_source) is MetricSource
                 and type(self.cost_source) is CostSource)
        _require(_time(self.started_at) and _time(self.finished_at) and self.started_at <= self.finished_at)
        _require(all(getattr(self, k) is None or _integer(getattr(self, k)) for k in METRICS))
        _require(self.metric_source != MetricSource.UNKNOWN or all(getattr(self,k) is None for k in METRICS))
        _require(self.parent_call_id != self.call_id)
        _require((self.retry_group_id is None) == (self.attempt_index is None))
        _require(self.attempt_index is None or (_integer(self.attempt_index) and self.attempt_index >= 1))
        _require(self.cost_micros is None or _integer(self.cost_micros))
        _require(self.currency is None or (type(self.currency) is str and re.fullmatch('[A-Z]{3}', self.currency)))
        _require((self.cost_source == CostSource.UNKNOWN) == (self.cost_micros is None))
        _require(self.cost_micros is None or self.currency is not None)
        _require(self.cost_source != CostSource.EXPLICIT_RATE_DERIVED or self.pricing_snapshot_ref is not None)

    @property
    def cost_claim(self):
        return {CostSource.UNKNOWN:'UNKNOWN', CostSource.PROVIDER_REPORTED:'REPORTED',
                CostSource.EXPLICIT_RATE_DERIVED:'ESTIMATED'}[self.cost_source]


class TokenBudgetLevel(str, Enum):
    INSTALLATION = 'INSTALLATION'
    PROJECT = 'PROJECT'
    TASK = 'TASK'
    RUN = 'RUN'


@dataclass(frozen=True, repr=False)
class TokenBudget:
    budget_id: str
    level: TokenBudgetLevel
    installation_id: str
    issued_at: float
    project_id: str = None
    task_id: str = None
    run_id: str = None
    max_total_tokens: int = None
    max_cost_micros: int = None
    currency: str = None
    warning_threshold_bps: int = 8000
    expires_at: float = None
    supersedes_budget_id: str = None

    def __post_init__(self):
        _ids(self, ('budget_id','installation_id'), ('project_id','task_id','run_id','supersedes_budget_id'))
        _require(type(self.level) is TokenBudgetLevel)
        depth = list(TokenBudgetLevel).index(self.level)
        _require(tuple(x is not None for x in (self.project_id,self.task_id,self.run_id)) == tuple(n < depth for n in range(3)))
        _require(all(x is None or _integer(x) for x in (self.max_total_tokens,self.max_cost_micros)))
        _require(self.currency is None or (type(self.currency) is str and re.fullmatch('[A-Z]{3}',self.currency)))
        _require(self.max_cost_micros is None or self.currency is not None)
        _require(_integer(self.warning_threshold_bps) and 1 <= self.warning_threshold_bps <= 10000)
        _require(_time(self.issued_at) and (self.expires_at is None or (_time(self.expires_at) and self.expires_at > self.issued_at)))
        _require(self.supersedes_budget_id != self.budget_id)


@dataclass(frozen=True)
class BudgetDecision:
    state: str
    budget_digests: tuple
    usage_digest: str


@dataclass(frozen=True)
class ProgressSnapshot:
    required_remaining_before: int
    required_remaining_after: int
    acceptance_criteria_closed: int
    verification_evidence_added: int
    blockers_resolved: int

    def __post_init__(self):
        _require(all(_integer(x) for x in vars(self).values()))


@dataclass(frozen=True, repr=False)
class ExecutionAccountabilitySnapshot:
    installation_id: str
    project_id: str
    task_id: str
    run_id: str
    task_verified_complete_at: float = None
    reconciliation_required: bool = False
    unresolved_retry_group_ids: tuple = ()
    invalid_parent_call_ids: tuple = ()
    progress_snapshot: ProgressSnapshot = None

    def __post_init__(self):
        _ids(self, ('installation_id','project_id','task_id','run_id'))
        _require(self.task_verified_complete_at is None or _time(self.task_verified_complete_at))
        _require(type(self.reconciliation_required) is bool)
        _require(self.progress_snapshot is None or type(self.progress_snapshot) is ProgressSnapshot)
        for name in ('unresolved_retry_group_ids','invalid_parent_call_ids'):
            values = tuple(getattr(self, name))
            _require(len(values) <= 128 and all(_text(v) for v in values))
            object.__setattr__(self, name, tuple(sorted(set(values))))


class TokenAnomalyType(str, Enum):
    ORPHAN_USAGE = 'ORPHAN_USAGE'
    POST_COMPLETION_USAGE = 'POST_COMPLETION_USAGE'
    UNRECONCILED_RETRY_USAGE = 'UNRECONCILED_RETRY_USAGE'
    RETRY_AMPLIFICATION = 'RETRY_AMPLIFICATION'
    CONTEXT_AMPLIFICATION = 'CONTEXT_AMPLIFICATION'
    LOW_PROGRESS_HIGH_TOKEN = 'LOW_PROGRESS_HIGH_TOKEN'


@dataclass(frozen=True)
class TokenAnomalyRules:
    retry_attempt_threshold: int
    retry_growth_bps: int
    context_growth_bps: int
    low_progress_token_threshold: int

    def __post_init__(self):
        _require(all(_integer(x) for x in vars(self).values()))
        _require(self.retry_attempt_threshold >= 2 and self.retry_growth_bps > 10000
                 and self.context_growth_bps > 10000 and self.low_progress_token_threshold > 0)


@dataclass(frozen=True, repr=False)
class TokenAnomaly:
    anomaly_id: str
    anomaly_type: TokenAnomalyType
    installation_id: str
    project_id: str
    task_id: str
    run_id: str
    usage_ids: tuple
    evidence_refs: tuple
    rule_id: str
    observed_at: float
    usage_count: int


def _history(records):
    records = tuple(records)
    _require(len(records) <= 10000 and all(type(r) is TokenUsageRecord for r in records))
    _require(len({(r.installation_id,r.usage_id) for r in records}) == len(records))
    _require(len({(r.installation_id,r.call_id) for r in records}) == len(records))
    return tuple(sorted(records, key=lambda r: (r.started_at,r.installation_id,r.call_id,r.usage_id)))


def _matches(scope, record):
    return all(getattr(scope,k) is None or getattr(scope,k) == getattr(record,k)
               for k in ('installation_id','project_id','task_id','run_id'))


def _attributed(r):
    return all(getattr(r,k) is not None for k in ('project_id','task_id','run_id','agent_id'))


def _digest_many(records):
    # Hash fixed-sized artifact digests without exceeding the chain canonical array bound.
    return hashlib.sha256(''.join(sc.artifact_digest(r) for r in records).encode('ascii')).hexdigest()


def validate_budget_stack(budgets, *, now):
    budgets = tuple(budgets)
    _require(_time(now) and len(budgets) <= 4 and all(type(b) is TokenBudget for b in budgets))
    budgets = tuple(sorted(budgets, key=lambda b:list(TokenBudgetLevel).index(b.level)))
    _require(len({b.level for b in budgets}) == len(budgets))
    _require(len({b.budget_id for b in budgets}) == len(budgets))
    for n,b in enumerate(budgets):
        _require(b.issued_at <= now and (b.expires_at is None or now < b.expires_at))
        for parent in budgets[:n]:
            _require(_matches(parent,b))
            for field in ('max_total_tokens','max_cost_micros'):
                cap, child = getattr(parent,field),getattr(b,field)
                _require(cap is None or child is None or child <= cap)
            if parent.max_cost_micros is not None and b.max_cost_micros is not None:
                _require(parent.currency == b.currency)
    return budgets


def evaluate_budget(usage_history, budget_stack, proposed_or_observed_usage=None, *, now):
    """Full lifetime history in each ancestor scope required; never live blocking.

    Replacement budgets retain prior usage (no implicit period reset). Missing
    attribution may belong to a scope, so makes that scope's budget UNKNOWN.
    """
    records = _history(tuple(usage_history) + (() if proposed_or_observed_usage is None else (proposed_or_observed_usage,)))
    budgets = validate_budget_stack(budget_stack, now=now)
    states = []
    for b in budgets:
        selected = tuple(r for r in records if _matches(b,r))
        ambiguous = any(r.installation_id == b.installation_id and not _attributed(r) for r in records)
        for metric,cap in (('total_tokens',b.max_total_tokens),('cost_micros',b.max_cost_micros)):
            if cap is None:
                continue
            known = sum(getattr(r,metric) for r in selected if getattr(r,metric) is not None
                        and (metric != 'cost_micros' or r.currency == b.currency))
            unknown = ambiguous or any(getattr(r,metric) is None or
                       (metric == 'cost_micros' and r.currency != b.currency) for r in selected)
            states.append('EXCEEDED' if known > cap else 'UNKNOWN' if unknown else
                          'WARNING' if known*10000 >= cap*b.warning_threshold_bps else 'WITHIN_BUDGET')
    state = next((s for s in ('EXCEEDED','UNKNOWN','WARNING') if s in states), 'WITHIN_BUDGET' if states else 'UNKNOWN')
    return BudgetDecision(state, tuple(sc.artifact_digest(b) for b in budgets), _digest_many(records))


def detect_anomalies(usage_records, snapshot, rules):
    records = _history(usage_records)
    _require(type(snapshot) is ExecutionAccountabilitySnapshot and type(rules) is TokenAnomalyRules)
    found = []

    def add(kind, subset):
        subset = tuple(subset)
        first = subset[0]
        rule = sc.artifact_digest((kind,rules))
        evidence = (_digest_many(subset),sc.artifact_digest(snapshot),rule)
        identity = sc.artifact_digest((kind,evidence))
        found.append(TokenAnomaly(identity,kind,first.installation_id,first.project_id,first.task_id,
                                 first.run_id,tuple(r.usage_id for r in subset[:128]),evidence,rule,
                                 max(r.finished_at for r in subset),len(subset)))

    for r in records:
        scoped = _matches(snapshot,r)
        if not _attributed(r) or (scoped and r.call_id in snapshot.invalid_parent_call_ids):
            add(TokenAnomalyType.ORPHAN_USAGE,(r,))
        if scoped and snapshot.task_verified_complete_at is not None and r.started_at > snapshot.task_verified_complete_at:
            add(TokenAnomalyType.POST_COMPLETION_USAGE,(r,))
        if scoped and snapshot.reconciliation_required and r.retry_group_id in snapshot.unresolved_retry_group_ids:
            add(TokenAnomalyType.UNRECONCILED_RETRY_USAGE,(r,))
    selected = tuple(r for r in records if _matches(snapshot,r))
    groups = {}
    for r in selected:
        if r.retry_group_id is not None:
            groups.setdefault((r.agent_id,r.retry_group_id),[]).append(r)
    for group in groups.values():
        _require(len({r.attempt_index for r in group}) == len(group))
        group.sort(key=lambda r:r.attempt_index)
        first,last = group[0],group[-1]
        if (len(group) >= rules.retry_attempt_threshold and first.total_tokens is not None
                and last.total_tokens is not None and first.total_tokens > 0
                and last.total_tokens*10000 >= first.total_tokens*rules.retry_growth_bps):
            add(TokenAnomalyType.RETRY_AMPLIFICATION,group)
    agents = {}
    for r in selected:
        if _attributed(r):
            agents.setdefault(r.agent_id,[]).append(r)
    for group in agents.values():
        if len(group) >= 2:
            first,last = group[0],group[-1]
            if (first.input_tokens is not None and first.input_tokens > 0 and last.input_tokens is not None
                    and last.input_tokens*10000 >= first.input_tokens*rules.context_growth_bps):
                add(TokenAnomalyType.CONTEXT_AMPLIFICATION,(first,last))
    p = snapshot.progress_snapshot
    if (selected and p is not None and all(r.total_tokens is not None for r in selected)
            and sum(r.total_tokens for r in selected) >= rules.low_progress_token_threshold
            and p.required_remaining_after >= p.required_remaining_before
            and p.acceptance_criteria_closed == p.verification_evidence_added == p.blockers_resolved == 0):
        add(TokenAnomalyType.LOW_PROGRESS_HIGH_TOKEN,selected)
    return tuple(sorted(found,key=lambda a:(a.anomaly_type.value,a.anomaly_id)))


@dataclass(frozen=True)
class TokenAccountabilityReport:
    record_count: int
    fully_attributed_count: int
    orphan_count: int
    known_total_tokens: int
    unknown_total_token_records: int
    known_metrics: tuple
    unknown_metric_records: tuple
    known_reported_cost_micros: tuple
    known_estimated_cost_micros: tuple
    unknown_cost_records: int
    budget_state: str
    anomaly_counts: tuple


def summarize(records, *, budget_decision=None, anomalies=()):
    records = _history(records)
    known = tuple((k,sum(getattr(r,k) for r in records if getattr(r,k) is not None)) for k in METRICS)
    unknown = tuple((k,sum(getattr(r,k) is None for r in records)) for k in METRICS)
    def costs(source):
        values = {}
        for r in records:
            if r.cost_source == source:
                values[r.currency] = values.get(r.currency,0) + r.cost_micros
        return tuple(sorted(values.items()))
    attributed = sum(_attributed(r) for r in records)
    return TokenAccountabilityReport(len(records),attributed,len(records)-attributed,
        dict(known)['total_tokens'],dict(unknown)['total_tokens'],known,unknown,
        costs(CostSource.PROVIDER_REPORTED),costs(CostSource.EXPLICIT_RATE_DERIVED),
        sum(r.cost_micros is None for r in records), 'UNKNOWN' if budget_decision is None else budget_decision.state,
        tuple((k.value,sum(a.anomaly_type == k for a in anomalies)) for k in TokenAnomalyType))


def _group(records, fields):
    groups = {}
    for r in _history(records):
        key = tuple(getattr(r,k) for k in fields)
        groups.setdefault(key,[]).append(r)
    return tuple((key,summarize(value)) for key,value in sorted(groups.items(),key=lambda pair:repr(pair[0])))


def by_project(records):
    return _group(records,('installation_id','project_id'))


def by_task(records):
    return _group(records,('installation_id','project_id','task_id'))


def by_run(records):
    return _group(records,('installation_id','project_id','task_id','run_id'))


def by_provider(records):
    return _group(records,('provider',))


def by_model(records):
    return _group(records,('provider','model'))


def _authorize(actor, obj, now, action=sc.ManagementAction.RSE_RECEIPT_RECORD):
    # Missing hierarchy remains in artifact; chain scope must be a valid prefix.
    project = obj.project_id
    task = obj.task_id if project is not None else None
    d = sc.authorize_management_change(actor,action,installation_id=obj.installation_id,
                                       project_id=project,task_id=task,now=now)
    _require(d.disposition == 'ALLOW')


def _append(chain, actor, obj, kind, identity, now, previous=None, subject=None, artifact=None):
    _authorize(actor,obj,now)
    project = obj.project_id
    task = obj.task_id if project is not None else None
    run = obj.run_id if task is not None else None
    return chain.append(sc.SecurityEventDraft(identity,kind,now,obj.installation_id,actor.role,
        actor.authority_id,'token accountability evidence',project_id=project,task_id=task,run_id=run,
        subject_id=subject,artifact_digest=sc.artifact_digest(obj if artifact is None else artifact),authority_digest=sc.artifact_digest(actor),
        previous_artifact_digest=None if previous is None else sc.artifact_digest(previous)))


def record_model_usage(chain, runtime_authority, usage_record, *, now):
    _require(type(usage_record) is TokenUsageRecord and _time(now) and now >= usage_record.finished_at)
    _require(chain.verify().valid)
    # Stable call identity is an additional duplicate guard, even if usage_id changes.
    call_ref = sc.artifact_digest(usage_record.call_id)
    _require(not any(r.event_type == 'MODEL_USAGE' and r.subject_ref == sc._ref(call_ref) for r in chain.records()))
    return _append(chain,runtime_authority,usage_record,sc.EventType.MODEL_USAGE,
                   'usage:'+usage_record.usage_id,now,subject=call_ref)


def record_budget(chain, actor, budget, *, now, ancestors=(), previous=None, extension_request_id=None):
    _require(type(budget) is TokenBudget)
    validate_budget_stack(tuple(ancestors)+(budget,),now=now)
    action = sc.ManagementAction[budget.level.value+'_POLICY_CHANGE']
    _authorize(actor,budget,now,action)
    _require(chain.verify().valid)
    kind = sc.EventType.TOKEN_BUDGET_CREATED
    if previous is None:
        _require(budget.supersedes_budget_id is None and extension_request_id is None)
    else:
        _require(type(previous) is TokenBudget and budget.supersedes_budget_id == previous.budget_id)
        _require(budget.issued_at >= previous.issued_at)
        _require(budget.level == previous.level and _matches(budget,previous) and _matches(previous,budget))
        old_digest = sc.artifact_digest(previous)
        _require(any(r.artifact_digest == old_digest and r.event_type in
                     ('TOKEN_BUDGET_CREATED','TOKEN_BUDGET_SUPERSEDED','TOKEN_BUDGET_EXTENSION_GRANTED') for r in chain.records()))
        _require(not any(r.previous_artifact_digest == old_digest for r in chain.records()))
        kind = sc.EventType.TOKEN_BUDGET_SUPERSEDED
        if extension_request_id is not None:
            _require(_text(extension_request_id))
            _require(any(r.event_ref == sc._ref('request:'+extension_request_id) and r.artifact_digest == old_digest
                         and r.event_type == 'TOKEN_BUDGET_EXTENSION_REQUESTED' for r in chain.records()))
            kind = sc.EventType.TOKEN_BUDGET_EXTENSION_GRANTED
    return _append(chain,actor,budget,kind,'budget:'+budget.budget_id,now,previous)


def request_budget_extension(chain, actor, budget, *, request_id, now):
    _require(type(budget) is TokenBudget and _text(request_id))
    _require(chain.verify().valid)
    # Scoped runtime may request its enclosing project budget using its own task scope.
    d = sc.authorize_management_change(actor,sc.ManagementAction.RSE_RECEIPT_RECORD,
        installation_id=budget.installation_id,project_id=actor.project_id,task_id=actor.task_id,now=now)
    _require(d.disposition == 'ALLOW' and (budget.project_id is None or budget.project_id == actor.project_id)
             and (budget.task_id is None or budget.task_id == actor.task_id))
    _require(any(r.artifact_digest == sc.artifact_digest(budget) and r.event_type in
                 ('TOKEN_BUDGET_CREATED','TOKEN_BUDGET_SUPERSEDED','TOKEN_BUDGET_EXTENSION_GRANTED') for r in chain.records()))
    return chain.append(sc.SecurityEventDraft('request:'+request_id,sc.EventType.TOKEN_BUDGET_EXTENSION_REQUESTED,
        now,budget.installation_id,actor.role,actor.authority_id,'budget extension request only',
        project_id=actor.project_id,task_id=actor.task_id,artifact_digest=sc.artifact_digest(budget),
        authority_digest=sc.artifact_digest(actor)))


def record_budget_decision(chain, actor, budget, decision, *, now):
    _require(type(budget) is TokenBudget and type(decision) is BudgetDecision)
    _require(sc.artifact_digest(budget) in decision.budget_digests and decision.state in ('WARNING','EXCEEDED'))
    # Stable per-budget state: repeated queries cannot append duplicate warnings.
    return _append(chain,actor,budget,sc.EventType['TOKEN_BUDGET_'+decision.state],
                   'budget-state:'+budget.budget_id+':'+decision.state,now,artifact=decision)


def record_anomaly(chain, actor, anomaly, *, now):
    _require(type(anomaly) is TokenAnomaly and type(anomaly.anomaly_type) is TokenAnomalyType)
    return _append(chain,actor,anomaly,sc.EventType.TOKEN_ANOMALY,'anomaly:'+anomaly.anomaly_id,now)
