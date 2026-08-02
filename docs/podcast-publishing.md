# Podcast Publishing Runbook

How to generate a podcast RSS feed with AutoInfo, host MP3 audio, and
manually submit to Apple Podcasts and Spotify for Podcasters.

---

## Quick Overview

```
Generate audio → Persist MP3 → Build podcast RSS → Host feed URL → Submit to directories
```

| Step | AutoInfo | Manual (you) |
|------|----------|---------------|
| 1. Create audio episodes | `generate_digest(domain, format="audio")` | — |
| 2. Host MP3 files | REST endpoint `GET /media/<file>` | Expose server publicly |
| 3. Build podcast RSS | `PodcastRSSDeliveryChannel.send()` | Upload feed XML |
| 4. Submit to Apple Podcasts | — | Apple Podcasts Connect |
| 5. Submit to Spotify | — | Spotify for Podcasters |

---

## Step 1 — Generate Audio Episodes

Generate digest or report content as MP3 audio.  The MP3 file is
automatically persisted to `exports/<domain>/podcast/ep-<timestamp>.mp3`.

**MCP tool call:**
```
generate_digest(domain="my-podcast", period="weekly", format="audio")
```

**CLI equivalent:**
```bash
autoinfo output digest --domain my-podcast --period weekly --format audio
```

The result:
- Returns: base64-encoded MP3 (backward-compatible)
- Side effect: writes `exports/my-podcast/podcast/ep-20260802_120000.mp3`

---

## Step 2 — Host MP3 Files

The AutoInfo REST API serves persisted audio files at:

```
http://localhost:8741/media/exports/my-podcast/podcast/ep-20260802_120000.mp3
```

**Safety:** Only files under `exports/` and `data/` are served. Path traversal
outside these roots returns 404.

**Security note:** The REST API binds to `127.0.0.1` by default. To make
MP3 files publicly accessible for podcast directory submission, you must:

1. Configure `rest_api.host` to `0.0.0.0` in `.autoinfo/config.yaml`
2. Or serve the `exports/` directory via nginx/Caddy reverse proxy
3. Ensure the URL in the RSS enclosure matches the public-facing URL

Verify with:
```bash
curl -I http://localhost:8741/media/exports/my-podcast/podcast/ep-20260802_120000.mp3
# → HTTP/1.1 200 OK
# → content-type: audio/mpeg
```

---

## Step 3 — Build Podcast RSS Feed

Use the `PodcastRSSDeliveryChannel` to generate an Apple Podcasts-compatible
RSS 2.0 feed with enclosure links and `itunes:*` namespace metadata.

**Configuration** (via config or payload):
```yaml
feed_url: "exports/my-podcast/feed.xml"
title: "My AutoInfo Podcast"
description: "Weekly AI-generated podcast from my AutoInfo knowledge base"
author: "Your Name"
language: "en"
image_url: "https://example.com/podcast-cover.jpg"
explicit: "no"
category: "Technology"
subcategory: "Podcasts"
base_url: "http://localhost:8741"  # or your public URL
```

**Payload example:**
```python
from autoinfo.delivery.rss import PodcastRSSDeliveryChannel
from autoinfo.models import Product, ProductType

channel = PodcastRSSDeliveryChannel()
product = Product(
    id="podcast-001",
    domain="my-podcast",
    type=ProductType.PROCESSED,
    name="weekly-podcast",
    config={...},
)

result = channel.send(
    product=product,
    payload={
        "title": "My AutoInfo Podcast",
        "description": "Weekly AI-generated podcast",
        "author": "Your Name",
        "language": "en",
        "image_url": "https://example.com/cover.jpg",
        "explicit": "no",
        "category": "Technology",
        "episodes": [
            {
                "title": "Episode 1 — Getting Started",
                "description": "First episode of our AutoInfo podcast.",
                "audio_url": "media/exports/my-podcast/podcast/ep-20260802_120000.mp3",
                "duration": "05:30",
                "guid": "ep-001",
                "pub_date": "2026-08-02T12:00:00+00:00",
                "episode_type": "full",
                "season": 1,
                "episode": 1,
            },
        ],
        "feed_url": "exports/my-podcast/feed.xml",
    },
    recipients=[],
)
```

