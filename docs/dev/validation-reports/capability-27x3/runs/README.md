# runs/ — per-domain, per-combination index

One file per **produced** product: `runs/<domain>/<combination>.md`, where
`<combination>` is the matrix cell id (e.g. `a1-b2-format.mardown`). A cell with
no artifact gets no file — absence is the gap signal, so never create a file to
"mark" an unimplemented cell.

Each file records:

```markdown
# <domain> / <cell>

- command: <exact command that produced the artifact>
- artifact: outputs/<domain>/<file> (<bytes>)
- produced_at: <ISO timestamp>
- gate L0: pass|fail (<command>)
- gate L2: pass|fail (<format>, details)
- gate L1: pass|fail|escalate|not-run (<battery command>)
- cost: <USD, or "unknown">
```

`runs/index.md` is generated from these files by
`.venv/bin/python scripts/coverage_matrix.py --evidence .` (the matrix reads the
same artifacts); it is a convenience view, not an independent source of truth.
