"""Explicit offline PR_CREATE qualification; never a live-account launcher.

Trusted host supplies authority, exact commitments and a bounded synthetic
transport. There is no CLI, ambient credential lookup or import-time activity.
Synthetic transport is trusted test code, not an isolation boundary.
"""
import json
from contextlib import closing
import math
from pathlib import Path
import re
import sys
import time
from urllib.parse import quote, urlsplit, urlunsplit


_FIELDS = frozenset(('schema', 'api_origin', 'repository', 'repository_id', 'head', 'base',
    'head_oid', 'base_oid', 'proposal_id', 'action_id', 'request_identity', 'payload_digest',
    'title', 'body', 'marker', 'draft', 'effect_scope', 'authorization_ref', 'expires_at',
    'post_budget', 'get_budget', 'byte_budget', 'time_budget', 'storage_domain', 'storage_id',
    'credential_source', 'credential_scope'))


def _require(ok):
    if not ok:
        raise ValueError('QUALIFICATION_REJECTED')


def _validate(m, now):
    _require(type(m) is dict and set(m) == _FIELDS)
    _require(m['schema'] == '20396.h6.pr-create.v1')
    for name in _FIELDS - {'repository_id', 'draft', 'expires_at', 'post_budget',
            'get_budget', 'byte_budget', 'time_budget'}:
        _require(type(m[name]) is str and 0 < len(m[name].encode()) <= 65536)
    _require(m['api_origin'] in ('https://api.github.com', 'https://api.example.invalid'))
    _require(re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+', m['repository']))
    _require(type(m['repository_id']) is int and m['repository_id'] > 0)
    _require(all(re.fullmatch('[0-9a-f]{40}', m[k]) for k in ('head_oid', 'base_oid')))
    _require(re.fullmatch('[0-9a-f]{64}', m['payload_digest']))
    _require(type(m['draft']) is bool and m['draft'])
    _require(m['effect_scope'] == 'PR_CREATE' and m['credential_source'] == 'EXPLICIT_SYNTHETIC_MEMORY')
    _require(m['credential_scope'] == m['api_origin'] + '/repos/' + m['repository'])
    _require(m['marker'] == '<!-- 20396-request:' + m['request_identity'] + ' -->')
    _require(m['title'].startswith('[SYNTHETIC H6] ') and m['body'].startswith('SYNTHETIC H6\n'))
    for key, low, high in [('post_budget', 1, 1), ('get_budget', 4, 16), ('byte_budget', 1, 1048576)]:
        _require(type(m[key]) is int and low <= m[key] <= high)
    _require(type(now) in (int, float) and math.isfinite(now))
    _require(type(m['expires_at']) in (int, float) and math.isfinite(m['expires_at']) and m['expires_at'] > now)
    _require(type(m['time_budget']) in (int, float) and math.isfinite(m['time_budget']) and 0 < m['time_budget'] <= 120)
    domain = Path(m['storage_domain'])
    _require(domain.is_absolute() and str(domain.resolve()) == str(domain))


class _BudgetTransport:
    tls_verified = True
    follows_redirects = False

    def __init__(self, synthetic, headers, manifest, cancelled, check_authority):
        self.synthetic, self.headers, self.m, self.cancelled = synthetic, headers, manifest, cancelled
        self.check_authority = check_authority
        self.posts = self.gets = self.bytes = 0
        self.start = time.monotonic()

    def request(self, method, url, headers, body, *, timeout, response_limit):
        self.check_authority()
        _require(not self.cancelled() and time.monotonic() - self.start < self.m['time_budget'])
        parsed = urlsplit(url)
        if parsed.scheme == 'https' and parsed.port == 443 and not parsed.username and not parsed.password:
            url = urlunsplit((parsed.scheme, parsed.hostname, parsed.path, parsed.query, parsed.fragment))
        prefix = self.m['credential_scope']
        _require(url == prefix or url.startswith(prefix + '/'))
        if method == 'POST':
            _require(url == prefix + '/pulls' and self.posts < self.m['post_budget'])
            self.posts += 1
        else:
            _require(method == 'GET' and self.gets < self.m['get_budget'] and not body)
            self.gets += 1
        remaining = self.m['byte_budget'] - self.bytes
        _require(remaining > 0)
        try:
            status, returned_headers, data = self.synthetic.request(method, url,
                (*headers, *self.headers), body, timeout=min(timeout, self.m['time_budget']),
                response_limit=min(response_limit, remaining))
            _require(type(data) is bytes and len(data) <= min(response_limit, remaining))
            self.bytes += len(data)
            self.check_authority()
            _require(not self.cancelled() and time.monotonic() - self.start < self.m['time_budget'])
            if '/pulls' in url and status in (200, 201):
                value = json.loads(data)
                records = value if type(value) is list else [value]
                for record in records:
                    _require(type(record) is dict)
                    for side in ('head', 'base'):
                        ref = record.get(side, {})
                        _require(type(ref.get('repo', {}).get('id')) is int
                            and ref['repo']['id'] == self.m['repository_id']
                            and ref.get('sha') == self.m[side + '_oid'])
            return status, returned_headers, data
        except Exception:
            raise ValueError('SYNTHETIC_TRANSPORT_UNCERTAIN') from None


def qualify(manifest, *, launch=False, synthetic_transport=None, credential_headers=(),
            authority=None, policy_stack=(), context=None, now=None,
            trusted_agent_id=None, create=False, recover=False, cancelled=lambda: False):
    """Return bounded classifications only. No raw responses or secrets returned.

    create=True is solely for host-established new storage. Existing paths never
    fall back to creation. Live transport is deliberately unavailable. Trusted
    callbacks must finish within their supplied budget; no DNS/deadline claim.
    """
    if not launch:
        return {'status': 'NOT_STARTED'}
    report = dict(status='QUALIFICATION_REJECTED', provenance='OFFLINE_SYNTHETIC',
        live_execution='LIVE_EXECUTION_BLOCKED_UNBOUNDED_DNS_OR_TRANSPORT',
        independent_corroboration='NOT_VALIDATED', posts=0, gets=0)
    transport = None
    started = time.monotonic()
    try:
        _validate(manifest, now)
        # Snapshot only validated primitive values. Never mutate the host manifest.
        m = dict(manifest)
        _require(type(create) is bool and type(recover) is bool and not (create and recover))
        _require(getattr(synthetic_transport, 'provenance', None) == 'OFFLINE_SYNTHETIC')
        _require(callable(cancelled) and not cancelled())
        directory = str(Path(__file__).resolve().parents[1] / '.agents/skills/long-horizon-engineering/scripts')
        sys.path.insert(0, directory)
        try:
            import agent_runtime_integration as bridge
        finally:
            sys.path.remove(directory)
        r, c, s, remote = bridge.rse, bridge.cet, bridge.sc, bridge.remote
        _require(type(context) is c.TraceContext and context.action_id == m['action_id'])
        _require(type(authority) is r.Authorization and authority.authorization_id == m['authorization_ref'])
        _require(type(trusted_agent_id) is str and trusted_agent_id)
        controller = bridge.AgentRuntimeBridge()
        target = m['credential_scope'] + '/pulls'
        prepared = controller.prepare(dict(proposal_id=m['proposal_id'], requested_action_class='PR_CREATE',
            requested_target=target, requested_parameters=dict(provider='github', repository=m['repository'],
                head=m['head'], base=m['base'], title=m['title'], body=m['body'].encode(), draft=m['draft'],
                request_identity=m['request_identity'], timeout=m['time_budget'], response_limit=m['byte_budget'])),
            context=context, trusted_agent_id=trusted_agent_id, authorization_ref=m['authorization_ref'],
            data_classification=r.DataClass.NON_SENSITIVE, now=now, expires_at=m['expires_at']).prepared
        _require(prepared is not None and prepared.payload_digest == m['payload_digest'])
        _require(r.evaluate_policy(prepared.action_request, policy_stack, authority, now).disposition == 'ALLOW')
        # Existing credential validator; synthetic values only, explicit host input.
        credentials = remote.HTTPSRemoteTransport(credential_headers=credential_headers)
        def current_authority():
            current = now + time.monotonic() - started
            _require(current < m['expires_at'] and current < authority.expires_at)
            _require(r.evaluate_policy(prepared.action_request, policy_stack, authority, current).disposition == 'ALLOW')
            return current
        transport = _BudgetTransport(synthetic_transport, credentials._credentials, m, cancelled, current_authority)
        with closing(r.CrossProcessOwner(m['storage_domain'])) as owner:
            journal = r.DurableSecurityJournal(str(Path(m['storage_domain']) / 'journal'),
                storage_id=m['storage_id'], create=create, owner=owner)
            chain = s.JsonlSecurityChain('h6-chain', context.installation_id,
                str(Path(m['storage_domain']) / 'chain'), create=create, owner=owner)
            controller = bridge.AgentRuntimeBridge(owner=owner)
            # Identity reads are independent synthetic GET calls, not authorizations.
            for suffix, expected in [('', None), ('/branches/' + quote(m['head'], safe=''), m['head_oid']),
                    ('/branches/' + quote(m['base'], safe=''), m['base_oid'])]:
                status, headers, data = transport.request('GET', m['credential_scope'] + suffix,
                    (('accept', 'application/vnd.github+json'), ('user-agent', '20396-remote-runtime-binding')),
                    b'', timeout=m['time_budget'], response_limit=m['byte_budget'])
                _require(status == 200 and not any(k.lower() == 'link' for k, v in headers))
                value = json.loads(data)
                if expected is None:
                    _require(type(value.get('id')) is int and value['id'] == m['repository_id']
                        and value.get('full_name') == m['repository'])
                else:
                    _require(value.get('commit', {}).get('sha') == expected)
            broker = r.CapabilityBroker()
            broker.register(r.CAPABILITIES[r.ActionClass.PR_CREATE], remote.PullRequestCreateAdapter(
                transport=transport, allowed_origins=(m['api_origin'],)))
            actor = s.SecurityAuthority('h6-runtime', s.AuthorityRole.RUNTIME, context.installation_id)
            binding = remote.RemoteRuntimeBinding(broker, journal, chain, actor,
                approved_payload_digests={m['action_id']:m['payload_digest']})
            method = controller.reconcile if recover else controller.execute
            out = method(prepared, binding=binding, expected_payload_digest=m['payload_digest'],
                expected_prepared_digest=prepared.prepared_digest, policy_stack=policy_stack,
                authorization=authority, context=context, now=current_authority())
            report.update(status=out.status, execution_state=out.receipt.execution_state,
                reconciliation_state=out.receipt.reconciliation_state)
    except Exception:
        # Input, service, storage and cancellation errors never expose raw text.
        report['status'] = 'QUALIFICATION_REJECTED'
    finally:
        if transport is not None:
            report.update(posts=transport.posts, gets=transport.gets)
    return report
