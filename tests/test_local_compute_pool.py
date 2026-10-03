"""Behavioral tests: injected workers perform no network/model execution."""
import importlib.util
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / '.agents/skills/long-horizon-engineering/scripts/local_compute_pool.py'
spec = importlib.util.spec_from_file_location('local_compute_pool', PATH)
pool = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pool
if PATH.exists():
    spec.loader.exec_module(pool)


class PoolTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(hasattr(pool, 'TaskPool'), 'bounded dispatcher API is not implemented')

    def node(self, name, **changes):
        values = dict(node_id=name, provider='provider', provider_version='1', model='small', config='q4',
                      consent=True, deployment_authorized=True, probed=True,
                      runtime_validated=True, privacy_scopes=frozenset({'project'}),
                      memory_available=16, max_concurrent_tasks=1,
                      qualifications=frozenset({pool.Qualification(name, 'provider', 'small', 'q4', 'review', '1')}))
        values.update(changes)
        return pool.Node(**values)

    def task(self, name, **changes):
        values = dict(task_id=name, task_class='review', data_scope='project',
                      privacy='LOCAL_ONLY', memory_required=4, payload='synthetic')
        values.update(changes)
        return pool.Task(**values)

    def run_pool(self, engine, tasks, worker, cloud_worker=None):
        bindings = {n.node_id: pool.BoundWorker(n.node_id, n.provider, n.model, n.config, worker, n.provider_version)
                    for n in engine.nodes.values()}
        return engine.run(tasks, bindings, cloud_worker, local_output_authorized=True)

    def test_independent_workers_execute_simultaneously(self):
        # Serial dispatch or missing reservation makes the barrier fail.
        barrier = threading.Barrier(2)
        engine = pool.TaskPool([self.node('a'), self.node('b')], pool.PoolBudget(2, 2), authorized_nodes={'a', 'b'})
        def worker(node, task):
            barrier.wait(timeout=2)
            return pool.WorkerResult(node.node_id)
        result = self.run_pool(engine, [self.task('one'), self.task('two')], worker)
        self.assertEqual({r.output for r in result.values()}, {'a', 'b'})
        self.assertEqual([r.state for r in result.values()], ['COMPLETED', 'COMPLETED'])

    def test_qualification_does_not_transfer_to_changed_model(self):
        engine = pool.TaskPool([self.node('a', model='other')], pool.PoolBudget(1, 1), authorized_nodes={'a'})
        result = self.run_pool(engine, [self.task('one')], lambda n, t: self.fail('unqualified dispatch'))
        self.assertEqual(result['one'].state, 'BLOCKED_BY_PRIVACY')

    def test_each_node_requires_all_gates_and_data_scope(self):
        for change in ({'consent': False}, {'deployment_authorized': False}, {'probed': False},
                       {'runtime_validated': False}, {'privacy_scopes': frozenset({'other'})}):
            with self.subTest(change=change):
                engine = pool.TaskPool([self.node('a', **change)], pool.PoolBudget(1, 1), authorized_nodes={'a'})
                result = self.run_pool(engine, [self.task('one')], lambda n, t: self.fail('unauthorized dispatch'))
                self.assertEqual(result['one'].state, 'BLOCKED_BY_PRIVACY')

    def test_known_failure_isolated_and_retried_on_other_qualified_node(self):
        engine = pool.TaskPool([self.node('a'), self.node('b')], pool.PoolBudget(1, 1), authorized_nodes={'a', 'b'})
        def worker(node, task):
            if node.node_id == 'a':
                raise pool.KnownFailure()
            return pool.WorkerResult('recovered')
        result = self.run_pool(engine, [self.task('one')], worker)['one']
        self.assertEqual((result.state, result.output, result.attempted_nodes), ('COMPLETED', 'recovered', ('a', 'b')))
        self.assertEqual(engine.node_states['a'], 'DEGRADED')

    def test_unknown_outcome_stops_retries_until_explicit_reconciliation(self):
        engine = pool.TaskPool([self.node('a'), self.node('b')], pool.PoolBudget(2, 2), authorized_nodes={'a', 'b'})
        def worker(node, task):
            raise TimeoutError('must not leak this content')
        task = self.task('one', privacy='CLOUD_ALLOWED', output_privacy='CLOUD_ALLOWED')
        result = self.run_pool(engine, [task], worker, lambda t: self.fail('unsafe cloud retry'))['one']
        self.assertTrue(result.reconciliation_required)
        self.assertIsNone(result.output)
        with self.assertRaises(ValueError):
            self.run_pool(engine, [task], lambda n, t: pool.WorkerResult('duplicate'))
        engine.reconcile('one', 'NOT_EXECUTED')
        result = self.run_pool(engine, [task], lambda n, t: pool.WorkerResult('recovered'))['one']
        self.assertEqual(result.output, 'recovered')

    def test_cloud_requires_input_and_output_permission(self):
        engine = pool.TaskPool([], pool.PoolBudget(1, 1))
        denied = self.run_pool(engine, [self.task('one', privacy='CLOUD_ALLOWED')], lambda n, t: None,
                            lambda t: self.fail('output not cloud allowed'))
        self.assertEqual(denied['one'].state, 'BLOCKED_BY_PRIVACY')
        allowed = self.run_pool(engine, [self.task('two', privacy='CLOUD_ALLOWED', output_privacy='CLOUD_ALLOWED')],
                             lambda n, t: None, lambda t: pool.WorkerResult('cloud'))
        self.assertEqual((allowed['two'].state, allowed['two'].output), ('FALLBACK_OPENAI', 'cloud'))

    def test_load_and_memory_headroom_choose_idle_eligible_node(self):
        engine = pool.TaskPool([self.node('a', current_load=3), self.node('b'), self.node('c', memory_available=1)],
                               pool.PoolBudget(2, 2), authorized_nodes={'a', 'b', 'c'})
        result = self.run_pool(engine, [self.task('one')], lambda n, t: pool.WorkerResult(n.node_id))
        self.assertEqual(result['one'].output, 'b')

    def test_migration_requires_fresh_gates_and_no_trust_transfer(self):
        replacement = pool.migrate_node(self.node('a'), 'new-device')
        engine = pool.TaskPool([replacement], pool.PoolBudget(1, 1), authorized_nodes={'new-device'})
        result = self.run_pool(engine, [self.task('one')], lambda n, t: self.fail('inherited trust'))
        self.assertEqual(result['one'].state, 'BLOCKED_BY_PRIVACY')
        self.assertFalse(replacement.qualifications)
        self.assertFalse(replacement.consent)

    def test_timeout_retains_capacity_and_rejects_premature_reconciliation(self):
        started, release = threading.Event(), threading.Event()
        engine = pool.TaskPool([self.node('a'), self.node('b')], pool.PoolBudget(1, 1, timeout_seconds=0.02), authorized_nodes={'a', 'b'})
        def blocked(node, task):
            started.set()
            release.wait(2)
            return pool.WorkerResult('late')
        try:
            result = self.run_pool(engine, [self.task('one')], blocked)['one']
            self.assertTrue(started.is_set())
            self.assertTrue(result.reconciliation_required)
            self.assertTrue(hasattr(engine, 'health'), 'deadline metrics missing')
            self.assertEqual(engine.health['a'].timeout_count, 1)
            with self.assertRaises(ValueError):
                engine.reconcile('one', 'NOT_EXECUTED')
            queued = self.run_pool(engine, [self.task('two')], lambda n, t: self.fail('capacity released'))
            self.assertEqual(queued['two'].state, 'QUEUED')
        finally:
            release.set()

    def test_local_output_is_withheld_without_explicit_local_boundary(self):
        node = self.node('a')
        engine = pool.TaskPool([node], pool.PoolBudget(1, 1), authorized_nodes={'a'})
        binding = pool.BoundWorker('a', 'provider', 'small', 'q4', lambda n, t: pool.WorkerResult('private result'), '1')
        result = engine.run([self.task('one')], {'a': binding})['one']
        self.assertEqual(result.state, 'COMPLETED')
        self.assertIsNone(result.output)
        self.assertTrue(result.output_withheld)

    def test_wrong_worker_binding_fails_before_execution(self):
        engine = pool.TaskPool([self.node('a')], pool.PoolBudget(1, 1), authorized_nodes={'a'})
        bad = pool.BoundWorker('b', 'provider', 'small', 'q4', lambda n, t: self.fail('bad binding'))
        with self.assertRaises(ValueError):
            engine.run([self.task('one')], {'a': bad})

    def test_topology_prefers_independent_pool_before_cluster(self):
        self.assertTrue(hasattr(pool, 'plan_topology'), 'topology planner missing')
        nodes = [self.node('a'), self.node('b')]
        cluster = pool.DistributedCandidate(True, True, True, True, True, True, True)
        self.assertEqual(pool.plan_topology([], [], pool.PoolBudget(2, 2)), 'OPENAI_ONLY')
        self.assertEqual(pool.plan_topology(nodes, [self.task('one')], pool.PoolBudget(2, 2)), 'SINGLE_NODE')
        self.assertEqual(pool.plan_topology(nodes, [self.task('one'), self.task('two')], pool.PoolBudget(2, 2), cluster), 'MULTI_NODE_TASK_POOL')
        oversized = [self.task('big', memory_required=64)]
        self.assertEqual(pool.plan_topology(nodes, oversized, pool.PoolBudget(2, 2), cluster), 'DISTRIBUTED_MODEL_CLUSTER_CANDIDATE')

    def test_distributed_recommendation_requires_every_gate(self):
        self.assertTrue(hasattr(pool, 'DistributedCandidate'), 'distributed contract missing')
        for missing in range(7):
            gates = [True] * 7
            gates[missing] = False
            result = pool.plan_topology([self.node('a'), self.node('b')], [self.task('big', memory_required=64)],
                                        pool.PoolBudget(2, 2), pool.DistributedCandidate(*gates))
            self.assertNotEqual(result, 'DISTRIBUTED_MODEL_CLUSTER_CANDIDATE')

    def test_pool_candidate_activation_and_node_removal(self):
        engine = pool.TaskPool([self.node('a'), self.node('b')], pool.PoolBudget(2, 2))
        self.assertTrue(hasattr(engine, 'pool_state'), 'pool lifecycle missing')
        self.assertEqual(engine.pool_state, 'MULTI_NODE_CANDIDATE')
        active = pool.TaskPool([self.node('a'), self.node('b')], pool.PoolBudget(2, 2), authorized_nodes={'a', 'b'})
        self.assertEqual(active.pool_state, 'MULTI_NODE_ACTIVE')
        active.remove_node('a')
        result = self.run_pool(active, [self.task('one')], lambda n, t: pool.WorkerResult(n.node_id))
        self.assertEqual(result['one'].output, 'b')

    def test_heterogeneous_models_keep_task_specific_identity(self):
        other = self.node('b', model='large', qualifications={pool.Qualification('b', 'provider', 'large', 'q4', 'logs', '1')})
        engine = pool.TaskPool([self.node('a'), other], pool.PoolBudget(2, 2), authorized_nodes={'a', 'b'})
        result = self.run_pool(engine, [self.task('review'), self.task('logs', task_class='logs')],
                               lambda n, t: pool.WorkerResult((n.node_id, n.model)))
        self.assertEqual(result['review'].output, ('a', 'small'))
        self.assertEqual(result['logs'].output, ('b', 'large'))

    def test_provider_version_change_invalidates_qualification(self):
        engine = pool.TaskPool([self.node('a', provider_version='2')], pool.PoolBudget(1, 1), authorized_nodes={'a'})
        result = self.run_pool(engine, [self.task('one')], lambda n, t: self.fail('stale qualification'))
        self.assertEqual(result['one'].state, 'BLOCKED_BY_PRIVACY')

    def test_unknown_node_still_consumes_active_node_budget(self):
        engine = pool.TaskPool([self.node('a'), self.node('b')], pool.PoolBudget(2, 1), authorized_nodes={'a', 'b'})
        def worker(node, task):
            raise TimeoutError()
        result = self.run_pool(engine, [self.task('one'), self.task('two')], worker)
        self.assertEqual(result['two'].state, 'QUEUED')

    def test_batch_budget_and_invalid_privacy_fail_closed(self):
        engine = pool.TaskPool([self.node('a')], pool.PoolBudget(1, 1, max_tasks=1), authorized_nodes={'a'})
        with self.assertRaises(ValueError):
            self.run_pool(engine, [self.task('one'), self.task('two')], lambda n, t: self.fail('over budget'))
        with self.assertRaises(ValueError):
            self.task('one', privacy='UNKNOWN')

    def test_concurrent_run_is_rejected(self):
        engine = pool.TaskPool([self.node('a')], pool.PoolBudget(1, 1), authorized_nodes={'a'})
        def worker(node, task):
            with self.assertRaises(ValueError):
                engine.run([self.task('nested')], {})
            return pool.WorkerResult('ok')
        self.assertEqual(self.run_pool(engine, [self.task('one')], worker)['one'].output, 'ok')

    def test_planner_keeps_single_node_when_it_meets_parallel_workload(self):
        nodes = [self.node('a', max_concurrent_tasks=2), self.node('b')]
        self.assertEqual(pool.plan_topology(nodes, [self.task('one'), self.task('two')], pool.PoolBudget(2, 2)), 'SINGLE_NODE')

    def test_assignment_failure_retains_inflight_and_unsubmitted_task_can_retry(self):
        release = threading.Event()
        real_executor = pool.ThreadPoolExecutor
        class FailingExecutor(real_executor):
            submissions = 0
            def submit(self, function, *args, **kwargs):
                self.submissions += 1
                if self.submissions == 2:
                    raise RuntimeError('assignment failed')
                return super().submit(function, *args, **kwargs)
        engine = pool.TaskPool([self.node('a'), self.node('b')], pool.PoolBudget(2, 2), authorized_nodes={'a', 'b'})
        def worker(node, task):
            release.wait(2)
            return pool.WorkerResult('done')
        try:
            with patch.object(pool, 'ThreadPoolExecutor', FailingExecutor):
                with self.assertRaises(RuntimeError):
                    self.run_pool(engine, [self.task('one'), self.task('two')], worker)
            with self.assertRaises(ValueError):
                self.run_pool(engine, [self.task('one')], lambda n, t: pool.WorkerResult('duplicate'))
            retry = self.run_pool(engine, [self.task('two')], lambda n, t: pool.WorkerResult('safe'))
            self.assertEqual(retry['two'].output, 'safe')
            self.assertTrue(hasattr(engine, 'health'), 'assignment interruption metrics missing')
            self.assertEqual(engine.health['a'].unknown_count, 1)
            self.assertEqual(engine.health['b'].assignment_failure_count, 1)
            self.assertEqual(engine.health['b'].failure_count, 0)
        finally:
            release.set()

    def test_worker_base_exception_retains_unknown_record(self):
        engine = pool.TaskPool([self.node('a')], pool.PoolBudget(1, 1), authorized_nodes={'a'})
        def worker(node, task):
            raise SystemExit()
        with self.assertRaises(SystemExit):
            self.run_pool(engine, [self.task('one')], worker)
        self.assertTrue(hasattr(engine, 'health'), 'interruption metrics missing')
        self.assertEqual(engine.health['a'].unknown_count, 1)
        with self.assertRaises(ValueError):
            self.run_pool(engine, [self.task('one')], lambda n, t: pool.WorkerResult('duplicate'))

    def test_disjoint_local_tasks_use_serial_pool_before_cluster(self):
        other = self.node('b', qualifications={pool.Qualification('b', 'provider', 'small', 'q4', 'logs', '1')})
        cluster = pool.DistributedCandidate(True, True, True, True, True, True, True)
        self.assertEqual(pool.plan_topology([self.node('a'), other], [self.task('one'), self.task('two', task_class='logs')],
                                           pool.PoolBudget(2, 1), cluster), 'MULTI_NODE_TASK_POOL')

    def test_health_reports_observed_success_failure_and_latency(self):
        engine = pool.TaskPool([self.node('a'), self.node('b')], pool.PoolBudget(1, 1), authorized_nodes={'a', 'b'})
        def worker(node, task):
            if node.node_id == 'a':
                raise pool.KnownFailure()
            return pool.WorkerResult('ok')
        self.run_pool(engine, [self.task('one'), self.task('two')], worker)
        self.assertTrue(hasattr(engine, 'health'), 'observed node health missing')
        self.assertEqual((engine.health['a'].failure_count, engine.health['a'].failure_rate), (1, 1.0))
        self.assertEqual((engine.health['b'].success_count, engine.health['b'].success_rate), (2, 1.0))
        self.assertGreaterEqual(engine.health['b'].observed_latency, 0)
        self.assertGreater(engine.health['b'].last_healthy_at, 0)
        self.assertIsNone(engine.health['a'].last_healthy_at)

    def test_timeout_health_is_failure_and_unknown_without_payload(self):
        engine = pool.TaskPool([self.node('a')], pool.PoolBudget(1, 1), authorized_nodes={'a'})
        def worker(node, task):
            raise TimeoutError('sensitive content must not be retained in health')
        self.run_pool(engine, [self.task('one')], worker)
        self.assertTrue(hasattr(engine, 'health'), 'observed node health missing')
        health = engine.health['a']
        self.assertEqual((health.failure_count, health.timeout_count, health.unknown_count), (1, 1, 1))
        self.assertEqual((health.failure_rate, health.timeout_rate), (1.0, 1.0))
        self.assertNotIn('sensitive', repr(health))

    def test_pool_state_excludes_stale_qualification_identity(self):
        for change in ({'model': 'other'}, {'provider': 'other'}, {'config': 'other'}, {'provider_version': '2'}):
            with self.subTest(change=change):
                engine = pool.TaskPool([self.node('a'), self.node('b', **change)], pool.PoolBudget(2, 2), authorized_nodes={'a', 'b'})
                self.assertEqual(engine.pool_state, 'SINGLE_NODE')

    def test_external_memory_and_correction_metrics_are_separate_from_observations(self):
        self.assertIn('memory_pressure', pool.Node.__dataclass_fields__, 'external pressure observation missing')
        engine = pool.TaskPool([self.node('a', memory_pressure=0.25, main_correction_rate=0.5)],
                               pool.PoolBudget(1, 1), authorized_nodes={'a'})
        self.run_pool(engine, [self.task('one')], lambda n, t: pool.WorkerResult('ok'))
        self.assertEqual(engine.health['a'].external_memory_pressure, 0.25)
        self.assertEqual(engine.health['a'].external_main_correction_rate, 0.5)
        self.assertEqual(engine.health['a'].success_rate, 1.0)
        with self.assertRaises(ValueError):
            self.node('bad', memory_pressure=1.5)


if __name__ == '__main__':
    unittest.main()
