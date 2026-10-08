"""Repository-only, read-only observation of one trusted local file postcondition.

Independent means bytes are read here rather than supplied by an adapter. This
is not an atomic snapshot, process authorship proof, authorization, reconciler,
or hostile-host sensor. Callers fix requests before execution and check binding.
Import does not collect or acquire resources. Standard library only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
import re
import stat
import uuid

_OPEN, _STAT = os.open, os.stat
_MAX_BYTES = 16 * 1024 * 1024
_REF = re.compile(r'ref:[A-Za-z0-9_.:-]{1,128}\Z')
_DIGEST = re.compile(r'[0-9a-f]{64}\Z')


@dataclass(frozen=True)
class ObservationRequest:
    root: str = field(repr=False)
    target: str = field(repr=False)
    root_ref: str
    root_identity: tuple
    target_ref: str
    attempt_ref: str
    scope_ref: str
    request_ref: str
    expected_size: int
    expected_digest: str
    max_bytes: int


@dataclass(frozen=True)
class ArtifactObservation:
    root_ref: str
    root_identity: tuple
    target_ref: str
    attempt_ref: str
    scope_ref: str
    request_ref: str
    expected_size: int
    expected_digest: str
    max_bytes: int
    status: str
    reason: str
    observed_size: int | None = None
    observed_digest: str | None = None
    file_identity: tuple | None = None
    expectation_match: str = 'UNKNOWN'
    process_authorship: str = 'NOT_PROVEN'
    retry_authorized: bool = False


def _supported():
    return (os.name == 'posix' and all(getattr(os, name, 0)
            for name in ('O_DIRECTORY', 'O_NOFOLLOW', 'O_NONBLOCK'))
            and _OPEN in os.supports_dir_fd and _STAT in os.supports_dir_fd
            and _STAT in os.supports_follow_symlinks and hasattr(os, 'getuid'))


def _parts(value, absolute=False):
    if type(value) is not str or '\x00' in value or len(value) > 4096:
        return None
    try:
        os.fsencode(value)
    except UnicodeEncodeError:
        return None
    if absolute:
        if not value.startswith('/'):
            return None
        value = value[1:]
    elif value.startswith('/'):
        return None
    parts = value.split('/')
    return parts if 1 <= len(parts) <= 128 and all(p not in ('', '.', '..') for p in parts) else None


def _inputs(root, target, expected_size, expected_digest, attempt_ref, scope_ref, max_bytes):
    return (_parts(root, True) is not None and _parts(target) is not None
            and type(expected_size) is int and 0 <= expected_size <= _MAX_BYTES
            and type(max_bytes) is int and 1 <= max_bytes <= _MAX_BYTES
            and type(expected_digest) is str and _DIGEST.fullmatch(expected_digest)
            and all(type(ref) is str and _REF.fullmatch(ref) for ref in (attempt_ref, scope_ref)))


def _directory_identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid)


def _file_identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _directory(path, handles, links, parent=None):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK,
                 **({} if parent is None else {'dir_fd': parent}))
    handles.append(fd)
    info = os.fstat(fd)
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError('BOUNDARY_CHANGED')
    links.append((parent, path, fd, _directory_identity(info)))
    return fd


def _root(root, handles, links):
    fd = _directory('/', handles, links)
    for part in _parts(root, True):
        fd = _directory(part, handles, links, fd)
    info = os.fstat(fd)
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('ROOT_BOUNDARY_UNAVAILABLE')
    return fd, (info.st_dev, info.st_ino)


def _check_links(links):
    for parent, path, fd, identity in links:
        if _directory_identity(os.fstat(fd)) != identity:
            raise ValueError('BOUNDARY_CHANGED')
        info = os.stat(path, follow_symlinks=False,
                       **({} if parent is None else {'dir_fd': parent}))
        if _directory_identity(info) != identity:
            raise ValueError('BOUNDARY_CHANGED')


def _close(handles):
    complete = True
    for fd in reversed(handles):
        try:
            os.close(fd)
        except OSError:
            # Attempt every remaining close. Never retry an ambiguous close:
            # another thread could reuse the descriptor number in the meantime.
            complete = False
    return complete


def bind_request(*, root, target, expected_size, expected_digest, attempt_ref, scope_ref, max_bytes):
    """Trusted controller prebinds a private canonical root BEFORE execution.

    No target read is performed. Root ancestry never follows symlinks; e.g. the
    caller supplies /private/tmp on Darwin rather than the /tmp symlink. A fresh
    request reference distinguishes observations of separate requests, including
    reuse of an attempt label. It is correlation, not authentication or a ledger.
    """
    try:
        root = os.fspath(root)
    except TypeError:
        raise ValueError('INVALID_OBSERVATION_REQUEST') from None
    if not _inputs(root, target, expected_size, expected_digest, attempt_ref, scope_ref, max_bytes):
        raise ValueError('INVALID_OBSERVATION_REQUEST')
    if not _supported():
        raise ValueError('OBSERVATION_UNSUPPORTED')
    handles, links = [], []
    try:
        _, identity = _root(root, handles, links)
        _check_links(links)
    except (OSError, ValueError):
        raise ValueError('ROOT_BOUNDARY_UNAVAILABLE') from None
    finally:
        if not _close(handles):
            raise ValueError('ROOT_BOUNDARY_UNAVAILABLE') from None
    digest = lambda value: hashlib.sha256(os.fsencode(value)).hexdigest()
    return ObservationRequest(root, target, digest(root), identity, digest(target),
        attempt_ref, scope_ref, 'ref:' + uuid.uuid4().hex, expected_size, expected_digest, max_bytes)


def _binding(request):
    return {name: getattr(request, name) for name in (
        'root_ref', 'root_identity', 'target_ref', 'attempt_ref', 'scope_ref',
        'request_ref', 'expected_size', 'expected_digest', 'max_bytes')}


def _valid_request(request):
    return (type(request) is ObservationRequest and _inputs(request.root, request.target,
            request.expected_size, request.expected_digest, request.attempt_ref,
            request.scope_ref, request.max_bytes)
            and request.root_ref == hashlib.sha256(os.fsencode(request.root)).hexdigest()
            and request.target_ref == hashlib.sha256(os.fsencode(request.target)).hexdigest()
            and type(request.request_ref) is str and _REF.fullmatch(request.request_ref))


def matches_request(request, observation):
    """Trusted consumer must reject wrong binding or prior-request substitution.

    This does not authenticate supplied evidence, detect replay within the SAME
    request, or prevent global replay. Collector and trusted caller share host
    trust; callers retain the current prebound request and provenance themselves.
    """
    return (bool(_valid_request(request)) and type(observation) is ArtifactObservation
            and _binding(request) == _binding(observation))


def collect(request):
    """Read one bounded regular file; never execute, authorize, retry, or persist.

    OBSERVED/MISMATCH still retains actual bytes' digest. Missing, inaccessible,
    changed, replaced or oversized files have UNKNOWN observation and match.
    These outcomes never imply NOT_APPLIED or clear an unresolved-action barrier.
    """
    if not _valid_request(request):
        raise ValueError('INVALID_OBSERVATION_REQUEST')
    binding = _binding(request)
    if not _supported():
        return ArtifactObservation(**binding, status='UNSUPPORTED', reason='REQUIRED_PRIMITIVES_UNAVAILABLE')
    handles, links = [], []
    try:
        fd, identity = _root(request.root, handles, links)
        if identity != request.root_identity:
            raise ValueError('BOUNDARY_CHANGED')
        parts = _parts(request.target)
        for part in parts[:-1]:
            fd = _directory(part, handles, links, fd)
        parent = fd
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        handles.append(fd)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('NOT_REGULAR_FILE')
        if before.st_size > request.max_bytes:
            raise ValueError('READ_LIMIT_EXCEEDED')
        digest, count = hashlib.sha256(), 0
        # The +1 sentinel distinguishes EOF at exactly the bound from overflow.
        # Even a lying/changing stat cannot cause an unlimited read loop.
        while count <= request.max_bytes:
            chunk = os.read(fd, min(65536, request.max_bytes + 1 - count))
            if not chunk:
                break
            count += len(chunk)
            if count > request.max_bytes:
                raise ValueError('READ_LIMIT_EXCEEDED')
            digest.update(chunk)
        after = os.fstat(fd)
        observed_identity = _file_identity(before)
        if observed_identity != _file_identity(after) or count != after.st_size:
            raise ValueError('FILE_CHANGED')
        if observed_identity != _file_identity(os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)):
            raise ValueError('FILE_CHANGED')
        _check_links(links)
        actual = digest.hexdigest()
        match = count == request.expected_size and actual == request.expected_digest
        return ArtifactObservation(**binding, status='OBSERVED', reason='BOUNDED_FILE_OBSERVATION',
            observed_size=count, observed_digest=actual, file_identity=observed_identity,
            expectation_match='MATCH' if match else 'MISMATCH')
    except ValueError as error:
        reason = str(error) if str(error) in (
            'BOUNDARY_CHANGED', 'ROOT_BOUNDARY_UNAVAILABLE', 'NOT_REGULAR_FILE',
            'READ_LIMIT_EXCEEDED', 'FILE_CHANGED') else 'OBSERVATION_UNAVAILABLE'
        return ArtifactObservation(**binding, status='UNKNOWN', reason=reason)
    except OSError:
        return ArtifactObservation(**binding, status='UNKNOWN', reason='OBSERVATION_UNAVAILABLE')
    finally:
        if not _close(handles):
            return ArtifactObservation(**binding, status='UNKNOWN', reason='CLEANUP_UNCERTAIN')
