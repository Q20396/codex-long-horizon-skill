"""Explicit offline PR_CREATE qualification; never a live-account launcher.

Trusted host supplies authority, exact commitments and a bounded synthetic
transport. There is no CLI, ambient credential lookup or import-time activity.
Synthetic transport is trusted test code, not an isolation boundary.
"""
import json
import hashlib
from contextlib import closing, contextmanager
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


class InjectedObservationLoss(Exception):
    """Trusted synthetic test hook: deliberately withheld observation, not network proof."""


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
        self.adapter_response = None
        self.get_readback = []
        self.fault_provenance = []
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
            if '/pulls' in url:
                objects = []
                if status in (200, 201):
                    for record in records[:2]:
                        if all(type(record.get(k)) is int and record[k] > 0 for k in ('id', 'number')):
                            objects.append({k:record[k] for k in ('id', 'number')})
                evidence = dict(http_status=status if type(status) is int else None,
                    response_sha256=hashlib.sha256(data).hexdigest(), objects=objects,
                    classification='SYNTHETIC_OBSERVATION_NOT_AUTHORITY',
                    object_count=len(records) if status in (200, 201) else 0)
                if method == 'POST': self.adapter_response = evidence
                else: self.get_readback.append(evidence)
            return status, returned_headers, data
        except InjectedObservationLoss:
            self.fault_provenance.append('INJECTED_OBSERVATION_LOSS')
            raise ValueError('SYNTHETIC_TRANSPORT_UNCERTAIN') from None
        except Exception:
            self.fault_provenance.append('SYNTHETIC_TRANSPORT_OR_VALIDATION_FAILURE')
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
        independent_corroboration='NOT_VALIDATED', posts=0, gets=0,
        adapter_response=None, get_readback=[], fault_provenance=[])
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
            report.update(adapter_response=transport.adapter_response,
                get_readback=transport.get_readback, fault_provenance=transport.fault_provenance)
    return report


_HOST_STAGES = frozenset(('NONE','ADMISSION','CAPTURE_HOST','CAPTURE_IMPORT','CAPTURE_SIGNAL_POLICY',
    'TTY_OPEN','TTY_POLICY','TTY_DUP','TTY_STREAM','CAPTURE_HANDLER','CAPTURE_TIMER','CONFIRM_READ',
    'CONFIRM_VALIDATE','PAT_READ','TOKEN_VALIDATE','INPUT_TIMEOUT','CAPTURE_COMPLETE',
    'CAPTURE_TIMER_CANCEL','CAPTURE_SIGNAL_RESTORE','CAPTURE_STREAM_CLOSE','CAPTURE_DUP_CLOSE',
    'CAPTURE_FD_CLOSE','POST_INPUT_EXPIRY','CORE_IMPORT','CORE_PATH_REMOVE','STORAGE_STAT',
    'STORAGE_POLICY','CODE_HASH_HOST','CODE_HASH_HOST_TEST','CODE_HASH_DOC','CODE_HASH_CORE',
    'CODE_HASH_CORE_TEST','OWNER_CONSTRUCT','OWNER_OPERATION','HOST_BODY','OWNER_CLOSE','COUNTERS','DIAGNOSTIC_RECORD'))
_HOST_ERROR_TYPES = ((ValueError,'VALUE_ERROR'),(TypeError,'TYPE_ERROR'),(OSError,'OS_ERROR'),
    (PermissionError,'PERMISSION_ERROR'),(FileNotFoundError,'FILE_NOT_FOUND'),
    (FileExistsError,'FILE_EXISTS'),(IsADirectoryError,'IS_DIRECTORY'),(NotADirectoryError,'NOT_DIRECTORY'),
    (TimeoutError,'TIMEOUT'),(InterruptedError,'INTERRUPTED'),(BlockingIOError,'WOULD_BLOCK'),
    (EOFError,'EOF'),(ImportError,'IMPORT_ERROR'),(ModuleNotFoundError,'MODULE_NOT_FOUND'),
    (RuntimeError,'RUNTIME_ERROR'),(KeyboardInterrupt,'KEYBOARD_INTERRUPT'),(SystemExit,'SYSTEM_EXIT'))
