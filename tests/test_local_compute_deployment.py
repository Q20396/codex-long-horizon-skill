import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

PATH = Path(__file__).resolve().parents[1] / '.agents/skills/long-horizon-engineering/scripts/local_compute_deployment.py'


class SyntheticJournal:
    def __init__(self):
        self.snapshot = {'state': 'CLEAN', 'download_gb': 0, 'peak_disk_gb': 0,
                         'iterations': 0, 'restarts': 0, 'elapsed_seconds': 0}
        self.events = []

    def load(self, node_id):
        return dict(self.snapshot)

    def __call__(self, event):
        self.events.append(event)
        self.snapshot.update(event)


class DeploymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if PATH.exists():
            spec = importlib.util.spec_from_file_location('local_compute_deployment', PATH)
            cls.m = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = cls.m
            spec.loader.exec_module(cls.m)

    def setUp(self):
        self.assertTrue(PATH.exists(), 'bounded deployment runtime is missing')

    def test_probe_requires_exact_node_consent_and_filters_identity(self):
        reads = []
        def reader(node):
            reads.append(node)
            return {'memory_available_gb': 16, 'serial_number': 'PRIVATE'}
        with self.assertRaises(PermissionError):
            self.m.collect_probe('b', {'a'}, reader)
        self.assertEqual(reads, [])
        self.assertEqual(self.m.collect_probe('a', {'a'}, reader),
                         {'node_id': 'a', 'memory_available_gb': 16})

    def test_gate_distinguishes_unknown_and_known_inadequacy(self):
        self.assertEqual(self.m.minimum_value_gate({}), 'INSUFFICIENT_EVIDENCE')
        self.assertEqual(self.m.minimum_value_gate({'memory_available_gb': 1}), 'INSUFFICIENT_EVIDENCE')
        probe = {'memory_available_gb': 16, 'free_storage_gb': 30}
        self.assertEqual(self.m.minimum_value_gate(probe), 'INSUFFICIENT_EVIDENCE')
        criteria = {'minimum_memory_gb': 8, 'minimum_disk_gb': 10,
                    'task_value': True, 'provider_compatible': True,
                    'correction_burden_acceptable': True}
        self.assertEqual(self.m.minimum_value_gate(probe, criteria), 'POTENTIALLY_VIABLE')
        self.assertEqual(self.m.minimum_value_gate({'memory_available_gb': 1}, criteria), 'NOT_MET')

    def test_selection_requires_explicit_approved_fit(self):
        candidates = [{'id': 'large', 'memory_gb': 40, 'disk_gb': 20},
                      {'id': 'small', 'memory_gb': 8, 'disk_gb': 10}]
        probe = {'memory_available_gb': 16, 'free_storage_gb': 30}
        self.assertIsNone(self.m.select_candidate(probe, candidates, {'large'}))
        self.assertEqual(self.m.select_candidate(probe, candidates, {'small'})['id'], 'small')
        candidates[0]['memory_gb'] = 12
        self.assertEqual(self.m.select_candidate(probe, candidates, {'small', 'large'})['id'], 'large')
        with self.assertRaises(ValueError):
            self.m.select_candidate(probe, [candidates[0], candidates[0]], {'large'})

    def runner(self, effects, adapter, journal=None, **limits):
        budget = self.m.Budget(**({'max_download_gb': 5, 'max_peak_disk_gb': 10,
                                  'max_iterations': 3, 'max_restarts': 1,
                                  'max_seconds': 10} | limits))
        approval = self.m.Approval('a', frozenset(e.fingerprint() for e in effects), budget)
        return self.m.DeploymentRunner(approval, adapter, journal=journal)

    def test_exact_effect_scope_and_default_transport(self):
        effect = self.m.Effect('a', 'download', 'model-v1', download_gb=2, peak_disk_gb=4)
        runner = self.runner([effect], self.m.UnsupportedAdapter())
        self.assertEqual(runner.run(effect)['state'], 'UNSUPPORTED')
        changed = self.m.Effect('a', 'download', 'model-v2', download_gb=2, peak_disk_gb=4)
        self.assertEqual(runner.run(changed)['state'], 'NOT_AUTHORIZED')

    def test_budget_reserves_cumulative_download_and_peak_disk(self):
        effect = self.m.Effect('a', 'download', 'model', download_gb=3, peak_disk_gb=4)
        runner = self.runner([effect], lambda effect, timeout: 'SUCCEEDED')
        self.assertEqual(runner.run(effect)['state'], 'SUCCEEDED')
        self.assertEqual(runner.run(effect)['state'], 'BUDGET_EXCEEDED')
        self.assertEqual(runner.download_gb, 3)

    def test_unknown_outcome_blocks_retry_until_read_only_reconciliation(self):
        effect = self.m.Effect('a', 'start', 'provider')
        def crash(effect, timeout):
            raise TimeoutError('sensitive exception must not escape')
        runner = self.runner([effect], crash)
        self.assertEqual(runner.run(effect)['state'], 'UNKNOWN_OUTCOME')
        self.assertEqual(runner.run(effect)['state'], 'RECONCILIATION_REQUIRED')
        self.assertEqual(runner.reconcile(lambda e: 'UNKNOWN')['state'], 'RECONCILIATION_REQUIRED')
        self.assertEqual(runner.reconcile(lambda e: 'NOT_APPLIED')['state'], 'RECONCILED')
        self.assertEqual(runner.run(effect)['state'], 'UNKNOWN_OUTCOME')

    def test_tuning_bounded_and_smoke_does_not_qualify(self):
        effects = [self.m.Effect('a', 'tune', str(i)) for i in range(4)]
        runner = self.runner(effects, lambda e, timeout: 'SUCCEEDED', max_iterations=2)
        results = runner.tune(effects)
        self.assertEqual([r['state'] for r in results], ['SUCCEEDED', 'SUCCEEDED', 'BUDGET_EXCEEDED'])
        self.assertTrue(all(r['task_qualified'] is False for r in results))

    def test_bad_numbers_and_restart_limits_fail_closed(self):
        with self.assertRaises(ValueError):
            self.m.Effect('a', 'download', 'x', download_gb=float('nan'))
        effect = self.m.Effect('a', 'restart', 'p')
        runner = self.runner([effect], lambda e, timeout: 'SUCCEEDED')
        self.assertEqual(runner.run(effect)['state'], 'SUCCEEDED')
        self.assertEqual(runner.run(effect)['state'], 'BUDGET_EXCEEDED')

    def test_exact_subprocess_recipe_and_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = (sys.executable, '-I', '-c', 'pass')
            effect = self.m.Effect('a', 'smoke', 'synthetic', recipe_digest=self.m.recipe_digest(argv, directory))
            adapter = self.m.SubprocessAdapter('a', {effect.fingerprint():
                (argv, directory)})
            runner = self.runner([effect], adapter)
            self.assertEqual(runner.run(effect)['state'], 'JOURNAL_REQUIRED')
            journal = SyntheticJournal()
            runner = self.runner([effect], adapter, journal=journal)
            self.assertEqual(runner.run(effect)['state'], 'SUCCEEDED')
            self.assertEqual(journal.events[0]['state'], 'PENDING')
            argv = (sys.executable, '-I', '-c', 'import time; time.sleep(5)')
            adapter = self.m.SubprocessAdapter('a', {effect.fingerprint(): (argv, directory)})
            self.assertEqual(self.runner([effect], adapter, journal=SyntheticJournal()).run(effect)['state'], 'NOT_APPLIED')
            effect = self.m.Effect('a', 'smoke', 'synthetic', recipe_digest=self.m.recipe_digest(argv, directory))
            adapter = self.m.SubprocessAdapter('a', {effect.fingerprint(): (argv, directory)})
            journal = SyntheticJournal()
            runner = self.runner([effect], adapter, journal=journal, max_seconds=0.1)
            self.assertEqual(runner.run(effect)['state'], 'UNKNOWN_OUTCOME')
            self.assertEqual(self.runner([effect], adapter, journal=journal).run(effect)['state'], 'RECONCILIATION_REQUIRED')
            adapter = self.m.SubprocessAdapter('other-node', {effect.fingerprint(): (argv, directory)})
            self.assertEqual(self.runner([effect], adapter, journal=SyntheticJournal()).run(effect)['state'], 'NOT_APPLIED')

    def test_approved_plan_stops_on_unknown_before_smoke(self):
        effects = [self.m.Effect('a', 'install', 'p'), self.m.Effect('a', 'smoke', 'p')]
        runner = self.runner(effects, lambda e, timeout: 'UNKNOWN')
        self.assertEqual([r['state'] for r in runner.execute_plan(effects)], ['UNKNOWN_OUTCOME'])

    def test_total_disk_footprint_over_budget_is_rejected(self):
        effect = self.m.Effect('a', 'download', 'p', peak_disk_gb=11)
        runner = self.runner([effect], lambda e, timeout: 'SUCCEEDED')
        self.assertEqual(runner.run(effect)['state'], 'BUDGET_EXCEEDED')
        self.assertEqual(runner.iterations, 0)

    def test_restored_budget_cannot_reset_and_write_only_journal_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = (sys.executable, '-I', '-c', 'pass')
            effect = self.m.Effect('a', 'download', 'p', download_gb=3,
                                   recipe_digest=self.m.recipe_digest(argv, directory))
            adapter = self.m.SubprocessAdapter('a', {effect.fingerprint(): (argv, directory)})
            self.assertEqual(self.runner([effect], adapter, journal=lambda e: None).run(effect)['state'], 'RECONCILIATION_REQUIRED')
            journal = SyntheticJournal()
            self.assertEqual(self.runner([effect], adapter, journal=journal).run(effect)['state'], 'SUCCEEDED')
            self.assertEqual(self.runner([effect], adapter, journal=journal).run(effect)['state'], 'BUDGET_EXCEEDED')

    def test_generic_adapter_restarts_reconcile_exact_pending_effect(self):
        effect = self.m.Effect('a', 'start', 'private-target-not-to-persist')
        journal = SyntheticJournal()
        first = self.runner([effect], lambda e, t: 'UNKNOWN', journal=journal)
        self.assertEqual(first.run(effect)['state'], 'UNKNOWN_OUTCOME')
        approval = first.approval
        restored = self.m.DeploymentRunner(approval, lambda e, t: 'SUCCEEDED',
                                          journal=journal, approved_effects=[effect])
        self.assertEqual(restored.run(effect)['state'], 'RECONCILIATION_REQUIRED')
        seen = []
        def reconcile(pending):
            seen.append(pending)
            return 'NOT_APPLIED'
        self.assertEqual(restored.reconcile(reconcile)['state'], 'RECONCILED')
        self.assertEqual(seen, [effect])
        self.assertNotIn('private-target', str(journal.snapshot))
        # Unknown elapsed time conservatively exhausts the old time budget.
        self.assertEqual(restored.run(effect)['state'], 'BUDGET_EXCEEDED')

    def test_durable_journal_exclusive_owner_and_atomic_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            with self.m.DurableJournal(path, 'a') as journal:
                with self.assertRaises(RuntimeError):
                    self.m.DurableJournal(path, 'a')
                effect = self.m.Effect('a', 'download', 'private', download_gb=3)
                first = self.runner([effect], lambda e, t: 'SUCCEEDED', journal=journal)
                self.assertEqual(first.run(effect)['state'], 'SUCCEEDED')
            self.assertNotIn('private', path.read_text())
            with self.m.DurableJournal(path, 'a') as journal:
                self.assertEqual(self.runner([effect], lambda e, t: 'SUCCEEDED', journal=journal).run(effect)['state'], 'BUDGET_EXCEEDED')
            with self.assertRaises(ValueError):
                with self.m.DurableJournal(path, 'b') as journal:
                    journal.load('b')

    def test_pool_reservations_survive_restart_and_count_per_node_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'pool.json'
            with self.m.DurableJournal(path, 'pool') as journal:
                pool = self.m.PoolBudgetLedger(journal, 5, 10)
                a = self.m.Effect('a', 'download', 'a', download_gb=3, peak_disk_gb=6)
                b = self.m.Effect('b', 'download', 'b', download_gb=1, peak_disk_gb=5)
                self.assertTrue(pool.reserve(a))
                self.assertFalse(pool.reserve(b))
                self.assertTrue(pool.reserve(self.m.Effect('b', 'download', 'b', download_gb=1, peak_disk_gb=4)))
            with self.m.DurableJournal(path, 'pool') as journal:
                pool = self.m.PoolBudgetLedger(journal, 5, 10)
                self.assertFalse(pool.reserve(a))

    def test_pool_concurrent_reservations_and_runner_stop_before_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.m.DurableJournal(Path(directory) / 'pool.json', 'pool') as journal:
                pool = self.m.PoolBudgetLedger(journal, 3, 10)
                effects = [self.m.Effect(node, 'download', 'p', download_gb=2, peak_disk_gb=3)
                           for node in ('a', 'b')]
                with ThreadPoolExecutor(max_workers=2) as executor:
                    outcomes = list(executor.map(pool.reserve, effects))
                self.assertEqual(sorted(outcomes), [False, True])
                calls = []
                first = self.runner([effects[0]], lambda e, t: calls.append(e))
                runner = self.m.DeploymentRunner(first.approval, lambda e, t: calls.append(e), pool_budget=pool)
                self.assertEqual(runner.run(effects[0])['state'], 'BUDGET_EXCEEDED')
                self.assertEqual(calls, [])

    def test_durable_journal_rejects_payload_in_metadata_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.m.DurableJournal(Path(directory) / 'node.json', 'a') as journal:
                with self.assertRaises(ValueError):
                    journal({'state': 'sensitive message'})
                with self.assertRaises(ValueError):
                    journal({'effect': 'secret command'})
                with self.assertRaises(ValueError):
                    journal({'download_gb': -1})

    def test_durable_pending_recovers_only_current_approved_effect(self):
        effect = self.m.Effect('a', 'configure', 'private')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            with self.m.DurableJournal(path, 'a') as journal:
                first = self.runner([effect], lambda e, t: 'UNKNOWN', journal=journal)
                duplicate = self.runner([effect], lambda e, t: 'SUCCEEDED', journal=journal)
                self.assertEqual(duplicate.run(effect)['state'], 'RECONCILIATION_REQUIRED')
                self.assertEqual(first.run(effect)['state'], 'UNKNOWN_OUTCOME')
            with self.m.DurableJournal(path, 'a') as journal:
                restored = self.m.DeploymentRunner(first.approval, journal=journal, approved_effects=[effect])
                self.assertEqual(restored.reconcile(lambda pending: 'APPLIED' if pending == effect else 'UNKNOWN')['state'], 'RECONCILED')
            with self.m.DurableJournal(path, 'a') as journal:
                self.assertEqual(journal.load('a')['state'], 'APPLIED')


