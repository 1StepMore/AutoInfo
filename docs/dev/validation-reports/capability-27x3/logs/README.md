# logs/ — captured command output

Naming: `<verb>-<domain>-<date>.log` (for example `collect-medical-research-2026-10-27.log`).
Verb prefixes in use: `collect`, `process`, `suite-baseline`, `suite`,
`coverage`, `diagnosis`, `structure`, `battery`.

Rules:

- Append the command as the first line (`$ <command>`) and the exit status as
  the last (`exit <code>`), so a log can be replayed.
- Never edit a log after capture. A re-run gets a new file with a new timestamp.
- These logs are committed (the generic `logs/` ignore rule is negated in
  `.gitignore` for this directory only) because they are the provenance for the
  numbers in the evidence tables.
