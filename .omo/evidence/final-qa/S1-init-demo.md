# Scenario 1: Init Demo — Evidence

## Command
```bash
TMPDIR=$(mktemp -d) && cd "$TMPDIR" && autoinfo init --demo medical-research
```

## Result: PASS (with note on topics)

**Directories created:**
- `.autoinfo/knowledge/00-Inbox/` ✅
- `.autoinfo/knowledge/01-Raw/` ✅
- `.autoinfo/knowledge/02-Draft/` ✅
- `.autoinfo/knowledge/03-Wiki/` ✅

**Sources in config.yaml:**
- pubmed ✅
- arXiv ✅ (new in v1.1)
- CrossRef ✅ (new in v1.1)
- Unpaywall ✅ (new in v1.1)

**Topics in config.yaml:**
- "IVF breakthroughs" ✅
- "Neuroplasticity" ⚠️ (expected "Brain Science" and "Neuroscience" — description says "脑科学/神经科学" but topic name is "Neuroplasticity", a neuroscience subfield)

## Config excerpts
```yaml
domains:
- name: medical-research
  active: true
  sources:
  - name: pubmed
  - name: arXiv
  - name: CrossRef
  - name: Unpaywall
  topics:
  - name: IVF breakthroughs
  - name: Neuroplasticity
```
