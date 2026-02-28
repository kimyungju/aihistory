# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Competition project ("New Kratoska Index") to digitize CO 273 Straits Settlements Original Correspondence from Gale Primary Sources via NUS Library Proxy. Theme: "Commodities and Capitalism."

Four-phase pipeline:
1. **Scraper + GCS Upload** — Selenium SSO → requests page download → GCS (current phase)
2. **OCR** — Document AI / Gemini on GCS images
3. **Index Generation** — NER, topic modeling, embeddings
4. **RAG Chatbot** — Vector search + Gemini Q&A + citations

Target data: CO273/534 (1,436 pages), CO273/550 (460 pages), CO273/579 (842 pages).

## Commands

```bash
# Setup (Python 3.14 on Windows)
python -m venv .venv
.venv\Scripts\Activate.ps1      # PowerShell (Cursor terminal)
source .venv/Scripts/activate   # Git Bash
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
    → download PDF parts per volume from Gale API (1.5s delay)
    → extract pages from parts as images, renumber continuously
    → save to pdfs/{volume_id}/images/page_NNNN.jpg
    → manifest.json per volume tracks parts + pages for resume
    → build per-volume PDF from images (Pillow + pypdf)
    → upload to gs://aihistory-co273/{volume_id}/
```

NUS authentication is isolated to `src/auth.py`. Everything downstream (OCR, index, chatbot) reads from GCS — no NUS auth needed.

## Key Design Decisions

- **Gale split-PDF reassembly**: Gale splits each volume into multiple PDF parts. The scraper downloads all parts, extracts pages as images, and renumbers them into a continuous sequence per volume. `metadata.json` tracks part-to-page mapping for traceability.
- **Hybrid Selenium + Requests**: Selenium only for NUS SSO login (supports 2FA/SAML). The actual downloads use `requests` with extracted cookies — much faster for ~2,738 pages.
- **Resume support**: `manifest.json` in each volume directory tracks downloaded parts and extracted pages. The `--resume` flag skips already-completed work.
- **Gale API endpoints**: Must be discovered manually via Chrome DevTools network inspection. Endpoint patterns go in `src/scraper.py` (`PAGE_URL_TEMPLATE`); volume Gale IDs go in `src/config.py` (`VOLUMES` dict). See `docs/gale-api-notes.md`.
- **GCS bucket** `aihistory-co273` in `asia-southeast1`. Auth via service account JSON key (path in `.env`).

## Configuration

Environment variables in `.env` (see `.env.example`):
- `GCS_BUCKET` — GCS bucket name
- `GCS_KEY_PATH` — path to GCP service account JSON key
- `GCS_REGION` — GCS region
- `GALE_BASE_URL` — Gale proxy URL through NUS library

Scraper tuning constants are in `src/config.py`: `DOWNLOAD_DELAY`, `MAX_RETRIES`, `REQUEST_TIMEOUT`.

## Session Start

At the start of every new session, read these before doing anything:
1. `dev/active/` — current task status, context, and checklists
2. `docs/plans/` — design docs and implementation plans

These files contain architecture decisions, task breakdowns, and progress tracking that persist across sessions.

## Project Status

Phase 1 scaffolding is complete (config, pyproject.toml, directory structure). Implementation modules (`auth.py`, `scraper.py`, `pdf_builder.py`, `gcs_upload.py`, `scripts/run.py`) are planned but not yet written. The implementation plan is at `docs/plans/2026-02-28-phase1-scraper-gcs.md`.

## Commit rules 

Never include coauthored by claude or anything equivalent. Keep the commit message short and concise.