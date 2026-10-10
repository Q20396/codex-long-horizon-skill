"""Synthetic H9 field-availability proxy; never a human-benefit experiment."""
from contextlib import ExitStack
from dataclasses import asdict
import importlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / '.agents/skills/long-horizon-engineering/scripts'
FIELDS = ('action_id', 'layer_a', 'layer_b', 'result', 'effect_class',
          'effect_ref', 'reason', 'evidence_refs', 'coverage_status',
          'compared_effect_ref')
# Frozen before implementation: name, result, reason, coverage, counterpart, refs.
SCENARIOS = (
    ('match', 'MATCH', 'EFFECT_MATCH', 'SCOPED_COMPLETE', 'ref:A', ('ref:observed',)),
    ('diverged', 'DIVERGED', 'MATERIAL_EFFECT_DIFFERENCE', 'SCOPED_COMPLETE', 'ref:B', ('ref:observed',)),
    ('unknown', 'UNKNOWN', 'TARGET_REALITY_UNKNOWN', 'UNKNOWN', None, ()),
    ('not_observed', 'NOT_OBSERVED', 'INSUFFICIENT_COVERAGE', 'PARTIAL', None, ()),
    ('gap', 'UNKNOWN', 'INSUFFICIENT_COVERAGE', 'UNKNOWN', None, ('ref:gap',)),
    ('missing_vs_empty', 'UNKNOWN', 'SOURCE_UNAVAILABLE', 'UNKNOWN', None, ()),
    ('duplicate', 'MATCH', 'EFFECT_MATCH', 'PARTIAL', 'ref:A', ('ref:one',)),
    ('references', 'EXTRA', 'UNEXPECTED_EFFECT_OBSERVED', 'SCOPED_COMPLETE', None, ('ref:one', 'ref:two')),
)
MARKERS = ('READ_ONLY_PRESENTATION', 'SOURCE_TRUST_NOT_ESTABLISHED',
           'NOT_EXECUTION_OR_RETRY_AUTHORITY')


class OperatorFindingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_path = sys.path[:]
        cls.names = ('cross_layer_verification', 'scripts.h9_operator_findings')
        cls.saved_modules = {n: sys.modules.get(n) for n in cls.names}
        for n in cls.names:
            sys.modules.pop(n, None)
        sys.path[:0] = [str(CORE), str(ROOT)]
        cls.core = importlib.import_module('cross_layer_verification')
        cls.presenter = (importlib.import_module('scripts.h9_operator_findings')
                         if (ROOT / 'scripts/h9_operator_findings.py').exists() else None)

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = cls.saved_path
        for n, old in cls.saved_modules.items():
            if old is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = old

    def setUp(self):
        self.assertIsNotNone(self.presenter, 'H9 formatter is not implemented')

    def finding(self, **updates):
        values = dict(action_id='ref:action', layer_a='ADAPTER_OBSERVED',
                      layer_b='HOST_OBSERVED', result='MATCH', effect_class='FILE_WRITE',
                      effect_ref='ref:A', reason='EFFECT_MATCH', evidence_refs=('ref:observed',),
                      coverage_status='SCOPED_COMPLETE', compared_effect_ref='ref:A')
        values.update(updates)
        return self.core.VerificationFinding(**values)

    def rows(self, output):
        return [json.loads(line[8:]) for line in output.splitlines() if line.startswith('FINDING ')]

    def reject(self, value):
        with self.assertRaises(ValueError) as caught:
            self.presenter.render_findings(value)
        self.assertEqual(str(caught.exception), 'H9_PRESENTATION_INPUT_INVALID')
        self.assertIsNone(caught.exception.__cause__)

    def test_eight_frozen_proxy_scenarios(self):
        for name, result, reason, coverage, counterpart, refs in SCENARIOS:
            with self.subTest(scenario=name):
                f = self.finding(result=result, reason=reason, coverage_status=coverage,
                                 compared_effect_ref=counterpart, evidence_refs=refs)
                findings = (f, f) if name == 'duplicate' else (f,)
                output = self.presenter.render_findings(findings)
                rows = self.rows(output)
                self.assertEqual(len(rows), len(findings))
                for row in rows:
                    self.assertEqual((row['result'], row['reason'], row['coverage_status'],
                                      row['compared_effect_ref'], row['evidence_refs']),
                                     (result, reason, coverage, counterpart, list(refs)))
                    expected = asdict(f)
                    expected['evidence_refs'] = list(refs)
                    self.assertEqual(row, expected)
                baseline = repr(findings)
                self.assertTrue(all(field + '=' in baseline for field in FIELDS))
                # Baseline already exposes all fields: improvement is fixed context only.
                for marker in MARKERS:
                    self.assertNotIn(marker, baseline)
                    self.assertIn(marker, output)
                self.assertIn('MATCH is scoped agreement, not all-effects proof.', output)
                self.assertIn('UNKNOWN is missing or ambiguous evidence, not success.', output)
                self.assertNotIn('aggregate', output.lower())

    def test_actual_verifier_none_empty_gap_and_divergence(self):
        def effect(ref):
            return ('FILE_WRITE', ref, 'ref:action', ('ref:evidence',), 'CORRELATED')
        values = [
            self.core.VerificationInput('ref:action'),
            self.core.VerificationInput('ref:action', declared_effects=(effect('ref:A'),),
                                        authorized_effects=()),
            self.core.VerificationInput('ref:action', declared_effects=(effect('ref:A'),),
                                        authorized_effects=(effect('ref:B'),)),
            self.core.VerificationInput('ref:action', adapter_observed_effects=(effect('ref:A'),),
                                        host_observed_effects=(), host_gap=True),
        ]
        results = []
        for value in values:
            findings = self.core.CrossLayerVerifier.verify(value)
            rows = self.rows(self.presenter.render_findings(findings))
            expected = json.loads(json.dumps([asdict(f) for f in findings]))
            self.assertEqual(rows, expected)
            results.extend(row['result'] for row in rows)
        self.assertIn('MISSING', results)
        self.assertIn('DIVERGED', results)
        self.assertIn('UNKNOWN', results)

    def test_order_duplicates_none_and_input_unchanged(self):
        first = self.finding(effect_ref='ref:Z', compared_effect_ref=None)
        second = self.finding(effect_ref=None, effect_class=None)
        values = [first, second, first]
        before = [asdict(f) for f in values]
        output = self.presenter.render_findings(values)
        self.assertEqual([r['effect_ref'] for r in self.rows(output)], ['ref:Z', None, 'ref:Z'])
        self.assertEqual(before, [asdict(f) for f in values])
        self.assertIn('null', output)

    def test_empty_and_1024_boundary(self):
        for empty in ([], ()):
            self.assertIn('NO_FINDINGS_SUPPLIED', self.presenter.render_findings(empty))
        f = self.finding()
        self.assertEqual(len(self.rows(self.presenter.render_findings([f] * 1024))), 1024)
        self.reject([f] * 1025)

    def test_output_limit_rejects_without_partial_output(self):
        refs = tuple('ref:' + str(i).zfill(3) + 'x' * 125 for i in range(32))
        f = self.finding(evidence_refs=refs)
        self.reject([f] * 1024)

    def test_reject_dynamic_objects_without_invocation(self):
        class Trap:
            def __iter__(self): raise AssertionError('iterated')
            def __str__(self): raise AssertionError('formatted')
            def __repr__(self): raise AssertionError('represented')
            def __eq__(self, other): raise AssertionError('compared')
        class ListSubclass(list):
            def __iter__(self): raise AssertionError('iterated subclass')
        class FindingSubclass(self.core.VerificationFinding):
            def __getattribute__(self, name): raise AssertionError('read subclass')
        f = self.finding()
        # Bypass construction: rejection must occur before any subclass access.
        child = object.__new__(FindingSubclass)
        for bad in (None, {}, 'secret', Trap(), ListSubclass([f]), iter([f]), [Trap()], [child]):
            self.reject(bad)
        for field in FIELDS:
            changed = self.finding()
            object.__setattr__(changed, field, Trap())
            self.reject([changed])
        changed = self.finding()
        object.__setattr__(changed, 'evidence_refs', (Trap(),))
        self.reject([changed])

    def test_str_subclasses_mixed_actions_and_mutated_contract_rejected(self):
        class Text(str):
            def __len__(self): raise AssertionError('custom length')
        for field, value in [('action_id', Text('ref:A')), ('layer_b', 'TARGET_REALITY'),
                             ('result', 'PASS'), ('reason', 'secret\nreason'),
                             ('coverage_status', 'COMPLETE'), ('effect_ref', 'ref:x\x1b[31m'),
                             ('effect_class', 'x'), ('evidence_refs', ('ref:z', 'ref:a')),
                             ('compared_effect_ref', 5)]:
            f = self.finding()
            object.__setattr__(f, field, value)
            self.reject([f])
        self.reject([self.finding(), self.finding(action_id='ref:other')])

    def test_plain_output_and_no_io_or_execution(self):
        import builtins, io, os, socket, subprocess
        f = self.finding()
        def forbidden(*args, **kwargs):
            raise AssertionError('unexpected external operation')
        with ExitStack() as stack:
            for target, name in ((builtins, 'open'), (io, 'open'), (os, 'open'),
                                 (socket, 'socket'), (subprocess, 'Popen')):
                stack.enter_context(patch.object(target, name, forbidden))
            output = self.presenter.render_findings((f,))
        self.assertEqual(len(self.rows(output)), 1)
        self.assertTrue(all(c == '\n' or 32 <= ord(c) < 127 for c in output))

    def test_missing_fields_and_nested_nonprimitives_are_fixed_errors(self):
        incomplete = object.__new__(self.core.VerificationFinding)
        self.reject([incomplete])
        for refs in (['ref:A'], ('ref:A', 'ref:A'), (False,), ('ref:' + 'x' * 129,)):
            f = self.finding()
            object.__setattr__(f, 'evidence_refs', refs)
            self.reject([f])

    def test_container_type_check_does_not_call_metaclass_equality(self):
        class Meta(type):
            def __eq__(self, other):
                raise AssertionError('metaclass equality invoked')
        class Dynamic(metaclass=Meta):
            pass
        self.reject(Dynamic())

    def test_import_from_explicit_root_has_no_application_io(self):
        import subprocess
        code = '''import sys, pathlib, builtins, io, os, socket, subprocess
from unittest.mock import patch
from contextlib import ExitStack
sys.path.insert(0, str(pathlib.Path.cwd()/'.agents/skills/long-horizon-engineering/scripts'))
import cross_layer_verification, json
def denied(*a, **k): raise AssertionError('application IO during import')
with ExitStack() as stack:
    for obj, name in ((builtins,'open'),(io,'open'),(os,'open'),(socket,'socket'),(subprocess,'Popen')):
        stack.enter_context(patch.object(obj,name,denied))
    from scripts.h9_operator_findings import render_findings
    assert 'NO_FINDINGS_SUPPLIED' in render_findings(())
'''
        result = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
