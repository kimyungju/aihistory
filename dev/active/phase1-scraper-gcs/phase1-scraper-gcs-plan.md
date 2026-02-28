# Phase 1: Gale PDF Scraper + GCS Upload — Strategic Plan

**Last Updated: 2026-02-28**

---

## Executive Summary

Build a Python tool to download ~1,896 scanned colonial record pages from Gale Primary Sources (CO 273: Straits Settlements Original Correspondence) and upload them to Google Cloud Storage. This is Phase 1 of a 4-phase competition project to create a "New Kratoska Index" — an AI-powered searchable index that surpasses the original Kratoska Index for CO 273 records.

Phase 1 isolates NUS library authentication to one team member. Everything downstream (OCR, NER, chatbot) reads from GCS — no NUS credentials needed for collaborators, judges, or demo.

---

## Current State Analysis

- **Project directory**: Empty (no code, no git, no dependencies)
- **Data source**: Gale Primary Sources via NUS Library Proxy (`go-gale-com.libproxy1.nus.edu.sg`)
- **Access method**: NUS SSO login → page-by-page viewer with download option
- **Target volumes**: CO273/534 (1,436 pages), CO273/550 (460 pages)
- **GCP**: Not yet set up (no project, no bucket, no service account)
- **Challenge theme**: "Commodities and Capitalism"

---

## Proposed Future State

A working CLI tool (`python -m scripts.run all`) that:
1. Opens a browser for NUS SSO login
2. Captures session cookies
3. Downloads all page images via Gale's internal API
4. Assembles pages into per-volume PDFs
5. Uploads everything to a GCS bucket accessible by the full team

```
gs://aihistory-co273/
├── CO273_534/
│   ├── pages/page_0001.jpg ... page_1436.jpg
│   ├── CO273_534_full.pdf
│   └── manifest.json
├── CO273_550/
│   ├── pages/page_0001.jpg ... page_0460.jpg
│   ├── CO273_550_full.pdf
│   └── manifest.json
└── metadata/volumes.json
```

---

## Implementation Phases & Agent Team Strategy

### Overview: 3 Phases, 3 Agent Teams

```
Phase A (sequential)     Phase B (parallel agents)        Phase C (sequential)
────────────────────     ───────────────────────          ────────────────────
Team Lead:               Team: core-modules               Team Lead:
  Task 1: Scaffold         Agent 1: auth + scraper          Task 7: CLI
  (git, deps, config)      Agent 2: pdf_builder + gcs       Task 8: Smoke test
                                                             Task 10: Integration
```

Tasks 3 (API discovery) and 9 (GCP setup) are **manual** — user does these.

---

### Phase A: Foundation (Sequential — Team Lead)

**Must complete before Phase B can start.**

#### Task 1: Project Scaffolding [Effort: S]

| Item | Detail |
|------|--------|
| **Creates** | `pyproject.toml`, `.gitignore`, `.env.example`, `src/__init__.py`, `src/config.py` |
| **Actions** | `git init`, create all files, `pip install -e ".[dev]"` |
| **Acceptance** | Git repo initialized, `pip install` succeeds, `python -c "from src.config import VOLUMES"` works |
| **Dependencies** | None |

#### Task 3: Gale API Endpoint Discovery [Effort: M] [MANUAL — USER]

| Item | Detail |
|------|--------|
| **Creates** | `docs/gale-api-notes.md`, updates `src/config.py` |
| **Actions** | Chrome DevTools inspection of Gale viewer network traffic |
| **Acceptance** | Document ID format known, page image URL pattern documented, config updated |
| **Dependencies** | Task 1 (for config file to update) |
| **Note** | This is a MANUAL task. The user must log in, inspect network traffic, and record API patterns. Can run in parallel with Phase B coding. |

#### Task 9: GCP Project & Bucket Setup [Effort: M] [MANUAL — USER]

| Item | Detail |
|------|--------|
| **Actions** | Create GCP project, enable Storage API, create service account + key, create bucket |
| **Acceptance** | `.env` configured with valid `GCS_BUCKET` and `GCS_KEY_PATH` |
| **Dependencies** | None (can run any time before Task 8) |
| **Note** | MANUAL task in Google Cloud Console. |

---

### Phase B: Core Modules (Parallel Agents)

**Two agents work simultaneously after Task 1 completes.**

#### Agent 1: Auth + Scraper

##### Task 2: Authentication Module [Effort: M]

| Item | Detail |
|------|--------|
| **Creates** | `src/auth.py`, `tests/test_auth.py` |
| **Functions** | `extract_cookies_from_driver()`, `create_session_with_cookies()`, `authenticate_gale()` |
| **Tests** | Cookie extraction from mock driver, session creation with cookies |
| **Acceptance** | `pytest tests/test_auth.py -v` passes (2 tests) |
| **Dependencies** | Task 1 |

