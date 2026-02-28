# Phase 1: Scraper + GCS — Task Checklist

**Last Updated: 2026-02-28 (session 3)**

---

## Tasks 1-9: ✅ Done

All code, tests, GCP setup, and docId config complete.

## Task 10: Real Download & Integration — IN PROGRESS

### 10a: Fix PDF download endpoint ❌ BLOCKED
- [x] Scraper runs end-to-end (auth → CSRF → download loop → manifest)
- [x] 26/26 docs downloaded for CO273_534
- [ ] **PDFs contain only disclaimers (2,479 bytes each), not real scanned documents**
- [ ] Need to find correct Gale download endpoint (possibly `/ps/callisto/BulkPDF/UBER2`)
- [ ] User must capture real download request via Chrome DevTools Network tab
- [ ] Update `src/scraper.py` with correct endpoint and form data
- [ ] Re-download CO273_534 with real PDFs

### 10b: Download remaining volumes
- [ ] CO273_550 (20 docs)
- [ ] CO273_579 (6 docs)

### 10c: Build + Upload
- [ ] `python -m scripts.run build` — merge PDFs
- [ ] `python -m scripts.run upload` — upload to GCS
- [ ] Verify in Cloud Console

---

## Bugs Fixed This Session

1. **UnicodeEncodeError** (cp949): Em dash `—` in auth.py print → replaced with `-`
2. **HTTP 500 on PDF download**: Missing form fields → added `disclaimerDisabled`, `deliveryType`, etc.
3. **`.gitignore` blocking volumes.json**: `*.json` rule → added `!data/volumes.json` exception

---

## Summary

| Item | Status |
|------|--------|
| Code + Tests (16/16) | ✅ |
| GCP Setup | ✅ |
| DocId Config (52 docs) | ✅ |
| PDF Download | ❌ Returns disclaimers, not real docs |
| Text Download | ❌ Returns empty content |
| Build + Upload | ⏳ Blocked by download fix |
