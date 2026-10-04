"""Synthetic CET contracts: no target execution, provider or host observation."""
from dataclasses import replace, asdict
import importlib
import json
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/long-horizon-engineering/scripts'


class CETTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_path = sys.path[:]
        cls.saved_modules = {n: sys.modules.get(n) for n in ('critical_execution_trace',
            'runtime_safety_envelope','security_authority_chain','token_accountability')}
        sys.path.insert(0,str(SCRIPTS))
        cls.m = importlib.import_module('critical_execution_trace') if (SCRIPTS/'critical_execution_trace.py').exists() else None

    @classmethod
    def tearDownClass(cls):
        # Older suites deliberately reload dependencies by module name. Do not
        # leave our early token import bound to a different chain class identity.
        sys.path[:] = cls.saved_path
        for name,module in cls.saved_modules.items():
            if module is None:
                sys.modules.pop(name,None)
            else:
                sys.modules[name] = module

    def setUp(self):
        self.assertIsNotNone(self.m,'CET implementation missing')
        self.r = self.m.rse
        self.s = self.m.sc

    def ctx(self, action='a', parent=None, **kw):
        args = dict(trace_id='tr',installation_id='i',project_id='p',task_id='t',run_id='r',
                    action_id=action,parent_action_id=parent,provider='vendor',model='model',runtime='runtime')
        args.update(kw)
        return self.m.TraceContext(**args)

    def event(self, action='a', parent=None, kind='FILE_READ', target='/repo/a', time=1, **kw):
        args = dict(event_id=action,context=self.ctx(action,parent),event_type=self.m.CriticalEventType[kind],
                    target=target,timestamp=time,source=self.m.ObservationSource.ADAPTER_OBSERVED,
                    data_classification=self.r.DataClass.SENSITIVE)
        args.update(kw)
        return self.m.CriticalEvent(**args)

    def trace(self, events, **kw):
        t = self.m.CriticalTrace('tr','i',**kw)
        for e in events:
            t.append(e)
        return t

    def risks(self, events, declarations=()):
        return self.m.detect_trace_risks(self.trace(events),declarations,
                    internal_network_origins=('https://internal.test',),approved_network_origins=())

    def test_declared_match_and_extra_categories(self):
        c = self.ctx()
        declared = self.m.DeclaredEffects(c,reads=('/repo/a',))
        self.assertEqual(self.m.compare_effects(declared,self.m.ObservedEffects(c,reads=('/repo/a',))).divergences,())
        cases = [('reads',('/secret/b',),'UNDECLARED_READ'),('writes',('/repo/b',),'UNDECLARED_WRITE'),
                 ('creates',('/repo/b',),'UNDECLARED_CREATE'),('deletes',('/repo/b',),'UNDECLARED_DELETE'),
                 ('moves',(('/repo/a','/repo/b'),),'UNDECLARED_MOVE'),('processes',('exe-ref',),'UNDECLARED_PROCESS'),
                 ('network_targets',('https://outside.test',),'UNDECLARED_NETWORK'),('secret_refs',('opaque-ref',),'UNDECLARED_SECRET_ACCESS'),
                 ('git_actions',(('GIT_PUSH','https://repo.test'),),'UNDECLARED_GIT_ACTION'),
                 ('external_actions',(('DEPLOY','https://deploy.test'),),'UNDECLARED_EXTERNAL_ACTION')]
        for field,value,expected in cases:
            with self.subTest(field=field):
                got = self.m.compare_effects(declared,self.m.ObservedEffects(c,**{field:value}))
                self.assertEqual([x.divergence_type.value for x in got.divergences],[expected])
                self.assertNotEqual(got.declared_digest,got.observed_digest)

    def test_logical_paths_not_prefix_scopes(self):
        c=self.ctx()
        d=self.m.DeclaredEffects(c,reads=('/repo/x/../a',))
        self.assertEqual(self.m.compare_effects(d,self.m.ObservedEffects(c,reads=('/repo/a',))).divergences,())
        self.assertEqual(len(self.m.compare_effects(d,self.m.ObservedEffects(c,reads=('/repo-private/a',))).divergences),1)

    def test_origin_normalization_and_secret_url_rejection(self):
        c=self.ctx()
        d=self.m.DeclaredEffects(c,network_targets=('HTTPS://EXAMPLE.TEST:443/a',))
        self.assertEqual(self.m.compare_effects(d,self.m.ObservedEffects(c,network_targets=('https://example.test/b',))).divergences,())
        for url in ('https://user:password@example.test','https://example.test/?token=secret','https://example.test/#secret'):
            with self.assertRaises(ValueError): self.event(kind='NETWORK_REQUEST',target=url)

    def test_git_commit_does_not_declare_push(self):
        c=self.ctx()
        d=self.m.DeclaredEffects(c,git_actions=(('GIT_COMMIT','/repo'),))
        o=self.m.ObservedEffects(c,git_actions=(('GIT_PUSH','https://repo.test'),))
        self.assertEqual(self.m.compare_effects(d,o).divergences[0].divergence_type.value,'UNDECLARED_GIT_ACTION')

    def test_observed_sources_closed(self):
        for source in ('MODEL_REPORTED','HOST_OBSERVED',self.m.ObservationSource.DECLARED):
            with self.assertRaises(ValueError): self.m.ObservedEffects(self.ctx(),source=source)
        with self.assertRaises(ValueError): self.event(event_type='arbitrary')

    def test_timestamps_bounded(self):
        for timestamp in (-1,True,float('nan'),float('inf'),2**54):
            with self.assertRaises(ValueError): self.event(time=timestamp)

    def test_duplicate_and_rebound_identity_rejected(self):
        t=self.trace((self.event(),))
        with self.assertRaises(ValueError): t.append(self.event())
        for ctx in (self.ctx(task_id='other'),self.ctx(parent='missing'),self.ctx(provider='other')):
            with self.assertRaises(ValueError): t.append(self.event(event_id='new',context=ctx))
        self.assertEqual(len(t.events()),1)

    def test_cycle_self_parent_and_time_reversal(self):
        with self.assertRaises(ValueError): self.ctx(parent='a')
        t=self.trace((self.event('a','b'),))
        with self.assertRaises(ValueError): t.append(self.event('b','a'))
        t=self.trace((self.event('a',time=10),))
        with self.assertRaises(ValueError): t.append(self.event('b','a',time=9))

    def test_missing_parent_partial_and_out_of_order_recovery(self):
        t=self.trace((self.event('b','a',time=2),),completeness=self.m.TraceCompleteness.COMPLETE,coverage_refs=('coverage',))
        self.assertEqual(t.verify_structure().completeness.value,'PARTIAL')
        self.assertEqual(t.verify_structure().orphan_action_count,1)
        t.append(self.event('a',time=1))
        self.assertEqual(t.verify_structure().completeness.value,'COMPLETE')
        self.assertEqual(t.children_of('a'),('b',))
        self.assertEqual(len(t.events_for_action('b')),1)

    def test_completeness_requires_attestation_and_safe_wording(self):
        with self.assertRaises(ValueError): self.trace((),completeness=self.m.TraceCompleteness.COMPLETE)
        for state in self.m.TraceCompleteness:
            t=self.trace((self.event(),),completeness=state,coverage_refs=('coverage',))
            result=self.m.analyze_trace(t,(self.m.DeclaredEffects(self.ctx(),reads=('/repo/a',)),),
                       internal_network_origins=(),approved_network_origins=())
            self.assertEqual(result.completeness,state)
            self.assertEqual((result.observed_event_count,result.declared_effect_count,result.divergence_count,result.risk_finding_count),(1,1,0,0))
            if state != self.m.TraceCompleteness.COMPLETE:
                self.assertIn('SUPPLIED_OBSERVATIONS',result.no_findings_statement)

    def test_causal_sensitive_secret_and_process_network_patterns(self):
        for kind,target,want in [('FILE_READ','/s','SENSITIVE_READ'),('SECRET_ACCESS','opaque-secret','SECRET_ACCESS')]:
            first=self.event('a',kind=kind,target=target)
            network=self.event('b','a','NETWORK_REQUEST','https://outside.test',2)
            self.assertIn(want+'_TO_EXTERNAL_NETWORK',{r.finding_type.value for r in self.risks((first,network))})
            process=self.event('p','a','PROCESS_START','exe-ref',2)
            network=self.event('n','p','NETWORK_REQUEST','https://outside.test',3)
            self.assertIn(want+'_TO_PROCESS_TO_EXTERNAL_NETWORK',{r.finding_type.value for r in self.risks((first,process,network))})

    def test_chronology_and_same_action_not_causal_edges(self):
        first=self.event()
        network=self.event('b',kind='NETWORK_REQUEST',target='https://outside.test',time=2)
        self.assertEqual(self.risks((first,network)),())
        self.assertEqual(self.risks((first,replace(network,context=self.ctx()))),())

    def test_internal_approved_and_subdomain_trust(self):
        for host,expected in [('internal.test',False),('sub.internal.test',True)]:
            events=(self.event(),self.event('b','a','NETWORK_REQUEST','https://'+host,2))
            self.assertEqual(bool(self.risks(events)),expected)
        events=(self.event(),self.event('b','a','NETWORK_REQUEST','https://approved.test',2))
        self.assertEqual(self.m.detect_trace_risks(self.trace(events),(),internal_network_origins=(),approved_network_origins=('https://approved.test',)),())

    def test_undeclared_risk_patterns_need_action_specific_declarations(self):
        a=self.event()
        b=self.event('b','a','NETWORK_REQUEST','https://outside.test',2)
        findings=self.risks((a,b),(self.m.DeclaredEffects(b.context),))
        self.assertIn('UNDECLARED_NETWORK_AFTER_SENSITIVE_READ',{x.finding_type.value for x in findings})
        a=self.event(kind='SECRET_ACCESS',target='opaque')
        b=self.event('b','a','PROCESS_START','exe',2)
        self.assertIn('UNDECLARED_PROCESS_AFTER_SECRET_ACCESS',{x.finding_type.value for x in self.risks((a,b),(self.m.DeclaredEffects(b.context),))})

    def test_declared_events_and_attempts_are_not_observed_effects(self):
        a=self.event(source=self.m.ObservationSource.DECLARED)
        b=self.event('b','a','NETWORK_REQUEST','https://outside.test',2)
        self.assertEqual(self.risks((a,b)),())
        a=self.event(status=self.m.EventStatus.ATTEMPTED)
        self.assertEqual(self.risks((a,b)),())

    def action(self,kind='READ_FILE',target='/repo/a',**kw):
        k=self.r.ActionClass[kind]
        args=dict(action_id='a',run_id='r',task_id='t',action_class=k,target=target,provider='vendor',runtime='runtime',
            data_classification=self.r.DataClass.SENSITIVE,authorization_ref='auth',capability=self.r.CAPABILITIES[k],expected_effect='untrusted prose')
        args.update(kw)
        return self.r.ActionRequest(**args)

    def test_rse_mapping_and_prose_not_authority(self):
        self.assertEqual(set(self.m.ACTION_EVENTS),set(self.r.ActionClass))
        for k in self.r.ActionClass:
            target='https://outside.test' if k in self.r.EGRESS_ACTIONS else '/repo/a'
            a=self.action(k.name,target,destination='/repo/b' if k==self.r.ActionClass.MOVE_FILE else None)
            d=self.m.declared_from_action(a,self.ctx())
            self.assertEqual(d,self.m.declared_from_action(replace(a,expected_effect='network fully allowed'),self.ctx()))
            self.assertEqual(self.m.effect_count(d),1)
        d=self.m.declared_from_action(self.action(),self.ctx())
        self.assertEqual(self.m.compare_effects(d,self.m.ObservedEffects(self.ctx(),network_targets=('https://outside.test',))).divergences[0].divergence_type.value,'UNDECLARED_NETWORK')

    def test_rse_denied_and_class_contradiction(self):
        action=self.action('NETWORK_REQUEST','https://outside.test')
        receipt=self.r._receipt(action,self.r.PolicyDecision('DENY','POLICY_DENIED'))
        event=self.event(kind='NETWORK_REQUEST',target='https://outside.test')
        findings=self.m.correlate_rse(action,receipt,event,attempt_linked=True).divergences
        self.assertEqual(findings[0].divergence_type.value,'OBSERVED_EFFECT_CONTRADICTS_RSE_DECISION')
        read=self.action()
        allowed=self.r._receipt(read,self.r.PolicyDecision('ALLOW','ALLOWED'))
        self.assertEqual(len(self.m.correlate_rse(read,allowed,event).divergences),1)
        with self.assertRaises(ValueError): self.m.correlate_rse(read,replace(allowed,action_id='wrong'),event)

    def test_trace_bounds_effect_bounds_depth_bounds(self):
        with self.assertRaises(ValueError): self.m.DeclaredEffects(self.ctx(),reads=tuple('/'+str(n) for n in range(self.m.MAX_EFFECTS+1)))
        t=self.trace(())
        for n in range(self.m.MAX_EVENTS): t.append(self.event(str(n)))
        with self.assertRaises(ValueError): t.append(self.event('overflow'))
        t=self.trace((self.event('0'),))
        for n in range(1,self.m.MAX_CAUSAL_DEPTH+1): t.append(self.event(str(n),str(n-1)))
        with self.assertRaises(ValueError): t.append(self.event('overflow',str(self.m.MAX_CAUSAL_DEPTH)))

    def test_order_independent_results_and_provider_independence(self):
        events=(self.event(),self.event('b','a','NETWORK_REQUEST','https://outside.test',2))
        self.assertEqual(self.risks(events),self.risks(tuple(reversed(events))))
        expected=[f.finding_type for f in self.risks(events)]
        for provider in ('OpenAI','Anthropic','Google','Local','Unknown'):
            changed=tuple(replace(e,context=replace(e.context,provider=provider)) for e in events)
            self.assertEqual([f.finding_type for f in self.risks(changed)],expected)

    def test_chain_anchors_privacy_authority_and_duplicates(self):
        chain=self.s.InMemorySecurityChain('chain','i')
        actor=self.s.SecurityAuthority('runtime',self.s.AuthorityRole.RUNTIME,'i','p','t')
        event=self.event(kind='SECRET_ACCESS',target='PRIVATE_MARKER')
        record=self.m.record_critical_event(chain,actor,event,now=5)
        self.assertEqual(record.event_type,'CRITICAL_TRACE_EVENT')
        self.assertNotIn('PRIVATE_MARKER',repr(event)+json.dumps(asdict(record)))
        with self.assertRaises(ValueError): self.m.record_critical_event(chain,actor,event,now=6)
        with self.assertRaises(ValueError): self.m.record_critical_event(chain,replace(actor,project_id='other'),replace(event,event_id='other'),now=6)
        divergence=self.m.compare_effects(self.m.DeclaredEffects(self.ctx()),self.m.ObservedEffects(self.ctx(),secret_refs=('opaque',))).divergences[0]
        self.assertEqual(self.m.record_trace_divergence(chain,actor,divergence,now=6).event_type,'TRACE_DIVERGENCE')
        risk=self.risks((event,self.event('b','a','NETWORK_REQUEST','https://outside.test',2)))[0]
        self.assertEqual(self.m.record_trace_risk(chain,actor,risk,now=6).event_type,'TRACE_RISK_FINDING')
        self.assertTrue(chain.verify().valid)

    def test_legacy_hash_and_token_chain_compatibility(self):
        chain=self.s.InMemorySecurityChain('chain','i')
        e=self.s.SecurityEventDraft('e',self.s.EventType.SECURITY_ALERT,1,'i',self.s.AuthorityRole.ROOT_OWNER,'root','test')
        self.assertEqual(chain.append(e).record_hash,'4d315ef290e844dcd7a7f751d1d5af017d74c15c33f07ae8a192ea916e2b6b30')
        import token_accountability as ta
        actor=self.s.SecurityAuthority('root',self.s.AuthorityRole.ROOT_OWNER,'i')
        ta.record_model_usage(chain,actor,ta.TokenUsageRecord('u','i','c','vendor','model',ta.UsagePurpose.REVIEW,1,2),now=3)
        self.m.record_critical_event(chain,actor,self.event(),now=4)
        self.assertTrue(chain.verify().valid)

    def test_import_has_no_active_effects(self):
        from unittest.mock import patch
        import builtins,os,socket,subprocess,threading
        code=compile((SCRIPTS/'critical_execution_trace.py').read_text(),'cet','exec')
        env=dict(os.environ)
        with patch.object(builtins,'open',side_effect=AssertionError('IO')),patch.object(os,'open',side_effect=AssertionError('IO')), \
             patch.object(socket,'socket',side_effect=AssertionError('network')),patch.object(subprocess,'Popen',side_effect=AssertionError('process')), \
             patch.object(threading.Thread,'start',side_effect=AssertionError('thread')):
            exec(code,{'__name__':self.m.__name__})
        self.assertEqual(dict(os.environ),env)

    def test_invalid_finding_artifacts_rejected(self):
        d=self.m.compare_effects(self.m.DeclaredEffects(self.ctx()),self.m.ObservedEffects(self.ctx(),reads=('/x',))).divergences[0]
        for kw in ({'divergence_type':'FREE_TEXT'},{'declared_digest':'not-digest'},{'severity':'arbitrary'},{'context':None}):
            with self.assertRaises(ValueError): replace(d,**kw)
        risk=self.risks((self.event(),self.event('b','a','NETWORK_REQUEST','https://outside.test',2)))[0]
        for kw in ({'finding_type':'FREE_TEXT'},{'event_ids':()},{'action_ids':('a',)}, {'evidence_digest':'bad'}):
            with self.assertRaises(ValueError): replace(risk,**kw)

    def test_scope_rebinding_and_parent_scope_mismatch(self):
        for kw in ({'project_id':'other'},{'run_id':'other'},{'runtime':'other'},{'model':'other'}):
            t=self.trace((self.event(),))
            with self.assertRaises(ValueError): t.append(self.event(event_id='new',context=self.ctx(**kw)))
        with self.assertRaises(ValueError): self.trace((self.event(),self.event('b','a',context=self.ctx('b','a',task_id='other'))))

    def test_missing_baselines_not_assumed_empty_and_cross_action_no_masking(self):
        a=self.event()
        b=self.event('b','a','NETWORK_REQUEST','https://outside.test',2)
        t=self.trace((a,b))
        d=self.m.DeclaredEffects(a.context,reads=('/repo/a',),network_targets=('https://outside.test',))
        result=self.m.analyze_trace(t,(d,),internal_network_origins=(),approved_network_origins=())
        self.assertEqual(result.undeclared_baseline_action_count,1)
        self.assertEqual(result.divergence_count,0)
        result=self.m.analyze_trace(t,(d,self.m.DeclaredEffects(b.context)),internal_network_origins=(),approved_network_origins=())
        self.assertEqual(result.divergence_count,1)
        with self.assertRaises(ValueError): self.risks((a,b),(d,d))

    def test_event_level_backward_causality_excluded(self):
        early=self.event(time=1)
        late=self.event(time=5,event_id='late')
        network=self.event('b','a','NETWORK_REQUEST','https://outside.test',2)
        findings=self.risks((early,late,network))
        self.assertTrue(findings)
        self.assertTrue(all('late' not in f.event_ids for f in findings))

    def test_event_optional_metadata_validation(self):
        for kw in ({'source':'HOST_OBSERVED'},{'status':'FAILED'},{'exit_code':0}, {'destination':'/x'}, {'evidence_refs':('x',)*17}):
            with self.assertRaises(ValueError): self.event(**kw)
        event=self.event(kind='PROCESS_EXIT',target='exe',exit_code=1)
        self.assertEqual(event.exit_code,1)
        with self.assertRaises(ValueError): self.event(kind='FILE_MOVE')

    def test_secret_repr_chain_artifacts_are_digest_only(self):
        c=self.ctx()
        d=self.m.DeclaredEffects(c)
        o=self.m.ObservedEffects(c,secret_refs=('PRIVATE_MARKER',))
        comparison=self.m.compare_effects(d,o)
        self.assertNotIn('PRIVATE_MARKER',repr(o)+repr(comparison)+repr(comparison.divergences[0]))

    def test_documented_operator_walkthrough(self):
        from contextlib import redirect_stdout
        from io import StringIO
        doc=(SCRIPTS.parent/'references/critical-execution-trace.md').read_text()
        example=doc.split('```python\n',1)[1].split('```',1)[0]
        out=StringIO()
        with redirect_stdout(out): exec(compile(example,'operator-example','exec'),{})
        self.assertIn('UNDECLARED_NETWORK',out.getvalue())
        self.assertIn('UNKNOWN',out.getvalue())

    def test_risk_evidence_binds_full_causal_basis(self):
        a=self.event()
        bridge=self.event('bridge','a','CAPABILITY_USE','cap',2)
        n=self.event('n','bridge','NETWORK_REQUEST','https://outside.test',3)
        first=self.risks((a,bridge,n))
        changed=self.risks((a,replace(bridge,target='other-cap'),n))
        self.assertNotEqual(first[0].evidence_digest,changed[0].evidence_digest)
        self.assertEqual(self.risks((a,replace(bridge,context=self.ctx('bridge')),n)),())
        d=self.m.DeclaredEffects(n.context)
        risks=self.risks((a,bridge,n),(d,))
        self.assertEqual(len({r.evidence_digest for r in risks}),len(risks))
        changed=self.risks((a,bridge,n),(replace(d,reads=('/other',)),))
        self.assertNotEqual(risks[0].evidence_digest,changed[0].evidence_digest)
        changed=self.m.detect_trace_risks(self.trace((a,bridge,n)),(),internal_network_origins=('https://different.test',),approved_network_origins=())
        self.assertNotEqual(first[0].evidence_digest,changed[0].evidence_digest)

    def test_rse_lifecycle_does_not_accuse_historical_or_uncertain_effects(self):
        action=self.action('NETWORK_REQUEST','https://outside.test')
        event=self.event(kind='NETWORK_REQUEST',target='https://outside.test')
        for policy,reason,execution,reconciliation,final in (
            ('DENY','ALREADY_COMPLETED','KNOWN_SUCCESS','NOT_REQUIRED','ALREADY_COMPLETED'),
            ('DENY','ALREADY_COMPLETED','RECONCILED_SUCCESS','NOT_REQUIRED','ALREADY_COMPLETED'),
            ('REQUIRE_RECONCILIATION','UNKNOWN_OUTCOME_PENDING','UNKNOWN_OUTCOME','RECONCILIATION_REQUIRED','REQUIRE_RECONCILIATION'),
            ('DENY','REEVALUATION_REQUIRED','RECONCILED_SUCCESS','RECONCILED_SUCCESS','RECONCILED_SUCCESS'),
            ('DENY','REEVALUATION_REQUIRED','RECONCILED_NOT_APPLIED','RECONCILED_NOT_APPLIED','RECONCILED_NOT_APPLIED'),
            ('REQUIRE_AUTHORIZATION','AUTHORIZATION_EXPIRED','NOT_ATTEMPTED','NOT_REQUIRED','REQUIRE_AUTHORIZATION')):
            receipt=self.r._receipt(action,self.r.PolicyDecision(policy,reason),execution,reconciliation,final=final)
            result=self.m.correlate_rse(action,receipt,event)
            self.assertEqual(result.divergences,())
            self.assertEqual(result.execution_state,execution)
            self.assertEqual(result.reconciliation_state,reconciliation)
            self.assertFalse(result.attempt_linked)
        denied=self.r._receipt(action,self.r.PolicyDecision('DENY','POLICY_DENIED'))
        self.assertEqual(self.m.correlate_rse(action,denied,event).divergences,())
        self.assertEqual(len(self.m.correlate_rse(action,denied,event,attempt_linked=True).divergences),1)


if __name__=='__main__': unittest.main()