The generated RSS XML contains:
```xml
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <itunes:author>Your Name</itunes:author>
    <itunes:title>My AutoInfo Podcast</itunes:title>
    <itunes:explicit>no</itunes:explicit>
    <itunes:image href="https://example.com/cover.jpg"/>
    <itunes:category text="Technology">
      <itunes:category text="Podcasts"/>
    </itunes:category>
    <item>
      <enclosure url="http://localhost:8741/media/exports/my-podcast/podcast/ep-20260802_120000.mp3"
                 length="0" type="audio/mpeg"/>
      <itunes:duration>05:30</itunes:duration>
      <itunes:episodeType>full</itunes:duration>
      <itunes:season>1</itunes:season>
      <itunes:episode>1</itunes:episode>
    </item>
  </channel>
</rss>
```

---

## Step 4 — Submit to Apple Podcasts Connect

Apple does not provide a public API for podcast submission.  You must
manually submit the RSS feed URL through Apple Podcasts Connect.

1. Go to https://podcastsconnect.apple.com/
2. Sign in with your Apple ID
3. Click "+" → **New Show** → enter your RSS feed URL
4. Apple validates the feed (checks `<enclosure>`, `itunes:*` namespace, cover art size)
5. Review metadata → **Submit**
6. Apple reviews your podcast (typically 24-72 hours)
7. Once approved, your podcast appears in Apple Podcasts

**Requirements check for Apple validation:**
- [ ] RSS 2.0 with `xmlns:itunes` declaration
- [ ] `<enclosure>` with valid `url`, `type="audio/mpeg"`, non-zero `length`
- [ ] `<itunes:image>` pointing to a 1400×1400 to 3000×3000 JPEG/PNG
- [ ] `<itunes:author>`, `<itunes:title>`, `<itunes:explicit>`
- [ ] At least one `<item>` with `<enclosure>`
- [ ] Feed URL must be publicly accessible (not localhost)

AutoInfo generates all XML metadata correctly — you only need to ensure
the feed URL and enclosure URLs are publicly accessible.

---

## Step 5 — Submit to Spotify for Podcasters

Spotify for Podcasters also requires manual RSS feed submission.

1. Go to https://podcasters.spotify.com/
2. Sign in → **Add Your Podcast** → paste your RSS feed URL
3. Spotify validates the feed
4. Confirm podcast details → **Submit**
5. Your podcast appears on Spotify (usually within hours)

**Additional Spotify notes:**
- Spotify does not require the `itunes:*` namespace but tolerates it
- Cover art: minimum 640×640 (recommended 3000×3000)
- Same RSS feed can be used for both Apple and Spotify

---

## Testing & Validation

### Validate RSS XML
```bash
# Parse and check for enclosure + itunes:*
python -c "
import xml.etree.ElementTree as ET
tree = ET.parse('exports/my-podcast/feed.xml')
ns = {'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd'}
channel = tree.find('channel')
enclosures = channel.findall('.//enclosure')
itunes_author = channel.find('.//itunes:author', ns)
assert len(enclosures) > 0, 'Missing enclosure'
assert itunes_author is not None, 'Missing itunes:author'
print('OK — valid podcast RSS')
"
```

### Verify enclosure URL
```bash
# Extract enclosure URL and curl it
URL=$(python -c "
import xml.etree.ElementTree as ET
tree = ET.parse('exports/my-podcast/feed.xml')
enc = tree.find('.//enclosure')
print(enc.get('url'))
")
curl -I "$URL"
# Should return HTTP/1.1 200 OK with content-type: audio/mpeg
```

### Apple Podcasts validation
- Use https://podba.se/validate/ to test your RSS feed before submitting
- Or Apple's own validator at https://podcastsconnect.apple.com/ (during submission)

### Regression check
```bash
# Plain RSS (no enclosure) still works
pytest tests/ -k "rss and not podcast" -x
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Enclosure URL returns 404 | MP3 not persisted or wrong path | Check `exports/<domain>/podcast/` for `.mp3` files |
| Apple rejects "invalid feed" | Missing `itunes:` namespace | Ensure `xmlns:itunes` in RSS root element |
| Apple rejects "no episodes" | Empty `<channel>` or no `<enclosure>` | At least one `<item>` with enclosure is required |
| Feed not reachable | REST API on localhost only | Set `host: "0.0.0.0"` in config or use reverse proxy |
| Enclosure length is 0 | `audio_data` not provided in payload | Pass actual audio bytes in episode dict's `audio_data` key |

---

## Reference

- Apple Podcasts RSS requirements: https://help.apple.com/itc/podcasts_connect/
- Spotify for Podcasters: https://podcasters.spotify.com/
- autoinfo podcast RSS implementation: `src/autoinfo/delivery/rss.py` (PodcastRSSDeliveryChannel)
- autoinfo audio persistence: `src/autoinfo/output/__init__.py` (_render_audio, _maybe_persist_audio)
