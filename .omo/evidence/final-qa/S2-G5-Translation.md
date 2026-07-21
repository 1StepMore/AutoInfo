# Scenario 2: G5 Translation Accuracy — Evidence

## Command (as written by user)
```bash
python3 -c "from autoinfo.quality import G5TranslationAccuracy; g5=G5TranslationAccuracy(); r=g5.check('Hello world', 'Bonjour le monde'); print(r)"
```

## Result: FAIL (test script type mismatch)

The `G5TranslationAccuracy.check()` method signature is:
```python
def check(self, item: Item, extraction: ExtractionResult) -> QualityResult:
```

It expects `Item` and `ExtractionResult` typed objects, not plain strings. Passing strings directly raises:
```
AttributeError: 'str' object has no attribute 'custom_fields'
```

## Correct invocation (works with proper types)

```python
from autoinfo.quality import G5TranslationAccuracy, Item, ExtractionResult

item = Item(id='t1', source_name='test', source_type='manual', 
            source_url='https://x.com', title='T1', content='Hello world')
extraction = ExtractionResult(item_id='t1', 
                              custom_fields={'translation': 'Bonjour le monde'})
g5 = G5TranslationAccuracy()
r = g5.check(item, extraction)
```

With proper objects and no API key, it gracefully degrades:
```
QualityResult(gate_name='G5-TranslationAccuracy', passed=False, score=0.0, 
  details={faithful: None, explanation: LLM check failed: ...AuthenticationError...})
```

## Empty-translation path (no LLM needed — works correctly)
```
QualityResult(gate_name='G5-TranslationAccuracy', passed=True, score=0.0,
  details={faithful: True, explanation: No translation to check, issues: []}, flagged=False)
```

**Recommendation:** Either update the test to construct proper objects, or add a string-convenience wrapper to `check()`.
