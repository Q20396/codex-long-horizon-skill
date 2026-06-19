# External Skill Adoption Review

Use this template before adopting, copying, installing, or adapting a public
GitHub skill or third-party skill package.

Do not include secrets, client names, legal evidence, medical information,
financial account details, identity documents, family information, private
correspondence, raw prompts, conversation text, local absolute paths, or
confidential source content.

## 1. Audit Status

- Audit status: PROPOSAL_ONLY
- User decision: PENDING
- Changes applied: NO
- Candidate installed: NO
- Candidate executed: NO
- Stable modified: NO
- Network used for this audit: NO / APPROVED SEPARATELY

## 2. Candidate Identity

- candidate_name:
- source_url:
- requested_ref:
- requested_tag:
- resolved_commit_sha:
- identity_verification_status: DISCOVERED / IDENTITY_VERIFIED / BLOCKED
- reviewed_at:
- reviewer:

Notes:

- Exact commit SHA is required.
- Requested tag and resolved SHA must both be recorded when a tag is used.
- Mutable refs such as `main`, `master`, `latest`, branch names,
  `refs/heads/**`, and moving aliases are not reproducible audit identities.
- GitHub Stars are discovery metadata only.
- Popularity is not safety evidence.

## 3. Source Ledger

- candidate_name:
- source_url:
- requested_ref:
- requested_tag:
- resolved_commit_sha:
- identity_verification_status:
- reviewed_at:
- files_inspected:
- files_not_inspected:
- license_name:
- license_file:
- license_status:
- attribution_requirement:
- provenance_notes:
- provenance_verified:
- copied_code_or_prose: NO
- copied_assets: NO
- copied_tests: NO
- reusable_ideas:
- security_findings:
- privacy_findings:
- trigger_overlap:
- review_status:
- user_approval_state: PENDING
- final_conclusion:

## 4. Scope Reviewed

- README reviewed:
- SKILL.md reviewed:
- Manifests reviewed:
- Templates reviewed:
- References reviewed:
- Scripts reviewed as data only:
- Installers reviewed as data only:
- CI/workflows reviewed:
- Examples reviewed:

## 5. Files Inspected

| File | Purpose | Notes |
| --- | --- | --- |
|  |  |  |

## 6. Files Not Inspected

| File or area | Reason | Review impact |
| --- | --- | --- |
|  |  |  |

## 7. License Review

- license_name:
- license_file:
- license_status:
- attribution_requirement:
- Copying permitted after review and approval: yes / no / unclear
- Unknown or incompatible license blocks copying and direct adoption:

## 8. Provenance Review

- provenance_notes:
- provenance_verified:
- Original authorship or source unclear:
- Third-party content present:
- Missing provenance requires manual security review:

## 9. Dangerous-Behavior Findings

| Category | Evidence | Exact file | Exact line or section | Severity | Execution required to verify? | Review incomplete? | Recommended disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |

Categories to check:

- SHELL AND PROCESS EXECUTION: shell=True, os.system, subprocess misuse,
  command construction from untrusted input, interpreter invocation, downloaded
  command execution
- DYNAMIC CODE: eval, exec, runpy, __import__, dynamic imports, dynamically
  generated code, download-and-execute behavior
- INSTALLER AND SUPPLY-CHAIN BEHAVIOR: do not run curl | sh or wget | sh;
  inspect install-time execution, post-install hooks, unpinned downloads,
  unpinned dependencies, package-manager lifecycle scripts, submodules,
  gitlinks, unexplained binaries, and obfuscated code
- CREDENTIAL AND SECRET ACCESS: Environment-variable harvesting, Tokens,
  Passwords, API keys, Credential files, SSH keys, Cloud credentials, Browser
  credentials, Secret-manager access
- PRIVACY AND USER-DATA ACCESS: Raw prompt collection, Full conversation
  collection, User profiling, Email access, Cloud-drive access, Browser-history
  access, Device information, GPS or location access, Contact access, Customer
  source-code upload, Hidden logging
- FILESYSTEM BEHAVIOR: Broad filesystem scans, Home-directory scans,
  Hidden-file scans, Sensitive-directory reads, Writes outside the authorized
  repository, Permission changes, Symlink manipulation, Deletion, Unbounded
  cleanup
- NETWORK BEHAVIOR: Hidden network requests, Dynamic endpoints, Uploads,
  Telemetry, Background communication, Proxy use, Local-network access,
  Downloaded binaries or scripts
- GIT AND RELEASE BEHAVIOR: do not perform Commit, Push, Merge, Auto-merge,
  Tag, Release, Publish, Deploy, Production execution, or branch-protection
  changes during the audit
- PERSISTENCE: Hooks, Background jobs, Scheduled tasks, Startup execution,
  Persistent memory, Hidden state, Long-lived processes
- SELF-MUTATION: Automatic update, Self-patching, Automatic skill rewriting,
  Mutation-manifest changes, Policy weakening, Test weakening, Evaluation
  weakening, Promotion-rule changes

