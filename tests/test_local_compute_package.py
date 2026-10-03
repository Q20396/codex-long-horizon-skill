"""Exercise the real default-profile assembler outside the source checkout."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LocalComputePackageTests(unittest.TestCase):
    def test_default_install_imports_beta_without_effects(self):
        self.check_installed_beta('profile')

    def test_direct_install_imports_beta_without_effects(self):
        self.check_installed_beta('direct')

    def check_installed_beta(self, mode):
        # Catches omitted inventory entries and imports tied to repository scripts.
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'installed'
            command = [
                sys.executable, str(ROOT / 'scripts/assemble_skill_profile.py'),
                '--profile', 'local-governance-core', '--output-root', str(target),
                '--apply',
            ]
            if mode == 'direct':
                target.mkdir()
                command = [sys.executable, str(ROOT / '.agents/skills/long-horizon-engineering/scripts/update_installed_skill.py'),
                           '--target-root', str(target), '--skill', 'long-horizon-engineering', '--apply']
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            skill = target / '.agents/skills/long-horizon-engineering'
            self.assertTrue((skill / 'SKILL.md').is_file())
            for name in ('local_compute_deployment', 'local_compute_pool'):
                self.assertTrue((skill / 'scripts' / (name + '.py')).is_file(), name)
            script = r'''
import sys, os, json
sys.path.insert(0, sys.argv[1])
def audit(event, args):
    if event.startswith(('socket.', 'subprocess.', 'os.spawn', 'os.exec')) or event in ('os.system', 'os.mkdir', 'os.remove', 'os.rename'):
        raise AssertionError('unexpected effect: ' + event)
    if event == 'open':
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            raise AssertionError('unexpected write')
sys.addaudithook(audit)
import local_compute_deployment as deployment
import local_compute_pool as pool
try:
    deployment.collect_probe('unapproved', set(), lambda _: (_ for _ in ()).throw(AssertionError('reader invoked')))
except PermissionError:
    pass
else:
    raise AssertionError('probe did not require consent')
assert deployment.minimum_value_gate({}) == 'INSUFFICIENT_EVIDENCE'
assert pool.Node('unapproved').consent is False
assert callable(pool.TaskPool)
print(json.dumps([deployment.__file__, pool.__file__]))
'''
            result = subprocess.run([sys.executable, '-I', '-B', '-c', script,
                                     str(skill / 'scripts')], cwd=temporary,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for path in json.loads(result.stdout):
                self.assertTrue(Path(path).is_relative_to(skill))
            result = subprocess.run([sys.executable, '-B', str(skill / 'scripts/check_skill_package.py'),
                                     '--installed'], cwd=target, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
