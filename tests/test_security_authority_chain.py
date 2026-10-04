"""Phase 1.25: real primitives, synthetic artifacts, temporary files only."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/long-horizon-engineering/scripts'
PATH = SCRIPTS / 'security_authority_chain.py'


class SecurityChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if PATH.exists():
            spec = importlib.util.spec_from_file_location('security_authority_chain', PATH)
            cls.m = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = cls.m
            spec.loader.exec_module(cls.m)

    def setUp(self):
        self.assertTrue(PATH.exists(), 'Phase 1.25 implementation missing')
        m = self.m
        self.root = m.SecurityAuthority('root', m.AuthorityRole.ROOT_OWNER, 'installation')
        self.admin = m.SecurityAuthority('admin', m.AuthorityRole.INSTALLATION_ADMIN, 'installation')
        self.project = m.SecurityAuthority('project-admin', m.AuthorityRole.PROJECT_AUTHORITY,
                                           'installation', project_id='project')
        self.task = m.SecurityAuthority('task-admin', m.AuthorityRole.TASK_AUTHORITY,
                                        'installation', project_id='project', task_id='task')
        self.runtime = m.SecurityAuthority('runtime', m.AuthorityRole.RUNTIME, 'installation',
                                           project_id='project', task_id='task')
        self.chain = m.InMemorySecurityChain('chain', 'installation')

    def event(self, identity='e1', **kwargs):
        values = dict(event_id=identity, event_type=self.m.EventType.SECURITY_ALERT,
                      timestamp=10, installation_id='installation', actor_role=self.root.role,
                      actor_id=self.root.authority_id, reason='synthetic reason')
        values.update(kwargs)
        return self.m.SecurityEventDraft(**values)

    def decision(self, actor, action, **kwargs):
        values = dict(installation_id='installation', project_id='project', task_id='task', now=10)
        values.update(kwargs)
        return self.m.authorize_management_change(actor, action, **values)

    def grant(self, **kwargs):
        values = dict(grant_id='bg', installation_id='installation', granted_by_authority_id='admin',
                      allowed_actions=frozenset({'READ_FILE'}), allowed_capabilities=frozenset({'filesystem.read'}),
                      allowed_targets=('/synthetic/a',), reason='synthetic emergency', issued_at=1,
                      expires_at=100, project_id='project', task_id='task')
        values.update(kwargs)
        return self.m.BreakGlassGrant(**values)

    def use(self, grant=None, **kwargs):
        values = dict(installation_id='installation', project_id='project', task_id='task', now=10,
                      action='READ_FILE', capability='filesystem.read', target='/synthetic/a')
        values.update(kwargs)
        return self.m.validate_break_glass(grant or self.grant(), **values)

    def test_canonical_bytes_are_fixed_and_numeric_semantics_normalized(self):
        self.assertEqual(self.m.canonical_bytes({'z': 1.0, 'a': ('é', True)}),
                         b'{"a":["\xc3\xa9",true],"z":1}')
        self.assertEqual(self.m.artifact_digest({'a': frozenset({'b', 'a'})}),
                         hashlib.sha256(b'{"a":["a","b"]}').hexdigest())

    def test_equivalent_event_seals_identically(self):
        a = self.chain.append(self.event())
        b = self.m.InMemorySecurityChain('chain', 'installation').append(self.event(timestamp=10.0))
        self.assertEqual(a, b)
        payload = asdict(a)
        payload.pop('record_hash')
        self.assertEqual(a.record_hash, hashlib.sha256(json.dumps(payload, sort_keys=True,
                         separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest())

    def test_link_sequence_and_genesis(self):
        records = [self.chain.append(self.event(str(i))) for i in range(3)]
        self.assertEqual([r.sequence for r in records], [1, 2, 3])
        self.assertEqual(records[0].previous_hash, '0' * 64)
        self.assertEqual(records[2].previous_hash, records[1].record_hash)
        self.assertTrue(self.chain.verify().valid)

    def test_modification_detected(self):
        r = self.chain.append(self.event())
        for changes in ({'timestamp': 11}, {'artifact_digest': 'a' * 64},
                        {'actor_role': 'RUNTIME'}, {'event_type': 'POLICY_CREATED'}):
            with self.subTest(changes=changes):
                result = self.m.verify_chain((replace(r, **changes),), 'chain', 'installation')
                self.assertFalse(result.valid)

    def test_reorder_middle_deletion_and_sequence_jump(self):
        rows = [self.chain.append(self.event(str(i))) for i in range(4)]
        for bad in ((rows[1], rows[0], *rows[2:]), (rows[0], *rows[2:]),
                    (replace(rows[0], sequence=2),)):
            self.assertFalse(self.m.verify_chain(bad, 'chain', 'installation').valid)

    def test_valid_tail_requires_expected_head(self):
        for i in range(5):
            self.chain.append(self.event(str(i)))
        head = self.chain.head()
        self.chain._records.pop()  # simulate privileged tampering, not public API
        self.assertTrue(self.chain.verify().valid)
        self.assertEqual(self.chain.verify_against(*head).reason, 'CHAIN_ROLLBACK_OR_DIVERGENCE')

    def test_prior_trusted_head_allows_valid_extension(self):
        self.chain.append(self.event())
        head = self.chain.head()
        self.chain.append(self.event('e2'))
        self.assertTrue(self.chain.verify_against(*head).valid)

    def test_rebuilt_chain_not_detectable_without_retained_head(self):
        self.chain.append(self.event())
        other = self.m.InMemorySecurityChain('chain', 'installation')
        other.append(self.event('different'))
        self.assertTrue(other.verify().valid)
        self.assertFalse(other.verify_against(*self.chain.head()).valid)

    def test_invalid_chain_append_is_closed(self):
        r = self.chain.append(self.event())
        self.chain._records[0] = replace(r, record_hash='f' * 64)
        with self.assertRaisesRegex(ValueError, '^CHAIN_INTEGRITY_FAILURE$'):
            self.chain.append(self.event('next'))
        self.assertEqual(len(self.chain.records()), 1)

    def test_duplicate_event_and_wrong_identity(self):
        self.chain.append(self.event())
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_EVENT_ID'):
            self.chain.append(self.event())
        with self.assertRaisesRegex(ValueError, 'CHAIN_ID_MISMATCH'):
            self.chain.append(self.event('x', installation_id='other'))
        self.assertFalse(self.m.verify_chain(self.chain.records(), 'other', 'installation').valid)

    def test_redaction_all_surfaces(self):
        marker = 'SYNTHETIC_PRIVATE_MARKER'
        record = self.chain.append(self.event(marker, actor_id=marker, subject_id=marker,
                                  reason=marker, evidence_refs=(marker,)))
        for output in (repr(record), self.m.canonical_bytes(asdict(record)).decode(), repr(self.chain.verify())):
            self.assertNotIn(marker, output)
        with self.assertRaisesRegex(ValueError, '^EVENT_INVALID$') as error:
            self.chain.append(self.event(marker * 1000))
        self.assertNotIn(marker, str(error.exception))

    def test_invalid_times_and_shapes(self):
        for value in (-1, True, float('nan'), float('inf'), 10**1000):
            with self.subTest(value=type(value).__name__):
                with self.assertRaisesRegex(ValueError, 'EVENT_INVALID'):
                    self.chain.append(self.event(timestamp=value))
                self.assertNotEqual(self.decision(self.admin, self.m.ManagementAction.PROJECT_POLICY_CHANGE,
                                                 now=value).disposition, 'ALLOW')
        with self.assertRaisesRegex(ValueError, 'EVENT_INVALID'):
            self.chain.append(self.event(evidence_refs=('x',) * 33))
        with self.assertRaises(ValueError):
            self.m.artifact_digest({'x': object()})

    def test_root_cannot_be_minted_or_disable_invariants(self):
        for actor in (self.root, self.admin, self.project, self.task, self.runtime):
            self.assertEqual(self.decision(actor, self.m.ManagementAction.PROJECT_POLICY_CHANGE,
                             root_invariant_change=True).reason, 'ROOT_INVARIANT_IMMUTABLE')
            self.assertNotEqual(self.decision(actor, self.m.ManagementAction.AUTHORITY_GRANT,
                                subject_authority=self.root).disposition, 'ALLOW')

    def test_runtime_has_no_management_authority(self):
        for action in self.m.ManagementAction:
            if action == self.m.ManagementAction.RSE_RECEIPT_RECORD:
                continue
            self.assertNotEqual(self.decision(self.runtime, action).disposition, 'ALLOW')

    def test_scope_and_role_matrix(self):
        m = self.m
        for actor, action, project, task, allowed in (
            (self.admin, m.ManagementAction.INSTALLATION_POLICY_CHANGE, None, None, True),
            (self.project, m.ManagementAction.PROJECT_POLICY_CHANGE, 'project', None, True),
            (self.project, m.ManagementAction.PROJECT_POLICY_CHANGE, 'other', None, False),
            (self.project, m.ManagementAction.INSTALLATION_POLICY_CHANGE, None, None, False),
            (self.task, m.ManagementAction.TASK_POLICY_CHANGE, 'project', 'task', True),
            (self.task, m.ManagementAction.TASK_POLICY_CHANGE, 'project', 'other', False),
            (self.task, m.ManagementAction.PROJECT_POLICY_CHANGE, 'project', None, False)):
            self.assertEqual(self.decision(actor, action, project_id=project, task_id=task).disposition == 'ALLOW', allowed)

    def test_child_cannot_escalate_or_extend_expiry(self):
        m = self.m
        for actor, subject in ((self.project, self.admin), (self.task, self.project),
                               (self.admin, self.root), (self.project, replace(self.task, project_id='other'))):
            self.assertNotEqual(self.decision(actor, m.ManagementAction.AUTHORITY_GRANT,
                                             subject_authority=subject).disposition, 'ALLOW')
        self.assertEqual(self.decision(self.project, m.ManagementAction.AUTHORITY_GRANT,
                                       subject_authority=self.task).disposition, 'ALLOW')
        self.assertNotEqual(self.decision(replace(self.project, expires_at=20),
            m.ManagementAction.AUTHORITY_GRANT, subject_authority=self.task).disposition, 'ALLOW')

    def test_revoked_expired_malformed_authority_denied(self):
        for actor in (replace(self.admin, revoked=True), replace(self.admin, expires_at=10),
                      replace(self.project, project_id=None), replace(self.task, task_id=None),
                      replace(self.admin, role='ROOT_OWNER'), replace(self.admin, expires_at=10**1000)):
            self.assertNotEqual(self.decision(actor, self.m.ManagementAction.PROJECT_POLICY_CHANGE).disposition, 'ALLOW')

    def test_break_glass_grant_authority(self):
        for actor in (self.root, self.admin, self.project, self.task, self.runtime):
            self.assertEqual(self.decision(actor, self.m.ManagementAction.BREAK_GLASS_GRANT).disposition == 'ALLOW',
                             actor in (self.root, self.admin))

    def test_break_glass_limits(self):
        self.assertEqual(self.use().disposition, 'ALLOW')
        for kwargs in ({'now':100}, {'now':0}, {'action':'DELETE_FILE'}, {'capability':'filesystem.write'},
                       {'target':'/synthetic/b'}, {'project_id':'other'}, {'root_invariant_change':True}):
            self.assertNotEqual(self.use(**kwargs).disposition, 'ALLOW')
        for changes in ({'reason':''}, {'expires_at':5000}, {'expires_at':1}, {'revoked':True},
                        {'allowed_targets':()}, {'allowed_actions':frozenset({'DISABLE_ROOT'})}):
            self.assertNotEqual(self.use(self.grant(**changes)).disposition, 'ALLOW')

    def test_management_history_preserves_old_artifacts(self):
        m = self.m
        old, new = {'synthetic_policy':1}, {'synthetic_policy':2}
        first = m.record_management_event(self.chain, self.admin, m.ManagementAction.PROJECT_POLICY_CHANGE,
            m.EventType.POLICY_CREATED, event_id='create', now=10, project_id='project', artifact=old)
        second = m.record_management_event(self.chain, self.admin, m.ManagementAction.PROJECT_POLICY_CHANGE,
            m.EventType.POLICY_SUPERSEDED, event_id='supersede', now=11, project_id='project',
            artifact=new, previous_artifact=old)
        self.assertEqual(second.previous_artifact_digest, m.artifact_digest(old))
        self.assertEqual(self.chain.records()[0], first)
        self.assertTrue(self.chain.verify().valid)

    def test_authority_revocation_history_and_future_denial(self):
        m = self.m
        for action, event, actor in ((m.ManagementAction.AUTHORITY_GRANT, m.EventType.AUTHORITY_GRANTED, self.task),
                                     (m.ManagementAction.AUTHORITY_REVOKE, m.EventType.AUTHORITY_REVOKED,
                                      replace(self.task, revoked=True))):
            m.record_management_event(self.chain, self.admin, action, event, event_id=event.value,
                now=10, project_id='project', task_id='task', artifact=actor, subject_authority=actor)
        self.assertEqual(len(self.chain.records()), 2)
        self.assertNotEqual(self.decision(replace(self.task, revoked=True), m.ManagementAction.TASK_POLICY_CHANGE).disposition,'ALLOW')

    def test_authorization_revocation_appends_and_denied_event_never_appends(self):
        m = self.m
        for action, event in ((m.ManagementAction.AUTHORIZATION_GRANT,m.EventType.AUTHORIZATION_GRANTED),
                              (m.ManagementAction.AUTHORIZATION_REVOKE,m.EventType.AUTHORIZATION_REVOKED)):
            m.record_management_event(self.chain,self.admin,action,event,event_id=event.value,now=10,
                                      project_id='project',task_id='task',artifact={'authorization':'synthetic'})
        with self.assertRaisesRegex(ValueError, 'CHANGE_OUT_OF_SCOPE'):
            m.record_management_event(self.chain,self.runtime,m.ManagementAction.PROJECT_POLICY_CHANGE,
                m.EventType.POLICY_CREATED,event_id='bad',now=10,project_id='project',task_id='task',artifact={})
        self.assertEqual(len(self.chain.records()),2)

    def test_break_glass_lifecycle_requires_use_and_explicit_expiration(self):
        m = self.m
        grant = self.grant()
        m.record_break_glass(self.chain,self.admin,grant,m.EventType.BREAK_GLASS_GRANTED,event_id='grant',now=1)
        m.record_break_glass(self.chain,self.runtime,grant,m.EventType.BREAK_GLASS_USED,event_id='use',now=10,
                            action='READ_FILE',capability='filesystem.read',target='/synthetic/a')
        m.record_break_glass(self.chain,self.admin,grant,m.EventType.BREAK_GLASS_EXPIRED,event_id='expire',now=100)
        self.assertEqual([r.event_type for r in self.chain.records()],
                         ['BREAK_GLASS_GRANTED','BREAK_GLASS_USED','BREAK_GLASS_EXPIRED'])
        self.assertNotEqual(self.use(now=100).disposition,'ALLOW')

    def test_receipt_reference_not_raw_content(self):
        spec = importlib.util.spec_from_file_location('rse_chain_fixture',SCRIPTS/'runtime_safety_envelope.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        receipt = module.evaluate_and_execute(None,(),None,None,None,10)
        r = self.m.record_receipt(self.chain,self.runtime,receipt,event_id='receipt',now=10,
                                  project_id='project',task_id='task')
        self.assertEqual(r.artifact_digest,self.m.artifact_digest(receipt))
        self.assertNotIn('MALFORMED_ACTION',repr(r))

    def test_break_glass_expiration_cannot_be_undone_by_backdating_use(self):
        m=self.m
        grant=self.grant()
        m.record_break_glass(self.chain,self.admin,grant,m.EventType.BREAK_GLASS_GRANTED,event_id='grant',now=1)
        m.record_break_glass(self.chain,self.admin,grant,m.EventType.BREAK_GLASS_EXPIRED,event_id='expire',now=100)
        with self.assertRaisesRegex(ValueError,'BREAK_GLASS_EXPIRED'):
            m.record_break_glass(self.chain,self.runtime,grant,m.EventType.BREAK_GLASS_USED,event_id='use',now=10,
                                action='READ_FILE',capability='filesystem.read',target='/synthetic/a')

    def test_break_glass_use_without_recorded_grant_denied(self):
        with self.assertRaisesRegex(ValueError,'BREAK_GLASS_NOT_ALLOWED'):
            self.m.record_break_glass(self.chain,self.runtime,self.grant(),self.m.EventType.BREAK_GLASS_USED,
                event_id='use',now=10,action='READ_FILE',capability='filesystem.read',target='/synthetic/a')

    def test_event_kind_cannot_bypass_management_check(self):
        with self.assertRaisesRegex(ValueError,'EVENT_INVALID'):
            self.m.record_management_event(self.chain,self.admin,self.m.ManagementAction.PROJECT_POLICY_CHANGE,
                self.m.EventType.AUTHORITY_GRANTED,event_id='bad',now=10,project_id='project',artifact={})
        self.assertEqual(self.chain.records(),())

    def test_record_evidence_is_immutable_and_bad_shape_fails_safely(self):
        r=self.chain.append(self.event())
        bad=replace(r,evidence_refs=['raw-private'])
        self.assertFalse(self.m.verify_chain((bad,),'chain','installation').valid)

    def test_cyclic_malformed_record_fails_closed_without_deepcopy(self):
        r=self.chain.append(self.event())
        cyclic=[]
        cyclic.append(cyclic)
        for field in ('evidence_refs','artifact_digest','timestamp'):
            with self.subTest(field=field):
                bad=replace(r,**{field:cyclic})
                self.assertFalse(self.m.verify_chain((bad,),'chain','installation').valid)
                self.chain._records=[bad]
                with self.assertRaisesRegex(ValueError,'CHAIN_INTEGRITY_FAILURE'):
                    self.chain.append(self.event('next'))

    def test_break_glass_broader_grant_records_actual_scoped_use(self):
        m=self.m
        for project in (None,'project'):
            with self.subTest(project=project):
                chain=m.InMemorySecurityChain('chain','installation')
                grant=self.grant(project_id=project,task_id=None)
                m.record_break_glass(chain,self.admin,grant,m.EventType.BREAK_GLASS_GRANTED,event_id='g',now=1)
                row=m.record_break_glass(chain,self.runtime,grant,m.EventType.BREAK_GLASS_USED,event_id='u',now=10,
                    project_id='project',task_id='task',action='READ_FILE',capability='filesystem.read',target='/synthetic/a')
                self.assertEqual(row.project_ref,hashlib.sha256(b'project').hexdigest())
                self.assertEqual(row.task_ref,hashlib.sha256(b'task').hexdigest())
                with self.assertRaises(ValueError):
                    m.record_break_glass(chain,self.runtime,grant,m.EventType.BREAK_GLASS_USED,event_id='bad',now=10,
                        project_id='other',task_id='task',action='READ_FILE',capability='filesystem.read',target='/synthetic/a')
                self.assertEqual(len(chain.records()),2)

    def test_break_glass_capability_map_matches_rse(self):
        spec=importlib.util.spec_from_file_location('rse_parity',SCRIPTS/'runtime_safety_envelope.py')
        module=importlib.util.module_from_spec(spec)
        sys.modules[spec.name]=module
        spec.loader.exec_module(module)
        self.assertEqual(self.m._ACTION_CAPABILITY,{a.value:c for a,c in module.CAPABILITIES.items()})

    def test_durable_same_object_threads_and_fsync(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'history.jsonl'
            chain=self.m.JsonlSecurityChain('chain','installation',path,create=True)
            with patch.object(self.m.os,'fsync',wraps=os.fsync) as sync:
                with ThreadPoolExecutor(max_workers=4) as pool:
                    list(pool.map(lambda i:chain.append(self.event(str(i))),range(12)))
                self.assertEqual(sync.call_count,12)
            self.assertEqual(chain.head()[0],12)
            self.assertTrue(chain.verify().valid)

    @unittest.skipUnless(os.name=='posix','POSIX file checks')
    def test_durable_symlink_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'history.jsonl'
            self.m.JsonlSecurityChain('chain','installation',path,create=True)
            link=Path(directory)/'link'
            link.symlink_to(path)
            with self.assertRaisesRegex(ValueError,'CHAIN_IO_FAILURE'):
                self.m.JsonlSecurityChain('chain','installation',link)

    def test_append_only_surface(self):
        for name in ('update_record','delete_record','replace_history','repair','truncate_to_valid'):
            self.assertFalse(hasattr(self.chain,name))
        self.chain.append(self.event())
        self.assertIsInstance(self.chain.records(),tuple)

    def test_same_object_threaded_append(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda i:self.chain.append(self.event(str(i))),range(40)))
        self.assertEqual([r.sequence for r in self.chain.records()],list(range(1,41)))
        self.assertTrue(self.chain.verify().valid)

    def test_durable_restart_permissions_and_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'history.jsonl'
            chain = self.m.JsonlSecurityChain('chain','installation',path,create=True)
            chain.append(self.event())
            other = self.m.JsonlSecurityChain('chain','installation',path)
            self.assertEqual(other.head(),chain.head())
            self.assertTrue(other.verify().valid)
            if os.name == 'posix':
                self.assertEqual(path.stat().st_mode & 0o777,0o600)
            with self.assertRaisesRegex(ValueError,'CHAIN_INTEGRITY_FAILURE'):
                self.m.JsonlSecurityChain('wrong','installation',path)
            with self.assertRaises(ValueError):
                self.m.JsonlSecurityChain('chain','installation',path,create=True)

    def test_partial_json_and_duplicate_keys_fail_closed_without_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'history.jsonl'
            chain = self.m.JsonlSecurityChain('chain','installation',path,create=True)
            chain.append(self.event())
            original = path.read_bytes()
            for bad in (original[:-4],original+b'{"sequence":2,"sequence":3}\n',original+b'\n'):
                path.write_bytes(bad)  # synthetic corruption fixture
                self.assertFalse(chain.verify().valid)
                with self.assertRaisesRegex(ValueError,'CHAIN_INTEGRITY_FAILURE'):
                    chain.append(self.event('next'))
                self.assertEqual(path.read_bytes(),bad)

    def test_durable_fsync_failure_latches_uncertainty(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'history.jsonl'
            chain=self.m.JsonlSecurityChain('chain','installation',path,create=True)
            with patch.object(self.m.os,'fsync',side_effect=OSError('SYNTHETIC_PRIVATE_MARKER')):
                with self.assertRaisesRegex(ValueError,'CHAIN_IO_UNCERTAIN') as error:
                    chain.append(self.event())
            self.assertNotIn('SYNTHETIC',str(error.exception))
            with self.assertRaisesRegex(ValueError,'CHAIN_IO_UNCERTAIN'):
                chain.append(self.event('next'))

    def test_durable_close_failure_also_latches_uncertainty(self):
        with tempfile.TemporaryDirectory() as directory:
            chain=self.m.JsonlSecurityChain('chain','installation',Path(directory)/'history',create=True)
            original_open=chain._open
            @contextmanager
            def failing_close(write=False):
                with original_open(write=write) as stream:
                    yield stream
                raise OSError('SYNTHETIC_PRIVATE_CLOSE')
            with patch.object(chain,'_open',side_effect=failing_close):
                with self.assertRaisesRegex(ValueError,'CHAIN_IO_UNCERTAIN'):
                    chain.append(self.event())
            with self.assertRaisesRegex(ValueError,'CHAIN_IO_UNCERTAIN'):
                chain.append(self.event('next'))

    def test_missing_file_not_silently_recreated(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'CHAIN_IO_FAILURE'):
                self.m.JsonlSecurityChain('chain','installation',Path(directory)/'missing')

    def test_import_has_no_effects(self):
        import socket
        import subprocess
        import threading
        source=PATH.read_text()
        namespace={'__name__':'security_authority_chain'}
        before=dict(os.environ)
        with patch('builtins.open',side_effect=AssertionError('read/write')), \
             patch.object(os,'open',side_effect=AssertionError('open')), \
             patch.object(socket,'socket',side_effect=AssertionError('network')), \
             patch.object(subprocess,'Popen',side_effect=AssertionError('process')), \
             patch.object(threading.Thread,'start',side_effect=AssertionError('thread')):
            exec(compile(source,str(PATH),'exec'),namespace)
        self.assertEqual(dict(os.environ),before)


if __name__ == '__main__':
    unittest.main()
