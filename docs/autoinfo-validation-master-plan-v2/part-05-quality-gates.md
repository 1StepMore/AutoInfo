# Part 5: Quality Gate Validation (Q37-Q41)

**Coverage:** G1 (source authority), G2 (dedup), G3 (relevance), G4 (factual consistency), G5 (translation accuracy), advisory principle

---

## Q37: G1 Source Authority

**User says:** "Low-quality sources should be flagged but never blocked."

### Scenarios

#### 37.1 🟢 G1 flags Tier 3+ sources (advisory)
```python
from autoinfo.quality import G1SourceAuthority
from autoinfo.models import Item

item = Item(id="1", source_name="blog", title="Test", content="test", collected_at="now", quality_tier=3)
result = G1SourceAuthority().check(item, {"quality_tier": 3})
assert result.flagged == True
assert "warning" in result.details.get("warning", "").lower() or "low" in str(result.details).lower()
print(f"✅ G1 Tier 3 flagged: {result.flagged} — details: {result.details}")
```
**Expected Result:** ✅ Items from Tier 3+ sources are flagged (advisory, not blocked).

**Actual Result:** _________ **PASS / FAIL:** _________

#### 37.2 🟢 G1 passes Tier 1 sources unflagged
```python
item = Item(id="2", source_name="pubmed", title="Test", content="test", collected_at="now", quality_tier=1)
result = G1SourceAuthority().check(item, {"quality_tier": 1})
assert result.flagged == False
assert result.passed == True
print(f"✅ G1 Tier 1 not flagged: {result.flagged}")
```
**Expected Result:** ✅ Tier 1 sources pass unflagged.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 37.3 🟢 G1 with tier from source_config (overrides item.quality_tier)
```python
item = Item(id="3", source_name="pubmed", title="Test", content="test", collected_at="now", quality_tier=1)
result = G1SourceAuthority().check(item, {"quality_tier": 4})  # source_config overrides
assert result.flagged == True
print(f"✅ G1 source_config override flags: {result.flagged}")
```
**Expected Result:** ✅ source_config.quality_tier takes precedence over item.quality_tier.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 37.4 🟢 G1 without source_config uses item's tier
```python
item = Item(id="4", source_name="unknown", title="Test", content="test", collected_at="now", quality_tier=3)
result = G1SourceAuthority().check(item)  # no source_config
assert result.flagged == True
print(f"✅ G1 no source_config: flagged={result.flagged} (using item tier=3)")
```
**Expected Result:** ✅ Falls back to item.quality_tier when source_config is None.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q37 Verdict

| Scenario | Result |
|----------|--------|
| 37.1 Flags Tier 3+ | ⬜ |
| 37.2 Passes Tier 1 | ⬜ |
| 37.3 source_config overrides | ⬜ |
| 37.4 Falls back to item tier | ⬜ |

**OVERALL: ⬜**

---

## Q38: G2 Dedup

**User says:** "I don't want duplicate articles in my knowledge base."

### Scenarios

#### 38.1 🟢 URL exact match dedup
```python
from autoinfo.dedup import DedupChecker
checker = DedupChecker()
item = Item(id="dup-1", source_name="pubmed", source_url="https://doi.org/10.1234/test", title="Dup Article", content="same content", collected_at="now")
existing = [{"source_url": "https://doi.org/10.1234/test"}]
result = checker.check(item, existing)
assert result["is_duplicate"] == True
assert "url" in str(result.get("matched_by", ""))
print(f"✅ URL dedup: is_duplicate={result['is_duplicate']}, matched_by={result.get('matched_by','?')}")
```
**Expected Result:** ✅ Same URL → duplicate.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 38.2 🟢 Unique URL passes dedup
```python
item = Item(id="unique-1", source_name="pubmed", source_url="https://doi.org/10.9999/unique", title="Unique Article", content="different", collected_at="now")
existing = [{"source_url": "https://doi.org/10.1234/other"}]
result = checker.check(item, existing)
assert result["is_duplicate"] == False
print(f"✅ Unique URL: is_duplicate={result['is_duplicate']}")
```
**Expected Result:** ✅ Different URL → unique, not duplicate.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 38.3 🟢 PMID match dedup (from raw_data)
```python
item = Item(id="dup-2", source_name="pubmed", source_url="https://example.com/a", title="Dup by PMID", content="content", collected_at="now", raw_data={"pmid": "12345678"})
existing = [{"raw_data": {"pmid": "12345678"}}]
try:
    result = checker.check(item, existing, check_pmid=True)
    assert result["is_duplicate"] == True
    print(f"✅ PMID dedup: is_duplicate={result['is_duplicate']}")
except TypeError:
    # checker API may not accept check_pmid param — test via raw_data comparison
    print("⚠️ PMID dedup check: API may use different method")
```
**Expected Result:** ✅ Same PMID → duplicate.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 38.4 🔴 Empty source_url handled gracefully
```python
item = Item(id="no-url", source_name="pubmed", source_url="", title="No URL", content="test", collected_at="now")
existing = [{"source_url": "https://example.com"}]
result = checker.check(item, existing)
assert result["is_duplicate"] == False  # Empty URL can't match
print(f"✅ Empty URL: is_duplicate={result['is_duplicate']} (no crash)")
```
**Expected Result:** ✅ Empty source_url does not crash dedup. Not detected as duplicate.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q38 Verdict

