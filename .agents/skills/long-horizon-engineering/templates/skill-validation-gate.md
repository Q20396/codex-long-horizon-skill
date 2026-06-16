# Skill Validation Gate

Use this before marking a skill improvement ready for review or deployment.

## Candidate

- Skill:
- Branch or commit:
- Related bounded edit:

## Checks To Run

| Check | Required | Result | Evidence |
| --- | --- | --- | --- |
| check_skill_package.py | yes |  |  |
| doctor.py | yes |  |  |
| test_expected_triggers.py | yes |  |  |
| audit_skill_descriptions.py | yes |  |  |
| Python compile, if scripts changed | conditional |  |  |
| git diff --check | yes |  |  |

## Trigger Fixture Impact

- Should-trigger cases added or changed:
- Should-not-trigger safety cases added or changed:
- Borderline cases added or changed:

## Package / Doctor Impact

- Required files added:
- Check scripts updated:
- Installed-skill behavior affected:

## Description Audit Impact

- Skill description changed: yes / no
- Trigger precision risk:

## Acceptance Criteria

-

## Rejection Criteria

-

## Final Decision

- Accept / reject / needs more evidence:
- Reason:
