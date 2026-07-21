# Scenario 4: collect --help --all flag — Evidence

## Command
```bash
autoinfo collect --help
```

## Result: PASS

## Output shows `--all / -A` flag:
```
╭─ Options ────────────────────────────────────────────────────────╮
│ --domain    TEXT     Domain to collect for (mutually exclusive    │
│                      with --all)                                 │
│ --all  -A           Collect for all active domains               │
│ --topic     TEXT     Topic / search query filter                 │
│ --source    TEXT     Source name filter (repeatable)             │
│ --limit     INTEGER  Max items to collect per source [default:20]│
│ --dry-run           Preview without storing                      │
│ --auto-process      Run processing immediately after collection  │
│ --json              Output as JSON                               │
╰──────────────────────────────────────────────────────────────────╯
```

The `--all` flag is present and documented as mutually exclusive with `--domain`.
