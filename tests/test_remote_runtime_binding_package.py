"""Installed core ships remote bindings without activating remote capabilities."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = Path('.agents/skills/long-horizon-engineering')


class RemoteRuntimeBindingPackageTests(unittest.TestCase):
    def test_core_install_import_is_inactive_and_self_contained(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'core'
            assembled = subprocess.run(
                [sys.executable, str(ROOT / 'scripts/assemble_skill_profile.py'),
                 '--profile', 'core-only', '--output-root', str(target), '--apply'],
                cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(assembled.returncode, 0, assembled.stderr)
            installed = target / SKILL
            self.assertTrue((installed / 'references/remote-runtime-binding.md').is_file())
            probe = '''
import http.client, os, pathlib, socket, subprocess, sys, threading
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
before = dict(os.environ)
with patch.object(subprocess, 'Popen', side_effect=AssertionError('process')), \\
     patch.object(socket, 'socket', side_effect=AssertionError('network')), \\
     patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS')), \\
     patch.object(http.client.HTTPSConnection, 'connect', side_effect=AssertionError('HTTP')), \\
     patch.object(threading.Thread, 'start', side_effect=AssertionError('thread')), \\
     patch.object(pathlib.Path, 'glob', side_effect=AssertionError('discovery')), \\
     patch.object(pathlib.Path, 'rglob', side_effect=AssertionError('discovery')), \\
     patch.object(os, 'open', side_effect=AssertionError('filesystem effect')):
    import remote_runtime_binding
    import runtime_safety_envelope as rse
    broker = rse.CapabilityBroker()
    assert not any(broker.has(name) for name in rse.CAPABILITIES.values())
assert before == dict(os.environ)
print('INACTIVE_REMOTE_CORE_IMPORT')
'''
            result = subprocess.run(
                [sys.executable, '-I', '-B', '-c', probe, str(installed / 'scripts')],
                cwd=temporary, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 'INACTIVE_REMOTE_CORE_IMPORT')

    def test_core_and_legacy_include_remote_artifacts(self):
        manifest = json.loads((ROOT / SKILL / 'package-manifest.json').read_text())
        core = set(manifest['components']['core']['paths'])
        for name in ('scripts/remote_runtime_binding.py', 'references/remote-runtime-binding.md'):
            self.assertIn(str(SKILL / name), core)
        optional = set(manifest['components']['bundled-optional']['paths'])
        self.assertFalse(core & optional)
