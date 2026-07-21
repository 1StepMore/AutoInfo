# Scenario 7: Webhook Handler — Evidence

## Command
```python
from autoinfo.collectors.webhook import WebhookHandler
h = WebhookHandler()
item = h.handle({'title':'T','content':'C','source_url':'https://x.com'})
print(item.title, item.source_type)
```

## Result: PASS

## Output
```
T webhook
```

WebhookHandler correctly creates an item with title "T" and source_type "webhook".
