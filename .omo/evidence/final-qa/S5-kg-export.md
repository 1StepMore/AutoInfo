# Scenario 5: knowledge graph export --help — Evidence

## Command
```bash
autoinfo knowledge graph export --help
```

## Result: PASS

## Output
```
 Usage: autoinfo knowledge graph export [OPTIONS]

 Export the knowledge graph for a domain.

 Produces a file containing all entities and relations from the knowledge
 graph, in the requested format.

╭─ Options ────────────────────────────────────────────────────────╮
│ *  --domain  TEXT  Domain to export knowledge graph for [required]│
│    --format  TEXT  Export format: json (default), graphml, csv    │
│                    [default: json]                                │
│    --output  TEXT  Output file path (default:                    │
│                    knowledge_graph_export.<format>)               │
│    --help          Show this message and exit.                   │
╰──────────────────────────────────────────────────────────────────╯
```

The `knowledge graph export` subcommand exists and shows `--domain` (required), `--format`, `--output` options.
