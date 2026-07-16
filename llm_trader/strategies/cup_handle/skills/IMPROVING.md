# Improving cup_handle — experiment method

Use the same promotion discipline as warrior
(`strategies/warrior/skills/IMPROVING.md`):

1. Hypothesis → objectify the feel-call → RULE_TRACE row.
2. Fork a new skill version (`batchsim new-version --strategy cup_handle …`).
3. Fixed holdout from `data/cup_handle/entries.db` (never mix with warrior sets).
4. Paired `batchsim compare` on effective R; promote only if gate clears.

Family-specific artifacts:

| File | Role |
|---|---|
| `RULE_TRACE.md` | cup_handle rule → methodology citation |
| `CHANGELOG.md` | experiment log for this family only |