_HOST_FUNCTIONS = frozenset(('_require','_capture_host','expired','_core_module','_host_code_identity',
    'run_live_host','_host_owner','_host_operation','_host_prepared','_host_read','_host_write_once',
    '_validate_live','_validate','_metadata','cleanup','note','_host_safe_error'))


def _host_safe_error(error,tb):
    """Fixed vocabulary only; never format an exception or inspect frame locals."""
    import errno
    kind=next((name for cls,name in _HOST_ERROR_TYPES if type(error) is cls),'OTHER')
    number=None
    if any(type(error) is cls for cls in (OSError,PermissionError,FileNotFoundError,FileExistsError,
            IsADirectoryError,NotADirectoryError,TimeoutError,InterruptedError,BlockingIOError)):
        value=OSError.errno.__get__(error,type(error))
        if type(value) is int and value in (errno.EACCES,errno.EPERM,errno.ENOENT,errno.EEXIST,
                errno.ENOTDIR,errno.EISDIR,errno.EIO,errno.EBADF,errno.EINTR,errno.ETIMEDOUT,
                errno.ENOSPC,errno.EMFILE,errno.ENFILE,errno.EROFS):number=value
    frames=[]
    while tb is not None and len(frames)<8:
        code=tb.tb_frame.f_code
        known=code.co_filename==__file__
        frames.append(dict(file='remote_account_qualification.py' if known else 'OTHER',
            function=code.co_name if known and code.co_name in _HOST_FUNCTIONS else 'OTHER',
            line=tb.tb_lineno))
        tb=tb.tb_next
    return dict(error=kind,errno=number,frames=frames,truncated=tb is not None)


class _HostDiagnostics:
    """Per-invocation host failure state; contains no credentials or dynamic hooks."""
    def __init__(self):
        self.stage='ADMISSION';self.completed='NONE';self.primary=None
        self.first=None;self.secondary=[];self.cleanups=[];self.truncated=False;self.failed=False

    def done(self):self.completed=self.stage

    def note(self,error,tb,stage=None):
        stage=self.stage if stage is None else stage
        stage=stage if type(stage) is str and stage in _HOST_STAGES else 'NONE'
        if self.primary is not None and error is self.primary[0]:return
        first=self.primary is None
        if first:self.primary=(error,tb)  # Freeze identity/tb before diagnostic work can fail.
        facts=dict(stage=stage,last_completed=self.completed)
        try:facts.update(_host_safe_error(error,tb))
        except BaseException:
            self.failed=True
            facts.update(error='OTHER',errno=None,frames=[],truncated=True)
            if len(self.secondary)<8:
                self.secondary.append(dict(stage='DIAGNOSTIC_RECORD',error='OTHER',errno=None,frames=[],truncated=True))
            else:self.truncated=True
        if first:self.first=facts
        elif len(self.secondary)<8:self.secondary.append(facts)
        else:self.truncated=True

    def cleanup(self,stage,call):
        try:call()
        except BaseException as error:
            self.note(error,sys.exc_info()[2],stage)
            status='FAILED'
        else:status='DONE'
        if len(self.cleanups)<8:self.cleanups.append(dict(stage=stage,status=status))
        else:self.truncated=True

    def report(self):
        return dict(schema='20396.h6.host-failure.v1',primary=self.first,secondary=self.secondary,
            cleanup=self.cleanups,truncated=self.truncated,diagnostic_failed=self.failed)


@contextmanager
def _host_owner(owner,diagnostics):
    body_failed=False
    try:
        yield owner
    except BaseException as error:
        body_failed=True
        diagnostics.note(error,sys.exc_info()[2])
        raise
    finally:
        diagnostics.cleanup('OWNER_CLOSE',owner.close)
        if not body_failed and diagnostics.primary is not None:
            error,tb=diagnostics.primary
            raise BaseException.with_traceback(error,tb)


