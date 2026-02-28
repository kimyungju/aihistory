# Phase 1: Scraper + GCS — Task Checklist

**Last Updated: 2026-02-28**

---

## Phase A: Foundation (Sequential — Team Lead)

### Task 1: Project Scaffolding [S]
- [ ] `git init`
- [ ] Create `pyproject.toml` with all dependencies
- [ ] Create `.gitignore` (pdfs/, .env, __pycache__, *.json creds)
- [ ] Create `.env.example`
- [ ] Create `src/__init__.py`
- [ ] Create `src/config.py` with VOLUMES, paths, settings
- [ ] Create directories: `src/`, `pdfs/`, `scripts/`, `tests/`
- [ ] `pip install -e ".[dev]"` succeeds
- [ ] Commit: `chore: scaffold project with config, dependencies, and gitignore`

---

## Phase B: Core Modules (Parallel Agents)

### Agent 1: auth-scraper

#### Task 2: Authentication Module [M]
- [ ] Write `tests/test_auth.py` (2 tests: cookie extraction, session creation)
- [ ] Run tests — verify FAIL
- [ ] Write `src/auth.py` (extract_cookies_from_driver, create_session_with_cookies, authenticate_gale)
- [ ] Run tests — verify 2 PASS
- [ ] Commit: `feat: add NUS SSO authentication module with cookie extraction`

#### Task 4: Scraper Module [L]
- [ ] Write `tests/test_scraper.py` (5 tests: URL build, manifest load/save, download success/fail)
- [ ] Run tests — verify FAIL
- [ ] Write `src/scraper.py` (build_page_url, load_manifest, save_manifest, download_page, scrape_volume)
- [ ] Run tests — verify 5 PASS
- [ ] Commit: `feat: add scraper module with page download and resume support`

### Agent 2: pdf-gcs

#### Task 5: PDF Builder Module [S]
- [ ] Write `tests/test_pdf_builder.py` (1 test: combine images → PDF, verify page count)
- [ ] Run tests — verify FAIL
- [ ] Write `src/pdf_builder.py` (build_pdf_from_images)
- [ ] Run tests — verify 1 PASS
- [ ] Commit: `feat: add PDF builder to combine page images into per-volume PDFs`

#### Task 6: GCS Upload Module [M]
- [ ] Write `tests/test_gcs_upload.py` (2 tests: single file upload, volume upload)
- [ ] Run tests — verify FAIL
- [ ] Write `src/gcs_upload.py` (get_gcs_client, get_bucket, upload_file, upload_volume, upload_all_volumes, list_bucket_contents)
- [ ] Run tests — verify 2 PASS
- [ ] Commit: `feat: add GCS upload module for volume files`

---

## Manual Tasks (User — can run in parallel with Phase B)

### Task 3: Gale API Endpoint Discovery [M] [MANUAL]
- [ ] Log into Gale via NUS proxy in Chrome
- [ ] Open CO 273 document in viewer
- [ ] Open DevTools → Network tab
- [ ] Navigate pages, identify page image API endpoint pattern
- [ ] Record: URL pattern, method, headers, parameters, response type
- [ ] Find Gale document IDs for CO273/534 and CO273/550
- [ ] Create `docs/gale-api-notes.md` with findings
- [ ] Update `src/config.py` VOLUMES with real gale_id values
- [ ] Update `src/scraper.py` PAGE_URL_TEMPLATE with real endpoint
- [ ] Commit: `docs: add Gale API endpoint discovery notes and volume IDs`

### Task 9: GCP Project & Bucket Setup [M] [MANUAL]
- [ ] Create GCP project named `aihistory`
- [ ] Enable Cloud Storage API
- [ ] Create service account `aihistory-uploader` with Storage Object Creator + Viewer roles
- [ ] Download JSON key file (keep out of git)
- [ ] Create bucket `aihistory-co273` in `asia-southeast1`
- [ ] Copy `.env.example` → `.env`, fill in `GCS_BUCKET` and `GCS_KEY_PATH`
- [ ] Create viewer service account for downstream collaborators
- [ ] Test bucket access with `gsutil ls gs://aihistory-co273/`

---

## Phase C: Integration (Sequential — Team Lead)

### Task 7: CLI Entry Point [S]
- [ ] Create `scripts/__init__.py`
- [ ] Create `scripts/run.py` with scrape/build/upload/all commands
- [ ] `python -m scripts.run --help` displays all commands
- [ ] Commit: `feat: add CLI entry point with scrape/build/upload/all commands`

### Task 8: End-to-End Smoke Test [S]
- [ ] Clean venv install: `pip install -e ".[dev]"`
- [ ] `pytest tests/ -v` — all 8+ tests pass
- [ ] `python -m scripts.run --help` — works
- [ ] `python -m scripts.run scrape --help` — works
- [ ] Commit: `chore: verify all tests pass and CLI works`

### Task 10: Real Download & Full Integration [XL]
- [ ] Verify Task 3 complete (API endpoints known)
- [ ] Verify Task 9 complete (GCS bucket ready)
- [ ] Test with 5 pages: `python -m scripts.run scrape`
- [ ] Verify 5 images in `pdfs/CO273_534/pages/`
- [ ] Run full download: `python -m scripts.run scrape --resume`
- [ ] Verify CO273_534: 1,436 pages downloaded
- [ ] Verify CO273_550: 460 pages downloaded
- [ ] Build PDFs: `python -m scripts.run build`
- [ ] Verify 2 assembled PDFs created
- [ ] Upload: `python -m scripts.run upload`
- [ ] Verify in GCS Console: all files present
- [ ] Test: non-NUS collaborator can access bucket with viewer SA
- [ ] Commit: `feat: configure real Gale API endpoints and verify download`

---

## Summary

| Phase | Tasks | Agent | Status |
|-------|-------|-------|--------|
| A | 1 (Scaffold) | Team Lead | Pending |
| B | 2, 4 (Auth + Scraper) | Agent 1 | Pending |
| B | 5, 6 (PDF + GCS) | Agent 2 | Pending |
| Manual | 3 (API Discovery) | User | Pending |
| Manual | 9 (GCP Setup) | User | Pending |
| C | 7, 8, 10 (Integration) | Team Lead | Pending |

**Total: 10 tasks, 3 agents, 2 manual user tasks**
