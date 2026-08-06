# Validation Run Reports

Versioned launch-validation run reports (fixes #129 P0-2).

## Layout

| Path | Content |
|------|---------|
| `validation-runs/<date>/scenarios.json` | Persisted scenario results per run (`run_validation_scenario(save_results=true)` or `validation_delivery.py`) |
| `validation-runs/<date>/evidence/` | A1-A12 evidence files collected during the run (git-tracked via `.gitignore` whitelist) |
| `validation-runs/latest.txt` | Pointer to the newest run directory |
| `docs/dev/validation-reports/launch-validation-<version>-<date>.md` | Executive run report generated from a run's `scenarios.json` |
| `validation-deliveries/<date>/` | Delivery zips from `validation_delivery.py` (fixed archive location) |
| `validation-runs/coverage/coverage-<date>.json` | Timestamped coverage audit output from `scripts/coverage_audit.py` |

## Workflow

```bash
# 1. Run scenarios, persisting results (MCP: pass save_results=true)
python3 scripts/validation_delivery.py --skip-llm-scenarios   # also persists + zips

# 2. Generate a versioned run report
python3 scripts/validation_report.py --version 1.9

# 3. Diff two runs for regression trends
python3 scripts/validation_diff.py                # latest vs previous

# 4. Timestamped tool-coverage audit
python3 scripts/coverage_audit.py
```

## Durability

`.omo/` remains gitignored, but `.omo/evidence/validation-runs/` and the
repo-root `validation-runs/` directory are whitelisted in `.gitignore`, so
run evidence and results are committed to git and survive clones/cleanups
instead of being ephemeral local files.
