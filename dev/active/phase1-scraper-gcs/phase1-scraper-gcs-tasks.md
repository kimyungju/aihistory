# Phase 1: Scraper + GCS — Task Checklist

**Last Updated: 2026-02-28 (session 4)**

---

## Tasks 1-9: ✅ Done

All code, tests, GCP setup, and docId config complete.

## Task 10: Real Download & Integration — IN PROGRESS

### 10a: Fix PDF download ⏳ FIXES APPLIED, NEEDS TESTING
- [x] Scraper runs end-to-end (auth → CSRF → download loop → manifest)
- [x] 26/26 docs downloaded for CO273_534 (disclaimers only)
- [x] User captured real endpoints via Chrome DevTools
- [x] Form data cleaned to match captured data (e2c8e02, dab05ff)
- [x] Auth now polls for JSESSIONID11_omni cookie (67dfbf3)
- [x] Disclaimer size rejection added (<5KB = rejected) (fc7629c)
- [x] Doc page visit before download added (fc7629c)
- [x] Referer headers added to requests (fc7629c)
- [x] Image download fallback added (c59d6c4)
- [x] Test subcommand added: `python -m scripts.run test --doc-id "GALE|..."` (7fe5b58)
- [ ] **TEST with NUS SSO** — verify real PDFs download (not disclaimers)
- [ ] If disclaimers persist, investigate image endpoint as alternative
- [ ] Delete old pdfs/CO273_534/ disclaimer files, re-download

### 10b: Download remaining volumes
- [ ] CO273_534 (26 docs) — re-download with fix
- [ ] CO273_550 (20 docs)
- [ ] CO273_579 (6 docs)

### 10c: Build + Upload
- [ ] `python -m scripts.run build` — merge PDFs
- [ ] `python -m scripts.run upload` — upload to GCS
- [ ] Verify in Cloud Console

---

## Bugs Fixed (Sessions 3-4)

1. **UnicodeEncodeError** (cp949): Em dash in auth.py → ASCII dash
2. **HTTP 500 on PDF download**: Missing form fields → added, then cleaned to match DevTools capture
3. **`.gitignore` blocking volumes.json**: Added `!data/volumes.json` exception
4. **Disclaimer-only PDFs**: Added size rejection, doc page visit, Referer headers, JSESSIONID11_omni wait
5. **Extra form fields**: Removed `title`, `asid`, `accessLevel`, `productCode` (PDF) and `text`, `fileName` (text)

---

## Summary

| Item | Status |
|------|--------|
| Code + Tests (28/28) | ✅ |
| GCP Setup | ✅ |
| DocId Config (52 docs) | ✅ |
| Download Fixes | ✅ Applied, needs SSO test |
| Image Download Fallback | ✅ Implemented |
| PDF Download | ⏳ Needs real test with NUS SSO |
| Build + Upload | ⏳ Blocked by download test |
