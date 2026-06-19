from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RFC = ROOT / "docs" / "rfcs" / "0001-controlled-evolution-architecture-and-trust-boundaries.md"


class EvolutionRfcContractTests(unittest.TestCase):
    def read_rfc(self) -> str:
        self.assertTrue(RFC.is_file(), f"Missing required RFC: {RFC}")
        return RFC.read_text(encoding="utf-8")

    def test_required_headings_are_present(self) -> None:
        text = self.read_rfc()
        headings = [
            "## Status",
            "## Purpose",
            "## Non-Goals",
            "## Current Stable Guarantees",
            "## Terminology",
            "## Product Invariants",
            "## Three-Loop Architecture",
            "## Inner Repair State Machine",
            "## Outer Improvement State Machine",
            "## Promotion State Machine",
            "## Exact SHA Identity",
            "## Trace and Redaction Contract",
            "## Failure Taxonomy",
            "## Eval Proposal Contract",
            "## Candidate Contract",
            "## Baseline/Candidate Comparison Contract",
            "## Completion Gate",
            "## Default-Deny Mutation Manifest",
            "## Existing Safety-Critical Paths",
            "## Immutable Trust Root",
            "## Anti-Cheating Controls",
            "## Evidence-Grounded Code Research",
            "## Metrics and Promotion Gates",
            "## Statistical and Inconclusive Results",
            "## Stable and Labs Boundary",
            "## Threat Model",
            "## Rollback Model",
            "## Compatibility",
            "## Version Roadmap",
            "## Explicitly Deferred Work",
            "## Open Questions",
            "## Acceptance Criteria",
        ]
        for heading in headings:
            self.assertIn(heading, text)

    def test_status_and_roadmap_boundaries(self) -> None:
        text = self.read_rfc()
        required = [
            "Status: PROPOSED",
            "Implementation: NOT STARTED",
            "Runtime behavior added by this RFC: NO",
            "User approval required for implementation: YES",
            "Candidate self-application: FORBIDDEN",
            "Automatic stable promotion: FORBIDDEN",
            "Labs implementation included: NO",
            "RFC-0001 is not v0.2 PR-02",
            "v0.2 PR-02 remains reserved for read-only installed-skill self-check",
            "RFC-0001 does not complete v0.3.0",
        ]
        for phrase in required:
            self.assertIn(phrase, text)

    def test_exact_sha_identity_contract(self) -> None:
        text = self.read_rfc()
        required = [
            "Exact commit SHA is the reproducible comparison identity.",
            "A tag is a human-readable input only.",
            "Every tag must resolve to an exact SHA.",
            "Record both requested tag and resolved SHA.",
            "Detect and report moved tags.",
            "A tag without its resolved SHA is insufficient.",
            "- main",
            "- master",
            "- latest",
            "- branch names",
            "- moving aliases",
        ]
        for phrase in required:
            self.assertIn(phrase, text)

    def test_trace_redaction_contract_prohibits_sensitive_content(self) -> None:
        text = self.read_rfc()
        required = [
            "Redaction before persistence is mandatory.",
            "When sensitivity is uncertain, do not persist the content.",
            "- raw prompts",
            "- full conversations",
            "- customer source contents",
            "- customer database contents",
            "- private absolute paths",
            "- Codex logs",
            "- precise device location",
            "- GPS location",
        ]
        for phrase in required:
            self.assertIn(phrase, text)

    def test_mutation_manifest_is_default_deny_and_exact_path(self) -> None:
        text = self.read_rfc()
        required = [
            "Default action: DENY",
            "Default exact-path write allowlist: EMPTY",
            "Candidate-specific approval: REQUIRED",
            "Exact repository-relative paths: REQUIRED",
            "Mixed-trust directory wildcards: FORBIDDEN",
            "Candidate cannot modify its own mutation manifest",
            "Candidate cannot approve its own paths",
            "The following broad paths are not freely candidate-mutable:",
            ".agents/skills/long-horizon-engineering/SKILL.md",
            ".agents/skills/long-horizon-engineering/references/**",
            ".agents/skills/long-horizon-engineering/templates/**",
            ".agents/skills/long-horizon-engineering/scripts/**",
        ]
        for phrase in required:
            self.assertIn(phrase, text)

    def test_safety_critical_paths_are_classified(self) -> None:
        text = self.read_rfc()
        required = [
            ".agents/skills/long-horizon-engineering/references/self-check-policy.md | IMMUTABLE TO CANDIDATES",
            ".agents/skills/long-horizon-engineering/references/capability-boundaries.md | IMMUTABLE TO CANDIDATES",
            ".agents/skills/long-horizon-engineering/references/safety-policy.md | IMMUTABLE TO CANDIDATES",
            ".agents/skills/long-horizon-engineering/references/client-privacy.md | IMMUTABLE TO CANDIDATES",
            ".agents/skills/long-horizon-engineering/templates/skill-validation-gate.md | REVIEW-ONLY",
            ".agents/skills/long-horizon-engineering/templates/bounded-skill-edit.md | REVIEW-ONLY",
            "A candidate may propose a human-reviewed change to review-only files",
        ]
        for phrase in required:
            self.assertIn(phrase, text)

    def test_anti_cheating_and_promotion_gates(self) -> None:
        text = self.read_rfc()
        required = [
            "- deleting tests",
            "- adding skip markers",
            "- weakening assertions",
            "- suppressing exit codes",
            "- claiming PASS for checks not run",
            "- editing promotion thresholds",
            "- editing protected evals",
            "- editing comparison logic",
            "- editing mutation enforcement",
            "False-success cases: 0",
            "Required-test execution rate: 100%",
            "Trust-root modifications: 0",
            "Test-weakening cases: 0",
            "Unauthorized dependencies: 0",
            "Unauthorized network actions: 0",
        ]
        for phrase in required:
            self.assertIn(phrase, text)

    def test_inconclusive_and_human_approval_rules(self) -> None:
        text = self.read_rfc()
        required = [
            "INCONCLUSIVE is not a pass.",
            "GATES_PASSED is not PROMOTED.",
            "Stable promotion cannot be automatic.",
            "INCONCLUSIVE never becomes GATES_PASSED.",
            "Human approval is still required after gates pass.",
            "One successful run is insufficient.",
        ]
        for phrase in required:
            self.assertIn(phrase, text)

    def test_stable_labs_boundary(self) -> None:
        text = self.read_rfc()
        required = [
            "Stable may not:",
            "- apply a candidate to Stable automatically",
            "- approve itself",
            "- merge itself",
            "- release itself",
            "- deploy itself",
            "Labs may not:",
            "- automatically merge into Stable",
            "- hold stable-main push credentials",
            "Stable -> Labs: controlled synchronization allowed.",
            "Labs -> Stable: human-reviewed promotion PR only.",
            "Automatic reverse synchronization: FORBIDDEN.",
        ]
        for phrase in required:
            self.assertIn(phrase, text)

    def test_labs_and_runtime_are_not_implemented(self) -> None:
        text = self.read_rfc()
        required = [
            "This RFC does not implement:",
            "- trace collection",
            "- repair execution",
            "- candidate mutation execution",
            "- baseline/candidate execution",
            "- promotion execution",
            "- network behavior",
            "- Labs implementation",
            "Labs is not implemented.",
        ]
        for phrase in required:
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