@contextmanager
def _host_operation(owner,diagnostics):
    # Observe the body before operation.__exit__ can mask its primary exception.
    try:
        with owner.operation():
            diagnostics.done();diagnostics.stage='HOST_BODY'
            try:yield
            except BaseException as error:
                diagnostics.note(error,sys.exc_info()[2])
                raise
    except BaseException as error:
        diagnostics.note(error,sys.exc_info()[2])
        primary,tb=diagnostics.primary
        if error is primary:raise
        raise BaseException.with_traceback(primary,tb) from None


def _core_module(*,_diagnostics=None):
    import importlib
    diagnostics=_diagnostics if _diagnostics is not None else _HostDiagnostics()
    diagnostics.stage='CORE_IMPORT'
    directory=str(Path(__file__).resolve().parents[1]/'.agents/skills/long-horizon-engineering/scripts')
    sys.path.insert(0,directory)
    body_failed=False
    try:
        result=importlib.import_module('agent_runtime_integration');diagnostics.done()
        return result
    except BaseException as error:
        body_failed=True;diagnostics.note(error,sys.exc_info()[2]);raise
    finally:
        diagnostics.cleanup('CORE_PATH_REMOVE',lambda:sys.path.remove(directory))
        if not body_failed and diagnostics.primary is not None:
            error,tb=diagnostics.primary
            raise BaseException.with_traceback(error,tb)


def _host_prepared(core,m,issued):
    r,c=core.rse,core.cet
    context=c.TraceContext('h6-trace','h6-install','h6-project','h6-task','h6-run',m['action_id'],
        None,'github','selected-terminal','runtime')
    controller=core.AgentRuntimeBridge()
    proposal=dict(proposal_id=m['proposal_id'],requested_action_class='PR_CREATE',
        requested_target=m['credential_scope']+'/pulls',requested_parameters=dict(provider='github',
            repository=m['repository'],head=m['head'],base=m['base'],title=m['title'],body=m['body'].encode(),
            draft=True,request_identity=m['request_identity'],timeout=m['time_budget'],response_limit=m['byte_budget']))
    prepared=controller.prepare(proposal,context=context,trusted_agent_id='h6-terminal-user',
        authorization_ref=m['authorization_ref'],data_classification=r.DataClass.NON_SENSITIVE,
        now=issued,expires_at=m['expires_at']).prepared
    _require(prepared is not None)
    policy=r.Policy('h6-terminal-core',r.PolicyLevel.CORE,frozenset({r.ActionClass.PR_CREATE}),
        read_roots=(m['storage_domain'],),write_roots=(m['storage_domain'],),network_mode=r.NetworkMode.ALLOWLIST,
        network_allowlist=('https://api.github.com',),allowed_egress_classes=frozenset({r.DataClass.NON_SENSITIVE}),
        allowed_capabilities=frozenset({prepared.action_request.capability}),expires_at=m['expires_at'])
    authority=r.Authorization(m['authorization_ref'],context.task_id,frozenset({r.ActionClass.PR_CREATE}),
        (prepared.action_request.target,),frozenset({prepared.action_request.capability}),m['expires_at'])
    return prepared,context,policy,authority


