# Phase 1: Scraper + GCS — Key Context

**Last Updated: 2026-02-28 (session 3 — data-driven docIds)**

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `data/volumes.json` | All 52 docIds by volume (data-driven config) | ✅ Created |
| `src/config.py` | `load_volumes()` reads from JSON | ✅ Updated |
| `src/scraper.py` | `scrape_volume()` accepts `doc_ids` list | ✅ Updated |
| `scripts/run.py` | Passes `doc_ids` from config | ✅ Updated |
| `src/auth.py` | NUS SSO auth (unchanged) | ✅ |
| `src/pdf_builder.py` | pypdf merge (unchanged) | ✅ |
| `src/gcs_upload.py` | GCS upload (unchanged) | ✅ |
| `.env` | GCS_KEY_PATH configured | ✅ |

**16/16 tests passing. 52 docIds across 3 volumes.**

---

## Architecture: Data-Driven DocIds

Previously: `config.py` had empty `search_url` per volume → scraper would discover docIds via HTML scraping.

Now: `data/volumes.json` has all 52 docIds hardcoded → scraper reads them directly, skips discovery.

```
data/volumes.json → src/config.py:load_volumes() → VOLUMES dict
                                                      ↓
scripts/run.py → scrape_volume(doc_ids=vol["doc_ids"]) → download each
```

To add more volumes: edit `data/volumes.json`, no code changes needed.

---

## Volume Summary

| Volume | Docs | Ref |
|--------|------|-----|
| CO273_534 | 26 | CO 273/534/1 through /26 |
| CO273_550 | 20 | CO 273/550/1 through /21 (no #9) |
| CO273_579 | 6 | CO 273/579/1 through /6 |

---

## GCP Setup (Complete)

- Project: `aihistory-488807`
- Bucket: `aihistory-co273` in `asia-southeast1`
- Key: configured in `.env` as `GCS_KEY_PATH`

---

## Next Step

Run Task 10: `python -m scripts.run scrape --volume CO273_534` with real NUS auth.