class OwnedFilesJournalTests(unittest.TestCase):
    """Only private temporary metadata; no real runtime/model/file contents."""
    setUpClass = DeploymentTests.__dict__['setUpClass']

    def snapshot(self):
        pin = 'a' * 64
        return {'schema': 1, 'binding': 'b'*64, 'root_binding': 'c'*64,
                'runtime_pin': pin, 'model_pin': 'd'*64,
                'root_identity': {'dev': 1, 'ino': 2}, 'io_state': 'CONFIRMED',
                'blobs': {pin: {'name': pin+'.blob', 'device': 1, 'inode': 3,
                    'bytes': 4, 'complete': True, 'sha256': pin, 'size': 4,
                    'mtime_ns': 5, 'ctime_ns': 6, 'close_confirmed': True}},
                'runtime': {'name': None, 'complete': False, 'tree': {}},
                'model': {'name': None, 'complete': False, 'tree': {}}}

    def test_owned_snapshot_roundtrip_deepcopy_and_budget_pending_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'node.json'
            with self.m.DurableJournal(path, 'a') as journal:
                journal({'state':'PENDING','effect':'e'*64,'download_gb':7,
                         'peak_disk_gb':8,'iterations':4,'restarts':2,'elapsed_seconds':9})
                previous = journal.load('a')
                self.assertIsNone(journal.load_owned_files('a'))
                owned = self.snapshot(); journal.save_owned_files('a', owned)
                owned['root_identity']['ino'] = 99
                restored = journal.load_owned_files('a')
                self.assertEqual(restored['root_identity']['ino'],2)
                restored['root_identity']['ino'] = 98
                self.assertEqual(journal.load_owned_files('a')['root_identity']['ino'],2)
                for key, value in previous.items():
                    self.assertEqual(journal.load('a')[key],value)
            with self.m.DurableJournal(path,'a') as journal:
                self.assertEqual(journal.load_owned_files('a'),self.snapshot())
                self.assertEqual(journal.load('a')['state'],'PENDING')
                self.assertEqual(journal.load('a')['iterations'],4)

    def test_invalid_types_paths_fields_and_counts_refused_before_write(self):
        variants = []
        for key, value in [('schema',True),('schema',-0.0),('binding','bad'),
                           ('io_state',False),('unexpected','secret')]:
            v=self.snapshot();v[key]=value;variants.append(v)
        for key,value in [('dev',True),('ino',-1),('ino',-0.0)]:
            v=self.snapshot();v['root_identity'][key]=value;variants.append(v)
        for key,value in [('name','/private/file'),('name','../file'),('complete',1),
                           ('bytes',True),('size',-0.0),('pid',123),('close_confirmed',0)]:
            v=self.snapshot();next(iter(v['blobs'].values()))[key]=value;variants.append(v)
        v=self.snapshot();v['runtime']['name']='/'+'a'*64+'.runtime';variants.append(v)
        v=self.snapshot();v['blobs']={format(i,'064x'):{**next(iter(v['blobs'].values())),
            'name':format(i,'064x')+'.blob','sha256':format(i,'064x')} for i in range(257)};variants.append(v)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'node.json'
            with self.m.DurableJournal(path,'a') as journal:
                for variant in variants:
                    with self.subTest(variant=str(variant)[:90]):
                        with self.assertRaises(ValueError):journal.save_owned_files('a',variant)
                        self.assertFalse(path.exists())
                with self.assertRaises(ValueError):journal.save_owned_files('wrong',self.snapshot())

    def test_unknown_io_retains_incomplete_receipt_without_promoting_authority(self):
        v=self.snapshot();v['io_state']='UNKNOWN'
        r=next(iter(v['blobs'].values()));r.update(name='a'*64+'.blob.part',complete=False,close_confirmed=False)
        for k in ('size','mtime_ns','ctime_ns'):r.pop(k)
        with tempfile.TemporaryDirectory() as directory:
            with self.m.DurableJournal(Path(directory)/'node.json','a') as journal:
                journal.save_owned_files('a',v)
                self.assertEqual(journal.load_owned_files('a')['io_state'],'UNKNOWN')
                v['io_state']='CONFIRMED'
                with self.assertRaises(ValueError):journal.save_owned_files('a',v)

    def test_tree_receipts_relative_parent_link_and_exact_kind(self):
        v=self.snapshot();pin=v['runtime_pin']
        base={'device':1,'inode':9,'size':0,'mtime_ns':5,'ctime_ns':6,'mode':0o700,'kind':0o040000}
        v['runtime']={'name':pin+'.runtime','complete':True,'tree':{
            '':base,'lib':dict(base,inode=10),'lib/engine':dict(base,inode=11,size=2,
                mode=0o755,kind=0o100000,sha256='f'*64,close_confirmed=True),
            'lib/link':dict(base,inode=12,mode=0o777,kind=0o120000,target='engine')}}
        with tempfile.TemporaryDirectory() as directory:
            with self.m.DurableJournal(Path(directory)/'node.json','a') as journal:
                journal.save_owned_files('a',v)
                for path,key,value in [('lib/engine','kind',True),('lib/link','target','../engine'),
                                       ('lib/engine','close_confirmed',False)]:
                    import copy
                    bad=copy.deepcopy(v);bad['runtime']['tree'][path][key]=value
                    with self.assertRaises(ValueError):journal.save_owned_files('a',bad)
                bad=copy.deepcopy(v);del bad['runtime']['tree']['lib']
                with self.assertRaises(ValueError):journal.save_owned_files('a',bad)

    def test_failure_is_unknown_and_counters_not_reset_or_retried(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'node.json'
            with self.m.DurableJournal(path,'a') as journal:
                journal({'iterations':3,'download_gb':5})
                original=path.read_bytes()
                with patch.object(self.m.os,'replace',side_effect=OSError('synthetic')) as replace:
                    with self.assertRaisesRegex(RuntimeError,'journal persistence unknown'):
                        journal.save_owned_files('a',self.snapshot())
                    self.assertEqual(replace.call_count,1)
                    with self.assertRaises(RuntimeError):journal.save_owned_files('a',self.snapshot())
                    self.assertEqual(replace.call_count,1)
                self.assertEqual(path.read_bytes(),original)
                self.assertEqual(journal.load('a')['state'],'PENDING')
                self.assertEqual(journal.load('a')['iterations'],3)
                self.assertEqual(journal.load('a')['download_gb'],5)
                with self.assertRaises(RuntimeError):journal.load_owned_files('a')
            # Failed media cannot be promised to store a failure marker; this old
            # complete disk snapshot has no ownership and never grants adoption.
            with self.m.DurableJournal(path,'a') as journal:
                self.assertIsNone(journal.load_owned_files('a'))
                self.assertEqual(journal.load('a')['iterations'],3)

    def test_persisted_invalid_snapshot_rejected_on_constructor(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'node.json'
            with self.m.DurableJournal(path,'a') as journal:
                journal.save_owned_files('a',self.snapshot())
            data=json.loads(path.read_text());data['owned_files']['root_identity']['dev']=True
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):self.m.DurableJournal(path,'a')

    def test_combined_journal_size_cap_includes_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'node.json'
            with self.m.DurableJournal(path,'a') as journal:
                journal._snapshot['existing_test_padding']='x'*(1024*1024)
                with self.assertRaisesRegex(ValueError,'journal too large'):
                    journal.save_owned_files('a',self.snapshot())
                self.assertFalse(path.exists())

    def test_entry_limit_counts_all_trees_and_blobs_together(self):
        v=self.snapshot(); template=next(iter(v['blobs'].values()))
        v['blobs']={format(i,'064x'):{**template,'name':format(i,'064x')+'.blob',
            'sha256':format(i,'064x')} for i in range(256)}
        with tempfile.TemporaryDirectory() as directory:
            with self.m.DurableJournal(Path(directory)/'node.json','a') as journal:
                journal.save_owned_files('a',v)
                v['runtime']={'name':v['runtime_pin']+'.runtime.part','complete':False,
                    'tree':{'':{'device':1,'inode':9,'size':0,'mtime_ns':5,
                                'ctime_ns':6,'mode':0o700,'kind':0o040000}}}
                with self.assertRaises(ValueError):journal.save_owned_files('a',v)
                self.assertEqual(len(journal.load_owned_files('a')['blobs']),256)

    def test_directory_sync_failure_does_not_claim_durable_success(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'node.json'
            with self.m.DurableJournal(path,'a') as journal:
                journal({'iterations':2,'elapsed_seconds':7})
                with patch.object(self.m.os,'fsync',side_effect=[None,OSError('synthetic')]):
                    with self.assertRaisesRegex(RuntimeError,'journal persistence unknown'):
                        journal.save_owned_files('a',self.snapshot())
                self.assertEqual(journal.load('a')['state'],'PENDING')
                self.assertEqual(journal.load('a')['iterations'],2)
                self.assertEqual(journal.load('a')['elapsed_seconds'],7)
                with self.assertRaises(RuntimeError):journal.load_owned_files('a')
                # Atomic replacement may already have occurred. This on-disk
                # metadata is not evidence of successful sync or authorization.
                self.assertTrue(path.exists())

    def test_negative_zero_integer_on_disk_rejected_without_normalization(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'node.json'
            with self.m.DurableJournal(path,'a') as journal:
                journal.save_owned_files('a',self.snapshot())
            text=path.read_text().replace('"dev": 1','"dev": -0')
            self.assertNotEqual(text,path.read_text())
            path.write_text(text)
            with self.assertRaisesRegex(ValueError,'noncanonical journal integer'):
                self.m.DurableJournal(path,'a')

    def test_optional_activity_fixed_states_and_legacy_absence(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.m.DurableJournal(Path(directory)/'node.json','a') as journal:
                original=self.snapshot();journal.save_owned_files('a',original)
                self.assertNotIn('activity',journal.load_owned_files('a'))
                for activity in ('NEVER_STARTED','POSSIBLY_ACTIVE','DIRECT_EXIT_DESCENDANTS_UNKNOWN'):
                    value={**original,'activity':activity};journal.save_owned_files('a',value)
                    self.assertEqual(journal.load_owned_files('a')['activity'],activity)
                for activity in ('IDLE','UNKNOWN','STOPPED',True,None,1,{'pid':123}):
                    with self.assertRaises(ValueError):
                        journal.save_owned_files('a',{**original,'activity':activity})
                self.assertEqual(journal.load_owned_files('a')['activity'],'DIRECT_EXIT_DESCENDANTS_UNKNOWN')

    def test_close_failure_consumes_fd_before_attempt_and_never_retries(self):
        from unittest.mock import patch
        import os
        with tempfile.TemporaryDirectory() as directory:
            journal=self.m.DurableJournal(Path(directory)/'node.json','a')
            original_fd=journal._fd
            try:
                with patch.object(self.m.os,'close',side_effect=OSError('synthetic ambiguous close')) as close:
                    with self.assertRaises(OSError):journal.close()
                    self.assertTrue(journal._closed);self.assertIsNone(journal._fd)
                    journal.close();self.assertEqual(close.call_args_list[0].args,(original_fd,))
                    self.assertEqual(close.call_count,1)
                with self.assertRaises(ValueError):journal.load('a')
            finally:
                # Mock did not really close; test owns and releases original FD.
                os.close(original_fd)


if __name__ == '__main__':
    unittest.main()
