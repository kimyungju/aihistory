# Phase 1 Design: Gale PDF Scraper + GCS Upload

**Date**: 2026-02-28
**Project**: aihistory — "New Kratoska Index" for CO 273 Colonial Records
**Phase**: 1 of 4 (Scraper + GCS Upload)

## Context

This project is part of a competition challenge to digitize and enhance the Kratoska Index for CO 273: Straits Settlements Original Correspondence. The full pipeline spans 4 phases:

1. **Phase 1 (this doc)**: Scrape page images from Gale Primary Sources → upload to GCS
2. **Phase 2**: OCR pipeline (Document AI / Gemini) on GCS images → rich text
3. **Phase 3**: "New Kratoska Index" — NER, topic modeling, summaries, embeddings
4. **Phase 4**: RAG chatbot with vector search + Gemini Q&A + citations

Phase 1 isolates NUS authentication to one team member. Everything downstream reads from GCS — no NUS auth needed for collaborators, judges, or demo.

## Target Data

| Volume | Pages | Source |
|--------|-------|--------|
| CO273/534 | 1,436 | Gale Primary Sources (SPOC) via NUS Library Proxy |
| CO273/550 | 460 | Gale Primary Sources (SPOC) via NUS Library Proxy |
| CO273/579 | 842 | Gale Primary Sources (SPOC) via NUS Library Proxy |

Theme: "Commodities and Capitalism"

## Architecture

```
NUS Team Member (one-time)         Downstream (no NUS auth)
─────────────────────────         ──────────────────────────
Selenium → NUS SSO login          GCS Bucket (public/SA access)
    ↓                                  ↓
Extract cookies                   Phase 2: OCR Pipeline
    ↓                                  ↓
requests + cookies                Phase 3: Index Generation
    ↓                                  ↓
Download PDF parts per volume     Phase 4: RAG Chatbot
    ↓
Extract pages as images
    ↓
Renumber continuously
    ↓
Upload to GCS
```

## Source Choice

Gale (high-res) over microfilm (grainy) — image quality directly impacts OCR accuracy (25% of competition score). Gale splits each volume into multiple PDF parts/chunks; our pipeline reassembles them into a unified per-volume page sequence.

## Approach

**Hybrid Selenium + Requests**:
- Selenium handles NUS SSO login (visible browser for 2FA/SAML)
- Session cookies transferred to `requests.Session`
- `requests` downloads PDF parts from Gale's internal API endpoints
- Each volume may consist of multiple Gale PDF parts — download all parts, extract pages as images, and renumber into a single continuous sequence per volume
- Faster and lighter than full browser automation for ~2,738 pages

## Project Structure

```
aihistory/
├── pyproject.toml
├── .env.example            # GCS key path, bucket name
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── auth.py             # Selenium NUS SSO → cookie extraction
│   ├── scraper.py          # Gale API discovery + page download
│   ├── pdf_builder.py      # Combine pages into per-volume PDFs
│   ├── gcs_upload.py       # Upload to Google Cloud Storage
│   └── config.py           # Volume definitions, paths, settings
├── pdfs/                   # Local download dir (gitignored)
│   └── {volume_id}/
│       ├── parts/          # Raw Gale PDF parts
│       ├── images/         # Extracted page images (renumbered)
│       └── manifest.json   # Download/extraction progress
└── scripts/
    └── run.py              # CLI: scrape | upload | all
```

## Component Details

### 1. auth.py — NUS SSO Authentication

- Launch visible Chrome via Selenium WebDriver
- Navigate to Gale proxy URL → triggers NUS SSO redirect
- Wait for user to complete login (supports 2FA, SAML)
- Detect successful login (check for Gale page element or URL)
- Extract all cookies from browser → `requests.Session`
- Close browser

### 2. scraper.py — Gale Page Download

**Discovery step** (manual, one-time): Inspect Gale's network traffic in Chrome DevTools to identify:
- Page image/PDF API endpoint pattern
- Required headers and parameters (document ID, page number)
- Any anti-scraping tokens
- How volumes are split into parts (e.g., CO273_534_part1.pdf, CO273_534_part2.pdf)

**Download logic**:
- Discover all PDF parts for each volume
- Download each part with 1-2 sec delay between requests
- Save raw parts as `pdfs/{volume_id}/parts/part_{NN}.pdf`
- Extract pages from each part as images using `pypdf` + `Pillow`
- Renumber pages continuously across parts → `pdfs/{volume_id}/pages/page_{NNNN}.jpg`
- Track progress in `pdfs/{volume_id}/manifest.json` (supports resume)
- Manifest records: parts downloaded, pages extracted, part-to-page mapping
- Retry failed downloads (max 3 attempts)

### 3. pdf_builder.py — Page Assembly

- Combine extracted page images into single per-volume PDF
- Preserve page order (already renumbered across parts)
- Use `pypdf` for PDF pages, `Pillow` for images → PDF

### 4. gcs_upload.py — Cloud Storage Upload

- Authenticate via service account JSON key
- Upload to bucket structure:
  ```
  gs://aihistory-co273/
  ├── CO273_534/
  │   ├── images/page_0001.jpg ...
  │   ├── ocr/                        ← populated by Phase 2
  │   ├── CO273_534_full.pdf
  │   └── metadata.json               ← volume, parts count, total pages, part-to-page mapping
  ├── CO273_550/
  │   ├── images/page_0001.jpg ...
  │   ├── ocr/
  │   ├── CO273_550_full.pdf
  │   └── metadata.json
  ├── CO273_579/
  │   ├── images/page_0001.jpg ...
  │   ├── ocr/
  │   ├── CO273_579_full.pdf
  │   └── metadata.json
  └── metadata/volumes.json
  ```
- Verify uploads by listing and comparing counts
- Bucket access: service-account-based for downstream (no NUS auth)

### 5. config.py — Configuration

```python
VOLUMES = {
    "CO273_534": {"gale_id": "TBD", "pages": 1436},
    "CO273_550": {"gale_id": "TBD", "pages": 460},
    "CO273_579": {"gale_id": "TBD", "pages": 842},
}
DOWNLOAD_DELAY = 1.5  # seconds between requests
MAX_RETRIES = 3
GCS_BUCKET = "aihistory-co273"
GCS_REGION = "asia-southeast1"
```

### 6. scripts/run.py — CLI Entry Point

```
python scripts/run.py scrape          # Auth + download pages
python scripts/run.py scrape --resume # Resume interrupted download
python scripts/run.py upload          # Upload to GCS
python scripts/run.py all             # Full pipeline
```

## Dependencies

```
selenium
requests
beautifulsoup4
pypdf
Pillow
google-cloud-storage
python-dotenv
```

## GCP Setup (Manual Steps)

1. Create GCP project
2. Enable Cloud Storage API
3. Create service account → grant "Storage Object Creator" + "Storage Object Viewer" roles
4. Download JSON key → save path in `.env`
5. Create bucket `aihistory-co273` in `asia-southeast1`
6. Configure bucket IAM for downstream service accounts

## Ethical Considerations

- 1-2 sec delay between requests (avoid overloading Gale)
- Used for academic research / competition only
- NUS library subscription grants legitimate access
- Downloaded data stored in private GCS bucket (not publicly redistributed)

## Risks

| Risk | Mitigation |
|------|------------|
| Gale API endpoint changes | Document endpoints; alert on download failures |
| NUS SSO session expires mid-download | Resume support via manifest tracking |
| Rate limiting / IP blocking | Conservative delays; resume support |
| Large download size (~2,738 pages) | Stream downloads; don't load all in memory |
