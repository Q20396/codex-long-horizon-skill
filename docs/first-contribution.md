# First Contribution

Start with a small, reviewable change. Good first contributions include:

- add one routing fixture
- improve one example prompt
- clarify one prompt in `prompts/`
- fix one broken internal link
- tighten one validation message

## Walkthrough

1. Fork the repository or create a feature branch.
2. Choose one scoped change.
3. If behavior changes, update `tests/expected-triggers.json`.
4. Run focused checks:

   ```bash
   python3 scripts/generate_skill_catalog.py --check
   python3 .agents/skills/long-horizon-engineering/scripts/test_expected_triggers.py
   ```

5. Run full validation:

   ```bash
   python3 scripts/full_skill_validation.py
   ```

6. If a skill description changed, regenerate and check the catalog:

   ```bash
   python3 scripts/generate_skill_catalog.py
   python3 scripts/generate_skill_catalog.py --check
   ```

7. Open a draft PR.
8. Include validation evidence and any known limitations.

Avoid making a whole new skill as your first contribution unless a maintainer
has already agreed on the scope.
