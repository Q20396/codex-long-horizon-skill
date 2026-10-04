"""Synthetic, caller-invoked Phase 1.35 contract tests; no provider binding."""
from dataclasses import replace, asdict
import importlib
import json
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/long-horizon-engineering/scripts'


class TokenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(SCRIPTS))
        cls.m = importlib.import_module('token_accountability') if (SCRIPTS / 'token_accountability.py').exists() else None

    def setUp(self):
        self.assertIsNotNone(self.m, 'Phase 1.35 implementation missing')
        self.s = self.m.sc
        self.chain = self.s.InMemorySecurityChain('chain', 'i')
        self.root = self.s.SecurityAuthority('root', self.s.AuthorityRole.ROOT_OWNER, 'i')
        self.runtime = self.s.SecurityAuthority('runtime', self.s.AuthorityRole.RUNTIME, 'i', 'p', 't')

    def usage(self, **kw):
        args = dict(usage_id='u', installation_id='i', project_id='p', task_id='t', run_id='r',
                    agent_id='a', call_id='c', provider='vendor', model='model', purpose=self.m.UsagePurpose.REVIEW,
                    started_at=10, finished_at=11, total_tokens=100, input_tokens=80,
                    output_tokens=20, metric_source=self.m.MetricSource.PROVIDER_REPORTED)
        args.update(kw)
        return self.m.TokenUsageRecord(**args)

    def budget(self, **kw):
        args = dict(budget_id='b', level=self.m.TokenBudgetLevel.PROJECT, installation_id='i',
                    project_id='p', max_total_tokens=500, issued_at=1)
        args.update(kw)
        return self.m.TokenBudget(**args)

    def snapshot(self, **kw):
        return self.m.ExecutionAccountabilitySnapshot('i', 'p', 't', 'r', **kw)

    def anomalies(self, records, **kw):
        return self.m.detect_anomalies(records, self.snapshot(**kw), self.m.TokenAnomalyRules(3, 20000, 20000, 200))

    def test_unknown_is_not_zero_and_categories_not_added(self):
        r = self.m.summarize((self.usage(total_tokens=None, cached_input_tokens=30, reasoning_tokens=None),))
        self.assertEqual(r.known_total_tokens, 0)
        self.assertEqual(r.unknown_total_token_records, 1)
        self.assertEqual(dict(r.unknown_metric_records)['reasoning_tokens'], 1)
        self.assertEqual(dict(r.known_metrics)['input_tokens'], 80)
        self.assertEqual(r.unknown_cost_records, 1)

    def test_duplicate_usage_and_call_rejected_from_aggregation(self):
        for other in (self.usage(), self.usage(usage_id='other')):
            with self.assertRaises(ValueError):
                self.m.summarize((self.usage(), other))

    def test_orphan_retained_and_full_attribution_clean(self):
        orphan = self.usage(task_id=None, run_id=None)
        self.assertEqual(self.m.summarize((orphan,)).orphan_count, 1)
        self.assertIn('ORPHAN_USAGE', [a.anomaly_type.value for a in self.anomalies((orphan,))])
        self.assertEqual(self.anomalies((self.usage(),)), ())

    def test_post_completion_uses_trusted_matching_scope_and_start(self):
        for start, expected in ((99, False), (100, False), (101, True)):
            got = self.anomalies((self.usage(started_at=start, finished_at=102),), task_verified_complete_at=100)
            self.assertEqual(any(a.anomaly_type.value == 'POST_COMPLETION_USAGE' for a in got), expected)
        self.assertEqual(self.anomalies((self.usage(task_id='other', started_at=101, finished_at=102),), task_verified_complete_at=100), ())

    def test_unknown_progress_does_not_mean_zero(self):
        self.assertEqual(self.anomalies((self.usage(total_tokens=300),)), ())

    def test_progress_rule_and_real_progress(self):
        for closed, expected in ((0, True), (1, False)):
            p = self.m.ProgressSnapshot(3, 3, closed, 0, 0)
            got = self.anomalies((self.usage(total_tokens=300),), progress_snapshot=p)
            self.assertEqual(any(a.anomaly_type.value == 'LOW_PROGRESS_HIGH_TOKEN' for a in got), expected)

    def test_retry_requires_explicit_unresolved_relationship(self):
        u = self.usage(retry_group_id='retry', attempt_index=2)
        self.assertEqual(self.anomalies((u,), reconciliation_required=True), ())
        got = self.anomalies((u,), reconciliation_required=True, reconciliation_required_at=9, unresolved_retry_group_ids=('retry',))
        self.assertEqual(got[0].anomaly_type.value, 'UNRECONCILED_RETRY_USAGE')

    def test_retry_context_amplification_and_determinism(self):
        records = tuple(self.usage(usage_id=str(n), call_id=str(n), retry_group_id='g', attempt_index=n,
                                  started_at=n, finished_at=n, total_tokens=n*100, input_tokens=n*80) for n in (1, 2, 3))
        result = self.anomalies(records)
        names = {a.anomaly_type.value for a in result}
        self.assertIn('RETRY_AMPLIFICATION', names)
        self.assertIn('CONTEXT_AMPLIFICATION', names)
        self.assertEqual(result, self.anomalies(tuple(reversed(records))))

    def test_unknown_context_does_not_manufacture_growth(self):
        records = (self.usage(input_tokens=None), self.usage(usage_id='v', call_id='d', started_at=12, finished_at=13, input_tokens=900))
        self.assertEqual(self.anomalies(records), ())

    def test_numeric_and_source_validation(self):
        for value in (-1, True, 1.5, float('nan'), 2**54):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.usage(cost_micros=value)
        for value in (-1, True, float('inf'), 2**54):
            with self.assertRaises(ValueError):
                self.usage(started_at=value)
        with self.assertRaises(ValueError):
            self.usage(metric_source=self.m.MetricSource.UNKNOWN)
        with self.assertRaises(ValueError):
            self.usage(cost_micros=5, currency='USD', cost_source=self.m.CostSource.EXPLICIT_RATE_DERIVED)

    def test_cost_reported_estimated_and_currencies_separate(self):
        a = self.usage(cost_micros=20, currency='USD', cost_source=self.m.CostSource.PROVIDER_REPORTED)
        b = self.usage(usage_id='v', call_id='d', cost_micros=30, currency='AUD',
                       cost_source=self.m.CostSource.EXPLICIT_RATE_DERIVED, pricing_snapshot_ref='rates')
        r = self.m.summarize((a, b))
        self.assertEqual(r.known_reported_cost_micros, (('USD', 20),))
        self.assertEqual(r.known_estimated_cost_micros, (('AUD', 30),))
        self.assertEqual(b.cost_claim, 'ESTIMATED')

    def test_provider_independent_grouping(self):
        records = tuple(self.usage(usage_id=str(n), call_id=str(n), provider=p) for n,p in enumerate(('OpenAI','Anthropic','Google','Local','Unknown')))
        for group in self.m.by_provider(records):
            self.assertEqual(group[1].known_total_tokens, 100)
        for fn in (self.m.by_project, self.m.by_task, self.m.by_run):
            self.assertEqual(fn(records)[0][1].known_total_tokens, 500)
        self.assertEqual(len(self.m.by_model(records)), 5)

    def test_budget_inherit_and_child_expansion(self):
        parent = self.budget()
        child = self.budget(budget_id='child', level=self.m.TokenBudgetLevel.TASK, task_id='t', max_total_tokens=None)
        self.assertEqual(self.m.evaluate_budget((self.usage(total_tokens=501),), (parent, child), now=20).state, 'EXCEEDED')
        with self.assertRaises(ValueError):
            self.m.validate_budget_stack((parent, replace(child, max_total_tokens=1000)), now=20)

    def test_budget_scope_counts_siblings_toward_parent(self):
        records = (self.usage(total_tokens=300), self.usage(usage_id='v', call_id='d', task_id='sibling', total_tokens=300))
        self.assertEqual(self.m.evaluate_budget(records, (self.budget(),), now=20).state, 'EXCEEDED')

    def test_budget_unknown_warning_exceeded(self):
        for amount, state in ((None,'UNKNOWN'), (100,'WITHIN_BUDGET'), (400,'WARNING'), (501,'EXCEEDED')):
            self.assertEqual(self.m.evaluate_budget((self.usage(total_tokens=amount),), (self.budget(),), now=20).state, state)
        self.assertEqual(self.m.evaluate_budget((), (), now=20).state, 'UNKNOWN')

    def test_runtime_cannot_create_or_extend_budget(self):
        with self.assertRaises(ValueError):
            self.m.record_budget(self.chain, self.runtime, self.budget(), now=20)
        self.assertEqual(self.chain.records(), ())

    def test_budget_authority_scope(self):
        for role, task in ((self.s.AuthorityRole.PROJECT_AUTHORITY, None), (self.s.AuthorityRole.TASK_AUTHORITY, 't')):
            actor = self.s.SecurityAuthority('actor', role, 'i', 'p', task)
            b = self.budget(level=self.m.TokenBudgetLevel.TASK, task_id='t') if task else self.budget()
            self.m.record_budget(self.chain, actor, b, now=20)
            with self.assertRaises(ValueError):
                self.m.record_budget(self.chain, actor, replace(b, budget_id='other', project_id='other'), now=20)
            self.chain = self.s.InMemorySecurityChain('chain', 'i')

    def test_extension_request_no_change_and_authorized_history(self):
        old = self.budget(max_total_tokens=200)
        self.m.record_budget(self.chain, self.root, old, now=20)
        self.m.request_budget_extension(self.chain, self.runtime, old, request_id='request', now=21)
        self.assertEqual(old.max_total_tokens, 200)
        new = self.budget(budget_id='new', supersedes_budget_id='b', max_total_tokens=400, issued_at=22)
        self.m.record_budget(self.chain, self.root, new, previous=old, extension_request_id='request', now=22)
        self.assertEqual([r.event_type for r in self.chain.records()], ['TOKEN_BUDGET_CREATED','TOKEN_BUDGET_EXTENSION_REQUESTED','TOKEN_BUDGET_EXTENSION_GRANTED'])
        self.assertEqual(self.chain.records()[-1].previous_artifact_digest, self.s.artifact_digest(old))
        self.assertTrue(self.chain.verify().valid)

    def test_usage_chain_duplicates_privacy_and_anomaly(self):
        u = self.usage(provider='PRIVATE_MARKER')
        self.m.record_model_usage(self.chain, self.runtime, u, now=20)
        with self.assertRaises(ValueError):
            self.m.record_model_usage(self.chain, self.runtime, u, now=21)
        a = self.anomalies((self.usage(task_id=None),))[0]
        self.m.record_anomaly(self.chain, self.root, a, now=20)
        self.assertEqual(self.chain.records()[0].artifact_digest, self.s.artifact_digest(u))
        self.assertNotIn('PRIVATE_MARKER', json.dumps([asdict(r) for r in self.chain.records()]))
        self.assertNotIn('PRIVATE_MARKER', repr(u))
        self.assertTrue(self.chain.verify().valid)

    def test_warning_stable_event_identity(self):
        b = self.budget()
        d = self.m.evaluate_budget((self.usage(total_tokens=400),), (b,), now=20)
        self.m.record_budget_decision(self.chain, self.root, b, d, now=20)
        with self.assertRaises(ValueError):
            self.m.record_budget_decision(self.chain, self.root, b, d, now=21)
        self.assertEqual(len(self.chain.records()), 1)

    def test_budget_decision_anchor_contains_accounting_evidence(self):
        b = self.budget()
        d = self.m.evaluate_budget((self.usage(total_tokens=501),), (b,), now=20)
        record = self.m.record_budget_decision(self.chain, self.root, b, d, now=20)
        self.assertEqual(record.artifact_digest, self.s.artifact_digest(d))

    def test_expired_ancestor_and_currency_mismatch_fail_closed(self):
        for parent in (self.budget(expires_at=5), self.budget(max_cost_micros=20, currency='USD')):
            child = self.budget(budget_id='child',level=self.m.TokenBudgetLevel.TASK,task_id='t',max_cost_micros=10,currency='AUD')
            with self.assertRaises(ValueError):
                self.m.validate_budget_stack((parent,child),now=20)

    def test_extension_cannot_reset_budget_time_or_branch_history(self):
        old = self.budget()
        self.m.record_budget(self.chain,self.root,old,now=20)
        with self.assertRaises(ValueError):
            self.m.record_budget(self.chain,self.root,self.budget(budget_id='n',supersedes_budget_id='b',issued_at=0),previous=old,now=21)

    def test_large_anomaly_is_anchorable(self):
        records = tuple(self.usage(usage_id=str(n),call_id=str(n)) for n in range(129))
        anomalies = self.anomalies(records,progress_snapshot=self.m.ProgressSnapshot(1,1,0,0,0))
        for a in anomalies:
            self.m.record_anomaly(self.chain,self.root,a,now=20)
        self.assertTrue(self.chain.verify().valid)

    def test_import_has_no_active_effects(self):
        from unittest.mock import patch
        import builtins, os, socket, subprocess, threading
        env = dict(os.environ)
        # Dependencies are loaded before monitoring the module body itself.
        source = (SCRIPTS / 'token_accountability.py').read_text()
        code = compile(source,'token_accountability.py','exec')
        namespace = {'__name__': self.m.__name__}
        with patch.object(builtins,'open',side_effect=AssertionError('file IO')), \
             patch.object(os,'open',side_effect=AssertionError('file IO')), \
             patch.object(socket,'socket',side_effect=AssertionError('network')), \
             patch.object(subprocess,'Popen',side_effect=AssertionError('process')), \
             patch.object(threading.Thread,'start',side_effect=AssertionError('thread')):
            exec(code,namespace)
        self.assertEqual(dict(os.environ),env)

    def test_report_rejects_budget_result_for_other_history(self):
        d = self.m.evaluate_budget((self.usage(),),(self.budget(),),now=20)
        with self.assertRaises(ValueError):
            self.m.summarize((self.usage(total_tokens=900),),budget_decision=d)

    def test_anomaly_collections_are_immutable_and_validated(self):
        a = self.anomalies((self.usage(task_id=None),))[0]
        values = ['u']
        other = replace(a,usage_ids=values)
        values.append('v')
        self.assertEqual(other.usage_ids,('u',))
        with self.assertRaises(ValueError):
            replace(a,observed_at=True)

    def test_context_requires_later_start_not_arbitrary_tie_order(self):
        records = (self.usage(), self.usage(usage_id='v',call_id='z',input_tokens=900))
        self.assertEqual(self.anomalies(records), ())

    def test_partial_progress_stays_unknown(self):
        p = self.m.ProgressSnapshot(3,3,None,0,0)
        self.assertEqual(self.anomalies((self.usage(total_tokens=300),),progress_snapshot=p), ())

    def test_r3_estimated_cost_never_certifies_reported_budget_state(self):
        b = self.budget(max_total_tokens=None,max_cost_micros=100,currency='USD')
        for source,state in ((self.m.CostSource.EXPLICIT_RATE_DERIVED,'UNKNOWN'),(self.m.CostSource.PROVIDER_REPORTED,'EXCEEDED')):
            u = self.usage(cost_micros=150,currency='USD',cost_source=source,pricing_snapshot_ref='rates')
            d = self.m.evaluate_budget((u,),(b,),now=20)
            self.assertEqual(d.state,state)
        mixed = (self.usage(cost_micros=50,currency='USD',cost_source=self.m.CostSource.PROVIDER_REPORTED),
                 self.usage(usage_id='v',call_id='d',cost_micros=150,currency='USD',
                            cost_source=self.m.CostSource.EXPLICIT_RATE_DERIVED,pricing_snapshot_ref='rates'))
        self.assertEqual(self.m.evaluate_budget(mixed,(b,),now=20).state,'UNKNOWN')

    def test_r3_reconciliation_needs_temporal_evidence(self):
        records = (self.usage(retry_group_id='retry',attempt_index=1),
                   self.usage(usage_id='v',call_id='d',started_at=20,finished_at=21,retry_group_id='retry',attempt_index=2))
        got = self.anomalies(records,reconciliation_required=True,reconciliation_required_at=15,unresolved_retry_group_ids=('retry',))
        self.assertEqual([(a.anomaly_type.value,a.usage_ids) for a in got],[('UNRECONCILED_RETRY_USAGE',('v',))])
        self.assertEqual(self.anomalies(records,reconciliation_required=True,unresolved_retry_group_ids=('retry',)),())

    def test_r3_invalid_parent_is_orphan_in_report(self):
        u = self.usage()
        anomalies = self.anomalies((u,),invalid_parent_call_ids=('c',))
        r = self.m.summarize((u,),anomalies=anomalies)
        self.assertEqual((r.fully_attributed_count,r.orphan_count),(0,1))

    def test_legacy_chain_hash_still_verifies(self):
        e = self.s.SecurityEventDraft('e',self.s.EventType.SECURITY_ALERT,1,'i',self.s.AuthorityRole.ROOT_OWNER,'root','test')
        r = self.chain.append(e)
        self.assertEqual(r.record_hash,'4d315ef290e844dcd7a7f751d1d5af017d74c15c33f07ae8a192ea916e2b6b30')
        self.assertTrue(self.chain.verify().valid)

    def test_ancestor_exceedance_not_recorded_as_child_exceedance(self):
        parent = self.budget()
        child = self.budget(budget_id='child',level=self.m.TokenBudgetLevel.TASK,task_id='t',max_total_tokens=400)
        records = (self.usage(total_tokens=100),self.usage(usage_id='v',call_id='d',task_id='sibling',total_tokens=450))
        d = self.m.evaluate_budget(records,(parent,child),now=20)
        self.assertEqual(d.state,'EXCEEDED')
        with self.assertRaises(ValueError):
            self.m.record_budget_decision(self.chain,self.root,child,d,now=20)
        self.m.record_budget_decision(self.chain,self.root,parent,d,now=20)

    def test_r4_anomaly_coverage_unknown_not_zero(self):
        u = self.usage()
        report = self.m.summarize((u,))
        self.assertEqual(report.anomaly_coverage,'NOT_PROVIDED')
        self.assertTrue(all(v is None for _,v in report.anomaly_counts))
        supplied = self.m.summarize((u,),anomalies=())
        self.assertEqual(supplied.anomaly_coverage,'SUPPLIED_FINDINGS')
        self.assertTrue(all(v == 0 for _,v in supplied.anomaly_counts))
        self.assertEqual(self.m.by_project((u,))[0][1].anomaly_coverage,'NOT_PROVIDED')

    def test_r4_reject_unrelated_or_changed_anomaly_usage(self):
        u = self.usage()
        findings = self.anomalies((u,),task_verified_complete_at=9)
        for records in ((),(replace(u,total_tokens=101),),(replace(u,project_id='other'),)):
            with self.assertRaises(ValueError):
                self.m.summarize(records,anomalies=findings)
        self.assertEqual(dict(self.m.summarize((u,),anomalies=findings).anomaly_counts)['POST_COMPLETION_USAGE'],1)
        with self.assertRaises(ValueError):
            self.m.summarize((u,),anomalies=findings+findings)

    def test_operator_documentation_examples_execute(self):
        doc = (SCRIPTS.parent / 'references/token-accountability.md').read_text()
        for block in doc.split('```python\n')[1:]:
            exec(compile(block.split('```')[0],'operator-example','exec'),{})


if __name__ == '__main__':
    unittest.main()