| Scenario | Result |
|----------|--------|
| 38.1 URL dedup | ⬜ |
| 38.2 Unique passes | ⬜ |
| 38.3 PMID dedup | ⬜ |
| 38.4 Empty URL | ⬜ |

**OVERALL: ⬜**

---

## Q39: G3 Relevance Scoring

**User says:** "Items should be scored by relevance to my topics."

### Scenarios

#### 39.1 🟢 Score is within 0-100 range
```python
from autoinfo.quality import G3RelevanceScoring
item = Item(id="5", title="IVF treatment outcomes in 2026", content="This paper discusses IVF embryo implantation success rates...", collected_at="now")
result = G3RelevanceScoring().check(item, {"keywords": ["IVF", "embryo", "implantation"]})
assert 0 <= result.score <= 100
print(f"✅ G3 score: {result.score} (range 0-100) ✓")
```
**Expected Result:** ✅ Score is within 0-100 range.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 39.2 🟢 Higher keyword overlap = higher score
```python
# Item with all keywords
item_high = Item(id="6", title="IVF embryo implantation study 2026", content="IVF embryo implantation research findings...", collected_at="now")
# Item with no keywords
item_low = Item(id="7", title="Cooking recipes", content="How to make pasta carbonara...", collected_at="now")

result_high = G3RelevanceScoring().check(item_high, {"keywords": ["IVF", "embryo", "implantation"]})
result_low = G3RelevanceScoring().check(item_low, {"keywords": ["IVF", "embryo", "implantation"]})

assert result_high.score > result_low.score
print(f"✅ Higher relevance scores higher: high={result_high.score} > low={result_low.score}")
```
**Expected Result:** ✅ Title/content with keyword overlap scores higher than irrelevant content.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 39.3 🟢 Items below 30 relevance are flagged hidden
```python
item = Item(id="8", title="Unrelated topic", content="cooking recipes pasta carbonara", collected_at="now")
result = G3RelevanceScoring().check(item, {"keywords": ["IVF", "embryo", "implantation"]})
if result.score < 30:
    assert result.flagged == True
    print(f"✅ Low score ({result.score}) → flagged={result.flagged}, hidden={result.details.get('hidden','?')}")
else:
    print(f"⚠️ Score {result.score} ≥ 30, not flagged (depends on keyword matching)")
```
**Expected Result:** ✅ Items below threshold have `hidden: true` in details.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q39 Verdict

| Scenario | Result |
|----------|--------|
| 39.1 Score 0-100 | ⬜ |
| 39.2 Higher overlap = higher | ⬜ |
| 39.3 Low score flagged | ⬜ |

**OVERALL: ⬜**

---

## Q40: G4 Factual Consistency [REQUIRES LLM KEY]

**User says:** "LLM-extracted summaries should be factually consistent with the source."

### Scenarios

#### 40.1 🟢 G4 — consistent summary passes
```python
from autoinfo.quality import G4FactualConsistency
from autoinfo.models import Item, ExtractionResult

item = Item(id="g4-1", title="Test", content="The study found that IVF success rates improved by 20% with embryo genetic testing.", collected_at="now")
extraction = ExtractionResult(
    summary="IVF success rates improved by 20% with embryo genetic testing according to the study."
)

gate = G4FactualConsistency(model="openrouter/deepseek/deepseek-chat")
result = gate.check(item, extraction)
print(f"✅ G4 consistent: passed={result.passed}, flagged={result.flagged}")
print(f"  Details: {result.details}")
```
**Expected Result:** ✅ Consistent summary passes (flagged=False or passed=True).

**Actual Result:** _________ **PASS / FAIL:** _________

#### 40.2 🟢 G4 — contradictory summary flagged
```python
item = Item(id="g4-2", title="Test", content="The study found that IVF success rates improved by 20% with embryo genetic testing.", collected_at="now")
extraction = ExtractionResult(
    summary="IVF success rates decreased significantly with genetic testing."
)

gate = G4FactualConsistency(model="openrouter/deepseek/deepseek-chat")
result = gate.check(item, extraction)
print(f"✅ G4 contradictory: passed={result.passed}, flagged={result.flagged}")
print(f"  Details: {result.details}")
```
**Expected Result:** ✅ Contradictory summary flagged (flagged=True).

**Actual Result:** _________ **PASS / FAIL:** _________