def _capture_host(m,mode,*,_diagnostics=None):
    """Human-operated terminal only. No connector export or stdin fallback."""
    diagnostics=_diagnostics if _diagnostics is not None else _HostDiagnostics()
    diagnostics.stage='CAPTURE_IMPORT'
    import getpass
    import os
    import signal
    import termios
    import warnings
    diagnostics.done()
    fd=duplicate=stream=None;handler=False;timer=False;body_failed=False
    try:
        diagnostics.stage='CAPTURE_SIGNAL_POLICY'
        _require(signal.getsignal(signal.SIGALRM)==signal.SIG_DFL
            and signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0));diagnostics.done()
        diagnostics.stage='TTY_OPEN'
        fd=os.open('/dev/tty',os.O_RDWR|os.O_NOCTTY|os.O_NOFOLLOW);diagnostics.done()
        diagnostics.stage='TTY_POLICY'
        _require(os.isatty(fd));termios.tcgetattr(fd);diagnostics.done()
        diagnostics.stage='TTY_DUP'
        duplicate=os.dup(fd);diagnostics.done()
        diagnostics.stage='TTY_STREAM'
        stream=os.fdopen(duplicate,'w',buffering=1);duplicate=None;diagnostics.done()
        def expired(*unused):
            diagnostics.stage='INPUT_TIMEOUT'
            raise ValueError('HOST_INPUT_EXPIRED')
        diagnostics.stage='CAPTURE_HANDLER';handler=True
        signal.signal(signal.SIGALRM,expired);diagnostics.done()
        diagnostics.stage='CAPTURE_TIMER';timer=True
        signal.setitimer(signal.ITIMER_REAL,60);diagnostics.done()
        identity=hashlib.sha256(_host_encode(m)).hexdigest()
        stream.write('H6 '+mode+' '+m['repository']+' '+identity+'\n')
        stream.write('Confirm trusted local clock/storage, exact scope, and token revocation responsibility.\n')
        with warnings.catch_warnings():
            warnings.simplefilter('error',getpass.GetPassWarning)
            diagnostics.stage='CONFIRM_READ'
            confirmation=getpass.getpass('Type '+mode.upper()+' '+identity+' (hidden): ',stream=stream);diagnostics.done()
            diagnostics.stage='CONFIRM_VALIDATE'
            _require(confirmation==mode.upper()+' '+identity);diagnostics.done()
            diagnostics.stage='PAT_READ'
            token=getpass.getpass('Repository-only PAT (hidden; never send to chat): ',stream=stream);diagnostics.done()
        diagnostics.stage='TOKEN_VALIDATE'
        _require(type(token) is str and 0<len(token)<=8192
            and all(33<=ord(ch)<=126 for ch in token));diagnostics.done()
        diagnostics.stage='CAPTURE_COMPLETE'
        return (('Authorization','Bearer '+token),)
    except BaseException as error:
        body_failed=True;diagnostics.note(error,sys.exc_info()[2]);raise
    finally:
        if timer:diagnostics.cleanup('CAPTURE_TIMER_CANCEL',lambda:signal.setitimer(signal.ITIMER_REAL,0))
        if handler:diagnostics.cleanup('CAPTURE_SIGNAL_RESTORE',lambda:signal.signal(signal.SIGALRM,signal.SIG_DFL))
        if stream is not None:diagnostics.cleanup('CAPTURE_STREAM_CLOSE',stream.close)
        if duplicate is not None:diagnostics.cleanup('CAPTURE_DUP_CLOSE',lambda:os.close(duplicate))
        if fd is not None:diagnostics.cleanup('CAPTURE_FD_CLOSE',lambda:os.close(fd))
        if not body_failed and diagnostics.primary is not None:
            error,tb=diagnostics.primary
            raise BaseException.with_traceback(error,tb)


