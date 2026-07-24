---
name: translator-qa-skill
description: Orchestrate high-quality translation workflows with automated quality assurance
author: AutoInfo
version: 1.0.0
---

# Translator QA Skill

## Purpose

Use this skill when the human asks you to translate content and verify its
quality. It covers the full pipeline: load domain terminology, forward
translate, run 5 quality gates, back-translate with a different model, refine
if needed, and return a composite score with per-round diagnostics.

The workflow is appropriate for high-stakes translation (medical documents,
commercial materials, academic content) where quality cannot be assumed on the
first pass.

## Workflow Steps

### 1. Prepare

Load domain terminology and resolve the LLM config before translating.

```
get_effective_llm_config(task="translation")
  → returns model, provider, base_url used for translation

load_terminology("medical-research")
  → returns Terminology(terms={...}, score_weights={...})
  → File: knowledge/<domain>/_terminology.yaml
  → Graceful: returns empty Terminology if file missing
```

The terminology dict feeds into Gate 2 (terminology check) and into the
forward translation prompt for domain-specific guardrails.

### 2. Translate

Call the forward translation MCP tool.

```
localize_content(
    content="...",
    source_lang="en",
    target_lang="zh",
    domain="medical-research"
)
  → returns {
      translated_title: "...",
      translated_body: "...",
      target_lang: "zh",
      source_lang: "en",
      success: true
    }
```

Two modes:

- **Content-ID mode**: pass `content_id` to translate a stored KB entry
  (translation is stored as a new file).
- **Direct content mode**: pass `content` + `source_lang` + `target_lang`
  for a one-shot translation without storage.

### 3. Verify Quality Gates

Run the 5 translation quality gates via
`run_translation_quality_gates()`. Gates 1-4 are deterministic (no LLM).
Gate 5 calls the LLM to assign sub-scores.

```
from autoinfo.quality import run_translation_quality_gates

result = run_translation_quality_gates(
    source="Original text...",
    target="Translated text...",
    source_lang="en",
    target_lang="zh",
    terminology_dict={"CRISPR": {"type": "do_not_translate"}},
)
  → returns {
      gates: {
        inline_tags:   {passed: bool, missing_tags: [...], extra_tags: [...]},
        terminology:   {passed: bool, violations: [...]},
        length_ratio:  {passed: bool, ratio: float},
        source_copy:   {passed: bool, similarity: float},
        llm_judge:     {faithfulness: int, terminology: int, style: int,
                        readability: int, issues: [str]}
      },
      composite_score: {composite: float, faithfulness: float, ...}
    }
```

Gate details:

| # | Gate | Function | What It Checks |
|---|------|----------|----------------|
| 1 | Inline Tags | `check_inline_tags()` | Code, link, image markdown preserved in translation |
| 2 | Terminology | `check_terminology()` | `do_not_translate` terms present literally; preferred translations used |
| 3 | Length Ratio | `check_length_ratio()` | Target/source ratio within [0.5, 2.0] |
| 4 | Source Copy | `check_source_copy()` | Similarity < 0.9 (translation was actually applied) |
| 5 | LLM Judge | `llm_judge()` | Faithfulness, terminology, style, readability (0-100 each) |

### 4. Back-Translate

If the composite score from Step 3 is below 70, run back-translation
verification with a **different model** from the forward pass.

```
from autoinfo.translation_qa import run_back_translation_pipeline

back_result = run_back_translation_pipeline(
    source_text="Original...",
    translated_text="Translated...",
    source_lang="en",
    target_lang="zh",
    model_pool=[
        "openrouter/deepseek/deepseek-chat",   # forward model
        "openrouter/anthropic/claude-sonnet",  # back-translate model
    ],
)
  → returns {
      round: 1,
      forward_model: "openrouter/.../deepseek-chat",
      back_model: "openrouter/.../claude-sonnet",
      judge_model: "openrouter/.../claude-sonnet",
      faithfulness: 85.0,
      issues: [
        {severity: "minor", description: "...", position: "paragraph 2"}
      ],
      composite_score: 72.5
    }
```

Key rule: the back-translation model must differ from the forward model.
The model pool picks `pool[0]` as forward and `pool[1]` as back. If only
one model is available, a warning is logged and the same model is reused
(suboptimal).

### 5. Refine

If issues remain (composite still below 70 after back-translation), run
multi-round refinement. Maximum 2 rounds.

```
from autoinfo.translation_qa import run_refinement_pipeline

refine_result = run_refinement_pipeline(
    source_text="Original...",
    initial_translation="Translated...",
    source_lang="en",
    target_lang="zh",
    model_pool=[...],
    threshold=70.0,
    max_rounds=2,
)
  → returns {
      final_translation: "...",
      rounds: [
        {round: 1, model_used: "...", faithfulness: 80.0,
         composite: 65.0, issues: [...]},
        {round: 2, model_used: "...", faithfulness: 92.0,
         composite: 78.0, issues: [...]}
      ],
      best_round_index: 1
    }
```

Refinement flow:

- **Round 1**: Uses the primary model (`pool[0]`), feeds judge issues into
  the prompt as a bullet list of what to fix.
- **Round 2**: Uses the secondary model (`pool[1]`) if available, includes
  ALL accumulated issues from all prior rounds.
- After all rounds, the candidate with the highest `composite_score` is
  returned as `final_translation`.

### 6. Score

Calculate the final composite quality score from the best translation
candidate.

```
from autoinfo.translation_qa import calculate_quality_score

score = calculate_quality_score(
    faithfulness=92.0,
    terminology=88.0,
    style=85.0,
    readability=90.0,
)
  → returns {
      composite: 89.5,
      faithfulness: 92.0,
      terminology: 88.0,
      style: 85.0,
      readability: 90.0,
      weights_used: {faithfulness: 40, terminology: 30,
                     style: 20, readability: 10}
    }
```

Default weights: faithfulness 40%, terminology 30%, style 20%,
readability 10%. Pass a custom `weights` dict to override. Weights are
auto-normalized if they don't sum to 100.

### 7. Report

Return the final translation and a QA report with per-round diagnostics.

```
{
  "final_translation": "... (best across all rounds)",
  "composite_score": 89.5,
  "quality_report": {
    "gates": {
      "inline_tags": {passed: true, missing: [], extra: []},
      "terminology": {passed: true, violations: []},
      "length_ratio": {passed: true, ratio: 1.32},
      "source_copy": {passed: true, similarity: 0.12},
      "llm_judge": {faithfulness: 92, terminology: 88, ...}
    },
    "back_translation": {
      "round": 1, "faithfulness": 85.0, "composite_score": 72.5,
      "issues": [...]
    },
    "refinement": {
      "rounds": [
        {"round": 1, "composite": 65.0, "issues": [...]},
        {"round": 2, "composite": 78.0, "issues": [...]}
      ],
      "best_round_index": 1
    },
    "final_score": {
      "composite": 89.5,
      "weights_used": {faithfulness: 40, terminology: 30, ...}
    }
  }
}
```

## MCP Tools Used

| Tool | Step | Purpose |
|------|------|---------|
| `localize_content` | 2 | Forward translation (content_id or direct content mode) |
| `get_effective_llm_config` | 1 | Resolve model, provider, base_url for translation task |

The remaining steps (3-7) use internal Python functions, not MCP tools:

- `load_terminology()` in `autoinfo.terminology`
- `run_translation_quality_gates()` in `autoinfo.quality`
- `run_back_translation_pipeline()` in `autoinfo.translation_qa`
- `run_refinement_pipeline()` in `autoinfo.translation_qa`
- `calculate_quality_score()` in `autoinfo.translation_qa`

## Thresholds and Limits

| Parameter | Value | When |
|-----------|-------|------|
| Back-translation trigger | composite < 70/100 | Step 3 → Step 4 |
| Max refinement rounds | 2 | Step 5 |
| Model diversity | Must use different model for back-translation | Step 4 |
| Length ratio bounds | [0.5, 2.0] | Gate 3 |
| Source copy threshold | similarity ≥ 0.9 = fail | Gate 4 |