## 10. Privacy Findings

- Customer names present:
- Client names present:
- Private repository names present:
- Private class names present:
- Private function names present:
- Private file paths present:
- Internal domains present:
- Database names present:
- Credentials present:
- Tokens present:
- API keys present:
- Customer source excerpts present:
- Raw prompts present:
- Conversation text present:
- Email addresses present:
- Account identifiers present:
- Local absolute paths present:
- Private problem converted to generic technical query before network use:

## 11. Security Findings

- High-risk behavior found:
- Guarded behavior found:
- Missing approval gates:
- Tests or safety rules weakened:
- Candidate attempts to bypass instructions or policy:

## 12. Network and Persistence Findings

- Hidden network requests:
- Dynamic endpoints:
- Uploads:
- Telemetry:
- Background communication:
- Proxy use:
- Local-network access:
- Hooks:
- Background jobs:
- Scheduled tasks:
- Startup execution:
- Persistent memory or hidden state:

## 13. Filesystem Findings

- Broad filesystem scans:
- Home-directory scans:
- Hidden-file scans:
- Sensitive-directory reads:
- Writes outside authorized repository:
- Permission changes:
- Symlink manipulation:
- Deletion:
- Unbounded cleanup:

## 14. Git, Release, and Deployment Findings

- Commit:
- Push:
- Merge:
- Auto-merge: do not perform automatically
- Tag:
- Release:
- Publish:
- Deploy:
- Production execution:
- Branch-protection changes:

## 15. Self-Mutation Findings

- Automatic update:
- Self-patching:
- Automatic skill rewriting:
- Mutation-manifest changes:
- Policy weakening:
- Test weakening:
- Evaluation weakening:
- Promotion-rule changes:

## 16. Trigger-Overlap Review

Allowed trigger-overlap values:

- NO_OVERLAP
- COMPLEMENTARY
- PARTIAL_OVERLAP
- CONFLICTING
- OVERBROAD
- NEEDS_MANUAL_ROUTING_REVIEW

Review fields:

- Candidate trigger description:
- Existing skill compared:
- Existing installed SKILL.md descriptions checked:
- Root trigger fixtures checked:
- Explicit-only extension boundaries checked:
- Safety and privacy trigger boundaries checked:
- Existing routing exclusions checked:
- Overlapping scenarios:
- Conflicting scenarios:
- Likely false positives:
- Likely false negatives:
- Whether implicit invocation is proposed:
- Routing recommendation:
- Reviewer notes:

Trigger overlap does not authorize routing changes. The audit may recommend,
but may not edit Stable trigger descriptions.

## 17. Reusable Ideas

- General design pattern that may be independently reimplemented:
- Evidence supporting usefulness:
- Constraints that must be preserved:
- Ideas rejected:

## 18. Material Proposed for Copying

- copied_code_or_prose: NO
- copied_assets: NO
- copied_tests: NO
- License/provenance approval present:
- Explicit user approval present:

No code, prose, asset, or test may be copied merely because it is public.

## 19. Required Adaptations

- Safety changes required:
- Privacy changes required:
- Routing changes requiring a separate proposal:
- Dependency changes requiring a separate proposal:
- Architectural changes requiring a separate proposal:

## 20. Residual Risks

- Incomplete review areas:
- Unknown license or provenance:
- Binary-only, obfuscated, or generated files:
- Candidate behavior requiring manual security review:
- Compatibility risk:

## 21. Final Conclusion

Allowed final conclusions (exact values):

- `ADOPT IDEA`
- `ADAPT WITH CHANGES`
- `REJECT`
- `NEEDS MANUAL SECURITY REVIEW`

Selected final_conclusion:

Meaning:

- `ADOPT IDEA` permits independent reimplementation of a design pattern only.
  It does not authorize copying, installation, execution, patch application, or
  Stable modification.
- `ADAPT WITH CHANGES` requires a new proposal and separate approval.
- `REJECT` authorizes no installation, execution, copying, or adaptation.
- `NEEDS MANUAL SECURITY REVIEW` authorizes no adoption action until review
  completes.

## 22. User Decision

- user_approval_state: PENDING
- Approval requested for:
- Approval explicitly granted:
- Approval explicitly denied:

## 23. Changes Applied

- changes_applied: NO
- candidate_installed: NO
- candidate_executed: NO
- stable_modified: NO
- Patch application performed: NO
- Trigger scope changed: NO

Mutation boundary:

- Default mutation action: DENY
- Default exact-path write allowlist: EMPTY
- Exact repository-relative path approval is required
- Mixed-trust directory wildcards are forbidden
- Proposal permission is not write permission
- Write permission is not approval
- Approval is not promotion

## 24. Rollback or Rejection Notes

- If rejected, why:
- If future adaptation is proposed, exact separate proposal path:
- Rollback plan if a later approved adaptation fails:
- Review notes:
