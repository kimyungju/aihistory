# Phase 1: Scraper + GCS — Key Context

**Last Updated: 2026-02-28 (session 3 — GCP setup walkthrough)**

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `docs/plans/2026-02-28-phase1-scraper-gcs-design.md` | Design document (approved) | ✅ Created |
| `docs/plans/2026-02-28-phase1-scraper-gcs.md` | Original impl plan (partially outdated after rewrite) | ✅ Created |
| `docs/plans/2026-02-28-gcp-setup-and-testing-design.md` | GCP + testing design | ✅ Created (uncommitted) |
| `pyproject.toml` | Project deps & metadata | ✅ Created |
| `src/config.py` | Volume definitions, GCS/Gale settings (52 lines) | ✅ Created — **search_url values still empty** |
| `src/auth.py` | NUS SSO auth → cookie extraction (78 lines) | ✅ Created |
| `src/scraper.py` | **REWRITTEN** — document-level PDF/text download | ✅ Rewritten |
| `src/pdf_builder.py` | **REWRITTEN** — pypdf merge (was Pillow image→PDF) | ✅ Rewritten |
| `src/gcs_upload.py` | Upload to GCS (77 lines) | ✅ Created |
| `scripts/run.py` | CLI: scrape/build/upload/all with --resume/--no-text/--volume | ✅ Updated |
| `tests/test_auth.py` | 2 auth tests | ✅ Created |
| `tests/test_scraper.py` | **REWRITTEN** — 10 tests with HTML fixtures | ✅ Rewritten |
| `tests/test_pdf_builder.py` | **REWRITTEN** — 2 tests for PDF merge | ✅ Rewritten |
| `tests/test_gcs_upload.py` | 2 GCS upload tests | ✅ Created |
| `.env` | Secrets (GCS key, bucket) | **Not yet created** |
| `credentials/gcs-key.json` | GCS service account key | **Not yet created** |

**Total: 16/16 tests passing**

---

## Critical Decisions

### 1. Document-Level Download (not page-by-page)
- **Discovery**: Gale has POST endpoints for entire document PDFs and OCR text
- **Impact**: ~50x faster (1 request per multi-page document vs 1 per page)
- **Rewrite**: scraper.py completely rewritten, pdf_builder.py changed from image→PDF to PDF merge

### 2. Hybrid Selenium + Requests
- **Why**: Selenium just for SSO auth, requests.Session for fast downloads
- **Auth flow**: Chrome visible browser → NUS SSO login → extract cookies → requests.Session

### 3. NUS Auth Isolation
- **Design**: Only one NUS team member runs the scraper
- **Everything downstream reads from GCS** — no NUS auth needed

### 4. Resume Support via Manifest (document-level)
- **Schema**: manifest.json tracks doc_ids, downloaded_pdfs/texts, failed_pdfs/texts per volume
- **CLI**: `--resume` flag skips already-downloaded documents

### 5. GCS Bucket Structure (updated for document-level)
```
gs://aihistory-co273/
├── CO273_534/documents/    ← individual document PDFs
├── CO273_534/text/         ← OCR text per document
├── CO273_534/CO273_534_full.pdf  ← merged volume PDF
├── CO273_550/...
├── CO273_579/...
└── metadata/volumes.json
```

---

## Gale API Endpoints (Discovered in Session 2)

### PDF Download
- **URL**: POST `https://go-gale-com.libproxy1.nus.edu.sg/ps/pdfGenerator/html`
- **Form data**: `prodId=SPOC`, `userGroupName=nuslib`, `downloadAction=DO_DOWNLOAD_DOCUMENT`, `retrieveFormat=PDF`, `docId=GALE|...`, `_csrf=TOKEN`

### OCR Text Download
- **URL**: POST `https://go-gale-com.libproxy1.nus.edu.sg/ps/htmlGenerator/forText`
- **Form data**: `retrieveFormat=PLAIN_TEXT`, `productCode=SPOC-3`, `docId=GALE|...`, `accessLevel=FULLTEXT`

### CSRF Token
- Found in hidden form field `<input name='_csrf' value='...'>`
- Also in `XSRF-TOKEN` cookie (same value)
- Extracted by `scraper.py:extract_csrf_token()`

### Document Discovery
- Paginate search results, extract GALE|... docIds from links via BeautifulSoup
- `scraper.py:discover_doc_ids()` handles pagination

---

## Scraper Functions (post-rewrite)

| Function | Purpose |
|----------|---------|
| `sanitize_doc_id(doc_id)` | "GALE\|..." → "GALE_..." for filenames |
| `extract_csrf_token(session, url)` | Parse hidden input, fallback to cookie |
| `discover_doc_ids(session, search_url)` | Paginate search, extract all docIds |
| `download_document_pdf(session, doc_id, csrf_token, output_dir)` | POST for PDF |
| `download_document_text(session, doc_id, csrf_token, output_dir)` | POST for text |
| `load_manifest(path)` / `save_manifest(path, data)` | JSON manifest I/O |
| `scrape_volume(session, volume_id, search_url, output_dir, resume, download_text)` | Orchestrator |

---

## Dependencies Between Components

```
config.py ← auth.py ← scraper.py ← run.py (scrape command)
config.py ← pdf_builder.py       ← run.py (build command)
config.py ← gcs_upload.py        ← run.py (upload command)
```

---

## Current Blockers

1. **search_url values empty** in `src/config.py` lines 31, 34, 37 — user needs to find volume-specific URLs from Gale sidebar facet filters
2. **GCP project not created** — user walking through GCP Console setup
3. **`.env` file not created** — depends on GCP service account key

---

## Environment

- Python: `/c/Users/yjkim/AppData/Local/Microsoft/WindowsApps/python3.exe` (3.14.3)
- Venv: `source .venv/Scripts/activate`
- No gcloud CLI — GCP setup via Cloud Console web UI
- Git: 12 commits on main branch

---

## Next Steps (for new session)

1. User completes GCP Console setup (project, bucket, service account, key download)
2. Create `.env` with `GCS_KEY_PATH=credentials/gcs-key.json`
3. User finds volume-specific search URLs from Gale sidebar facets → fill into config.py
4. Real download test: `python -m scripts.run scrape --volume CO273_534`
5. Full pipeline: scrape all → build → upload
6. Verify bucket contents