## Example Agent-Arg Dialogue

**Human**: Translate this medical abstract from English to Chinese and QA it.

**Agent**:

```
Step 1: get_effective_llm_config(task="translation")
        load_terminology("medical-research")
Step 2: localize_content(
          content="We report a phase 3 trial of CRISPR-Cas9 edited...",
          source_lang="en", target_lang="zh",
          domain="medical-research")
Step 3: run_translation_quality_gates(...) → composite: 58.3
Step 4: composite < 70 → run_back_translation_pipeline(...)
        → faithfulness: 62.0, issues: [major×1, minor×2]
Step 5: issues found → run_refinement_pipeline(...)
        → round 1: composite 68.1
        → round 2: composite 84.2 → best_round_index: 1
Step 6: calculate_quality_score(faithfulness=90, terminology=85, ...)
        → composite: 87.3
Step 7: return final_translation + full QA report
```

**Agent**: Here is the translation and QA report. The final composite score
is 87.3 after 2 refinement rounds. One minor terminology issue remains
(the term "allele" was translated inconsistently in paragraph 3).
The back-translation model was Claude Sonnet (different from the forward
DeepSeek model), which confirmed the faithfulness score at 90/100.

## QA Scenarios

### Scenario A: Clean pass (no refinement needed)

```
Source: "The patient was administered 5mg of atorvastatin daily."
Target: "患者每日服用5mg阿托伐他汀。"
Gates: all pass
Composite: 92.4
Action: Return immediately, no back-translation or refinement.
```

### Scenario B: Source copy detected (translation not applied)

```
Source: "Hello world"
Target: "Hello world" (same text, no translation)
Gate 4 source_copy: similarity 1.0 → FAIL
Action: Flag as untranslated, do not back-translate.
        Ask human: "The target text is identical to the source.
        Do you want to retry with a different model?"
```

### Scenario C: Terminology violation (do_not_translate term translated)

```
Source: "CRISPR-Cas9 gene editing"
Target: "基因编辑" (CRISPR-Cas9 was translated instead of kept literal)
Gate 2 terminology: FAIL - term "CRISPR" expected as "CRISPR"
Action: Flag violation. If composite < 70, run back-translation.
        During refinement, explicitly tell the model: "CRISPR-Cas9
        must appear literally in the translation."
```

### Scenario D: Low faithfulness (back-translation + refinement required)

```
Source: "The study found no significant difference between groups (p=0.34)."
Target: "研究发现两组间有显著差异。" (meaning flipped: "found significant")
Gate 5 llm_judge: faithfulness 15, issues: ["meaning reversed"]
Composite: 22.0 → trigger back-translation
Back-translation: faithfulness 20, issues: [major: "opposite meaning"]
Refinement round 1: faithfulness 55 (still wrong)
Refinement round 2: faithfulness 88 (corrected)
Final composite: 82.0
Action: Return round 2 translation. Include issue note about the
        original meaning reversal to alert the human reviewer.
```

### Scenario E: Perfect inline tags but wrong language

```
Source (EN): "Run `pip install autoinfo` to install."
Target (ZH): "运行 `pip install autoinfo` 进行安装。"
Gate 1 inline_tags: PASS (backticks preserved)
Gate 4 source_copy: similarity 0.25 → PASS (clearly different text)
Gate 5 llm_judge: faithfulness 92, terminology 95, style 88, readability 90
Composite: 92.0
Action: Return as-is. This is a good translation where code blocks
        were correctly preserved while surrounding text was translated.
```

## Constraints

- Do NOT skip forward translation (Step 2) and go straight to quality gates.
- Do NOT use the same LLM model for forward translation and back-translation.
  Model diversity is the core assumption behind back-translation verification.
- Do NOT exceed 2 refinement rounds without asking the human for permission.
- Do NOT modify the terminology YAML files. Read them only.
- Do NOT discard the initial translation if refinement fails. Always fall
  back to the best available candidate.
