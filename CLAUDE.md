# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Competition project ("New Kratoska Index") to digitize CO 273 Straits Settlements Original Correspondence from Gale Primary Sources via NUS Library Proxy. Theme: "Commodities and Capitalism."

Four-phase pipeline:
1. **Scraper + GCS Upload** — Selenium SSO → requests page download → GCS (current phase)
2. **OCR** — Document AI / Gemini on GCS images
3. **Index Generation** — NER, topic modeling, embeddings
4. **RAG Chatbot** — Vector search + Gemini Q&A + citations

Target data: CO273/534 (1,436 pages), CO273/550 (460 pages).

## Commands

```bash
# Setup
python -m venv .venv
source .venv/Scripts/activate   # Windows (Git Bash)
pip install -e ".[dev]"

# Tests
python -m pytest tests/ -v              # all tests
python -m pytest tests/test_auth.py -v  # single test file
python -m pytest tests/ -k "test_name"  # single test by name

# CLI pipeline
python -m scripts.run scrape [--resume]  # NUS SSO auth + download pages
python -m scripts.run build              # combine page images into PDFs
python -m scripts.run upload             # upload to GCS bucket
python -m scripts.run all [--resume]     # full pipeline
```

## Architecture

```
NUS SSO (Selenium, visible browser)
    → extract cookies → requests.Session
    → download page images from Gale API (1.5s delay between requests)
    → save to pdfs/{volume_id}/pages/page_NNNN.{ext}
    → manifest.json per volume tracks progress for resume
    → build per-volume PDF from images (Pillow + pypdf)
    → upload to gs://aihistory-co273/{volume_id}/
```

NUS authentication is isolated to `src/auth.py`. Everything downstream (OCR, index, chatbot) reads from GCS — no NUS auth needed.

## Key Design Decisions

- **Hybrid Selenium + Requests**: Selenium only for NUS SSO login (supports 2FA/SAML). The actual page downloads use `requests` with extracted cookies — much faster for ~1,900 pages.
- **Resume support**: `manifest.json` in each volume directory tracks downloaded/failed pages. The `--resume` flag skips already-downloaded pages.
- **Gale API endpoints**: Must be discovered manually via Chrome DevTools network inspection. Endpoint patterns go in `src/scraper.py` (`PAGE_URL_TEMPLATE`); volume Gale IDs go in `src/config.py` (`VOLUMES` dict). See `docs/gale-api-notes.md`.
- **GCS bucket** `aihistory-co273` in `asia-southeast1`. Auth via service account JSON key (path in `.env`).

## Configuration

Environment variables in `.env` (see `.env.example`):
- `GCS_BUCKET` — GCS bucket name
- `GCS_KEY_PATH` — path to GCP service account JSON key
- `GCS_REGION` — GCS region
- `GALE_BASE_URL` — Gale proxy URL through NUS library

Scraper tuning constants are in `src/config.py`: `DOWNLOAD_DELAY`, `MAX_RETRIES`, `REQUEST_TIMEOUT`.

## Plans

Design docs and implementation plans live in `docs/plans/`. Read these before starting work on any phase — they contain architecture decisions, task breakdowns, and verification checklists.

## Project Status

Phase 1 scaffolding is complete (config, pyproject.toml, directory structure). Implementation modules (`auth.py`, `scraper.py`, `pdf_builder.py`, `gcs_upload.py`, `scripts/run.py`) are planned but not yet written. The implementation plan is at `docs/plans/2026-02-28-phase1-scraper-gcs.md`.

## Commit rules 

Never include coauthored by claude or anything equivalent. Keep the commit message short and concise.