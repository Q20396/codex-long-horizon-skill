"""Opt-in customer local-compute adapter (Beta), not an install hook.

No effects on import. Grants/qualification references are trusted host assertions,
not authenticated human authorization. No automatic downloads, runtime installer,
daemon, default Codex changes, cloud fallback, content logging or replay prevention.
Explicit lifecycle staging only accepts catalog-pinned assets and separate consent.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import stat
import tarfile
import selectors
import re
import sys
import time
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

# -I deliberately excludes the script directory. Bind only this installed,
# resolved directory, never cwd/PYTHONPATH; ordinary imports remain effect-free.
if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import local_compute_deployment as deployment
import local_compute_pool as pool
import token_accountability as accounting

NAME = '本地算力辅助（Beta）'
TASKS = frozenset({'diff-classification', 'log-summary', 'test-failure-summary'})
MAX_RESPONSE = 131072
MAX_INPUT = 32768


class CleanupUnknown(RuntimeError):
    """Original probe handle termination/close could not be confirmed."""


class Stopped(ValueError):
    """Fixed public reason only; never include raw tool output or task content."""


def require(ok, code):
    if not ok:
        raise Stopped(code)


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Grant:
    node_id: str
    scopes: frozenset
    expires_at: float
    reference: str
    binding: str = ''

    def __post_init__(self):
        require(type(self.node_id) is str and 0 < len(self.node_id) <= 128, 'GRANT_NODE')
        require(number(self.expires_at), 'GRANT_TIME')
        require(type(self.reference) is str and 0 < len(self.reference) <= 128, 'GRANT_REFERENCE')
        require(type(self.binding) is str, 'GRANT_BINDING')
        object.__setattr__(self, 'scopes', frozenset(self.scopes))
        require(self.scopes <= {'probe', 'inspect-runtime', 'qualify', 'infer', 'return-to-cloud'}, 'GRANT_SCOPE')

    def check(self, node, scope, binding='', now=None):
        now = time.time() if now is None else now
        require(number(now), 'CLOCK_UNKNOWN')
        require(node == self.node_id and scope in self.scopes and now < self.expires_at,
                'CONSENT_REQUIRED_OR_EXPIRED')
        require(not binding or self.binding == binding, 'AUTHORIZATION_CHANGED')


def load_catalog(path=None):
    path = path or Path(__file__).resolve().parent.parent / 'references/local-model-assist-catalog.json'
    with open(path, 'rb') as handle:
        raw = handle.read(32769)
    require(len(raw) <= 32768, 'CATALOG_CAP')
    try:
        value = json.loads(raw)
        require(value['schema_version'] == 1 and len(value['models']) <= 3, 'CATALOG_SHAPE')
        for model in value['models']:
            require(len(model['manifest_sha256']) == 64 and
                    all(c in '0123456789abcdef' for c in model['manifest_sha256']), 'CATALOG_DIGEST')
        return value
    except (KeyError, TypeError, json.JSONDecodeError):
        raise Stopped('CATALOG_SHAPE') from None


def _command(argv):
    # Bounded POSIX pipe read; Windows needs a separately qualified pipe adapter.
    require(os.name == 'posix', 'BOUNDED_COMMAND_ADAPTER_UNAVAILABLE')
    deadline = time.monotonic()+8
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)
    raw = bytearray()
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline-time.monotonic()-1  # reserve cleanup
                require(remaining > 0, 'PROBE_COMMAND_TIMEOUT')
                require(selector.select(remaining), 'PROBE_COMMAND_TIMEOUT')
                chunk = os.read(proc.stdout.fileno(), min(4096, 65537-len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
                require(len(raw) <= 65536, 'PROBE_COMMAND_CAP')
        require(proc.wait(timeout=max(.001, deadline-time.monotonic())) == 0, 'PROBE_COMMAND_FAILED')
        return raw.decode('utf-8', errors='strict')
    finally:
        try:
            if proc.poll() is None:
                proc.kill()  # only the original owned handle; no group/digital PID
                proc.wait(timeout=max(.001, deadline-time.monotonic()))
        except BaseException:
            raise CleanupUnknown('PROBE_CLEANUP_UNKNOWN') from None
        finally:
            try:
                proc.stdout.close()
            except BaseException:
                raise CleanupUnknown('PROBE_CLEANUP_UNKNOWN') from None


def _read_metadata(path):
    with open(path, 'r') as handle:
        value = handle.read(32769)
    require(len(value) <= 32768, 'METADATA_CAP')
    return value


class PlatformReader:
    """Use vendor/OS tools, not a new GPU library; absent facts stay None.

    Injected functions are for synthetic tests. Caller must only invoke through
    probe() with exact node consent. Raw command outputs are not returned/logged.
    """
    def __init__(self, disk_root, command=_command, read_text=None,
                 system=None, architecture=None, disk_free=None):
        self.disk_root = disk_root
        self.command = command
        self.read_text = read_text or _read_metadata
        self.system = system or platform.system
        self.architecture = architecture or platform.machine
        self.disk_free = disk_free or (lambda p: shutil.disk_usage(p).free)

    def __call__(self, node_id):
        system, arch = self.system(), self.architecture()
        result = dict(os=system, architecture=arch, memory_total_gb=None,
                      memory_available_gb=None, unified_memory=system == 'Darwin' and arch == 'arm64',
                      accelerator=None, gpu_memory_gb=None, free_storage_gb=None)
        try:
            result['free_storage_gb'] = self.disk_free(self.disk_root) / 1024**3
            if system == 'Darwin':
                result['memory_total_gb'] = int(self.command(['/usr/sbin/sysctl', '-n', 'hw.memsize'])) / 1024**3
                # Conservative free+speculative page snapshot, not reserved VRAM.
                vm = self.command(['/usr/bin/vm_stat'])
                page = re.search(r'page size of (\d+) bytes', vm)
                free = re.search(r'Pages free:\s+(\d+)', vm)
                speculative = re.search(r'Pages speculative:\s+(\d+)', vm)
                if page and free and speculative:
                    result['memory_available_gb'] = (int(free[1])+int(speculative[1]))*int(page[1])/1024**3
                displays = json.loads(self.command(['/usr/sbin/system_profiler', 'SPDisplaysDataType', '-json']))
                result['accelerator'] = [{'name': str(x.get('sppci_model', 'UNKNOWN'))[:128],
                                          'backend': 'Metal', 'driver': 'OS_MANAGED'}
                                         for x in displays.get('SPDisplaysDataType', [])[:8]]
            elif system == 'Linux':
                fields = dict(line.split(':', 1) for line in self.read_text('/proc/meminfo').splitlines() if ':' in line)
                for field, key in [('MemTotal', 'memory_total_gb'), ('MemAvailable', 'memory_available_gb')]:
                    if field in fields:
                        result[key] = int(fields[field].split()[0]) / 1024**2
            # Vendor CLI only, no discovery/install of a missing runtime or driver.
            if system in ('Linux', 'Windows'):
                rows = self.command(['nvidia-smi', '--query-gpu=name,memory.total,memory.free,driver_version',
                                     '--format=csv,noheader,nounits']).splitlines()
                devices = []
                for row in rows[:8]:
                    name, total, free, driver = [v.strip() for v in row.split(',')]
                    devices.append({'name': name[:128], 'backend': 'CUDA', 'driver': driver[:64],
                                    'total_gb': float(total)/1024, 'available_gb': float(free)/1024})
                result['accelerator'] = devices
                if devices:
                    result['gpu_memory_gb'] = max(x['available_gb'] for x in devices)
        except (OSError, ValueError, subprocess.SubprocessError):
            # Missing vendor/OS facts do not imply zero resources or unsupported device.
            pass
        return result


def probe(node_id, grant, reader, now=None):
    grant.check(node_id, 'probe', now=now)
    return deployment.collect_probe(node_id, {node_id}, reader)


def recommend(snapshot, catalog, task_class):
    require(task_class in TASKS, 'TASK_NOT_QUALIFIED')
    total, available = snapshot.get('memory_total_gb'), snapshot.get('memory_available_gb')
    if not number(total) or not number(available):
        return {'state': 'UNKNOWN', 'reason': 'AVAILABLE_MEMORY_UNKNOWN', 'candidate': None}
    reserve = max(8, total * .25)
    usable = min(available, max(0, total-reserve))
    if not snapshot.get('unified_memory'):
        gpu = snapshot.get('gpu_memory_gb')
        if not number(gpu):
            return {'state': 'UNKNOWN', 'reason': 'GPU_AVAILABLE_UNKNOWN', 'candidate': None}
        usable = min(usable, max(0, gpu-1))
    fit = deployment.select_candidate(
        {'memory_available_gb': usable, 'free_storage_gb': snapshot.get('free_storage_gb')},
        catalog['models'], [m['id'] for m in catalog['models'] if task_class in m['task_classes']])
    return {'state': 'CANDIDATE_ONLY' if fit else 'SKIPPED',
            'reason': 'TASK_QUALITY_NOT_VERIFIED' if fit else 'RESOURCES_INSUFFICIENT', 'candidate': fit}


def onboarding(existing, candidate, prior_binding=None, authorized_binding=None,
               authorization_expires_at=None, now=None):
    """Pure install/upgrade decision. Never downloads or modifies customer settings."""
    if candidate is None:
        return {'state': 'SKIPPED', 'actions': []}
    binding = digest(candidate)
    same = (existing.get('provider_version') == candidate['provider_version'] and
            existing.get('model_digest') == candidate['manifest_sha256'])
    if existing.get('pending_unknown'):
        return {'state': 'UNKNOWN', 'actions': [], 'binding': binding}
    now = time.time() if now is None else now
    if (not number(now) or not number(authorization_expires_at) or now >= authorization_expires_at
            or authorized_binding != binding):
        return {'state': 'CONSENT_REQUIRED', 'actions': [], 'binding': binding}
    if same and prior_binding == binding:
        return {'state': 'REUSE_EXISTING', 'actions': [], 'binding': binding,
                'preserve_custom_config': True, 'runtime_validation': 'REQUIRED'}
    return {'state': 'INSTALL_ADAPTER_REQUIRED', 'actions': [], 'binding': binding,
            'preserve_custom_config': True, 'download_bytes': candidate['download_bytes']}


@dataclass(frozen=True)
class PinnedBlob:
    """One catalog-selected asset. No arbitrary URLs or executable payloads."""
    url: str
    size: int
    sha256: str
    kind: str

    def __post_init__(self):
        parsed = urlsplit(self.url)
        require(parsed.scheme == 'https' and parsed.hostname in
                {'github.com', 'registry.ollama.ai'} and not parsed.username and
                not parsed.password and not parsed.query and not parsed.fragment and
                parsed.port in (None, 443), 'ASSET_SOURCE')
        require(type(self.size) is int and 0 < self.size <= 40*1024**3, 'ASSET_SIZE')
        require(type(self.sha256) is str and re.fullmatch('[0-9a-f]{64}', self.sha256), 'ASSET_DIGEST')
        require(self.kind in {'runtime-archive', 'model-blob'}, 'ASSET_KIND')

    @property
    def name(self):
        return self.sha256 + '.blob'


def catalog_blob(candidate, catalog, *, kind, sha256):
    """Resolve only fixed catalog assets; model blob ownership is separate from model installation."""
    require(candidate in catalog['models'], 'ASSET_CANDIDATE_UNKNOWN')
    if kind == 'runtime-archive':
        asset = catalog['runtime'].get('darwin_asset', {})
        require(asset.get('sha256') == sha256, 'ASSET_NOT_PINNED')
        url = ('https://github.com/ollama/ollama/releases/download/v' +
               catalog['runtime']['version'] + '/' + asset['name'])
        return PinnedBlob(url, asset['bytes'], sha256, kind)
    require(kind == 'model-blob', 'ASSET_KIND')
    matches = [x for x in candidate['layers'] + ([candidate['config_blob']] if 'config_blob' in candidate else [])
               if x['digest'] == 'sha256:'+sha256]
    require(len(matches) == 1, 'ASSET_NOT_PINNED')
    return PinnedBlob('https://registry.ollama.ai/v2/library/' +
                      candidate['id'].split(':')[0] + '/blobs/sha256:'+sha256,
                      matches[0]['size'], sha256, kind)


@dataclass(frozen=True)
class LifecycleConsent:
    """Explicit effect authority, not inferred from probe/inference consent."""
    node_id: str
    binding: str
    expires_at: float
    actions: frozenset

    def __post_init__(self):
        require(type(self.node_id) is str and 0 < len(self.node_id) <= 128, 'LIFECYCLE_NODE')
        require(type(self.binding) is str and re.fullmatch('[0-9a-f]{64}', self.binding), 'LIFECYCLE_BINDING')
        require(number(self.expires_at), 'LIFECYCLE_EXPIRY')
        object.__setattr__(self, 'actions', frozenset(self.actions))
        require(self.actions <= {'stage', 'cleanup', 'install-runtime', 'uninstall-runtime', 'rollback-runtime', 'install-model', 'uninstall-model', 'rollback-model', 'start-service', 'stop-service', 'save-ownership', 'restore-ownership', 'confirm-idle'}, 'LIFECYCLE_SCOPE')

    def check(self, node_id, binding, action, now):
        require(number(now) and node_id == self.node_id and binding == self.binding and
                action in self.actions and now < self.expires_at, 'LIFECYCLE_CONSENT_REQUIRED')


def lifecycle_binding(node_id, root, candidate, blobs):
    return digest({'node': node_id, 'root': str(Path(root).absolute()),
                   'candidate': candidate, 'assets': [b.__dict__ for b in blobs]})


def model_manifest(candidate):
    """Verify fixed raw registry manifest; no mutable tag lookup or model execution."""
    raw=candidate.get('manifest_json')
    require(type(raw) is str and 0 < len(raw.encode()) <= 4096,'MODEL_MANIFEST_MISSING')
    require(hashlib.sha256(raw.encode()).hexdigest()==candidate['manifest_sha256'],'MODEL_MANIFEST_HASH')
    parsed=json.loads(raw)
    require(parsed.get('schemaVersion')==2 and parsed.get('layers') and
            type(candidate.get('config_blob')) is dict,'MODEL_MANIFEST_SHAPE')
    require({'digest':parsed['config']['digest'],'size':parsed['config']['size']}==candidate['config_blob'],
            'MODEL_CONFIG_BINDING')
    require([{'digest':x['digest'],'size':x['size']} for x in parsed['layers']]==candidate['layers'],
            'MODEL_LAYER_BINDING')
    for item in candidate['layers']+[candidate['config_blob']]:
        require(re.fullmatch('sha256:[0-9a-f]{64}',item['digest']) and
                type(item['size']) is int and item['size']>0,'MODEL_BLOB_SHAPE')
    require(len({x['digest'] for x in candidate['layers']+[candidate['config_blob']]})==
            len(candidate['layers'])+1,'MODEL_BLOB_DUPLICATE')
    require(re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]*:[A-Za-z0-9][A-Za-z0-9_.-]*',candidate['id']),
            'MODEL_REGISTRATION_NAME')
    return raw.encode()


def runtime_layout(asset):
    """Validate the exact inspected archive metadata, never execute tar instructions."""
    members = asset.get('members')
    require(type(members) is list and 0 < len(members) <= 64, 'RUNTIME_LAYOUT_UNVERIFIED')
    entries = {}
    for item in members:
        require(type(item) is dict, 'RUNTIME_MEMBER_SHAPE')
        name = item.get('name')
        require(type(name) is str and 0 < len(name) <= 128 and
                all(re.fullmatch('[A-Za-z0-9_.-]+', p) and p not in ('.', '..')
                    for p in name.split('/')) and len(name.split('/')) <= 3,
                'RUNTIME_MEMBER_PATH')
        require(name not in entries and item.get('type') in ('0', '2', '5') and
                type(item.get('size')) is int and item['size'] >= 0 and
                item.get('mode') in ('0o644', '0o755'), 'RUNTIME_MEMBER_SHAPE')
        require(item['type'] == '0' or item['size'] == 0, 'RUNTIME_MEMBER_SIZE')
        if item['type'] == '2':
            target = item.get('linkname')
            require(type(target) is str and re.fullmatch('[A-Za-z0-9_.-]+', target) and
                    target not in ('.','..'), 'RUNTIME_LINK_TARGET')
        else:
            require(item.get('linkname') == '', 'RUNTIME_LINK_TARGET')
        entries[name] = item
    require(sum(x['size'] for x in members) == asset.get('unpacked_bytes') and
            0 < asset['unpacked_bytes'] <= 2*1024**3, 'RUNTIME_UNPACKED_LIMIT')
    require(entries.get('ollama', {}).get('type') == '0', 'RUNTIME_EXECUTABLE_MISSING')
    for name,item in entries.items():
        parent = name.rpartition('/')[0]
        require(not parent or entries.get(parent,{}).get('type') == '5', 'RUNTIME_MEMBER_PARENT')
        if item['type'] == '2':
            target = parent+'/' if parent else ''
            target += item['linkname']; seen = {name}
            while entries.get(target,{}).get('type') == '2':
                require(target not in seen, 'RUNTIME_LINK_CYCLE'); seen.add(target)
                target = target.rpartition('/')[0] + ('/' if '/' in target else '') + entries[target]['linkname']
            require(entries.get(target,{}).get('type') == '0', 'RUNTIME_LINK_UNBOUND')
    return entries


class PinnedStage:
    """Pinned staging and explicitly authorized owned runtime/model file install.

    Reuses deployment budget and durable unknown ledger. Existing private root is
    the sole write scope. Fetcher returns a context-managed binary stream; default
    HTTPS transport allows only the observed pinned-runtime CDN edge.
    Receipts live in caller memory; a restart without them retains cleanup UNKNOWN.
    Runtime extraction requires the exact reviewed archive inventory. Service
    activation is a separately authorized original-handle controller.
    """
    def __init__(self, node_id, root, candidate, blobs, consent, budget, journal,
                 *, fetcher=None, clock=time.monotonic, wall_clock=time.time, catalog=None):
        require(type(node_id) is str and 0 < len(node_id) <= 128, 'LIFECYCLE_NODE')
        require(isinstance(budget, deployment.Budget), 'LIFECYCLE_BUDGET')
        require(isinstance(consent, LifecycleConsent), 'LIFECYCLE_CONSENT_REQUIRED')
        require(type(blobs) in (list, tuple) and 0 < len(blobs) <= 16 and
                all(isinstance(b, PinnedBlob) for b in blobs), 'ASSET_PLAN')
        require(len({b.name for b in blobs}) == len(blobs), 'ASSET_PLAN_DUPLICATE')
        self.plan_effect_count=len(blobs)+int('install-runtime' in consent.actions)+int('install-model' in consent.actions)
        require(budget.max_iterations >= self.plan_effect_count,'LIFECYCLE_ITERATION_BUDGET')
        catalog = load_catalog() if catalog is None else catalog
        self.catalog = json.loads(json.dumps(catalog))
        for blob in blobs:
            require(blob == catalog_blob(candidate, catalog, kind=blob.kind, sha256=blob.sha256),
                    'ASSET_NOT_PINNED')
        require(isinstance(journal, deployment.DurableJournal), 'DURABLE_JOURNAL_REQUIRED')
        self.node_id, self.root = node_id, Path(root).absolute()
        self.candidate, self.blobs = candidate, tuple(blobs)
        self.binding = lifecycle_binding(node_id, self.root, candidate, self.blobs)
        self.consent, self.wall_clock, self.clock = consent, wall_clock, clock
        self.journal, self.activity = journal, 'NEVER_STARTED'
        self.persistent_mode = 'save-ownership' in consent.actions
        self.restored = False
        self.started, self.max_seconds = clock(), budget.max_seconds
        consent.check(node_id, self.binding, 'stage', wall_clock())
        require(self.root == self.root.resolve(), 'STAGE_PARENT_ALIAS')
        info = self.root.lstat()
        require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and
                info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
                'STAGE_ROOT_NOT_PRIVATE')
        require(journal.path.parent == self.root, 'STAGE_JOURNAL_SCOPE')
        self.identity = (info.st_dev, info.st_ino)
        self.root_fd = os.open(self.root, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        self.closed = False
        try:
            opened = os.fstat(self.root_fd)
            require((opened.st_dev, opened.st_ino) == self.identity, 'STAGE_ROOT_CHANGED')
            # Same-root bounded metadata accounting, never a recursive scan.
            # Budget is total staged footprint, not just the newly fetched blob.
            existing_bytes, entries = 0, 0
            with os.scandir(self.root_fd) as directory:
                for entry in directory:
                    entries += 1
                    require(entries <= 32, 'STAGE_EXISTING_ENTRY_CAP')
                    metadata = entry.stat(follow_symlinks=False)
                    require(stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.getuid(),
                            'STAGE_EXISTING_TYPE_UNKNOWN')
                    existing_bytes += max(metadata.st_size, getattr(metadata, 'st_blocks', 0)*512)
                    require(existing_bytes <= 80*1024**3, 'STAGE_EXISTING_SIZE_CAP')
            self.receipts, self.failure, self.additional = {}, None, []
            self.runtime_tree, self.runtime_name, self.runtime_complete = {}, None, False
            self.model_tree, self.model_name, self.model_complete = {}, None, False
            self.fetcher = fetcher or self._fetch
            # DurableJournal permits 1MiB; reserve current+atomic replacement and
            # per-file directory/block overhead conservatively. Not a disk quota.
            peak_bytes = existing_bytes + sum(x.size for x in blobs) + 2*1024**2 + 4096*(len(blobs)+2)
            # Runtime and model copies coexist with staged blobs. Their footprint
            # is cumulative, never max(runtime, model). Reserve it on the first
            # download so an inadequate lifecycle plan cannot partially fetch.
            if 'install-runtime' in consent.actions:
                asset=self.catalog['runtime']['darwin_asset'];runtime_layout(asset)
                peak_bytes += asset['unpacked_bytes']+4096*len(asset['members'])
            if 'install-model' in consent.actions:
                model_manifest(candidate)
                assets=candidate['layers']+[candidate['config_blob']]
                peak_bytes += sum(x['size'] for x in assets)+len(candidate['manifest_json'].encode())+4096*(len(assets)+10)

            self.effects = tuple(deployment.Effect(node_id, 'download', b.sha256,
                               download_gb=b.size/1024**3,
                               peak_disk_gb=peak_bytes/1024**3,
                               recipe_digest=digest(b.__dict__)) for b in blobs)
            self.install_effect = None
            all_effects = self.effects
            if 'install-runtime' in consent.actions:
                asset = self.catalog['runtime']['darwin_asset']
                require(any(b.kind == 'runtime-archive' and b.sha256 == asset['sha256'] for b in blobs),
                        'RUNTIME_ARCHIVE_NOT_PLANNED')
                runtime_layout(asset)
                self.install_effect = deployment.Effect(node_id, 'install', asset['sha256'],
                    peak_disk_gb=peak_bytes/1024**3,
                    recipe_digest=digest(asset))
                all_effects += (self.install_effect,)
            self.model_effect = None
            if 'install-model' in consent.actions:
                model_manifest(candidate)
                expected_assets=candidate['layers']+[candidate['config_blob']]
                require({x['digest'].split(':')[1] for x in expected_assets} <= {b.sha256 for b in blobs},
                        'MODEL_ASSETS_NOT_PLANNED')
                self.model_effect=deployment.Effect(node_id,'install',candidate['manifest_sha256'],
                    peak_disk_gb=peak_bytes/1024**3,
                    recipe_digest=digest({'model':candidate,'layout':'OLLAMA_PRIVATE_LEGACY_V1'}))
                require(self.install_effect is None or self.model_effect.target != self.install_effect.target,
                        'EFFECT_TARGET_COLLISION')
                all_effects += (self.model_effect,)
            approval = deployment.Approval(node_id, frozenset(e.fingerprint() for e in all_effects), budget)
            self.runner = deployment.DeploymentRunner(approval, self._apply, clock=clock,
                                journal=journal, approved_effects=all_effects)
        except BaseException:
            os.close(self.root_fd); self.closed = True
            raise

    def _apply(self, effect, remaining):
        if self.model_effect is not None and effect == self.model_effect:
            return self._install_model(effect,remaining)
        return self._install(effect, remaining) if effect.action == 'install' else self._stage(effect, remaining)

    @staticmethod
    def _fetch(blob, timeout):
        request = Request(blob.url, headers={'Accept': 'application/octet-stream'})
        return build_opener(ProxyHandler({}), AssetRedirect(blob)).open(request, timeout=timeout)

    def _root_check(self):
        require(not self.closed, 'STAGE_CLOSED')
        a, b = os.fstat(self.root_fd), self.root.lstat()
        require((a.st_dev, a.st_ino) == self.identity == (b.st_dev, b.st_ino) and
                stat.S_ISDIR(b.st_mode) and stat.S_IMODE(b.st_mode) == 0o700 and
                b.st_uid == os.getuid(), 'STAGE_ROOT_CHANGED')

    def _stage(self, effect, remaining):
        blob = next(b for b in self.blobs if b.sha256 == effect.target)
        part = blob.name+'.part'
        fd, receipt = None, None
        deadline = self.clock()+remaining
        try:
            self.consent.check(self.node_id, self.binding, 'stage', self.wall_clock())
            self._root_check()
            require(self.clock() < deadline, 'STAGE_DEADLINE')
            # Both names must be absent; never overwrite prior or unowned content.
            for name in (blob.name, part):
                try: os.stat(name, dir_fd=self.root_fd, follow_symlinks=False)
                except FileNotFoundError: continue
                raise Stopped('STAGE_FILE_CONFLICT')
            fd = os.open(part, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600,
                         dir_fd=self.root_fd)
            info = os.fstat(fd)
            receipt = {'name': part, 'device': info.st_dev, 'inode': info.st_ino,
                       'bytes': 0, 'complete': False, 'sha256': blob.sha256,
                       'close_confirmed': False}
            self.receipts[blob.sha256] = receipt
            hasher, total = hashlib.sha256(), 0
            with self.fetcher(blob, max(.001, deadline-self.clock())) as source:
                while True:
                    require(self.clock() < deadline, 'STAGE_DEADLINE')
                    chunk = source.read(min(65536, blob.size-total+1))
                    require(type(chunk) is bytes, 'STAGE_SOURCE_TYPE')
                    require(self.clock() < deadline, 'STAGE_DEADLINE')
                    if not chunk: break
                    require(total+len(chunk) <= blob.size, 'STAGE_SIZE_LIMIT')
                    view = memoryview(chunk)
                    while view:
                        require(self.clock() < deadline, 'STAGE_DEADLINE')
                        count = os.write(fd, view)
                        require(type(count) is int and count > 0, 'STAGE_SHORT_WRITE')
                        view = view[count:]
                    total += len(chunk); hasher.update(chunk)
                    receipt['bytes'] = total
            require(total == blob.size, 'STAGE_LENGTH_MISMATCH')
            require(hasher.hexdigest() == blob.sha256, 'STAGE_HASH_MISMATCH')
            os.fsync(fd)
            require(self.clock() < deadline, 'STAGE_DEADLINE')
            final = os.fstat(fd)
            require((final.st_dev, final.st_ino) == (info.st_dev, info.st_ino) and
                    final.st_size == total, 'STAGE_IDENTITY_CHANGED')
            closing_fd, fd = fd, None  # consume before close; a raised close may have succeeded
            try:
                os.close(closing_fd)
            except OSError:
                self.additional.append('STAGE_CLOSE_UNKNOWN')
                raise Stopped('STAGE_CLOSE_UNKNOWN') from None
            receipt['close_confirmed'] = True
            self._root_check()
            require(self.clock() < deadline, 'STAGE_DEADLINE')
            os.link(part, blob.name, src_dir_fd=self.root_fd, dst_dir_fd=self.root_fd,
                    follow_symlinks=False)
            os.unlink(part, dir_fd=self.root_fd)
            receipt.update(name=blob.name, complete=True)
            snapshot = os.stat(blob.name, dir_fd=self.root_fd, follow_symlinks=False)
            receipt.update(size=snapshot.st_size, mtime_ns=snapshot.st_mtime_ns, ctime_ns=snapshot.st_ctime_ns)
            os.fsync(self.root_fd)
            require(self.clock() < deadline, 'STAGE_DEADLINE')
            return 'SUCCEEDED'
        except Exception as error:
            if self.failure is None:
                self.failure = str(error) if isinstance(error, Stopped) else 'STAGE_IO_UNKNOWN'
            return 'UNKNOWN'
        finally:
            if fd is not None:
                try:
                    snapshot = os.fstat(fd)
                    if receipt is not None:
                        receipt.update(size=snapshot.st_size, mtime_ns=snapshot.st_mtime_ns, ctime_ns=snapshot.st_ctime_ns)
                except OSError:
                    self.additional.append('STAGE_METADATA_UNKNOWN')
                finally:
                    closing_fd, fd = fd, None
                    try:
                        os.close(closing_fd)
                        if receipt is not None:
                            receipt['close_confirmed'] = True
                    except OSError:
                        self.additional.append('STAGE_CLOSE_UNKNOWN')
                        # Never fstat/retry this numeric FD after close was attempted.

    def stage(self):
        require(not self.restored, 'RESTORED_CONTROLLER_NO_DOWNLOAD_AUTHORITY')
        self.consent.check(self.node_id, self.binding, 'stage', self.wall_clock())
        self._root_check()
        results = self.runner.execute_plan(self.effects)
        complete = len(results) == len(self.effects) and all(x['state'] == 'SUCCEEDED' for x in results)
        return {'state': 'STAGED_NOT_INSTALLED' if complete else 'STOP',
                'effects': results, 'reason': self.failure, 'additional': tuple(self.additional),
                'installation': 'NOT_PERFORMED',
                'archive_layout': ('FIXED_METADATA_AVAILABLE' if self.catalog.get('runtime', {}).get('darwin_asset', {}).get('members') else 'UNVERIFIED'),
                'runtime_validation': 'NOT_RUN', 'task_qualification': 'NOT_RUN'}

    def _capture_runtime(self, name, info, *, tree=None, **extra):
        tree = self.runtime_tree if tree is None else tree
        tree[name] = dict(device=info.st_dev,inode=info.st_ino,
            size=info.st_size,mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns,
            mode=stat.S_IMODE(info.st_mode),kind=stat.S_IFMT(info.st_mode),**extra)

    def _runtime_parent(self, name, *, tree=None, top=None):
        """Open only our already-created directories, never a symlink parent."""
        tree = self.runtime_tree if tree is None else tree
        top = self.runtime_name if top is None else top
        fd = os.open(top,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=self.root_fd)
        try:
            info=os.fstat(fd); expected=tree['']
            require((info.st_dev,info.st_ino)==(expected['device'],expected['inode']), 'RUNTIME_ROOT_CHANGED')
            partial=''
            for component in name.split('/')[:-1]:
                following=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                old,fd=fd,following
                self._close_parent(old)
                partial=partial+'/'+component if partial else component
                info=os.fstat(fd);expected=tree[partial]
                require((info.st_dev,info.st_ino)==(expected['device'],expected['inode']), 'RUNTIME_PARENT_CHANGED')
            return fd
        except BaseException:
            self._close_parent(fd)
            raise

    def _close_parent(self,fd):
        primary=sys.exc_info()[1]
        try:os.close(fd)
        except OSError:
            self.additional.append('RUNTIME_PARENT_CLOSE_UNKNOWN')
            if primary is None:raise Stopped('RUNTIME_PARENT_CLOSE_UNKNOWN') from None

    def _refresh_runtime_directories(self, *, tree=None, top=None):
        tree = self.runtime_tree if tree is None else tree
        top = self.runtime_name if top is None else top
        for name,receipt in list(tree.items()):
            if receipt['kind'] != stat.S_IFDIR:continue
            if not name:
                info=os.stat(top,dir_fd=self.root_fd,follow_symlinks=False)
            else:
                parent=self._runtime_parent(name,tree=tree,top=top)
                try:info=os.stat(name.split('/')[-1],dir_fd=parent,follow_symlinks=False)
                finally:self._close_parent(parent)
            require((info.st_dev,info.st_ino)==(receipt['device'],receipt['inode']), 'RUNTIME_DIRECTORY_CHANGED')
            self._capture_runtime(name,info,tree=tree)

    def _install(self, effect, remaining):
        """Install pinned runtime files only. No service execution, model pull or qualification."""
        deadline=self.clock()+remaining
        asset=self.catalog['runtime']['darwin_asset']
        entries=runtime_layout(asset)
        archive=asset['sha256']+'.blob'
        final=asset['sha256']+'.runtime';partial=final+'.part'
        try:
            self.consent.check(self.node_id,self.binding,'install-runtime',self.wall_clock())
            self._root_check()
            receipt=self.receipts.get(asset['sha256'],{})
            require(receipt.get('complete') and receipt.get('close_confirmed'), 'RUNTIME_STAGE_REQUIRED')
            for name in (partial,final):
                try:os.stat(name,dir_fd=self.root_fd,follow_symlinks=False)
                except FileNotFoundError:continue
                raise Stopped('RUNTIME_INSTALL_CONFLICT')
            fd=os.open(archive,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=self.root_fd)
            with os.fdopen(fd,'rb') as source:
                before=os.fstat(source.fileno())
                require((before.st_dev,before.st_ino,before.st_size)==
                        (receipt['device'],receipt['inode'],asset['bytes']), 'RUNTIME_ARCHIVE_CHANGED')
                hasher=hashlib.sha256();length=0
                while True:
                    require(self.clock()<deadline,'RUNTIME_INSTALL_DEADLINE')
                    chunk=source.read(min(65536,asset['bytes']-length+1))
                    if not chunk:break
                    length+=len(chunk);require(length<=asset['bytes'],'RUNTIME_ARCHIVE_SIZE')
                    hasher.update(chunk)
                require(length==asset['bytes'] and hasher.hexdigest()==asset['sha256'],'RUNTIME_ARCHIVE_HASH')
                source.seek(0)
                with tarfile.open(fileobj=source,mode='r:gz') as bundle:
                    actual=[]
                    for member in bundle:
                        require(len(actual)<64,'RUNTIME_MEMBER_CAP')
                        kind='0' if member.isfile() else ('2' if member.issym() else ('5' if member.isdir() else '?'))
                        actual.append(dict(name=member.name,size=member.size,type=kind,
                                           mode=oct(member.mode),linkname=member.linkname))
                    require(actual==asset['members'],'RUNTIME_ARCHIVE_LAYOUT_CHANGED')
                    require(self.clock()<deadline,'RUNTIME_INSTALL_DEADLINE')
                    os.mkdir(partial,0o700,dir_fd=self.root_fd);self.runtime_name=partial
                    self._capture_runtime('',os.stat(partial,dir_fd=self.root_fd,follow_symlinks=False))
                    # New private tree only; regular files first, exact symlinks last.
                    for name,item in entries.items():
                        require(self.clock()<deadline,'RUNTIME_INSTALL_DEADLINE')
                        if item['type']=='2':continue
                        parent=self._runtime_parent(name)
                        try:
                            leaf=name.split('/')[-1]
                            if item['type']=='5':
                                os.mkdir(leaf,0o700,dir_fd=parent)
                                self._capture_runtime(name,os.stat(leaf,dir_fd=parent,follow_symlinks=False))
                            else:
                                fd=os.open(leaf,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
                                with os.fdopen(fd,'wb') as output:
                                    self._capture_runtime(name,os.fstat(output.fileno()),close_confirmed=False)
                                    content=bundle.extractfile(name);count=0;h=hashlib.sha256()
                                    require(content is not None,'RUNTIME_MEMBER_MISSING')
                                    with content:
                                        while True:
                                            require(self.clock()<deadline,'RUNTIME_INSTALL_DEADLINE')
                                            chunk=content.read(min(65536,item['size']-count+1))
                                            if not chunk:break
                                            count+=len(chunk);require(count<=item['size'],'RUNTIME_MEMBER_SIZE')
                                            require(output.write(chunk)==len(chunk),'RUNTIME_MEMBER_SHORT_WRITE');h.update(chunk)
                                    require(count==item['size'],'RUNTIME_MEMBER_SIZE')
                                    output.flush();os.fchmod(output.fileno(),int(item['mode'],8));os.fsync(output.fileno())
                                info=os.stat(leaf,dir_fd=parent,follow_symlinks=False)
                                self._capture_runtime(name,info,sha256=h.hexdigest(),close_confirmed=True)
                        finally:self._close_parent(parent)
                    for name,item in entries.items():
                        if item['type']!='2':continue
                        require(self.clock()<deadline,'RUNTIME_INSTALL_DEADLINE')
                        parent=self._runtime_parent(name)
                        try:
                            os.symlink(item['linkname'],name.split('/')[-1],dir_fd=parent)
                            self._capture_runtime(name,os.stat(name.split('/')[-1],dir_fd=parent,follow_symlinks=False),target=item['linkname'])
                        finally:self._close_parent(parent)
                after=os.fstat(source.fileno())
                require((after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)==
                        (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns),
                        'RUNTIME_ARCHIVE_CHANGED')
            self._refresh_runtime_directories()
            require(self.clock()<deadline,'RUNTIME_INSTALL_DEADLINE');self._root_check()
            # Cooperative private root; destination was absent and never overwritten deliberately.
            require(not os.path.lexists(self.root/final),'RUNTIME_INSTALL_CONFLICT')
            os.rename(partial,final,src_dir_fd=self.root_fd,dst_dir_fd=self.root_fd)
            self.runtime_name=final;self.runtime_complete=True
            self._refresh_runtime_directories();os.fsync(self.root_fd)
            require(self.clock()<deadline,'RUNTIME_INSTALL_DEADLINE')
            return 'SUCCEEDED'
        except Exception as error:
            if self.failure is None:self.failure=str(error) if isinstance(error,Stopped) else 'RUNTIME_INSTALL_IO_UNKNOWN'
            if self.runtime_name is not None:
                try:self._refresh_runtime_directories()
                except Exception:self.additional.append('RUNTIME_DIRECTORY_STATE_UNKNOWN')
            return 'UNKNOWN'

    def install_runtime(self):
        self.consent.check(self.node_id,self.binding,'install-runtime',self.wall_clock())
        require(self.install_effect is not None,'RUNTIME_INSTALL_NOT_APPROVED')
        result=self.runner.run(self.install_effect)
        return {'state':'RUNTIME_FILES_INSTALLED_UNVALIDATED' if result['state']=='SUCCEEDED' else 'STOP',
                'effect':result,'reason':self.failure,'runtime_validation':'NOT_RUN',
                'task_qualification':'NOT_RUN','service_started':False}

    def validate_runtime_files(self):
        """Read-only verification for a separately authorized owned service start."""
        self._root_check()
        require(self.runtime_complete and self.runtime_name is not None, 'RUNTIME_INSTALL_INCOMPLETE')
        self._validate_runtime_tree(self.started+self.max_seconds)
        return {'runtime_path':str(self.root/self.runtime_name/'ollama'),
                'root_identity':self.identity,
                'archive_sha256':self.catalog['runtime']['darwin_asset']['sha256'],
                'binary_receipt':dict(self.runtime_tree['ollama']),
                'runtime_validation':'NOT_RUN'}

    def _validate_runtime_tree(self, deadline, *, tree=None, top=None):
        tree = self.runtime_tree if tree is None else tree
        top = self.runtime_name if top is None else top
        # First validate every object before deleting any, including exact directory inventory.
        for name,receipt in tree.items():
            require(self.clock()<deadline,'RUNTIME_REMOVE_DEADLINE')
            if not name:
                info=os.stat(top,dir_fd=self.root_fd,follow_symlinks=False)
                parent=None
            else:
                parent=self._runtime_parent(name,tree=tree,top=top)
                info=os.stat(name.split('/')[-1],dir_fd=parent,follow_symlinks=False)
            try:
                require((info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,stat.S_IMODE(info.st_mode),stat.S_IFMT(info.st_mode))==
                    (receipt['device'],receipt['inode'],receipt['size'],receipt['mtime_ns'],receipt['ctime_ns'],receipt['mode'],receipt['kind']),
                    'RUNTIME_REMOVE_IDENTITY_UNKNOWN')
                if receipt['kind']==stat.S_IFREG:
                    require(receipt.get('close_confirmed') and info.st_nlink==1,'RUNTIME_REMOVE_CLOSE_UNKNOWN')
                    fd=os.open(name.split('/')[-1],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent)
                    with os.fdopen(fd,'rb') as value:
                        h=hashlib.sha256();count=0
                        while True:
                            require(self.clock()<deadline,'RUNTIME_REMOVE_DEADLINE')
                            chunk=value.read(min(65536,receipt['size']-count+1))
                            if not chunk:break
                            count+=len(chunk);require(count<=receipt['size'],'RUNTIME_REMOVE_SIZE_CHANGED');h.update(chunk)
                    require(count==receipt['size'] and h.hexdigest()==receipt['sha256'],'RUNTIME_REMOVE_HASH_CHANGED')
                elif receipt['kind']==stat.S_IFLNK:
                    require(os.readlink(name.split('/')[-1],dir_fd=parent)==receipt['target'],'RUNTIME_REMOVE_LINK_CHANGED')
                elif receipt['kind']==stat.S_IFDIR:
                    directory_fd = (os.open(top,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=self.root_fd)
                                    if not name else os.open(name.split('/')[-1],os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent))
                    try:
                        expected={n[len(name)+1:] if name else n for n in tree
                                  if n and n.rpartition('/')[0]==name}
                        actual=set()
                        with os.scandir(directory_fd) as children:
                            for child in children:
                                require(len(actual)<64,'RUNTIME_REMOVE_ENTRY_CAP');actual.add(child.name)
                        require(actual==expected,'RUNTIME_REMOVE_UNOWNED_ENTRY')
                    finally:self._close_parent(directory_fd)
            finally:
                if parent is not None:self._close_parent(parent)

    def _remove_tree(self,tree,top,deadline):
        for name in sorted((n for n in tree if n), key=lambda n:(n.count('/'),n), reverse=True):
            require(self.clock()<deadline,'RUNTIME_REMOVE_DEADLINE')
            parent=self._runtime_parent(name,tree=tree,top=top)
            try:
                receipt=tree[name]
                current=os.stat(name.split('/')[-1],dir_fd=parent,follow_symlinks=False)
                require((current.st_dev,current.st_ino,stat.S_IFMT(current.st_mode))==
                        (receipt['device'],receipt['inode'],receipt['kind']),'RUNTIME_REMOVE_IDENTITY_UNKNOWN')
                if receipt['kind']==stat.S_IFDIR:os.rmdir(name.split('/')[-1],dir_fd=parent)
                else:
                    require((current.st_size,current.st_mtime_ns,current.st_ctime_ns)==
                            (receipt['size'],receipt['mtime_ns'],receipt['ctime_ns']),'RUNTIME_REMOVE_IDENTITY_UNKNOWN')
                    os.unlink(name.split('/')[-1],dir_fd=parent)
            finally:self._close_parent(parent)
        require(self.clock()<deadline,'RUNTIME_REMOVE_DEADLINE')
        os.rmdir(top,dir_fd=self.root_fd);os.fsync(self.root_fd)

    def remove_runtime(self, consent, *, idle_confirmed=False, rollback=False):
        """Explicit same-session owned uninstall/rollback. No recursive blind deletion."""
        action='rollback-runtime' if rollback else 'uninstall-runtime'
        consent.check(self.node_id,self.binding,action,self.wall_clock())
        require(idle_confirmed is True,'RUNTIME_IDLE_UNCONFIRMED')
        if self.activity != 'NEVER_STARTED':
            consent.check(self.node_id, self.binding, 'confirm-idle', self.wall_clock())
        require(self.runtime_name is not None and self.runtime_tree,'RUNTIME_OWNERSHIP_UNKNOWN')
        self._root_check()
        deadline=self.started+self.max_seconds
        self._validate_runtime_tree(deadline)
        self._mark_owned_mutation()
        self._remove_tree(self.runtime_tree,self.runtime_name,deadline)
        self.runtime_name=None;self.runtime_tree.clear();self.runtime_complete=False
        if self.persistent_mode: self.save_ownership()
        return {'state':'OWNED_RUNTIME_REMOVED','journal_retained':True,'other_installations_modified':False}

    def _install_model(self,effect,remaining):
        """Offline registration in a new private Ollama legacy model store, never a pull."""
        deadline=self.clock()+remaining;manifest=model_manifest(self.candidate)
        final=self.candidate['manifest_sha256']+'.models';partial=final+'.part'
        tree=self.model_tree
        try:
            self.consent.check(self.node_id,self.binding,'install-model',self.wall_clock());self._root_check()
            for name in (partial,final):
                try:os.stat(name,dir_fd=self.root_fd,follow_symlinks=False)
                except FileNotFoundError:continue
                raise Stopped('MODEL_INSTALL_CONFLICT')
            assets=self.candidate['layers']+[self.candidate['config_blob']]
            for item in assets:
                receipt=self.receipts.get(item['digest'].split(':')[1],{})
                require(receipt.get('complete') and receipt.get('close_confirmed'),'MODEL_STAGE_REQUIRED')
            os.mkdir(partial,0o700,dir_fd=self.root_fd);self.model_name=partial
            self._capture_runtime('',os.stat(partial,dir_fd=self.root_fd,follow_symlinks=False),tree=tree)
            model,tag=self.candidate['id'].split(':')
            directories=['blobs','manifests','manifests/registry.ollama.ai',
                'manifests/registry.ollama.ai/library','manifests/registry.ollama.ai/library/'+model]
            for name in directories:
                require(self.clock()<deadline,'MODEL_INSTALL_DEADLINE')
                parent=self._runtime_parent(name,tree=tree,top=partial)
                try:
                    os.mkdir(name.split('/')[-1],0o700,dir_fd=parent)
                    self._capture_runtime(name,os.stat(name.split('/')[-1],dir_fd=parent,follow_symlinks=False),tree=tree)
                finally:self._close_parent(parent)
            for item in assets:
                sha=item['digest'].split(':')[1];receipt=self.receipts[sha]
                name='blobs/sha256-'+sha;parent=self._runtime_parent(name,tree=tree,top=partial)
                try:
                    input_fd=os.open(sha+'.blob',os.O_RDONLY|os.O_NOFOLLOW,dir_fd=self.root_fd)
                    with os.fdopen(input_fd,'rb') as source:
                        before=os.fstat(source.fileno())
                        require((before.st_dev,before.st_ino,before.st_size)==
                                (receipt['device'],receipt['inode'],item['size']),'MODEL_STAGE_CHANGED')
                        self._write_registered_file(name,parent,source,item['size'],sha,deadline)
                        after=os.fstat(source.fileno())
                        require((after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)==
                                (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns),
                                'MODEL_STAGE_CHANGED')
                finally:self._close_parent(parent)
            name='manifests/registry.ollama.ai/library/'+model+'/'+tag
            parent=self._runtime_parent(name,tree=tree,top=partial)
            try:
                import io
                self._write_registered_file(name,parent,io.BytesIO(manifest),len(manifest),
                                             self.candidate['manifest_sha256'],deadline)
            finally:self._close_parent(parent)
            self._refresh_runtime_directories(tree=tree,top=partial)
            require(self.clock()<deadline,'MODEL_INSTALL_DEADLINE');self._root_check()
            require(not os.path.lexists(self.root/final),'MODEL_INSTALL_CONFLICT')
            os.rename(partial,final,src_dir_fd=self.root_fd,dst_dir_fd=self.root_fd)
            self.model_name=final;self.model_complete=True
            self._refresh_runtime_directories(tree=tree,top=final);os.fsync(self.root_fd)
            require(self.clock()<deadline,'MODEL_INSTALL_DEADLINE')
            return 'SUCCEEDED'
        except Exception as error:
            if self.failure is None:self.failure=str(error) if isinstance(error,Stopped) else 'MODEL_INSTALL_IO_UNKNOWN'
            if self.model_name is not None:
                try:self._refresh_runtime_directories(tree=tree,top=self.model_name)
                except Exception:self.additional.append('MODEL_DIRECTORY_STATE_UNKNOWN')
            return 'UNKNOWN'

    def _write_registered_file(self,name,parent,source,size,sha,deadline):
        fd=os.open(name.split('/')[-1],os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
        tree=self.model_tree
        with os.fdopen(fd,'wb') as output:
            self._capture_runtime(name,os.fstat(output.fileno()),tree=tree,close_confirmed=False)
            count=0;h=hashlib.sha256()
            while True:
                require(self.clock()<deadline,'MODEL_INSTALL_DEADLINE')
                chunk=source.read(min(65536,size-count+1))
                if not chunk:break
                count+=len(chunk);require(count<=size,'MODEL_REGISTER_SIZE')
                require(output.write(chunk)==len(chunk),'MODEL_REGISTER_SHORT_WRITE');h.update(chunk)
            require(count==size and h.hexdigest()==sha,'MODEL_REGISTER_HASH')
            output.flush();os.fsync(output.fileno())
        self._capture_runtime(name,os.stat(name.split('/')[-1],dir_fd=parent,follow_symlinks=False),
                              tree=tree,sha256=sha,close_confirmed=True)

    def install_model(self):
        self.consent.check(self.node_id,self.binding,'install-model',self.wall_clock())
        require(self.model_effect is not None,'MODEL_INSTALL_NOT_APPROVED')
        result=self.runner.run(self.model_effect)
        return {'state':'MODEL_FILES_REGISTERED_UNVALIDATED' if result['state']=='SUCCEEDED' else 'STOP',
                'effect':result,'reason':self.failure,'runtime_validation':'NOT_RUN',
                'task_qualification':'NOT_RUN','service_started':False}

    def validate_model_files(self):
        self._root_check()
        require(self.model_complete and self.model_name is not None,'MODEL_REGISTRATION_INCOMPLETE')
        self._validate_runtime_tree(self.started+self.max_seconds,tree=self.model_tree,top=self.model_name)
        return {'models_root':str(self.root/self.model_name),'manifest_sha256':self.candidate['manifest_sha256'],
                'model_validation':'NOT_RUN','qualified':False}

    def remove_model(self,consent,*,idle_confirmed=False,rollback=False):
        action='rollback-model' if rollback else 'uninstall-model'
        consent.check(self.node_id,self.binding,action,self.wall_clock())
        require(idle_confirmed is True,'MODEL_IDLE_UNCONFIRMED')
        if self.activity != 'NEVER_STARTED':
            consent.check(self.node_id, self.binding, 'confirm-idle', self.wall_clock())
        require(self.model_name is not None and self.model_tree,'MODEL_OWNERSHIP_UNKNOWN')
        self._root_check();deadline=self.started+self.max_seconds
        self._validate_runtime_tree(deadline,tree=self.model_tree,top=self.model_name)
        self._mark_owned_mutation()
        self._remove_tree(self.model_tree,self.model_name,deadline)
        self.model_name=None;self.model_tree.clear();self.model_complete=False
        if self.persistent_mode: self.save_ownership()
        return {'state':'OWNED_MODEL_REMOVED','journal_retained':True,'other_models_modified':False}

    def cleanup(self, consent):
        """Explicit cleanup only of same-session owned entries; no recursive deletion."""
        consent.check(self.node_id, self.binding, 'cleanup', self.wall_clock())
        self._root_check()
        require(self.clock()-self.started < self.max_seconds, 'CLEANUP_DEADLINE')
        for receipt in self.receipts.values():
            require(receipt.get('close_confirmed') is True, 'CLEANUP_CLOSE_UNKNOWN')
            info = os.stat(receipt['name'], dir_fd=self.root_fd, follow_symlinks=False)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid() and
                    stat.S_IMODE(info.st_mode) == 0o600 and
                    (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) ==
                    (receipt['device'], receipt['inode'], receipt.get('size'),
                     receipt.get('mtime_ns'), receipt.get('ctime_ns')), 'CLEANUP_IDENTITY_UNKNOWN')
        if self.receipts: self._mark_owned_mutation()
        for receipt in self.receipts.values():
            require(self.clock()-self.started < self.max_seconds, 'CLEANUP_DEADLINE')
            os.unlink(receipt['name'], dir_fd=self.root_fd)
        os.fsync(self.root_fd)
        require(self.clock()-self.started < self.max_seconds, 'CLEANUP_DEADLINE')
        self.receipts.clear()
        if self.persistent_mode: self.save_ownership()
        return {'state': 'OWNED_STAGE_REMOVED', 'runtime_uninstalled': False,
                'journal_retained': True}

    def _mark_owned_mutation(self):
        """Crash before final checkpoint must not leave a stale valid owner tree."""
        if not self.persistent_mode:
            return
        self.consent.check(self.node_id, self.binding, 'save-ownership', self.wall_clock())
        require(self.clock() < self.started+self.max_seconds, 'OWNERSHIP_SAVE_DEADLINE')
        owned = self.journal.load_owned_files(self.node_id)
        require(owned is not None, 'OWNERSHIP_NOT_RECORDED_NO_ADOPTION')
        owned['io_state'] = 'UNKNOWN'
        self.journal.save_owned_files(self.node_id, owned)
        require(self.clock() < self.started+self.max_seconds, 'OWNERSHIP_SAVE_DEADLINE')

    def save_ownership(self):
        """Save only our captured creations, never infer authority from a record."""
        self.consent.check(self.node_id, self.binding, 'save-ownership', self.wall_clock())
        self._root_check()
        require(self.clock() < self.started+self.max_seconds, 'OWNERSHIP_SAVE_DEADLINE')
        confirmed = (not self.additional and
                     all(x.get('close_confirmed') is True for x in self.receipts.values()) and
                     all(x.get('close_confirmed') is True and x.get('sha256')
                         for tree in (self.runtime_tree, self.model_tree) for x in tree.values()
                         if x['kind'] == stat.S_IFREG))
        snapshot = {'schema': 1, 'binding': self.binding,
                    'root_binding': digest(str(self.root)),
                    'root_identity': {'dev': self.identity[0], 'ino': self.identity[1]},
                    'runtime_pin': self.catalog['runtime']['darwin_asset']['sha256'],
                    'model_pin': self.candidate['manifest_sha256'],
                    'io_state': 'CONFIRMED' if confirmed else 'UNKNOWN',
                    'blobs': self.receipts,
                    'runtime': {'name': self.runtime_name, 'complete': self.runtime_complete, 'tree': self.runtime_tree},
                    'model': {'name': self.model_name, 'complete': self.model_complete, 'tree': self.model_tree},
                    'activity': self.activity}
        if self.activity not in {'NEVER_STARTED', 'POSSIBLY_ACTIVE', 'DIRECT_EXIT_DESCENDANTS_UNKNOWN'}:
            snapshot.pop('activity')  # Legacy absence stays UNKNOWN, never idle.
        # Existing elapsed/cost/iteration reservations are never reset.
        old = self.journal.load(self.node_id)
        self.journal({'elapsed_seconds': max(old['elapsed_seconds'], self.clock()-self.started)})
        self.journal.save_owned_files(self.node_id, snapshot)
        require(self.clock() < self.started+self.max_seconds, 'OWNERSHIP_SAVE_DEADLINE')
        self.persistent_mode = True
        return {'state': 'OWNERSHIP_RECORDED_NOT_AUTHORITY', 'activity': self.activity}

    @classmethod
    def restore_owned(cls, node_id, root, candidate, blobs, consent, budget, journal,
                      *, clock=time.monotonic, wall_clock=time.time, catalog=None):
        """Fresh authority plus bounded full revalidation; no install or PID adoption."""
        require(isinstance(consent, LifecycleConsent) and isinstance(budget, deployment.Budget),
                'RESTORE_AUTHORITY_AND_BUDGET_REQUIRED')
        root = Path(root).absolute()
        binding = lifecycle_binding(node_id, root, candidate, blobs)
        consent.check(node_id, binding, 'restore-ownership', wall_clock())
        require(isinstance(journal, deployment.DurableJournal) and journal.path.parent == root,
                'RESTORE_JOURNAL_SCOPE')
        saved = journal.load(node_id)
        owned = journal.load_owned_files(node_id)
        require(owned is not None, 'OWNERSHIP_NOT_RECORDED_NO_ADOPTION')
        catalog = load_catalog() if catalog is None else catalog
        require(owned['binding'] == binding and owned['root_binding'] == digest(str(root)) and
                owned['runtime_pin'] == catalog['runtime']['darwin_asset']['sha256'] and
                owned['model_pin'] == candidate['manifest_sha256'] and
                owned['io_state'] == 'CONFIRMED', 'OWNERSHIP_BINDING_OR_IO_UNKNOWN')
        for blob in blobs:
            require(blob == catalog_blob(candidate, catalog, kind=blob.kind, sha256=blob.sha256),
                    'ASSET_NOT_PINNED')
        for field, limit in (('download_gb', budget.max_download_gb),
                             ('peak_disk_gb', budget.max_peak_disk_gb),
                             ('iterations', budget.max_iterations), ('restarts', budget.max_restarts),
                             ('elapsed_seconds', budget.max_seconds)):
            require(number(saved.get(field)) and saved[field] <= limit, 'RESTORE_BUDGET_ALREADY_CONSUMED')
        info = root.lstat()
        identity = (owned['root_identity']['dev'], owned['root_identity']['ino'])
        require(root == root.resolve() and stat.S_ISDIR(info.st_mode) and
                stat.S_IMODE(info.st_mode) == 0o700 and info.st_uid == os.getuid() and
                (info.st_dev, info.st_ino) == identity, 'RESTORE_ROOT_IDENTITY_CHANGED')
        self = cls.__new__(cls)
        self.node_id, self.root, self.identity = node_id, root, identity
        self.candidate, self.catalog, self.blobs = candidate, catalog, tuple(blobs)
        self.binding, self.consent, self.journal = binding, consent, journal
        self.clock, self.wall_clock = clock, wall_clock
        self.started, self.max_seconds = clock()-saved['elapsed_seconds'], budget.max_seconds
        self.receipts, self.failure, self.additional = owned['blobs'], None, []
        self.activity = owned.get('activity', 'UNKNOWN')
        self.persistent_mode, self.restored = True, True
        for kind in ('runtime', 'model'):
            setattr(self, kind+'_name', owned[kind]['name'])
            setattr(self, kind+'_complete', owned[kind]['complete'])
            setattr(self, kind+'_tree', owned[kind]['tree'])
        self.effects = (); self.install_effect = self.model_effect = None
        self.closed = False
        self.root_fd = os.open(root, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            self._root_check()
            self.runner = deployment.DeploymentRunner(
                deployment.Approval(node_id, frozenset(), budget), self._apply,
                clock=clock, journal=journal)
            pins = {b.sha256: b for b in blobs}
            require(set(self.receipts) <= set(pins), 'RESTORE_UNOWNED_BLOB')
            for pin, receipt in self.receipts.items():
                require(clock() < self.started+self.max_seconds, 'RESTORE_DEADLINE')
                metadata = os.stat(receipt['name'], dir_fd=self.root_fd, follow_symlinks=False)
                require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1 and
                        metadata.st_uid == os.getuid() and stat.S_IMODE(metadata.st_mode) == 0o600 and
                        (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns) ==
                        (receipt['device'], receipt['inode'], receipt.get('size'), receipt.get('mtime_ns'), receipt.get('ctime_ns')),
                        'RESTORE_BLOB_IDENTITY_CHANGED')
                if receipt['complete']:
                    require(metadata.st_size == pins[pin].size, 'RESTORE_BLOB_SIZE_CHANGED')
                    fd = os.open(receipt['name'], os.O_RDONLY|os.O_NOFOLLOW, dir_fd=self.root_fd)
                    with os.fdopen(fd, 'rb') as source:
                        before = os.fstat(source.fileno()); h = hashlib.sha256(); total = 0
                        require((before.st_dev, before.st_ino) == (metadata.st_dev, metadata.st_ino), 'RESTORE_BLOB_CHANGED')
                        while True:
                            require(clock() < self.started+self.max_seconds, 'RESTORE_DEADLINE')
                            chunk = source.read(min(65536, metadata.st_size-total+1))
                            if not chunk: break
                            total += len(chunk); require(total <= metadata.st_size, 'RESTORE_BLOB_CHANGED'); h.update(chunk)
                        after = os.fstat(source.fileno())
                        require((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) ==
                                (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns) and
                                total == metadata.st_size and h.hexdigest() == pin, 'RESTORE_BLOB_HASH_CHANGED')
            for kind in ('runtime', 'model'):
                tree, top = getattr(self, kind+'_tree'), getattr(self, kind+'_name')
                if top is not None:
                    self._validate_runtime_tree(self.started+self.max_seconds, tree=tree, top=top)
            # Evidence does not clear a pending effect or create execution rights.
            return self
        except BaseException:
            self.close()
            raise

    def close(self):
        if not self.closed:
            closing_fd, self.root_fd = self.root_fd, None
            self.closed = True
            os.close(closing_fd)


def inspect_existing_lifecycle(node_id, grant, client, candidate, now=None):
    """Inspect real API facts under explicit consent, never infer task qualification."""
    require(client.version == candidate['provider_version'] and client.model == candidate['id'] and
            client.pin == candidate['manifest_sha256'], 'LIFECYCLE_CLIENT_BINDING')
    grant.check(node_id, 'inspect-runtime', digest(candidate), now=now)
    facts = client.inspect()
    return {'state': 'REUSE_EXISTING_TASK_QUALIFICATION_REQUIRED',
            'provider_version': facts['provider_version'], 'model_digest': facts['model_digest'],
            'configuration_modified': False, 'download_bytes': 0, 'qualified': False}


def lifecycle_readiness(existing, candidate, *, real_runtime_ref=None,
                        real_task_ref=None, evidence_kind='SYNTHETIC'):
    """Read supplied evidence only: synthetic or install success never grants qualification."""
    if existing.get('pending_unknown'):
        return {'state': 'UNKNOWN', 'qualified': False}
    same = (existing.get('provider_version') == candidate['provider_version'] and
            existing.get('model_digest') == candidate['manifest_sha256'])
    real = (evidence_kind == 'REAL' and same and
            type(real_runtime_ref) is str and 0 < len(real_runtime_ref) <= 128 and
            type(real_task_ref) is str and 0 < len(real_task_ref) <= 128)
    return {'state': 'CALLER_REAL_EVIDENCE_REQUIRES_VERIFICATION' if real else 'UNQUALIFIED',
            'qualified': False, 'reuse_candidate': same,
            'reason': 'NO_AUTOMATIC_QUALIFICATION_FROM_STAGE_OR_SYNTHETIC'}


class AssetRedirect(HTTPRedirectHandler):
    """Only the exact release CDN edge observed for the pinned runtime asset.

    Model registries and further/other redirects still fail closed. Signed query
    strings are never logged; final payload length/hash remain mandatory.
    """
    def __init__(self, blob):
        self.blob, self.used = blob, False

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        source, target = urlsplit(req.full_url), urlsplit(newurl)
        require(not self.used and self.blob.kind == 'runtime-archive' and
                req.full_url == self.blob.url and source.hostname == 'github.com' and
                target.scheme == 'https' and target.hostname == 'release-assets.githubusercontent.com' and
                target.port in (None, 443) and not target.username and not target.password and
                not target.fragment, 'ASSET_REDIRECT_REJECTED')
        self.used = True
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Stopped('LOCAL_REDIRECT_REJECTED')


class OllamaClient:
    """Loopback-only client; never starts a service or pulls a model.

    Owner must attest isolated local-only service configuration; API checks are
    cooperative-host identity snapshots, not authentication or atomic pinning.
    Network errors latch UNKNOWN in this instance: no automatic retry/fallback.
    """
    def __init__(self, endpoint, version, model, manifest_sha256, transport=None,
                 timeout=10, local_service_ref=None):
        require(type(endpoint) is str and len(endpoint) <= 128, 'LOOPBACK_REQUIRED')
        require(type(version) is str and 0 < len(version) <= 64 and version != 'UNKNOWN',
                'RUNTIME_VERSION_REQUIRED')
        url = urlsplit(endpoint)
        require(url.scheme == 'http' and url.hostname == '127.0.0.1' and
                url.username is None and url.password is None and url.path in ('', '/') and
                not url.query and not url.fragment and url.port and 1 <= url.port <= 65535,
                'LOOPBACK_REQUIRED')
        require(type(local_service_ref) is str and 0 < len(local_service_ref) <= 128,
                'LOCAL_SERVICE_CONFIGURATION_REQUIRED')
        require(type(model) is str and len(model) <= 128 and
                re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*(?::[A-Za-z0-9_.-]+)?', model)
                and 'cloud' not in model.lower(),
                'LOCAL_MODEL_REQUIRED')
        require(type(manifest_sha256) is str and len(manifest_sha256) == 64 and
                all(c in '0123456789abcdef' for c in manifest_sha256), 'MODEL_PIN_REQUIRED')
        require(number(timeout) and 0 < timeout <= 30, 'CALL_BUDGET')
        self.endpoint, self.version, self.model = endpoint.rstrip('/'), version, model
        self.pin, self.timeout, self.uncertain = manifest_sha256, timeout, False
        self.transport = transport or self._http

    def _http(self, method, path, body):
        data = None if body is None else json.dumps(body, allow_nan=False).encode()
        request = Request(self.endpoint+path, data=data, method=method,
                          headers={'Content-Type': 'application/json'})
        # Explicitly disable environment proxies and redirects, including same-host ones.
        deadline=getattr(self,'session_deadline',None)
        timeout=self.timeout
        if deadline is not None:
            remaining=deadline-time.monotonic()
            require(remaining>0,'SERVICE_SESSION_DEADLINE')
            timeout=min(timeout,remaining)
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=timeout) as response:
            require(response.status == 200, 'LOCAL_HTTP_STATUS')
            raw = response.read(MAX_RESPONSE+1)
        if deadline is not None:require(time.monotonic()<deadline,'SERVICE_SESSION_DEADLINE')
        require(len(raw) <= MAX_RESPONSE, 'LOCAL_RESPONSE_CAP')
        return json.loads(raw)

    def call(self, method, path, body=None):
        require(not self.uncertain, 'OUTCOME_UNKNOWN_RECONCILE_REQUIRED')
        try:
            value = self.transport(method, path, body)
            require(type(value) is dict and len(json.dumps(value).encode()) <= MAX_RESPONSE, 'LOCAL_RESPONSE_SHAPE')
            return value
        except Exception:
            self.uncertain = True
            raise pool.UnknownOutcome('LOCAL_CALL_OUTCOME_UNKNOWN') from None

    def inspect(self):
        require(self.call('GET', '/api/version').get('version') == self.version, 'RUNTIME_VERSION_CHANGED')
        entries = self.call('GET', '/api/tags').get('models')
        require(type(entries) is list and len(entries) <= 128, 'MODEL_LIST_INVALID')
        matches = [m for m in entries if type(m) is dict and m.get('name') == self.model]
        require(len(matches) == 1 and matches[0].get('digest') in (self.pin, 'sha256:'+self.pin)
                and not matches[0].get('remote_host') and not matches[0].get('remote_model'),
                'MODEL_IDENTITY_CHANGED')
        return {'provider_version': self.version, 'model_digest': self.pin}

    def execute(self, task):
        require(task.task_class in TASKS and type(task.payload) is str and
                len(task.payload.encode()) <= MAX_INPUT, 'TASK_INPUT_BOUNDARY')
        try:
            self.inspect()
            value = self.call('POST', '/api/chat', {'model': self.model, 'stream': False,
                             'messages': [{'role': 'user', 'content': task.payload}],
                             'options': {'num_ctx': 8192, 'num_predict': 512}})
            require(value.get('done') is True and value.get('model') == self.model, 'INFERENCE_INCOMPLETE')
            output = value.get('message', {}).get('content')
            require(type(output) is str and len(output.encode()) <= 32768, 'INFERENCE_OUTPUT_INVALID')
            self.inspect()
            return output, value
        except Exception:
            self.uncertain = True
            raise pool.UnknownOutcome('LOCAL_INFERENCE_OUTCOME_UNKNOWN') from None



def usage_record(raw, *, call_id, model, started, finished, provider='ollama', cloud=False):
    """Reuse existing ledger schema. Missing usage remains UNKNOWN, never zero."""
    inp = raw.get('input_tokens') if cloud else raw.get('prompt_eval_count')
    out = raw.get('output_tokens') if cloud else raw.get('eval_count')
    valid = all(type(x) is int and 0 <= x <= 2**53 for x in (inp, out)) and inp+out <= 2**53
    return accounting.TokenUsageRecord(
        usage_id=call_id, installation_id='local-assist', call_id=call_id,
        provider=provider, model=model, purpose=accounting.UsagePurpose.TEST_ANALYSIS,
        started_at=started, finished_at=finished,
        input_tokens=inp if valid else None, output_tokens=out if valid else None,
        total_tokens=inp+out if valid else None,
        metric_source=(accounting.MetricSource.PROVIDER_REPORTED if cloud else accounting.MetricSource.RUNTIME_REPORTED)
        if valid else accounting.MetricSource.UNKNOWN)


def task_binding(client, task_class, data_scope):
    return digest({'provider': 'ollama', 'version': client.version, 'model': client.model,
                   'manifest': client.pin, 'endpoint': client.endpoint,
                   'task_class': task_class, 'data_scope': data_scope})


def validate_node(node, client, task, qualification_record=None):
    require(isinstance(node, pool.Node), 'QUALIFIED_NODE_REQUIRED')
    binding = task_binding(client, task.task_class, task.data_scope)
    if qualification_record is not None:
        record = qualification_record
        exact_record_binding(client, task.task_class, task.data_scope, record)
        require(type(task.payload) is str, 'EXACT_QUALIFICATION_REQUIRED')
        actual = hashlib.sha256(task.payload.encode('utf-8')).hexdigest()
        require(record.get('input_sha256') == actual and record.get('data_scope') == task.data_scope and
                number(record.get('expires_at')) and time.time() < record['expires_at'] and
                record.get('quality_binding') == quality_binding(client, task.task_class,
                                              task.data_scope, record.get('criteria_scope')),
                'EXACT_QUALIFICATION_INPUT_CHANGED')
        binding = exact_task_binding(client, task.task_class, task.data_scope,
                                     actual, record.get('criteria_sha256'))
        require(record.get('exact_config') == binding, 'EXACT_QUALIFICATION_BINDING')
    require(node.provider == 'ollama' and node.provider_version == client.version and
            node.model == client.model and node.config == binding and node.state == 'HEALTHY' and
            node.qualifies(task) and node.memory_available >= task.memory_required,
            'NODE_QUALIFICATION_OR_RESOURCE_MISMATCH')
    return binding


def run_local(task, client, grant, node, *, local_output=False, now=None, qualification_record=None):
    binding = validate_node(node, client, task, qualification_record)
    grant.check(node.node_id, 'infer', binding, now)
    if task.output_privacy == 'CLOUD_ALLOWED':
        grant.check(node.node_id, 'return-to-cloud', binding, now)
    # Node/qualifications are supplied evidence, never minted from a string ref.
    node_id = node.node_id
    usage = []
    def execute(registered_node, item):
        require(registered_node == node, 'NODE_BINDING_CHANGED')
        started = time.time()
        try:
            output, raw = client.execute(item)
        except BaseException:
            usage.append(usage_record({}, call_id=item.task_id, model=client.model,
                                      started=started, finished=time.time()))
            raise
        usage.append(usage_record(raw, call_id=item.task_id, model=client.model,
                                  started=started, finished=time.time()))
        if qualification_record is not None:
            # Re-running the same input can yield a different answer. Validate
            # this answer again before releasing it, not just the earlier sample.
            try:
                def unique(pairs):
                    result = {}
                    for key, value in pairs:
                        require(key not in result, 'QUALITY_DUPLICATE_KEY'); result[key] = value
                    return result
                canonical = json.dumps(json.loads(output, object_pairs_hook=unique), sort_keys=True,
                                       separators=(',', ':'), allow_nan=False).encode('utf-8')
                valid = hashlib.sha256(canonical).hexdigest() == qualification_record['criteria_sha256']
            except (TypeError, ValueError, Stopped):
                valid = False
            if not valid:
                raise pool.KnownFailure('EXACT_OUTPUT_QUALITY_FAILED')
        return pool.WorkerResult(output)
    worker = pool.BoundWorker(node_id, 'ollama', client.model, binding, execute, client.version)
    dispatcher = pool.TaskPool([node], pool.PoolBudget(1, 1, max_tasks=1,
                               timeout_seconds=client.timeout*5), authorized_nodes={node_id})
    # Deliberately no cloud_worker. The trusted caller declares its output boundary.
    result = dispatcher.run([task], {node_id: worker}, local_output_authorized=local_output)
    return result[task.task_id], tuple(usage)


def service_binding(stage, port=11434, context=8192):
    """Bind service authority separately from staging/install authority."""
    require(type(port) is int and 1024 <= port <= 65535, 'SERVICE_PORT')
    require(type(context) is int and 512 <= context <= 32768, 'SERVICE_CONTEXT')
    return digest({'stage': stage.binding, 'port': port, 'context': context,
                   'host': '127.0.0.1', 'operation': 'owned-ollama-service-v1'})


class OwnedOllamaService:
    """Session-owned direct handle only; no inference or descendant qualification.

    Cooperating-host path replacement remains possible between file validation
    and exec. Cleanup authority is checked together with start authority and
    retained only for this original handle, including after consent expiration.
    Startup uses the stage software budget with five seconds reserved for cleanup.
    Continued service lifetime requires host supervision; there is no watchdog.
    """
    def __init__(self, stage, consent, *, port=11434, context=8192,
                 popen=subprocess.Popen, clock=time.monotonic, wall_clock=time.time):
        require(isinstance(stage, PinnedStage), 'SERVICE_STAGE_REQUIRED')
        self.stage, self.consent = stage, consent
        self.port, self.context = port, context
        self.binding = service_binding(stage, port, context)
        self.popen, self.clock, self.wall_clock = popen, clock, wall_clock
        self.handle = None
        self.attempted = False
        self.cleanup_attempted = False
        self.service_root = None
        self.cleanup_result = None

    def start(self, *, idle_confirmed=False):
        require(not self.attempted, 'SERVICE_ALREADY_ATTEMPTED')
        now = self.wall_clock()
        self.consent.check(self.stage.node_id, self.binding, 'start-service', now)
        self.consent.check(self.stage.node_id, self.binding, 'stop-service', now)
        require(not self.stage.runner.recovery_required, 'SERVICE_PENDING_RECONCILIATION')
        if self.stage.activity != 'NEVER_STARTED':
            self.consent.check(self.stage.node_id, self.binding, 'confirm-idle', now)
            require(idle_confirmed is True, 'SERVICE_IDLE_UNCONFIRMED')
        self.attempted = True
        # Never compare a service clock with the stage clock origin.
        startup_deadline = self.stage.started + self.stage.max_seconds - 5
        def startup_remaining():
            observed = self.stage.clock()
            return number(observed) and observed < startup_deadline
        require(startup_remaining(), 'START_SOFTWARE_DEADLINE')
        runtime = self.stage.validate_runtime_files()
        model = self.stage.validate_model_files()
        self.stage._root_check()
        require(startup_remaining(), 'START_SOFTWARE_DEADLINE')
        # Exclusive private creation: never reuse another service's HOME/TMP.
        import tempfile
        self.service_root = Path(tempfile.mkdtemp(prefix='service-', dir=self.stage.root))
        os.chmod(self.service_root, 0o700)
        home, tmp = self.service_root/'home', self.service_root/'tmp'
        home.mkdir(mode=0o700); tmp.mkdir(mode=0o700)
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(home), 'TMPDIR': str(tmp),
               'OLLAMA_HOST': '127.0.0.1:'+str(self.port),
               'OLLAMA_MODELS': model['models_root'], 'OLLAMA_NO_CLOUD': '1',
               'OLLAMA_NOHISTORY': '1', 'OLLAMA_NUM_PARALLEL': '1',
               'OLLAMA_MAX_LOADED_MODELS': '1', 'OLLAMA_KEEP_ALIVE': '0',
               'OLLAMA_CONTEXT_LENGTH': str(self.context)}
        require(startup_remaining(), 'START_SOFTWARE_DEADLINE')
        self.stage.activity = 'POSSIBLY_ACTIVE'
        if self.stage.persistent_mode:
            self.stage.save_ownership()
        try:
            self.handle = self.popen([runtime['runtime_path'], 'serve'],
                cwd=str(Path(runtime['runtime_path']).parent), env=env,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, close_fds=True)
        except Exception:
            # No numeric PID fallback or attempt to adopt a different service.
            raise Stopped('SERVICE_START_FAILED_HANDLE_UNKNOWN') from None
        try:
            exited = self.handle.poll() is not None
        except Exception:
            return {'state': 'SERVICE_START_STATUS_UNKNOWN', 'cleanup': self.stop(seconds=5),
                    'health': 'NOT_RUN', 'inference': 'NOT_RUN', 'descendants': 'UNKNOWN'}
        if exited:
            return {'state': 'SERVICE_START_FAILED_HANDLE_EXITED', 'cleanup': self.stop(seconds=5),
                    'health': 'NOT_RUN', 'inference': 'NOT_RUN', 'descendants': 'UNKNOWN'}
        if not startup_remaining():
            return {'state': 'START_SOFTWARE_DEADLINE', 'cleanup': self.stop(seconds=5),
                    'health': 'NOT_RUN', 'inference': 'NOT_RUN', 'descendants': 'UNKNOWN'}
        return {'state': 'SERVICE_STARTED_UNVALIDATED', 'health': 'NOT_RUN',
                'inference': 'NOT_RUN', 'task_qualification': 'NOT_RUN',
                'descendants': 'UNKNOWN', 'archive_sha256': runtime['archive_sha256'],
                'manifest_sha256': model['manifest_sha256'],
                'execution_identity': 'COOPERATING_HOST_PATH_BOUND_NOT_ATOMIC'}

    def stop(self, *, seconds=5):
        require(number(seconds) and 0 < seconds <= 5, 'SERVICE_CLEANUP_BUDGET')
        require(self.attempted, 'SERVICE_NOT_STARTED')
        if self.cleanup_attempted:
            return dict(self.cleanup_result)
        self.cleanup_attempted = True
        self.cleanup_result = {'state': 'CLEANUP_UNKNOWN', 'direct_process': 'UNKNOWN',
                               'descendants': 'UNKNOWN', 'files_retained': True}
        if self.handle is None:
            return dict(self.cleanup_result)
        deadline = self.clock()+seconds
        try:
            if self.handle.poll() is None:
                require(self.clock() < deadline, 'SERVICE_CLEANUP_DEADLINE')
                self.handle.terminate()
                remaining = deadline-self.clock()
                require(remaining > 0, 'SERVICE_CLEANUP_DEADLINE')
                try:
                    self.handle.wait(timeout=min(remaining, seconds/2))
                except subprocess.TimeoutExpired:
                    require(self.clock() < deadline, 'SERVICE_CLEANUP_DEADLINE')
                    self.handle.kill()
                    remaining = deadline-self.clock()
                    require(remaining > 0, 'SERVICE_CLEANUP_DEADLINE')
                    self.handle.wait(timeout=remaining)
            else:
                remaining = deadline-self.clock()
                require(remaining > 0, 'SERVICE_CLEANUP_DEADLINE')
                self.handle.wait(timeout=remaining)
            self.cleanup_result['state'] = 'DIRECT_PROCESS_REAPED'
            self.cleanup_result['direct_process'] = 'EXIT_CONFIRMED'
            self.stage.activity = 'DIRECT_EXIT_DESCENDANTS_UNKNOWN'
            if self.stage.persistent_mode:
                self.stage.save_ownership()
        except Exception:
            pass  # Fixed UNKNOWN; no second cleanup attempt or raw exception.
        return dict(self.cleanup_result)


def compare_cloud_usage(baseline, assisted, *, same_task, same_model, quality_passed, complete):
    if not all(x is True for x in (same_task, same_model, quality_passed, complete)):
        return {'state': 'UNKNOWN', 'saved_tokens': None}
    groups = []
    models = set()
    for records in (baseline, assisted):
        if len(records) > 1000 or len({r.call_id for r in records}) != len(records):
            return {'state': 'UNKNOWN', 'saved_tokens': None}
        models.update(r.model for r in records)
        if not records or any(r.provider != 'openai' or r.metric_source != accounting.MetricSource.PROVIDER_REPORTED or
                              r.total_tokens is None for r in records):
            return {'state': 'UNKNOWN', 'saved_tokens': None}
        groups.append(sum(r.total_tokens for r in records))
    if len(models) != 1:
        return {'state': 'UNKNOWN', 'saved_tokens': None}
    return {'state': 'OBSERVED_SCOPED_COMPARISON', 'saved_tokens': groups[0]-groups[1]}


def qualify_customer_task(node_id, snapshot, client, task_class, data_scope, grant,
                          *, native_probe=False, now=time.time):
    """One bounded task-format check; synthetic/injected clients never mint a Node.

    Native evidence is still a cooperative-host observation, not authentication
    or a guarantee for every future task. The CLI performs its own native probe.
    """
    binding = task_binding(client, task_class, data_scope)
    grant.check(node_id, 'qualify', binding, now=now())
    require(task_class in TASKS, 'TASK_NOT_QUALIFIED')
    candidate = next((x for x in load_catalog()['models'] if x['id'] == client.model), None)
    require(candidate is not None and client.version == candidate['provider_version'] and
            client.pin == candidate['manifest_sha256'], 'QUALIFICATION_MODEL_BINDING')
    recommended = recommend(snapshot, {**load_catalog(), 'models': [candidate]}, task_class)
    require((recommended.get('candidate') or {}).get('id') == candidate['id'],
            'QUALIFICATION_RESOURCES_INSUFFICIENT')
    checks = {
        'log-summary': ('Return only JSON counting these levels: INFO,ERROR,ERROR.', {'INFO': 1, 'ERROR': 2}),
        'diff-classification': ('Return only JSON {"kind":"test"} for changed file tests/test_example.py.', {'kind': 'test'}),
        'test-failure-summary': ('Return only JSON {"failed":"test_example"} for: FAIL test_example.', {'failed': 'test_example'}),
    }
    prompt, expected = checks[task_class]
    task = pool.Task('qualification-check', task_class, data_scope, payload=prompt)
    output, raw = client.execute(task)
    try:
        passed = json.loads(output) == expected
    except (TypeError, json.JSONDecodeError):
        passed = False
    grant.check(node_id, 'qualify', binding, now=now())
    native = (native_probe is True and type(client) is OllamaClient and
              getattr(client.transport, '__self__', None) is client and
              getattr(client.transport, '__func__', None) is OllamaClient._http)
    usage = usage_record(raw, call_id='qualification-check', model=client.model,
                         started=now(), finished=now())
    result = {'state': 'TASK_CHECK_PASSED' if passed else 'TASK_CHECK_FAILED',
              'qualified': False, 'evidence_kind': 'NATIVE' if native else 'SYNTHETIC',
              'check_scope': 'ONE_FIXED_FORMAT_CASE', 'cloud_savings': 'UNVERIFIED',
              'usage': {'input_tokens': usage.input_tokens, 'output_tokens': usage.output_tokens,
                        'total_tokens': usage.total_tokens,
                        'metric_source': usage.metric_source.value}}
    # A public fixed-answer formatting check cannot establish arbitrary task
    # competence, even when the inference was native. Never mint a pool Node.
    result['reason'] = 'REAL_TASK_QUALITY_EVIDENCE_REQUIRED'
    return result


def public_usage(record):
    """Only normalized numeric ledger fields; no provider response or task text."""
    values = (record.input_tokens, record.output_tokens, record.total_tokens)
    valid = (all(type(v) is int and 0 <= v <= 2**53 for v in values) and
             values[0]+values[1] == values[2] and values[2] <= 2**53)
    return {'input_tokens': values[0] if valid else None,
            'output_tokens': values[1] if valid else None,
            'total_tokens': values[2] if valid else None,
            'metric_source': record.metric_source.value if valid else 'UNKNOWN'}


def quality_binding(client, task_class, data_scope, criteria_scope):
    require(type(criteria_scope) is str and criteria_scope.startswith('file:') and
            os.path.isabs(criteria_scope[5:]), 'QUALITY_CRITERIA_SCOPE_REQUIRED')
    require(type(data_scope) is str and data_scope.startswith('file:') and
            os.path.isabs(data_scope[5:]), 'QUALITY_INPUT_SCOPE_REQUIRED')
    return digest({'task_binding': task_binding(client, task_class, data_scope),
                   'criteria_scope': criteria_scope, 'method': 'exact-json-input-v1'})


def exact_task_binding(client, task_class, data_scope, input_sha256, criteria_sha256):
    require(all(type(value) is str and re.fullmatch('[0-9a-f]{64}', value)
                for value in (input_sha256, criteria_sha256)), 'EXACT_TASK_HASH_REQUIRED')
    return digest({'task_binding': task_binding(client, task_class, data_scope),
                   'input_sha256': input_sha256, 'criteria_sha256': criteria_sha256,
                   'method': 'exact-input-qualified-v2'})


def qualify_exact_input(node_id, snapshot, client, task_class, data_scope, payload,
                        expected_json, criteria_scope, grant, *, native_probe=False,
                        expires_at=None, now=time.time):
    """Qualify only these exact bytes against separately authorized expected JSON.

    This is a cooperating-host observation, not authenticated attestation or a
    task-class competence claim. Injected transports never produce a Node.
    The caller must acquire input/criteria only after the exact grant check and
    independently retain their own quality criteria; no raw bodies are returned.
    """
    binding = quality_binding(client, task_class, data_scope, criteria_scope)
    started = now()
    grant.check(node_id, 'qualify', binding, now=started)
    require(type(payload) is str and 0 < len(payload.encode('utf-8')) <= MAX_INPUT,
            'QUALITY_INPUT_CAP')
    criteria = json.dumps(expected_json, sort_keys=True, separators=(',', ':'), allow_nan=False)
    require(len(criteria.encode('utf-8')) <= 16384, 'QUALITY_CRITERIA_CAP')
    require(task_class in TASKS, 'TASK_NOT_QUALIFIED')
    catalog = load_catalog()
    candidate = next((x for x in catalog['models'] if x['id'] == client.model), None)
    require(candidate is not None and client.version == candidate['provider_version'] and
            client.pin == candidate['manifest_sha256'], 'QUALIFICATION_MODEL_BINDING')
    recommended = recommend(snapshot, {**catalog, 'models': [candidate]}, task_class)
    require((recommended.get('candidate') or {}).get('id') == candidate['id'],
            'QUALIFICATION_RESOURCES_INSUFFICIENT')
    task = pool.Task('customer-quality-check', task_class, data_scope, payload=payload)
    output, raw = client.execute(task)
    require(type(output) is str and len(output.encode('utf-8')) <= MAX_INPUT,
            'QUALITY_OUTPUT_CAP')
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'QUALITY_DUPLICATE_KEY')
            result[key] = value
        return result
    try:
        parsed = json.loads(output, object_pairs_hook=unique_pairs)
        actual = json.dumps(parsed, sort_keys=True, separators=(',', ':'), allow_nan=False)
        passed = actual == criteria
    except (ValueError, TypeError, Stopped):
        passed = False
    finished = now()
    grant.check(node_id, 'qualify', binding, now=finished)
    limit = min(grant.expires_at, finished+600)
    if expires_at is not None:
        require(number(expires_at), 'QUALITY_EXPIRY')
        limit = min(limit, expires_at)
    require(limit > finished, 'QUALITY_EXPIRY')
    native = (native_probe is True and type(client) is OllamaClient and
              getattr(client.transport, '__self__', None) is client and
              getattr(client.transport, '__func__', None) is OllamaClient._http)
    qualified = passed and native
    result = {'schema_version': 2, 'state': 'EXACT_INPUT_QUALIFIED' if qualified else
              ('SYNTHETIC_CHECK_PASSED' if passed else 'QUALITY_CHECK_FAILED'),
              'qualified': qualified, 'check_scope': 'EXACT_INPUT',
              'evidence_kind': 'NATIVE' if native else 'SYNTHETIC',
              'input_sha256': hashlib.sha256(payload.encode('utf-8')).hexdigest(),
              'criteria_sha256': hashlib.sha256(criteria.encode('utf-8')).hexdigest(),
              'output_sha256': hashlib.sha256(output.encode('utf-8')).hexdigest(),
              'criteria_scope': criteria_scope, 'data_scope': data_scope,
              'expires_at': limit, 'quality_binding': binding,
              'cloud_savings': 'UNVERIFIED',
              'usage': public_usage(usage_record(raw, call_id='customer-quality-check',
                        model=client.model, started=started, finished=finished))}
    if qualified:
        config = exact_task_binding(client, task_class, data_scope,
                                    result['input_sha256'], result['criteria_sha256'])
        result['exact_config'] = config
        result['node'] = {'node_id': node_id, 'provider': 'ollama', 'model': client.model,
                         'config': config, 'consent': True, 'deployment_authorized': True,
                         'probed': True, 'runtime_validated': True, 'state': 'HEALTHY',
                         'privacy_scopes': [data_scope], 'memory_available': candidate['memory_gb'],
                         'provider_version': client.version,
                         'qualifications': [{'node_id': node_id, 'provider': 'ollama',
                            'model': client.model, 'config': config, 'task_class': task_class,
                            'provider_version': client.version}]}
    return result


def customer_deployment_plan(node_id, root, model_id):
    """Effect-free exact plan; no permission is inferred from this output."""
    require(type(root) is str and os.path.isabs(root), 'PRIVATE_INSTALL_ROOT_REQUIRED')
    catalog = load_catalog()
    candidate = next((x for x in catalog['models'] if x['id'] == model_id), None)
    require(candidate is not None, 'MODEL_NOT_IN_CATALOG')
    asset = catalog['runtime']['darwin_asset']
    blobs = [catalog_blob(candidate, catalog, kind='runtime-archive', sha256=asset['sha256'])]
    for item in candidate['layers']+[candidate['config_blob']]:
        blob = catalog_blob(candidate, catalog, kind='model-blob', sha256=item['digest'].split(':')[1])
        if blob not in blobs:
            blobs.append(blob)
    total = sum(b.size for b in blobs)
    return {'state': 'DEPLOYMENT_CONSENT_REQUIRED', 'node_id': node_id,
            'root': root, 'model_id': model_id,
            'binding': lifecycle_binding(node_id, root, candidate, blobs),
            'actions': ['stage', 'install-runtime', 'install-model', 'save-ownership'],
            'reuse_actions': ['restore-ownership', 'save-ownership'], 'reuse_download_bytes': 0,
            'reuse_scope': 'SAME_EXACT_PINS_ONLY',
            'download_bytes': total,
            'minimum_new_disk_bytes': total+asset['unpacked_bytes']+candidate['download_bytes']+4*1024**2,
            'minimum_iterations': len(blobs)+2, 'fee': 0,
            'platform': 'Darwin_SOURCE_SUPPORTED_NATIVE_UNVERIFIED',
            'service_start_authorized': False, 'qualification': 'NOT_RUN',
            'cloud_savings': 'UNVERIFIED'}


def deploy_customer_files(stage):
    """Run only this already authorized controller; no service start/inference."""
    require(isinstance(stage, PinnedStage), 'DEPLOYMENT_CONTROLLER_REQUIRED')
    for action in ('stage', 'install-runtime', 'install-model'):
        stage.consent.check(stage.node_id, stage.binding, action, stage.wall_clock())
    results = [stage.stage()]
    if getattr(stage, 'persistent_mode', False):
        stage.save_ownership()
    if results[-1]['state'] != 'STAGED_NOT_INSTALLED':
        return {'state': 'STOP', 'phases': results}
    results.append(stage.install_runtime())
    if getattr(stage, 'persistent_mode', False):
        stage.save_ownership()
    if results[-1]['state'] != 'RUNTIME_FILES_INSTALLED_UNVALIDATED':
        return {'state': 'STOP', 'phases': results}
    results.append(stage.install_model())
    if getattr(stage, 'persistent_mode', False):
        stage.save_ownership()
    return {'state': 'FILES_PREPARED_UNVALIDATED' if stage.model_complete else 'STOP',
            'phases': results, 'service_started': False, 'qualified': False,
            'ownership_recovery': 'SAME_CONTROLLER_ONLY_RESTART_REQUIRES_VERIFICATION'}


def customer_setup(node_id, disk_root, *, ask=input, reader=None, now=time.time):
    """Local explicit consent -> probe -> recommendation, never deployment consent.

    Intended for the customer's own terminal. Tests inject both public answers
    and the metadata reader; this function does not persist an approval record.
    """
    if ask(NAME+'：启用可选引导？输入 yes；其他输入跳过：').strip() != 'yes':
        return {'state': 'SKIPPED', 'probe_performed': False, 'actions': []}
    if ask('仅读取系统/架构、GPU、可用内存及磁盘；不读文件正文或序列号。允许？输入 yes：').strip() != 'yes':
        return {'state': 'PROBE_DECLINED', 'probe_performed': False, 'actions': []}
    require(os.path.isabs(disk_root), 'PROBE_ROOT_REQUIRED')
    grant = Grant(node_id, frozenset({'probe'}), now()+60, 'local-terminal-confirmation')
    snapshot = probe(node_id, grant, reader or PlatformReader(disk_root), now=now())
    recommendation = recommend(snapshot, load_catalog(), 'log-summary')
    return {'state': 'RECOMMENDATION_ONLY', 'probe_performed': True,
            'snapshot': snapshot, 'recommendation': recommendation,
            'deployment_authorized': False, 'inference_authorized': False,
            'next': 'EXACT_DEPLOYMENT_PLAN_AND_SEPARATE_CONSENT_REQUIRED',
            'qualification': 'NOT_RUN', 'cloud_savings': 'UNVERIFIED'}


def read_local_record(path, cap=8192):
    with open(path, 'rb') as source:
        raw = source.read(cap+1)
    require(len(raw) <= cap, 'LOCAL_RECORD_CAP')
    value = json.loads(raw)
    require(type(value) is dict, 'LOCAL_RECORD_SHAPE')
    return value


def exact_record_binding(client, task_class, scope, record):
    """Validate record/path authority before any read of the scoped task body."""
    require(type(record) is dict and record.get('schema_version') == 2 and
            record.get('qualified') is True and record.get('evidence_kind') == 'NATIVE' and
            record.get('check_scope') == 'EXACT_INPUT' and record.get('data_scope') == scope and
            number(record.get('expires_at')) and time.time() < record['expires_at'] and
            record.get('quality_binding') == quality_binding(client, task_class, scope,
                                                             record.get('criteria_scope')),
            'EXACT_QUALIFICATION_SCOPE_OR_EXPIRY')
    binding = exact_task_binding(client, task_class, scope, record.get('input_sha256'),
                                 record.get('criteria_sha256'))
    require(record.get('exact_config') == binding, 'EXACT_QUALIFICATION_BINDING')
    return binding


def read_task_bytes(path, cap=MAX_INPUT):
    """Caller must check exact path authorization before invoking this reader."""
    fd = os.open(path, os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_size <= cap, 'INPUT_TYPE_OR_CAP')
        data = os.read(fd, cap+1); after = os.fstat(fd)
        require(len(data) == before.st_size and
                (before.st_dev, before.st_ino, before.st_mode, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_mode, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                'INPUT_CHANGED_OR_SHORT')
        return data
    finally:
        os.close(fd)


def private_record_target(path):
    require(path and os.path.isabs(path), 'PRIVATE_RECORD_TARGET_REQUIRED')
    target = Path(path); info = target.parent.lstat()
    require(target.parent == target.parent.resolve() and stat.S_ISDIR(info.st_mode) and
            info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700 and
            not os.path.lexists(target), 'PRIVATE_RECORD_TARGET_CONFLICT')
    return target


def write_private_record(path, value):
    target = private_record_target(path)
    data = json.dumps(value, ensure_ascii=True, allow_nan=False).encode('utf-8')
    require(len(data) <= 16384, 'QUALIFICATION_CAP')
    fd = os.open(target, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as output:
        require(output.write(data) == len(data), 'QUALIFICATION_SHORT_WRITE')
        output.flush(); os.fsync(output.fileno())


def wizard_argv(node, model_id, **options):
    """Exact installed CLI, suitable for an existing Codex exec tool."""
    result = [sys.executable, '-I', '-B', str(Path(__file__).resolve()),
              'wizard', '--node', node, '--model-id', model_id]
    for key, value in options.items():
        require(type(value) is not bool or key=='idle_confirmed','WIZARD_ARGUMENT_TYPE')
        if value is True:
            result += ['--'+key.replace('_','-')]
        elif value is not None and value is not False:
            result += ['--'+key.replace('_','-'), str(value)]
    return result


def _wizard_record(root, label, value, *, now):
    """At most twelve scoped authorization records; never an ownership ledger."""
    files=[]
    with os.scandir(root) as entries:
        for index,entry in enumerate(entries):
            require(index<32,'WIZARD_DIRECTORY_LIMIT')
            if entry.name.startswith('wizard-') and entry.name.endswith('.json'):
                files.append(root/entry.name)
                require(len(files)<=12,'WIZARD_RECORD_LIMIT')
    # Reuse an exact still-valid record, never silently renew its scope/expiry.
    for path in files:
        if not path.name.startswith('wizard-'+label+'-'):
            continue
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,'rb') as source:
            before=os.fstat(source.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and
                    stat.S_IMODE(before.st_mode)==0o600 and before.st_nlink==1 and
                    before.st_size<=16384,'WIZARD_RECORD_IDENTITY')
            raw=source.read(16385);after=os.fstat(source.fileno())
            require(len(raw)==before.st_size and
                    (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
                    (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),
                    'WIZARD_RECORD_CHANGED')
        old=json.loads(raw)
        require(type(old) is dict,'WIZARD_RECORD_SHAPE')
        if ({k:v for k,v in old.items() if k != 'expires_at'} ==
            {k:v for k,v in value.items() if k != 'expires_at'} and
            (('expires_at' not in value and old==value) or
             (number(old.get('expires_at')) and now() < old['expires_at'] <= value['expires_at']))):
            return str(path)
    require(len(files)<12,'WIZARD_RECORD_LIMIT')
    target = root/('wizard-'+label+'-'+digest(value)[:20]+'.json')
    write_private_record(str(target),value)
    return str(target)


def _wizard_session_answer(ask, prompt, deadline):
    require(time.monotonic()<deadline,'SERVICE_SESSION_DEADLINE')
    if ask is input:
        print(prompt,flush=True)
        with selectors.DefaultSelector() as selector:
            selector.register(sys.stdin,selectors.EVENT_READ)
            require(bool(selector.select(max(0,deadline-time.monotonic()))),'SERVICE_SESSION_DEADLINE')
            answer=sys.stdin.readline(256)
        require(answer.endswith('\n'),'WIZARD_CONFIRMATION_SHAPE')
    else:
        answer=ask(prompt)
    require(time.monotonic()<deadline,'SERVICE_SESSION_DEADLINE')
    return answer.strip()=='yes'


def _wizard_port_available(port, deadline):
    """Loopback only, no HTTP/data. A busy/unknown endpoint is never adopted."""
    import errno, socket
    require(type(port) is int and 1024<=port<=65535,'SERVICE_PORT')
    remaining=deadline-time.monotonic()
    require(remaining>0,'SERVICE_SESSION_DEADLINE')
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as connection:
        connection.settimeout(min(1,remaining))
        result=connection.connect_ex(('127.0.0.1',port))
    require(time.monotonic()<deadline,'SERVICE_SESSION_DEADLINE')
    require(result!=0,'WIZARD_LOCAL_PORT_BUSY')
    require(result==errno.ECONNREFUSED,'WIZARD_LOCAL_PORT_UNKNOWN')


def _wizard_wait_ready(stage, service, candidate, deadline, *, client_factory=None, sleep=None):
    """At most three read-only GET rounds; only connection refusal may repeat.

    Cooperating-host port/handle checks are observations, not an atomic socket
    ownership proof. No inference request is retried or sent by this gate.
    """
    import errno
    from urllib.error import URLError
    factory=OllamaClient if client_factory is None else client_factory
    pause=time.sleep if sleep is None else sleep
    for attempt in range(3):
        require(time.monotonic()<deadline and stage.clock()<stage.started+stage.max_seconds-5,
                'SERVICE_SESSION_DEADLINE')
        require(service.handle is not None and service.handle.poll() is None,'SERVICE_HANDLE_EXITED')
        client=factory('http://127.0.0.1:'+str(service.port),candidate['provider_version'],
            candidate['id'],candidate['manifest_sha256'],timeout=5,local_service_ref=service.binding)
        client.session_deadline=deadline
        try:
            version=client._http('GET','/api/version',None)
            require(type(version) is dict and version.get('version')==candidate['provider_version'],
                    'RUNTIME_VERSION_CHANGED')
            tags=client._http('GET','/api/tags',None)
            entries=tags.get('models') if type(tags) is dict else None
            require(type(entries) is list and len(entries)<=128,'MODEL_LIST_INVALID')
            matches=[x for x in entries if type(x) is dict and x.get('name')==candidate['id']]
            require(len(matches)==1 and matches[0].get('digest') in
                    (candidate['manifest_sha256'],'sha256:'+candidate['manifest_sha256']) and
                    not matches[0].get('remote_host') and not matches[0].get('remote_model'),
                    'MODEL_IDENTITY_CHANGED')
            require(service.handle.poll() is None,'SERVICE_HANDLE_EXITED')
            require(time.monotonic()<deadline and stage.clock()<stage.started+stage.max_seconds-5,
                    'SERVICE_SESSION_DEADLINE')
            return {'state':'READ_ONLY_READY','rounds':attempt+1,'atomic_port_identity':False}
        except (URLError,ConnectionRefusedError) as error:
            reason=error.reason if isinstance(error,URLError) else error
            require(isinstance(reason,ConnectionRefusedError) or
                    (isinstance(reason,OSError) and reason.errno==errno.ECONNREFUSED),
                    'WIZARD_READY_CONNECTION_UNKNOWN')
            require(service.handle.poll() is None,'SERVICE_HANDLE_EXITED')
            require(attempt<2,'WIZARD_READY_REFUSED')
            remaining=deadline-time.monotonic()
            require(remaining>0,'SERVICE_SESSION_DEADLINE')
            pause(min(.1,remaining))
    raise Stopped('WIZARD_READY_UNKNOWN')


def customer_wizard(args, *, ask=None, reader=None, now=time.time):
    """Bounded customer handoff using existing stages and the original journal.

    Interactive authorization records are local assertions, not authenticated
    approval or a second ledger. No effects occur merely by importing this API.
    """
    require(sys.stdin.isatty(), 'WIZARD_LOCAL_TERMINAL_REQUIRED')
    ask = input if ask is None else ask
    require(args.disk_root and args.install_root and os.path.isabs(args.disk_root) and
            os.path.isabs(args.install_root), 'WIZARD_ROOT_ARGUMENTS_REQUIRED')
    require(number(args.session_seconds) and 0 < args.session_seconds <= 300,
            'SERVICE_SESSION_AUTHORITY_REQUIRED')
    root = Path(args.install_root)
    if args.wizard_phase == 'plan':
        if ask(NAME+'：启用本地模型交接向导？输入 yes：').strip() != 'yes':
            return {'state':'SKIPPED','probe_performed':False,'actions':[]}
        existing = read_local_record(args.existing_state,4096) if args.existing_state else {}
        catalog = load_catalog()
        candidate = next((x for x in catalog['models'] if x['id']==args.model_id),None)
        require(candidate is not None,'MODEL_NOT_IN_CATALOG')
        prior = onboarding(existing,candidate,existing.get('prior_binding'),
                           existing.get('authorized_binding'),existing.get('authorization_expires_at'))
        if ask('允许读取系统、架构、GPU、可用内存和磁盘元数据？不读正文。输入 yes：').strip() != 'yes':
            return {'state':'PROBE_DECLINED','probe_performed':False,'actions':[]}
        probe_grant = Grant(args.node,frozenset({'probe'}),now()+1800,'wizard-terminal-probe')
        snapshot = probe(args.node,probe_grant,reader or PlatformReader(args.disk_root),now=now())
        recommendation = recommend(snapshot,catalog,args.task_class)
        selected = recommendation.get('candidate')
        if selected is None:
            return {'state':'RESOURCES_UNQUALIFIED','recommendation':recommendation,
                    'probe_performed':True,'actions':[],'qualified':False}
        plan = customer_deployment_plan(args.node,str(root),selected['id'])
        require(snapshot.get('os')=='Darwin' and snapshot.get('architecture') in {'arm64','x86_64'},
                'RUNTIME_PLATFORM_UNSUPPORTED')
        reuse = os.path.lexists(root/'lifecycle.json')
        actions = (plan['reuse_actions'] if reuse else plan['actions'])
        old_budget=None
        if reuse:
            require(args.budget_file,'WIZARD_EXISTING_BUDGET_FILE_REQUIRED')
            old_budget=read_local_record(args.budget_file)
            deployment.Budget(**old_budget)
            saved=read_local_record(str(root/'lifecycle.json'),1024*1024)
            owned=saved.get('owned_files')
            require(saved.get('state') in {'CLEAN','SUCCEEDED','NOT_APPLIED','UNSUPPORTED','APPLIED'} and
                    saved.get('owned_files_state')=='RECORDED' and type(owned) is dict and
                    owned.get('binding')==plan['binding'] and owned.get('io_state')=='CONFIRMED',
                    'WIZARD_EXISTING_STATE_PENDING_OR_PINS_CHANGED')
        budget={'max_download_gb':math.ceil(plan['download_bytes']/1024**3),
                'max_peak_disk_gb':math.ceil((plan['minimum_new_disk_bytes']+16*1024**2)/1024**3),
                'max_iterations':plan['minimum_iterations'],'max_restarts':0,'max_seconds':1800}
        if reuse:budget=old_budget
        print(json.dumps({'state':'DEPLOYMENT_CONSENT_PREVIEW','model':selected['id'],
            'model_pin':selected['manifest_sha256'],'model_source':'https://registry.ollama.ai',
            'runtime_version':catalog['runtime']['version'],
            'runtime_pin':catalog['runtime']['darwin_asset']['sha256'],
            'runtime_source':'https://github.com/ollama/ollama/releases',
            'root':str(root),'actions':actions,'budget':budget,
            'download_bytes':0 if reuse else plan['download_bytes'],
            'writes':'private authorization JSON and owned files; journal records consumption/ownership, never grants authority'},
            ensure_ascii=True),flush=True)
        prompt = ('同精确版本恢复，保留原消耗、不下载' if reuse else
                  '下载并隔离安装固定版本，下载上限 '+str(plan['download_bytes'])+'B')
        if ask(prompt+'；不启动模型、不改Codex。允许写专用授权记录及私有目录？输入 yes：').strip() != 'yes':
            return {'state':'DEPLOYMENT_DECLINED','probe_performed':True,'recommendation':recommendation}
        if not root.exists():
            require(root.parent==root.parent.resolve(),'STAGE_ROOT_NOT_PRIVATE')
            root.mkdir(mode=0o700)
        info=root.lstat()
        require(root==root.resolve() and stat.S_ISDIR(info.st_mode) and info.st_uid==os.getuid() and
                stat.S_IMODE(info.st_mode)==0o700,'STAGE_ROOT_NOT_PRIVATE')
        life={'node_id':args.node,'binding':plan['binding'],'expires_at':now()+1800,
              'actions':sorted(set(actions)|{'restore-ownership','save-ownership'})}
        grant={'node_id':args.node,'scopes':['probe'],'expires_at':probe_grant.expires_at,
               'reference':probe_grant.reference,'binding':''}
        if reuse:
            # Reuse the customer's explicit original budget. Never silently grant
            # a new time/download/iteration domain for an existing journal.
            require(args.budget_file,'WIZARD_EXISTING_BUDGET_FILE_REQUIRED')
            budget_path=args.budget_file
            budget=old_budget
        else:
            budget_path=_wizard_record(root,'budget',budget,now=now)
        grant_path=_wizard_record(root,'probe',grant,now=now)
        life_path=_wizard_record(root,'lifecycle',life,now=now)
        return {'state':'DEPLOYMENT_AUTHORIZED_NOT_STARTED','existing_config':prior,
                'recommendation':recommendation,'budget':budget,
                'next_argv':wizard_argv(args.node,selected['id'],wizard_phase='deploy',
                    disk_root=args.disk_root,install_root=str(root),grant_file=grant_path,
                    lifecycle_consent_file=life_path,budget_file=budget_path,
                    input_file=args.input_file,quality_case_file=args.quality_case_file,
                    task_class=args.task_class,session_seconds=args.session_seconds,port=args.port,idle_confirmed=args.idle_confirmed),
                'cloud_savings':'UNVERIFIED'}
    root_info=root.lstat()
    require(root==root.resolve() and stat.S_ISDIR(root_info.st_mode) and
            root_info.st_uid==os.getuid() and stat.S_IMODE(root_info.st_mode)==0o700,
            'STAGE_ROOT_NOT_PRIVATE')
    require(args.lifecycle_consent_file and args.budget_file,'RESTORE_AUTHORITY_AND_BUDGET_REQUIRED')
    if args.wizard_phase == 'recovery':
        plan=customer_deployment_plan(args.node,str(root),args.model_id)
        old_consent=LifecycleConsent(**read_local_record(args.lifecycle_consent_file))
        require(old_consent.node_id==args.node and old_consent.binding==plan['binding'],
                'OWNERSHIP_BINDING_OR_IO_UNKNOWN')
        budget=deployment.Budget(**read_local_record(args.budget_file))
        status_argv=wizard_argv(args.node,args.model_id,install_root=str(root),
            lifecycle_consent_file=args.lifecycle_consent_file,budget_file=args.budget_file)
        status_argv[4]='ownership-status'
        if ask('仅核对本项目既有所有权、身份和预算，不删除、不清UNKNOWN。允许只读核验？输入 yes：').strip()!='yes':
            return {'state':'RECOVERY_DECLINED','actions':[]}
        catalog=load_catalog();candidate=next(x for x in catalog['models'] if x['id']==args.model_id)
        asset=catalog['runtime']['darwin_asset']
        blobs=[catalog_blob(candidate,catalog,kind='runtime-archive',sha256=asset['sha256'])]
        for descriptor in candidate['layers']+[candidate['config_blob']]:
            blob=catalog_blob(candidate,catalog,kind='model-blob',sha256=descriptor['digest'].split(':')[1])
            if blob not in blobs:blobs.append(blob)
        # This new explicit read-only confirmation is not inferred from old JSON.
        audit=LifecycleConsent(args.node,plan['binding'],now()+60,frozenset({'restore-ownership'}))
        with deployment.DurableJournal(root/'lifecycle.json',args.node) as journal:
            saved=journal.load(args.node)
            owned=(journal.load_owned_files(args.node) if saved.get('owned_files_state')!='UNKNOWN' else None)
            if (saved.get('state') not in {'CLEAN','SUCCEEDED','NOT_APPLIED','UNSUPPORTED','APPLIED'} or
                    owned is None or owned.get('io_state')!='CONFIRMED'):
                return {'state':'STOP','reason':'RECOVERY_UNKNOWN_OR_PENDING_NO_DELETE',
                        'ownership_status_argv':status_argv,'cleanup_authorized':False,'retry':False}
            stage=PinnedStage.restore_owned(args.node,root,candidate,blobs,audit,budget,journal,
                catalog=catalog,wall_clock=now)
            try:
                if not stage.runtime_complete or not stage.model_complete:
                    return {'state':'STOP','reason':'RECOVERY_PARTIAL_NO_DELETE',
                            'ownership_status_argv':status_argv,'cleanup_authorized':False,'retry':False}
                actions={'restore-ownership','save-ownership','uninstall-model','uninstall-runtime'}
                if stage.activity!='NEVER_STARTED':actions.add('confirm-idle')
                print(json.dumps({'state':'UNINSTALL_CONSENT_PREVIEW','model':args.model_id,
                    'binding':plan['binding'],'root':str(root),'actions':sorted(actions),
                    'budget':read_local_record(args.budget_file),'activity':stage.activity,
                    'idle':'requires fresh independent host idle confirmation; record is not proof',
                    'journal_preserved':True},ensure_ascii=True),flush=True)
                require(args.idle_confirmed,'UNINSTALL_REQUIRES_FRESH_HOST_IDLE_CONFIRMATION')
                if ask('你已独立确认原服务及后代闲置，并明确要求仅卸载已核验的本项目文件？输入 yes；不能确认则停止：').strip()!='yes':
                    return {'state':'UNINSTALL_DECLINED','cleanup_authorized':False}
                fresh={'node_id':args.node,'binding':plan['binding'],'expires_at':now()+300,
                       'actions':sorted(actions)}
                path=_wizard_record(root,'uninstall',fresh,now=now)
                command=wizard_argv(args.node,args.model_id,install_root=str(root),
                    lifecycle_consent_file=path,budget_file=args.budget_file,idle_confirmed=True)
                command[4]='uninstall'
                return {'state':'UNINSTALL_AUTHORIZED_NOT_EXECUTED','next_argv':command,
                        'journal_preserved':True,'unknown_not_cleared':True,'automatic_delete':False}
            finally:stage.close()
    if args.wizard_phase == 'deploy':
        # Dispatch the already-tested gate, with its separate probe and exact pins.
        import contextlib, io
        call=['deploy-files','--node',args.node,'--model-id',args.model_id,
              '--install-root',str(root),'--grant-file',args.grant_file or '',
              '--lifecycle-consent-file',args.lifecycle_consent_file,'--budget-file',args.budget_file,
              '--task-class',args.task_class]
        output=io.StringIO()
        with contextlib.redirect_stdout(output): rc=main(call)
        require(len(output.getvalue().encode())<=16384,'WIZARD_STAGE_OUTPUT_CAP')
        result=json.loads(output.getvalue())
        if rc or result.get('state')!='FILES_PREPARED_UNVALIDATED':
            return {'state':'STOP','phase':'deploy','stage_result':result,'retry':False}
        return {'state':'FILES_PREPARED_UNVALIDATED','qualified':False,
                'next_argv':wizard_argv(args.node,args.model_id,wizard_phase='session',
                    disk_root=args.disk_root,install_root=str(root),
                    lifecycle_consent_file=args.lifecycle_consent_file,budget_file=args.budget_file,
                    input_file=args.input_file,quality_case_file=args.quality_case_file,
                    task_class=args.task_class,session_seconds=args.session_seconds,port=args.port,idle_confirmed=args.idle_confirmed),
                'required_arguments':([] if args.input_file and args.quality_case_file else
                                      ['--input-file','--quality-case-file']),
                'instructions':'质量文件须由客户独立定义期望JSON；不是模型生成的真值。'}
    require(args.wizard_phase=='session','WIZARD_PHASE')
    if not args.input_file or not args.quality_case_file:
        return {'state':'TASK_QUALITY_ARGUMENTS_REQUIRED','required_arguments':['--input-file','--quality-case-file'],
                'next_argv':wizard_argv(args.node,args.model_id,wizard_phase='session',disk_root=args.disk_root,
                    install_root=str(root),lifecycle_consent_file=args.lifecycle_consent_file,
                    budget_file=args.budget_file,session_seconds=args.session_seconds,port=args.port,idle_confirmed=args.idle_confirmed),
                'inference_authorized':False}
    require(os.path.isabs(args.input_file) and os.path.isabs(args.quality_case_file),'INPUT_PATH_REQUIRED')
    plan=customer_deployment_plan(args.node,str(root),args.model_id);catalog=load_catalog()
    candidate=next(x for x in catalog['models'] if x['id']==args.model_id)
    asset=catalog['runtime']['darwin_asset']
    blobs=[catalog_blob(candidate,catalog,kind='runtime-archive',sha256=asset['sha256'])]
    for descriptor in candidate['layers']+[candidate['config_blob']]:
        blob=catalog_blob(candidate,catalog,kind='model-blob',sha256=descriptor['digest'].split(':')[1])
        if blob not in blobs:blobs.append(blob)
    consent=LifecycleConsent(**read_local_record(args.lifecycle_consent_file))
    budget=deployment.Budget(**read_local_record(args.budget_file))
    with deployment.DurableJournal(root/'lifecycle.json',args.node) as journal:
        stage=PinnedStage.restore_owned(args.node,root,candidate,blobs,consent,budget,journal,catalog=catalog)
        service=None
        try:
            require(not stage.runner.recovery_required,'SERVICE_PENDING_RECONCILIATION')
            require(args.session_seconds <= stage.max_seconds-(stage.clock()-stage.started)-5,'SERVICE_SESSION_BUDGET')
            if stage.activity!='NEVER_STARTED':
                require(args.idle_confirmed,'SERVICE_IDLE_UNCONFIRMED')
                require(ask('你已独立确认原服务及后代闲置？输入 yes；不能确认则停止：').strip()=='yes',
                        'SERVICE_IDLE_UNCONFIRMED')
            if ask('允许检查本地回环端口、独立启动私有服务并最多3轮只读version/tags就绪检查；最多 '+str(args.session_seconds)+'秒，退出清理原句柄？输入 yes：').strip()!='yes':
                return {'state':'SERVICE_DECLINED','qualified':False}
            service_actions={'start-service','stop-service'}
            if stage.activity!='NEVER_STARTED':service_actions.add('confirm-idle')
            service_grant=LifecycleConsent(args.node,service_binding(stage,args.port),now()+args.session_seconds+30,
                                           frozenset(service_actions))
            service_path=_wizard_record(root,'service',{'node_id':args.node,'binding':service_grant.binding,
                'expires_at':service_grant.expires_at,'actions':sorted(service_actions)},now=now)
            service_grant=LifecycleConsent(**read_local_record(service_path))
            preparation_deadline=time.monotonic()+max(0,stage.max_seconds-(stage.clock()-stage.started)-5)
            client=OllamaClient('http://127.0.0.1:'+str(args.port),candidate['provider_version'],
                candidate['id'],candidate['manifest_sha256'],timeout=5,local_service_ref=service_grant.binding)
            scope='file:'+os.path.abspath(args.input_file);criteria='file:'+os.path.abspath(args.quality_case_file)
            if not _wizard_session_answer(ask,'允许读取指定输入与期望JSON，仅送本地模型作精确输入质量检查，并再次读取硬件元数据？输入 yes：',preparation_deadline):
                return {'state':'QUALIFICATION_DECLINED','qualified':False}
            grant=Grant(args.node,frozenset({'probe','qualify'}),min(now()+300,service_grant.expires_at),
                'wizard-exact-quality',quality_binding(client,args.task_class,scope,criteria))
            quality_path=_wizard_record(root,'quality',{'node_id':args.node,'scopes':sorted(grant.scopes),
                'expires_at':grant.expires_at,'reference':grant.reference,'binding':grant.binding},now=now)
            grant=Grant(**read_local_record(quality_path))
            grant.check(args.node,'qualify',quality_binding(client,args.task_class,scope,criteria),now=now())
            payload=read_task_bytes(args.input_file).decode('utf-8',errors='strict')
            def unique(pairs):
                result={}
                for key,value in pairs:
                    require(key not in result,'QUALITY_DUPLICATE_KEY');result[key]=value
                return result
            def invalid_constant(_):raise Stopped('QUALITY_NONFINITE')
            expected=json.loads(read_task_bytes(args.quality_case_file,16384),
                                object_pairs_hook=unique,parse_constant=invalid_constant)
            snapshot=probe(args.node,grant,reader or PlatformReader(args.disk_root),now=now())
            allow_return=_wizard_session_answer(ask,
                '仅质量检查通过后，允许Codex工具再执行该精确输入并将结果返回Codex云端？输入 yes：',
                preparation_deadline)
            if not allow_return:return {'state':'RETURN_TO_CLOUD_DECLINED','qualified':False}
            require(args.session_seconds <= stage.max_seconds-(stage.clock()-stage.started)-5,'SERVICE_SESSION_BUDGET')
            require(now()+args.session_seconds <= service_grant.expires_at,'SERVICE_CONSENT_SESSION_WINDOW')
            _wizard_port_available(args.port,preparation_deadline)
            service=OwnedOllamaService(stage,service_grant,port=args.port)
            started=service.start(idle_confirmed=args.idle_confirmed)
            require(started['state']=='SERVICE_STARTED_UNVALIDATED','SERVICE_START_FAILED')
            deadline=time.monotonic()+args.session_seconds
            active_wall_deadline=now()+args.session_seconds
            _wizard_wait_ready(stage,service,candidate,deadline)
            client.session_deadline=deadline
            qualification=qualify_exact_input(args.node,snapshot,client,args.task_class,scope,payload,
                expected,criteria,grant,native_probe=True,
                expires_at=min(grant.expires_at,active_wall_deadline,now()+max(0,deadline-time.monotonic())),now=now)
            require(qualification['qualified'],'WIZARD_QUALITY_NOT_QUALIFIED')
            require(time.monotonic()<deadline,'SERVICE_SESSION_DEADLINE')
            qualification_path=_wizard_record(root,'qualified',qualification,now=now)
            qualification=read_local_record(qualification_path,16384)
            require(qualification.get('qualified') is True and now()<qualification['expires_at'],
                    'WIZARD_QUALITY_NOT_QUALIFIED')
            infer=Grant(args.node,frozenset({'infer','return-to-cloud'}),qualification['expires_at'],
                        'wizard-exact-assist',qualification['exact_config'])
            infer_path=_wizard_record(root,'infer',{'node_id':args.node,'scopes':sorted(infer.scopes),
                'expires_at':infer.expires_at,'reference':infer.reference,'binding':infer.binding},now=now)
            infer=Grant(**read_local_record(infer_path))
            infer.check(args.node,'infer',qualification['exact_config'],now=now())
            infer.check(args.node,'return-to-cloud',qualification['exact_config'],now=now())
            command=[sys.executable,'-I','-B',str(Path(__file__).resolve()),'assist','--grant-file',infer_path,
                '--node',args.node,'--model-id',args.model_id,'--endpoint',client.endpoint,
                '--local-service-ref',service.binding,'--qualification-file',qualification_path,
                '--task-class',args.task_class,'--task-id','wizard-customer-task','--input-file',args.input_file,
                '--return-to-cloud']
            import shlex
            print(json.dumps({'state':'CODEX_TOOL_COMMAND_READY_SERVICE_ACTIVE','argv':command,
                'command':shlex.join(command),'session_seconds':args.session_seconds,
                'instructions':'保持此终端运行；在本次会话截止前由Codex执行该命令。程序不会自动调用Codex。',
                'codex_session':'NOT_RUN','cloud_savings':'UNVERIFIED'},ensure_ascii=True),flush=True)
            while time.monotonic()<deadline and stage.clock()<stage.started+stage.max_seconds-5:
                if service.handle.poll() is not None:break
                time.sleep(min(.1,max(0,deadline-time.monotonic())))
            return {'state':'SESSION_ENDED','codex_session':'NOT_OBSERVED','cloud_savings':'UNVERIFIED'}
        finally:
            primary=sys.exc_info()[0] is not None
            cleanup=None
            try:
                if service is not None:
                    try:cleanup=service.stop()
                    except Exception:cleanup={'state':'CLEANUP_UNKNOWN','descendants':'UNKNOWN'}
                    print(json.dumps({'state':'SERVICE_CLEANUP_RECEIPT','cleanup':cleanup,
                        'primary_failure_preserved':primary},ensure_ascii=True),flush=True)
                    if not primary:
                        require(cleanup.get('state')=='DIRECT_PROCESS_REAPED','WIZARD_CLEANUP_UNKNOWN')
            finally:
                try:stage.close()
                except Exception:
                    if primary:
                        print(json.dumps({'state':'STAGE_CLOSE_UNKNOWN','primary_failure_preserved':True}),flush=True)
                    else:raise Stopped('STAGE_CLOSE_UNKNOWN') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=NAME+'：显式入口；不自动安装/启用')
    parser.add_argument('action', choices=['status', 'prepare', 'setup', 'wizard', 'deployment-plan',
                                         'deploy-files', 'ownership-status', 'upgrade-check',
                                         'uninstall', 'serve-session', 'probe', 'inspect-runtime', 'qualify', 'assist'])
    parser.add_argument('--wizard-phase', choices=['plan','deploy','session','recovery'], default='plan')
    parser.add_argument('--grant-file')
    parser.add_argument('--node', default='this-device')
    parser.add_argument('--disk-root')
    parser.add_argument('--model-id', default='qwen3.5:4b')
    parser.add_argument('--existing-state')
    parser.add_argument('--endpoint', default='http://127.0.0.1:11434')
    parser.add_argument('--local-service-ref')
    parser.add_argument('--qualification-file')
    parser.add_argument('--install-root')
    parser.add_argument('--lifecycle-consent-file')
    parser.add_argument('--budget-file')
    parser.add_argument('--service-consent-file')
    parser.add_argument('--session-seconds', type=float, default=30)
    parser.add_argument('--port', type=int, default=11434)
    parser.add_argument('--idle-confirmed', action='store_true')
    parser.add_argument('--quality-case-file')
    parser.add_argument('--qualification-output')
    parser.add_argument('--task-class', choices=sorted(TASKS), default='log-summary')
    parser.add_argument('--task-id')
    parser.add_argument('--input-file')
    parser.add_argument('--return-to-cloud', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.action == 'wizard':
            result=customer_wizard(args)
            print(json.dumps(result,ensure_ascii=True,allow_nan=False))
            return 2 if result.get('state')=='STOP' else 0
        if args.action in ('ownership-status', 'upgrade-check', 'uninstall', 'serve-session'):
            plan = customer_deployment_plan(args.node, args.install_root, args.model_id)
            require(args.lifecycle_consent_file and args.budget_file, 'RESTORE_AUTHORITY_AND_BUDGET_REQUIRED')
            consent = LifecycleConsent(**read_local_record(args.lifecycle_consent_file))
            consent.check(args.node, plan['binding'], 'restore-ownership', time.time())
            budget = deployment.Budget(**read_local_record(args.budget_file))
            approved_root = Path(args.install_root)
            root_metadata = approved_root.lstat()
            require(approved_root == approved_root.resolve() and stat.S_ISDIR(root_metadata.st_mode) and
                    root_metadata.st_uid == os.getuid() and stat.S_IMODE(root_metadata.st_mode) == 0o700,
                    'RESTORE_ROOT_NOT_PRIVATE')
            catalog = load_catalog(); candidate = next(x for x in catalog['models'] if x['id'] == args.model_id)
            asset = catalog['runtime']['darwin_asset']
            blobs = [catalog_blob(candidate, catalog, kind='runtime-archive', sha256=asset['sha256'])]
            blobs += [catalog_blob(candidate, catalog, kind='model-blob', sha256=x['digest'].split(':')[1])
                      for x in candidate['layers']+[candidate['config_blob']]]
            with deployment.DurableJournal(Path(args.install_root)/'lifecycle.json', args.node) as journal:
                stage = PinnedStage.restore_owned(args.node, args.install_root, candidate, blobs,
                                                  consent, budget, journal, catalog=catalog)
                try:
                    if args.action in ('ownership-status', 'upgrade-check'):
                        result = {'state': 'OWNED_FILES_REVALIDATED', 'runtime_complete': stage.runtime_complete,
                                  'model_complete': stage.model_complete, 'activity': stage.activity,
                                  'reconciliation_required': stage.runner.recovery_required,
                                  'upgrade': 'SAME_PINS_REUSE_ONLY_NEW_PINS_REQUIRE_NEW_PRIVATE_ROOT',
                                  'qualified': False}
                    elif args.action == 'uninstall':
                        for action in ('save-ownership', 'uninstall-model', 'uninstall-runtime'):
                            consent.check(args.node, stage.binding, action, time.time())
                        require(args.idle_confirmed, 'UNINSTALL_REQUIRES_FRESH_HOST_IDLE_CONFIRMATION')
                        # Validate both trees before the first removal; do not infer idle from records.
                        if stage.model_name: stage._validate_runtime_tree(stage.started+stage.max_seconds, tree=stage.model_tree, top=stage.model_name)
                        if stage.runtime_name: stage._validate_runtime_tree(stage.started+stage.max_seconds)
                        if stage.activity != 'NEVER_STARTED':
                            consent.check(args.node, stage.binding, 'confirm-idle', time.time())
                        result = {'state': 'OWNED_FILES_REMOVED', 'removals': []}
                        if stage.model_name:
                            result['removals'].append(stage.remove_model(consent, idle_confirmed=True))
                            stage.save_ownership()
                        if stage.runtime_name:
                            result['removals'].append(stage.remove_runtime(consent, idle_confirmed=True))
                            stage.save_ownership()
                    else:
                        require(args.service_consent_file and number(args.session_seconds) and
                                0 < args.session_seconds <= 300, 'SERVICE_SESSION_AUTHORITY_REQUIRED')
                        service_consent = LifecycleConsent(**read_local_record(args.service_consent_file))
                        service = OwnedOllamaService(stage, service_consent, port=args.port)
                        remaining = stage.max_seconds-(stage.clock()-stage.started)-5
                        require(args.session_seconds <= remaining, 'SERVICE_SESSION_BUDGET')
                        result = {'state': 'SERVICE_SESSION_UNVALIDATED',
                                  'start': service.start(idle_confirmed=args.idle_confirmed)}
                        try:
                            if result['start']['state'] == 'SERVICE_STARTED_UNVALIDATED':
                                deadline = time.monotonic()+args.session_seconds
                                while (time.monotonic() < deadline and
                                       stage.clock() < stage.started+stage.max_seconds-5 and
                                       service.handle.poll() is None):
                                    time.sleep(min(.1, max(0, deadline-time.monotonic())))
                                if stage.clock() >= stage.started+stage.max_seconds-5:
                                    result['state'] = 'SESSION_SOFTWARE_DEADLINE'
                        except KeyboardInterrupt:
                            result['state'] = 'SESSION_INTERRUPTED'
                        finally:
                            result['cleanup'] = service.stop()
                finally:
                    stage.close()
            print(json.dumps(result, ensure_ascii=True, allow_nan=False))
            return 0 if args.action != 'serve-session' else 2  # start/reap is not native acceptance.
        if args.action in ('deployment-plan', 'deploy-files'):
            plan = customer_deployment_plan(args.node, args.install_root, args.model_id)
            if args.action == 'deployment-plan':
                print(json.dumps(plan, ensure_ascii=False, allow_nan=False))
                return 0
            require(args.lifecycle_consent_file and args.budget_file, 'DEPLOYMENT_CONSENT_AND_BUDGET_REQUIRED')
            def bounded_json(path):
                with open(path, 'rb') as source:
                    raw = source.read(8193)
                require(len(raw) <= 8192, 'DEPLOYMENT_RECORD_CAP')
                value = json.loads(raw)
                require(type(value) is dict, 'DEPLOYMENT_RECORD_SHAPE')
                return value
            consent = LifecycleConsent(**bounded_json(args.lifecycle_consent_file))
            reuse_requested = os.path.lexists(Path(args.install_root)/'lifecycle.json')
            for action in plan['reuse_actions'] if reuse_requested else plan['actions']:
                consent.check(args.node, plan['binding'], action, time.time())
            budget = deployment.Budget(**bounded_json(args.budget_file))
            require(reuse_requested or (budget.max_iterations >= plan['minimum_iterations'] and
                    budget.max_download_gb*1024**3 >= plan['download_bytes'] and
                    budget.max_peak_disk_gb*1024**3 >= plan['minimum_new_disk_bytes']),
                    'DEPLOYMENT_BUDGET_INSUFFICIENT')
            catalog = load_catalog()
            candidate = next(x for x in catalog['models'] if x['id'] == args.model_id)
            asset = catalog['runtime']['darwin_asset']
            blobs = [catalog_blob(candidate, catalog, kind='runtime-archive', sha256=asset['sha256'])]
            blobs += [catalog_blob(candidate, catalog, kind='model-blob', sha256=x['digest'].split(':')[1])
                      for x in candidate['layers']+[candidate['config_blob']]]
            # Caller-created private root is required; do not create/adopt it here.
            root = Path(args.install_root)
            info = root.lstat()
            require(root == root.resolve() and stat.S_ISDIR(info.st_mode) and
                    info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
                    'STAGE_ROOT_NOT_PRIVATE')
            require(args.grant_file is not None, 'PROBE_CONSENT_REQUIRED')
            probe_grant = Grant(**bounded_json(args.grant_file))
            # Explicit probe authority precedes native OS/resource reads.
            snapshot = probe(args.node, probe_grant, PlatformReader(str(root)))
            require(snapshot.get('os') == 'Darwin', 'RUNTIME_PLATFORM_UNSUPPORTED')
            probe_grant.check(args.node, 'probe')
            version = platform.mac_ver()[0].split('.')[0]
            require(version.isdigit() and int(version) >= 14 and
                    snapshot.get('architecture') in {'arm64', 'x86_64'},
                    'RUNTIME_PLATFORM_VERSION_UNSUPPORTED')
            fit = recommend(snapshot, {**catalog, 'models': [candidate]}, args.task_class)
            require((fit.get('candidate') or {}).get('id') == candidate['id'],
                    'DEPLOYMENT_RESOURCES_INSUFFICIENT')
            with deployment.DurableJournal(root/'lifecycle.json', args.node) as journal:
                stage = (PinnedStage.restore_owned(args.node, root, candidate, blobs, consent, budget, journal, catalog=catalog)
                         if reuse_requested else PinnedStage(args.node, root, candidate, blobs, consent, budget, journal))
                try:
                    if reuse_requested:
                        require(not stage.runner.recovery_required and stage.runtime_complete and stage.model_complete,
                                'REUSE_INCOMPLETE_OR_PENDING')
                        stage.save_ownership()
                        result = {'state': 'FILES_PREPARED_UNVALIDATED', 'reused': True,
                                  'download_bytes': 0, 'qualified': False, 'service_started': False}
                    else:
                        result = deploy_customer_files(stage)
                finally:
                    stage.close()
            print(json.dumps(result, ensure_ascii=True, allow_nan=False))
            return 0 if result['state'] == 'FILES_PREPARED_UNVALIDATED' else 2
        if args.action == 'setup':
            require(sys.stdin.isatty() and args.disk_root is not None, 'LOCAL_TERMINAL_AND_ROOT_REQUIRED')
            result = customer_setup(args.node, args.disk_root)
            print(json.dumps(result, ensure_ascii=False, allow_nan=False))
            return 0
        if args.action == 'status':
            print(json.dumps({'name': NAME, 'state': 'OPT_IN_REQUIRED', 'automatic_install_hook': False,
                              'probe_fields': sorted(deployment.PROBE_FIELDS),
                              'cloud_savings': 'UNVERIFIED'}, ensure_ascii=False))
            return 0
        if args.action == 'prepare':
            catalog = load_catalog()
            candidates = [m for m in catalog['models'] if m['id'] == args.model_id]
            require(len(candidates) == 1, 'MODEL_NOT_IN_CATALOG')
            existing = {}
            if args.existing_state:
                with open(args.existing_state, 'rb') as handle:
                    raw = handle.read(4097)
                require(len(raw) <= 4096, 'EXISTING_STATE_CAP')
                existing = json.loads(raw)
                require(type(existing) is dict, 'EXISTING_STATE_SHAPE')
            result = onboarding(existing, candidates[0], existing.get('prior_binding'),
                                existing.get('authorized_binding'), existing.get('authorization_expires_at'))
            result['guide'] = {'feature': NAME, 'optional': True,
                               'permissions': ['hardware-metadata', 'download-install',
                                               'bounded-validation', 'task-data-and-result-return'],
                               'consent_separate_per_scope': True,
                               'decline_preserves_20396': True,
                               'model_deployment': 'NOT_STARTED',
                               'wizard_argv': wizard_argv(args.node,args.model_id),
                               'required_arguments': ['--disk-root','--install-root']}
            # This command only plans. Existing records are assertions, never runtime proof.
            print(json.dumps(result, ensure_ascii=True, allow_nan=False))
            return 0
        require(args.grant_file is not None, 'CONSENT_REQUIRED')
        with open(args.grant_file, 'rb') as handle:
            raw = handle.read(4097)
        require(len(raw) <= 4096, 'GRANT_CAP')
        grant = Grant(**json.loads(raw))
        if args.action == 'probe':
            require(args.disk_root is not None, 'PROBE_ROOT_REQUIRED')
            snapshot = probe(args.node, grant, PlatformReader(args.disk_root))
            print(json.dumps(snapshot, ensure_ascii=True, allow_nan=False))
            return 0
        if args.action == 'inspect-runtime':
            model = next((x for x in load_catalog()['models'] if x['id'] == args.model_id), None)
            require(model is not None, 'MODEL_NOT_IN_CATALOG')
            client = OllamaClient(args.endpoint, model['provider_version'], model['id'],
                                  model['manifest_sha256'], local_service_ref=args.local_service_ref)
            result = inspect_existing_lifecycle(args.node, grant, client, model)
            print(json.dumps(result, ensure_ascii=True, allow_nan=False))
            return 0
        if args.action == 'qualify':
            require(args.disk_root and args.input_file and os.path.isabs(args.input_file),
                    'QUALIFICATION_ROOT_AND_DATA_SCOPE_REQUIRED')
            model = next((m for m in load_catalog()['models'] if m['id'] == args.model_id), None)
            require(model is not None, 'MODEL_NOT_IN_CATALOG')
            client = OllamaClient(args.endpoint, model['provider_version'], model['id'],
                                  model['manifest_sha256'], timeout=5,
                                  local_service_ref=args.local_service_ref)
            scope = 'file:'+os.path.abspath(args.input_file)
            if args.quality_case_file:
                require(os.path.isabs(args.quality_case_file), 'QUALITY_CRITERIA_SCOPE_REQUIRED')
                criteria_scope = 'file:'+os.path.abspath(args.quality_case_file)
                grant.check(args.node, 'qualify', quality_binding(client, args.task_class, scope, criteria_scope))
                private_record_target(args.qualification_output)
                payload = read_task_bytes(args.input_file).decode('utf-8', errors='strict')
                def unique_pairs(pairs):
                    result = {}
                    for key, value in pairs:
                        require(key not in result, 'QUALITY_DUPLICATE_KEY'); result[key] = value
                    return result
                expected = json.loads(read_task_bytes(args.quality_case_file, 16384), object_pairs_hook=unique_pairs)
                snapshot = probe(args.node, grant, PlatformReader(args.disk_root))
                result = qualify_exact_input(args.node, snapshot, client, args.task_class, scope,
                                               payload, expected, criteria_scope, grant, native_probe=True)
                if result['qualified']:
                    write_private_record(args.qualification_output, result)
                print(json.dumps({'state': result['state'], 'qualified': result['qualified'],
                                  'record_written': result['qualified'], 'usage': result['usage'],
                                  'cloud_savings': 'UNVERIFIED'}, ensure_ascii=True, allow_nan=False))
                return 0 if result['qualified'] else 2
            grant.check(args.node, 'qualify', task_binding(client, args.task_class, scope))
            snapshot = probe(args.node, grant, PlatformReader(args.disk_root))
            result = qualify_customer_task(args.node, snapshot, client, args.task_class,
                                           scope, grant, native_probe=True)
            # Contains only the fixed public fixture result and scoped Node, never input body.
            print(json.dumps(result, ensure_ascii=True, allow_nan=False))
            return 0 if result['qualified'] else 2
        # Tool stdout can enter the Codex cloud context: never release LOCAL_ONLY here.
        require(args.return_to_cloud and args.input_file and args.task_id and
                args.qualification_file, 'EXPLICIT_TOOL_RETURN_REQUIRED')
        require(os.path.isabs(args.input_file), 'INPUT_PATH_REQUIRED')
        model = next((m for m in load_catalog()['models'] if m['id'] == args.model_id), None)
        require(model is not None, 'MODEL_NOT_IN_CATALOG')
        client = OllamaClient(args.endpoint, model['provider_version'], model['id'],
                              model['manifest_sha256'], local_service_ref=args.local_service_ref)
        scope = 'file:'+os.path.abspath(args.input_file)
        with open(args.qualification_file, 'rb') as handle:
            qualification_raw = handle.read(16385)
        require(len(qualification_raw) <= 16384, 'QUALIFICATION_CAP')
        record = json.loads(qualification_raw)
        require(type(record) is dict, 'QUALIFICATION_SHAPE')
        require(number(record.get('expires_at')) and time.time() < record['expires_at'], 'QUALIFICATION_EXPIRED')
        node_fields = record['node']
        require(type(node_fields) is dict and type(node_fields.get('qualifications')) is list
                and len(node_fields['qualifications']) <= 32
                and all(type(q) is dict for q in node_fields['qualifications']), 'QUALIFICATION_SHAPE')
        node_fields['qualifications'] = frozenset(pool.Qualification(**q) for q in node_fields['qualifications'])
        node = pool.Node(**node_fields)
        require(node.node_id == args.node, 'NODE_BINDING_CHANGED')
        exact_record = record if record.get('schema_version') == 2 else None
        binding = (record.get('exact_config') if exact_record is not None else
                   task_binding(client, args.task_class, scope))
        grant.check(args.node, 'infer', binding)
        grant.check(args.node, 'return-to-cloud', binding)
        admission_task = pool.Task(args.task_id, args.task_class, scope, privacy='CLOUD_ALLOWED',
                                   output_privacy='CLOUD_ALLOWED', memory_required=model['memory_gb'])
        if exact_record is None:
            validate_node(node, client, admission_task)
        else:
            require(binding == exact_record_binding(client, args.task_class, scope, record) and
                    node.config == binding and node.qualifies(admission_task), 'EXACT_QUALIFICATION_BINDING')
        # Consent precedes reading task content; path is part of the exact binding.
        fd = os.open(args.input_file, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_INPUT, 'INPUT_TYPE_OR_CAP')
            raw = os.read(fd, MAX_INPUT+1)
            after = os.fstat(fd)
            require(len(raw) == before.st_size and (before.st_dev, before.st_ino, before.st_mode, before.st_size, before.st_mtime_ns, before.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_mode, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'INPUT_CHANGED_OR_SHORT')
        finally:
            os.close(fd)
        task = pool.Task(args.task_id, args.task_class, scope, privacy='CLOUD_ALLOWED',
                         output_privacy='CLOUD_ALLOWED', memory_required=model['memory_gb'],
                         payload=raw.decode('utf-8', errors='strict'))
        result, usage = run_local(task, client, grant, node, qualification_record=exact_record)
        print(json.dumps({'state': result.state, 'output': result.output,
                          'reconciliation_required': result.reconciliation_required,
                          'usage': [public_usage(item) for item in usage],
                          'cloud_savings': 'UNVERIFIED'}, ensure_ascii=True, allow_nan=False))
        return 0 if result.state == 'COMPLETED' else 2
    except CleanupUnknown:
        print(json.dumps({'name': NAME, 'state': 'UNKNOWN', 'reason': 'PROBE_CLEANUP_UNKNOWN'}))
        return 2
    except (Stopped, OSError, ValueError, TypeError, KeyError, RuntimeError, pool.UnknownOutcome):
        print(json.dumps({'name': NAME, 'state': 'STOP', 'reason': 'ADMISSION_OR_FACTS_UNKNOWN'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