##### Task 4: Scraper Module [Effort: L]

| Item | Detail |
|------|--------|
| **Creates** | `src/scraper.py`, `tests/test_scraper.py` |
| **Functions** | `build_page_url()`, `load_manifest()`, `save_manifest()`, `download_page()`, `scrape_volume()` |
| **Tests** | URL building, manifest round-trip, mock download success/failure |
| **Acceptance** | `pytest tests/test_scraper.py -v` passes (5 tests) |
| **Dependencies** | Task 1 |

#### Agent 2: PDF Builder + GCS Upload

##### Task 5: PDF Builder Module [Effort: S]

| Item | Detail |
|------|--------|
| **Creates** | `src/pdf_builder.py`, `tests/test_pdf_builder.py` |
| **Functions** | `build_pdf_from_images()` |
| **Tests** | Combine 3 test images into PDF, verify page count |
| **Acceptance** | `pytest tests/test_pdf_builder.py -v` passes (1 test) |
| **Dependencies** | Task 1 |

##### Task 6: GCS Upload Module [Effort: M]

| Item | Detail |
|------|--------|
| **Creates** | `src/gcs_upload.py`, `tests/test_gcs_upload.py` |
| **Functions** | `get_gcs_client()`, `get_bucket()`, `upload_file()`, `upload_volume()`, `upload_all_volumes()`, `list_bucket_contents()` |
| **Tests** | Mock single file upload, mock volume upload with correct paths |
| **Acceptance** | `pytest tests/test_gcs_upload.py -v` passes (2 tests) |
| **Dependencies** | Task 1 |

---

### Phase C: Integration (Sequential — Team Lead)

**After Phase B agents complete and Phase A manual tasks done.**

#### Task 7: CLI Entry Point [Effort: S]

| Item | Detail |
|------|--------|
| **Creates** | `scripts/__init__.py`, `scripts/run.py` |
| **Commands** | `scrape [--resume]`, `build`, `upload`, `all [--resume]` |
| **Acceptance** | `python -m scripts.run --help` displays all commands |
| **Dependencies** | Tasks 2, 4, 5, 6 |

#### Task 8: Install & End-to-End Smoke Test [Effort: S]

| Item | Detail |
|------|--------|
| **Actions** | Clean install in venv, run all tests, verify CLI |
| **Acceptance** | `pytest tests/ -v` passes all 8+ tests, CLI help works |
| **Dependencies** | Tasks 1–7 |

#### Task 10: Real Download Test & Full Run [Effort: XL]

| Item | Detail |
|------|--------|
| **Actions** | Update config with real Gale IDs (from Task 3), test 5-page download, run full download (~1,896 pages), build PDFs, upload to GCS (requires Task 9) |
| **Acceptance** | GCS bucket contains all page images + assembled PDFs for both volumes |
| **Dependencies** | Tasks 3, 8, 9 |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Gale API endpoint not discoverable | Medium | High | Fall back to full Selenium automation (Approach A) |
| NUS SSO session expires mid-download | High | Low | Resume support via manifest.json tracking |
| Gale rate-limits or blocks requests | Medium | Medium | 1.5s delay between requests; resume on block |
| GCS bucket permissions misconfigured | Low | Medium | Test with viewer SA before sharing with team |
| ChromeDriver version mismatch | Medium | Low | Use `webdriver-manager` auto-install if needed |

---

## Success Metrics

1. All ~1,896 page images downloaded and verified (no corruption)
2. Two assembled PDFs (CO273_534, CO273_550) viewable
3. GCS bucket accessible by non-NUS team members
4. All unit tests pass (8+ tests)
5. CLI provides clear scrape/build/upload workflow
6. Resume support works (interrupt and restart without re-downloading)

---

## Required Resources

| Resource | Status | Notes |
|----------|--------|-------|
| Python 3.11+ | Check | `python --version` |
| Chrome browser | Check | For Selenium + manual API inspection |
| ChromeDriver | Install | Match Chrome version |
| NUS account | Have | For SSO login to Gale |
| GCP account | Need | Free tier sufficient for storage |
| GCP billing | Need | Cloud Storage has minimal cost |

---

## Timeline (Agent-Parallel Execution)

| Step | What | Who | Depends On |
|------|------|-----|-----------|
| 1 | Task 1: Scaffold | Team Lead | — |
| 2a | Task 2+4: Auth + Scraper | Agent 1 | Step 1 |
| 2b | Task 5+6: PDF + GCS | Agent 2 | Step 1 |
| 2c | Task 3: API Discovery | User (manual) | Step 1 |
| 2d | Task 9: GCP Setup | User (manual) | — |
| 3 | Task 7: CLI | Team Lead | Steps 2a, 2b |
| 4 | Task 8: Smoke Test | Team Lead | Step 3 |
| 5 | Task 10: Real Download | Team Lead + User | Steps 2c, 2d, 4 |