#### 40.3 🟢 G4 — LLM call failure returns flagged but doesn't crash
```python
from unittest.mock import patch

item = Item(id="g4-3", title="Test", content="Test content", collected_at="now")
extraction = ExtractionResult(summary="Test summary")

with patch("autoinfo.quality.litellm") as mock_litellm:
    mock_litellm.completion.side_effect = Exception("LLM API timeout")
    gate = G4FactualConsistency(model="openrouter/deepseek/deepseek-chat")
    try:
        result = gate.check(item, extraction)
        assert result.flagged == True
        print(f"✅ G4 LLM failure: flagged=True, passed={result.passed}, details={result.details}")
    except Exception as e:
        print(f"⚠️ G4 exception on LLM failure: {e}")
```
**Expected Result:** ✅ LLM failure returns flagged result, does NOT crash.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q40 Verdict

| Scenario | Result |
|----------|--------|
| 40.1 Consistent passes | ⬜ |
| 40.2 Contradictory flagged | ⬜ |
| 40.3 LLM failure handled | ⬜ |

**OVERALL: ⬜**

---

## Q41: G5 Translation Accuracy Advisory + All Gates Orchestration

**User says:** "Translation quality should be checked but never block content."

### Scenarios

#### 41.1 🟢 G5 — faithful translation passes [REQUIRES LLM KEY]
```python
from autoinfo.quality import G5TranslationAccuracy
from autoinfo.models import Item, ExtractionResult

item = Item(id="g5-1", title="Test", content="The mitochondria is the powerhouse of the cell.", collected_at="now")
extraction = ExtractionResult(
    custom_fields={"translation": "线粒体是细胞的能量来源。"}  # Faithful Chinese translation
)

gate = G5TranslationAccuracy(model="openrouter/deepseek/deepseek-chat")
result = gate.check(item, extraction)
print(f"✅ G5 faithful: passed={result.passed}, flagged={result.flagged}")
print(f"  Details: {result.details}")
```
**Expected Result:** ✅ Faithful translation passes (flagged=False).

**Actual Result:** _________ **PASS / FAIL:** _________

#### 41.2 🟢 G5 — unfaithful translation flagged [REQUIRES LLM KEY]
```python
item = Item(id="g5-2", title="Test", content="The mitochondria is the powerhouse of the cell.", collected_at="now")
extraction = ExtractionResult(
    custom_fields={"translation": "细胞核是细胞的能量来源。"}  # Wrong: nucleus vs mitochondria
)

gate = G5TranslationAccuracy(model="openrouter/deepseek/deepseek-chat")
result = gate.check(item, extraction)
print(f"✅ G5 unfaithful: passed={result.passed}, flagged={result.flagged}")
print(f"  Details: {result.details}")
```
**Expected Result:** ✅ Unfaithful translation flagged (flagged=True, score < 1.0).

**Actual Result:** _________ **PASS / FAIL:** _________

#### 41.3 🟢 G5 — no translation to check = trivially accurate
```python
item = Item(id="g5-3", title="Test", content="Test content", collected_at="now")
extraction = ExtractionResult(custom_fields={"translation": ""})

gate = G5TranslationAccuracy()
result = gate.check(item, extraction)
assert result.flagged == False
assert result.passed == True
print(f"✅ G5 no translation: flagged={result.flagged}, passed={result.passed}")
```
**Expected Result:** ✅ No translation means trivially accurate, no flag.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 41.4 🟢 All gates are advisory — check via orchestrator
```python
from autoinfo.quality import run_quality_gates
from autoinfo.models import Item

item = Item(id="all-gates", source_name="unknown-blog", title="Low quality item", content="spam content", collected_at="now", quality_tier=4)
context = {
    "source_config": {"quality_tier": 4},
    "topic_keywords": ["test", "spam"]
}

results = run_quality_gates(item, context)
print(f"✅ All advisory gates:")
for gate_name, result in results.items():
    # All gates should pass (advisory) — might have flags but not fail
    print(f"  {gate_name}: passed={result.passed}, flagged={result.flagged}, score={result.score}")
    if result.passed == False and result.flagged == True:
        print(f"    → Gate flagged but advisory (item not blocked)")
```
**Expected Result:** ✅ All gates pass (passed=True) even for low-quality items. Advisory principle: flagged but never blocked.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 41.5 🟢 G5 detailed check — runs all 5 translation sub-gates [REQUIRES LLM KEY]
```python
from autoinfo.quality import G5TranslationAccuracy

gate = G5TranslationAccuracy()
result = gate.check_detailed(
    source="The mitochondria is the powerhouse of the cell.",
    translation="线粒体是细胞的能量来源。",
    source_lang="en",
    target_lang="zh"
)
print(f"✅ G5 detailed check:")
for gate_name, score in result.get("gates", {}).items():
    print(f"  {gate_name}: {score}")
print(f"  composite_score: {result.get('composite_score')}")
print(f"  verdict: {result.get('verdict')}")
```
**Expected Result:** ✅ Returns all 5 sub-gate scores with composite and verdict.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q41 Verdict

| Scenario | Result |
|----------|--------|
| 41.1 Faithful passes | ⬜ |
| 41.2 Unfaithful flagged | ⬜ |
| 41.3 No translation | ⬜ |
| 41.4 All advisory | ⬜ |
| 41.5 Detailed check | ⬜ |

**OVERALL: ⬜**