def _host_encode(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode()


def _host_read(owner,path,limit=32768):
    import os
    import stat
    owner.require_path(str(path))
    fd=os.open(str(path),os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(fd)
        _require(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and info.st_nlink==1
            and not info.st_mode&0o077 and 0<info.st_size<=limit)
        data=os.read(fd,limit+1);_require(len(data)==info.st_size)
        value=json.loads(data);_require(_host_encode(value)==data)
    finally:os.close(fd)
    owner.bind(str(path));return value


def _host_write_once(owner,path,value,limit=4096):
    import os
    owner.require_path(str(path));data=_host_encode(value);_require(len(data)<=limit)
    fd=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        _require(os.write(fd,data)==len(data));os.fsync(fd)
    finally:os.close(fd)
    parent=os.open(str(path.parent),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(parent)
    finally:os.close(parent)
    owner.bind(str(path))


def _host_code_identity(*,_diagnostics=None):
    root=Path(__file__).resolve().parents[1]
    names=('scripts/remote_account_qualification.py','tests/test_remote_account_qualification.py',
        'docs/h6-real-remote-account-e2e.md','.agents/skills/long-horizon-engineering/scripts/remote_runtime_binding.py',
        'tests/test_remote_runtime_binding.py')
    stages=('CODE_HASH_HOST','CODE_HASH_HOST_TEST','CODE_HASH_DOC','CODE_HASH_CORE','CODE_HASH_CORE_TEST')
    result={}
    for p,stage in zip(names,stages):
        if _diagnostics is not None:_diagnostics.stage=stage
        result[p]=hashlib.sha256((root/p).read_bytes()).hexdigest()
        if _diagnostics is not None:_diagnostics.done()
    return result


def _phase_record(session,mode):
    return dict(schema='20396.h6.phase.v1',phase=mode,
        session_sha256=hashlib.sha256(_host_encode(session)).hexdigest(),
        gets=8 if mode=='create' else 2,posts=1 if mode=='create' else 0,bytes=1048576,seconds=60)


def _metadata(transport,p,policy,authority,limits,kind,number=None):
    limits.check()
    status,headers,data=transport.qualification_get(p.action_request,p.normalized_payload,kind,
        policy_stack=(policy,),authorization=authority,now=time.time(),number=number)
    _require(status==200 and not any(k.lower() in ('link','location') for k,v in headers))
    return json.loads(data)


def run_live_host(manifest,*,mode,launch=False):
    """One explicitly human-operated phase; imports/disabled calls never execute.

    No real invocation is authorized by the offline implementation's tests.
    Two durable prepaid phase slots never refund or restart after any failure.
    """
    if launch is False:return {'status':'NOT_STARTED'}
    import os
    report=dict(status='LIVE_HOST_BLOCKED',provenance='LIVE_PR_CREATE_HOST',posts=0,gets=0,
        execution_state='UNKNOWN_OUTCOME',reconciliation_state='NOT_RUN',cleanup='UNKNOWN',
        independent_corroboration='NOT_VALIDATED',credential_lifecycle='USER_REVOCATION_REQUIRED')
    limits=transport=None;root=None;diagnostics=_HostDiagnostics()
    try:
        _require(type(launch) is bool and mode in ('create','recover'))
        now=time.time();m=dict(manifest)
        # Shape validation only. This temporary object is not provider evidence.
        witness={k:m[k] for k in ('repository','repository_id','head','base','head_oid','base_oid')}
        witness.update(observed_at=now,expires_at=min(now+30,m['expires_at']),provenance='TRUSTED_HOST_PREFLIGHT_V1')
        _validate_live(m,witness,now)
        _require(m['byte_budget']<=65536)
        diagnostics.done()
        # Human confirmation is the host authority source; no bool/provenance
        # parameter, credential FD or model payload substitutes for this step.
        diagnostics.stage='CAPTURE_HOST'
        headers=_capture_host(m,mode,_diagnostics=diagnostics);diagnostics.done()
        diagnostics.stage='POST_INPUT_EXPIRY'
        now=time.time();_require(now<m['expires_at']);diagnostics.done()
        diagnostics.stage='CORE_IMPORT'
        core=_core_module(_diagnostics=diagnostics);r,s=core.rse,core.sc
        root=Path(m['storage_domain'])
        diagnostics.stage='STORAGE_STAT'
        info=root.stat();diagnostics.done()
        diagnostics.stage='STORAGE_POLICY'
        _require(root.resolve()==root and info.st_uid==os.getuid() and not info.st_mode&0o077);diagnostics.done()
        code=_host_code_identity(_diagnostics=diagnostics)
        diagnostics.stage='OWNER_CONSTRUCT'
        owner=r.CrossProcessOwner(str(root));diagnostics.done()
        with _host_owner(owner,diagnostics):
            diagnostics.stage='OWNER_OPERATION'
            with _host_operation(owner,diagnostics):
                allowed={'.h2-owner','session.json','create-reserved.json','recover-reserved.json',
                    'create-outcome.json','recover-outcome.json','journal','chain'}
                _require(set(os.listdir(root))<=allowed)
                if mode=='create':
                    _require(set(os.listdir(root))=={'.h2-owner'})
                    p,context,policy,authority=_host_prepared(core,m,now)
                    _require(p.payload_digest==m['payload_digest'])
                    session=dict(schema='20396.h6.host-session.v1',manifest=m,issued_at=now,
                        expires_at=m['expires_at'],code=code,prepared_digest=p.prepared_digest,
                        material_identity=p.material_effect_identity,domain=[info.st_dev,info.st_ino])
                    _host_write_once(owner,root/'session.json',session,32768)
                else:
                    session=_host_read(owner,root/'session.json')
                    _require(set(session)=={'schema','manifest','issued_at','expires_at','code','prepared_digest','material_identity','domain'}
                        and session['schema']=='20396.h6.host-session.v1' and session['manifest']==m
                        and session['code']==code and session['domain']==[info.st_dev,info.st_ino]
                        and type(session['issued_at']) in (int,float) and math.isfinite(session['issued_at'])
                        and session['issued_at']<=now<session['expires_at']<=session['issued_at']+600)
                    _require(_host_read(owner,root/'create-reserved.json',4096)==_phase_record(session,'create'))
                    prior=_host_read(owner,root/'create-outcome.json',4096)
                    _require(set(prior)=={'schema','session_sha256','direct_completion','group_cleanup','descendants'}
                        and prior['schema']=='20396.h6.outcome.v2'
                        and prior['session_sha256']==hashlib.sha256(_host_encode(session)).hexdigest()
                        and prior['direct_completion'] in ('SELECTED_DIRECT_WORKER_COMPLETE','NO_WORKER_LAUNCHED')
                        and prior['group_cleanup']=='UNKNOWN' and prior['descendants']=='UNKNOWN')
                    p,context,policy,authority=_host_prepared(core,m,session['issued_at'])
                    _require(p.payload_digest==m['payload_digest'] and p.prepared_digest==session['prepared_digest']
                        and p.material_effect_identity==session['material_identity'])
                _host_write_once(owner,root/(mode+'-reserved.json'),_phase_record(session,mode))
                limits=core.remote._PRQualificationLimits(m,mode=mode,expires_at=session['expires_at'],issued_at=session['issued_at'])
                journal=r.DurableSecurityJournal(str(root/'journal'),storage_id=m['storage_id'],create=mode=='create',owner=owner)
                chain=s.JsonlSecurityChain('h6-live-chain',context.installation_id,str(root/'chain'),create=mode=='create',owner=owner)
                controller=core.AgentRuntimeBridge(owner=owner)
                transport=core.remote.PRCreateBoundedHTTPS(credential_headers=headers,qualification_limits=limits,
                    selected_direct=True)
                adapter=core.remote.PullRequestCreateAdapter(transport=transport,allowed_origins=('https://api.github.com',))
                broker=r.CapabilityBroker();broker.register(p.action_request.capability,adapter)
                actor=s.SecurityAuthority('h6-live-runtime',s.AuthorityRole.RUNTIME,context.installation_id)
                binding=core.remote.RemoteRuntimeBinding(broker,journal,chain,actor,
                    approved_payload_digests={m['action_id']:m['payload_digest']})
                if mode=='create':
                    for unused in range(2):
                        repo=_metadata(transport,p,policy,authority,limits,'repo')
                        _require(type(repo.get('id')) is int and repo['id']==m['repository_id'] and repo.get('full_name')==m['repository'])
                        for side in ('head','base'):
                            ref=_metadata(transport,p,policy,authority,limits,side)
                            _require(ref.get('commit',{}).get('sha')==m[side+'_oid'])
                limits.check()
                out=(controller.execute if mode=='create' else controller.reconcile)(p,binding=binding,
                    expected_payload_digest=m['payload_digest'],expected_prepared_digest=p.prepared_digest,
                    policy_stack=(policy,),authorization=authority,context=context,now=time.time())
                report.update(status=out.status,execution_state=out.receipt.execution_state,
                    reconciliation_state=out.receipt.reconciliation_state)
                if mode=='create' and out.receipt.execution_state=='KNOWN_SUCCESS':
                    _metadata(transport,p,policy,authority,limits,'list')
                if transport._qualification.number is not None:
                    _metadata(transport,p,policy,authority,limits,'pull',transport._qualification.number)
                limits.check()
                report['object_number']=limits.number
                report['readback']='SAME_PROVIDER_SAME_CLIENT_OBSERVATION_ONLY'
                report['observations']=list(limits.observations)
                summary=transport._selected_summary()
                report.update(summary);report['cleanup']='UNKNOWN'
                _host_write_once(owner,root/(mode+'-outcome.json'),dict(schema='20396.h6.outcome.v2',
                    session_sha256=hashlib.sha256(_host_encode(session)).hexdigest(),**summary))
                _require(_host_code_identity(_diagnostics=diagnostics)==code)
    except BaseException as error:
        diagnostics.note(error,sys.exc_info()[2])
        report['status']='LIVE_HOST_BLOCKED'  # Keep any known effect state; never print raw errors.
    finally:
        if limits is not None:
            try:report.update(posts=limits.posts,gets=limits.gets,reserved_response_bytes=limits.reserved_bytes)
            except BaseException as error:
                diagnostics.note(error,sys.exc_info()[2],'COUNTERS');report['status']='LIVE_HOST_BLOCKED'
        if diagnostics.primary is not None:
            try:report['diagnostics']=diagnostics.report()
            except BaseException:
                report['diagnostics']=dict(schema='20396.h6.host-failure.v1',diagnostic_failed=True,truncated=True)
        # Credentials are never returned; Python memory erasure is not guaranteed.
    return report


def _live_host_cli():
    """Only a human may invoke this after separate live-run authorization."""
    import os
    if len(sys.argv)!=3 or sys.argv[1] not in ('--live-create-once','--live-recover-once'):
        return {'status':'NOT_STARTED'}
    try:
        path=Path(sys.argv[2]);_require(path.is_absolute())
        fd=os.open(str(path),os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            import stat
            info=os.fstat(fd);_require(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid()
                and info.st_nlink==1 and not info.st_mode&0o077 and 0<info.st_size<=32768)
            data=os.read(fd,32769);_require(len(data)==info.st_size)
            m=json.loads(data);_require(_host_encode(m)==data)
        finally:os.close(fd)
        return run_live_host(m,mode='create' if sys.argv[1]=='--live-create-once' else 'recover',launch=True)
    except BaseException:return {'status':'LIVE_HOST_BLOCKED'}


def _validate_live(manifest, preflight, now):
    """Validate non-secret commitments; a witness is not execution authority."""
    _require(type(manifest) is dict and set(manifest) == _FIELDS)
    m = dict(manifest)
    _require(m['schema'] == '20396.h6.pr-create.live.v1'
        and m['api_origin'] == 'https://api.github.com'
        and m['repository'] == 'Q20396/20396-acceptance-sandbox'
        and m['credential_source'] == 'HOST_ANONYMOUS_PIPE_V1')
    # Reuse v1 primitive validation without conferring synthetic provenance.
    check = dict(m, schema='20396.h6.pr-create.v1',
        credential_source='EXPLICIT_SYNTHETIC_MEMORY')
    _validate(check, now)
    _require(type(now) in (int, float) and now >= 0
        and m['expires_at'] - now <= 600
        and m['get_budget'] == 10 and m['byte_budget'] <= 262144
        and 0 < m['time_budget'] <= 30
        and len(m['title'].encode()) <= 128 and len(m['body'].encode()) <= 4096)
    keys = ('repository', 'repository_id', 'head', 'base', 'head_oid', 'base_oid')
    _require(type(preflight) is dict and set(preflight) == set(keys) | {
        'observed_at', 'expires_at', 'provenance'})
    _require(all(type(preflight[k]) is type(m[k]) and preflight[k] == m[k] for k in keys)
        and preflight['provenance'] == 'TRUSTED_HOST_PREFLIGHT_V1')
    for key in ('observed_at', 'expires_at'):
        _require(type(preflight[key]) in (int, float) and math.isfinite(preflight[key]))
    _require(preflight['observed_at'] <= now < preflight['expires_at']
        and now - preflight['observed_at'] <= 30
        and preflight['expires_at'] <= min(m['expires_at'], preflight['observed_at'] + 30))
    return m


def _live_channel_ready():
    """No approved host delivery integration exists. Not a caller-controlled flag.

    A manifest, credential FD or provenance string cannot establish this trust.
    Enabling a real channel requires a separately reviewed host integration.
    """
    return False


def _read_live_credential(fd):
    """Reserved host seam, tested only with fake tokens; takes ownership of fd.

    Only FIFO type/access are checked, not anonymity or producer identity.
    Never called by qualify_live while the host channel remains unconfirmed.
    Reject standard descriptors without closing them. No secret diagnostics.
    """
    import fcntl
    import os
    import select
    import stat
    _require(type(fd) is int and fd >= 3)
    try:
        _require(stat.S_ISFIFO(os.fstat(fd).st_mode)
            and fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY)
        os.set_blocking(fd, False)
        deadline = time.monotonic() + 5
        value = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            _require(remaining > 0)
            ready, _, _ = select.select([fd], [], [], remaining)
            _require(bool(ready))
            chunk = os.read(fd, min(1024, 8193-len(value)))
            if not chunk:
                break
            value.extend(chunk)
            _require(len(value) <= 8192)
        _require(bool(value) and all(33 <= b <= 126 for b in value))
        _require(time.monotonic() < deadline)
        return (('Authorization', 'Bearer ' + value.decode('ascii')),)
    except Exception:
        raise ValueError('LIVE_CREDENTIAL_INPUT_REJECTED') from None
    finally:
        os.close(fd)


def _live_adapter(remote, credential_headers):
    """Use core exact types: no callback wrapper, fallback or budget substitution.

    Construction does not perform I/O. A later reviewed host integration must
    register this exact adapter through the existing RemoteRuntimeBinding so
    that the binding, not this harness, creates the original _PRBudget.
    """
    return remote.PullRequestCreateAdapter(
        transport=remote.PRCreateBoundedHTTPS(credential_headers=credential_headers),
        allowed_origins=('https://api.github.com',))


def qualify_live(manifest, *, launch=False, credential_fd=None, preflight=None,
                 authority=None, policy_stack=(), context=None, now=None,
                 trusted_agent_id=None, recover=False, cancelled=lambda: False):
    """Explicit live admission only; current host credential gate is unresolved.

    There is deliberately no execution branch, CLI, token discovery, credential
    read or journal creation here. The reserved authority/context arguments do
    not grant permission. Real execution and GET recovery remain NOT_RUN.
    """
    if launch is False:
        return {'status':'NOT_STARTED'}
    report = dict(status='QUALIFICATION_REJECTED', provenance='LIVE_PR_CREATE_NOT_EXECUTED',
        live_execution='BLOCKED_CREDENTIAL_CHANNEL_UNCONFIRMED', posts=0, gets=0,
        independent_corroboration='NOT_VALIDATED', credential_lifecycle='NOT_VALIDATED')
    try:
        _require(type(launch) is bool and type(recover) is bool and callable(cancelled))
        _validate_live(manifest, preflight, now)
        _require(not cancelled())
        # No caller-provided flag, fake provenance or existing connector token
        # can enable the unresolved host integration. Do not consume the FD.
        if not _live_channel_ready():
            report['status'] = 'BLOCKED_CREDENTIAL_CHANNEL_UNCONFIRMED'
        else:
            report['status'] = 'BLOCKED_LIVE_HOST_INTEGRATION_NOT_IMPLEMENTED'
    except Exception:
        pass  # Never expose a raw exception, payload or credential.
    return report


if __name__ == '__main__':
    print(json.dumps(_live_host_cli(),sort_keys=True))
