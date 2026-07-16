# Maintaining cup_handle skills — versioning & the base pointer

Same mechanics as warrior (`strategies/warrior/skills/MAINTAINING.md`), scoped to
**this** family's tree:

| Path | Role |
|---|---|
| `strategies/cup_handle/skills/skill_versions.json` | `base` + content hashes |
| `strategies/cup_handle/skills/trade_skills/<v>.md` | sealed skill versions |

```bash
python3 -m trading.llm_trader.batchsim current --strategy cup_handle
python3 -m trading.llm_trader.batchsim new-version --strategy cup_handle --from 0.1.0 --to 0.2.0
# edit strategies/cup_handle/skills/trade_skills/0.2.0.md
python3 -m trading.llm_trader.batchsim run --strategy cup_handle --version 0.2.0 ...
python3 -m trading.llm_trader.batchsim promote --strategy cup_handle --version 0.2.0
```

**Never edit a sealed version in place.** Files are chmod read-only after first use.

Promotion / experiment method: follow warrior's `IMPROVING.md` process (paired
batch gate, RULE_TRACE update) with cup_handle testsets and `--strategy cup_handle`.
