# Phase 1: Scraper + GCS — Key Context

**Last Updated: 2026-02-28**

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `docs/plans/2026-02-28-phase1-scraper-gcs-design.md` | Design document (approved) | Created |
| `docs/plans/2026-02-28-phase1-scraper-gcs.md` | Full implementation plan with code | Created |
| `pyproject.toml` | Project deps & metadata | To create |
| `src/config.py` | Volume definitions, GCS/Gale settings | To create |
| `src/auth.py` | NUS SSO auth → cookie extraction | To create |
| `src/scraper.py` | Gale page image download | To create |
| `src/pdf_builder.py` | Combine images → PDF | To create |
| `src/gcs_upload.py` | Upload to GCS | To create |
| `scripts/run.py` | CLI entry point | To create |
| `.env` | Secrets (GCS key, bucket) | To create (gitignored) |
| `docs/gale-api-notes.md` | API endpoint discovery notes | To create (manual) |

---

## Critical Decisions

### 1. Hybrid Selenium + Requests (chosen over full Selenium or manual download)
- **Why**: Selenium just for SSO auth, requests for fast downloads
- **Trade-off**: Requires manual API endpoint discovery, but ~10x faster for 1,896 pages
- **Fallback**: If API can't be reverse-engineered, fall back to full Selenium automation

### 2. NUS Auth Isolation
- **Design**: Only one NUS team member runs the scraper
- **Everything downstream reads from GCS** — no NUS auth needed
- **Enables**: collaborators, judges, demo without NUS credentials

### 3. Resume Support via Manifest
- **Why**: Downloading 1,896 pages takes time; session may expire
- **How**: `manifest.json` tracks downloaded/failed pages per volume
- **CLI**: `--resume` flag skips already-downloaded pages

### 4. GCS Bucket Structure
```
gs://aihistory-co273/
├── CO273_534/pages/     ← individual page images (for OCR pipeline)
├── CO273_534/full.pdf   ← assembled PDF (for human viewing)
├── CO273_550/pages/
├── CO273_550/full.pdf
└── metadata/volumes.json
```
Both page images AND assembled PDFs stored — pages for downstream OCR, PDFs for human reference.

---

## Dependencies Between Components

```
config.py ← auth.py ← scraper.py ← run.py (scrape command)
config.py ← pdf_builder.py       ← run.py (build command)
config.py ← gcs_upload.py        ← run.py (upload command)
```

- `auth.py` and `scraper.py` share session management
- `pdf_builder.py` and `gcs_upload.py` are independent of each other
- All modules import from `config.py`
- `run.py` orchestrates all modules

---

## External Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| selenium | >=4.15.0 | Browser automation for NUS SSO |
| requests | >=2.31.0 | HTTP downloads from Gale API |
| beautifulsoup4 | >=4.12.0 | HTML parsing (if needed) |
| lxml | >=5.0.0 | Fast HTML parser backend |
| pypdf | >=3.17.0 | PDF reading/validation |
| Pillow | >=10.0.0 | Image → PDF conversion |
| google-cloud-storage | >=2.14.0 | GCS upload/list |
| python-dotenv | >=1.0.0 | .env file loading |
| pytest | >=7.4.0 | Testing (dev) |

---

## Agent Team Assignments

### Team Lead (this session)
- Task 1: Project scaffolding
- Task 7: CLI entry point
- Task 8: Smoke test
- Task 10: Integration test
- Code review of agent outputs

### Agent 1: "auth-scraper"
- Task 2: `src/auth.py` + `tests/test_auth.py`
- Task 4: `src/scraper.py` + `tests/test_scraper.py`
- Must follow TDD (test first, then implement)
- Complete code provided in implementation plan

### Agent 2: "pdf-gcs"
- Task 5: `src/pdf_builder.py` + `tests/test_pdf_builder.py`
- Task 6: `src/gcs_upload.py` + `tests/test_gcs_upload.py`
- Must follow TDD
- Complete code provided in implementation plan

### User (Manual Tasks)
- Task 3: Gale API endpoint discovery (Chrome DevTools)
- Task 9: GCP project + bucket setup (Cloud Console)

---

## Gale Source Details

- **URL**: `https://go-gale-com.libproxy1.nus.edu.sg/ps/searchWithin.do?...`
- **Collection**: CO 273: Straits Settlements Original Correspondence
- **Product**: SPOC (State Papers Online Colonial)
- **User group**: nuslib
- **Auth**: NUS SSO (SAML/2FA)
- **Viewer**: Page-by-page with download option
- **Total records in collection**: ~42,229 (we want 2 specific volumes)

---

## Competition Context

**Challenge Objective 2**: "Digitize the scanned Kratoska Index and algorithmically link its keywords back to the specific CO 273 files as well as add more keywords and descriptions to make files more understandable."

**Strategy**: Build a "New Kratoska Index" that auto-generates keywords (NER), summaries (Gemini), and semantic links (embeddings) — making the old index obsolete while remaining backward-compatible.

**Phase 1 role**: Get the raw data into GCS so the rest of the pipeline can work without NUS auth.
