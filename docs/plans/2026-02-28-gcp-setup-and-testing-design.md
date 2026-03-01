# GCP Setup + Real Download Test — Design

**Status**: COMPLETE. GCP project `aihistory-488807`, bucket `aihistory-co273` configured.

**Date**: 2026-02-28

## Task 9: GCP Setup

1. Create GCP project `aihistory` at console.cloud.google.com
2. Create Cloud Storage bucket `aihistory-co273` in `asia-southeast1`
3. Create service account `aihistory-uploader` with Storage Object Creator + Viewer roles
4. Download JSON key, configure `.env`
5. Create viewer service account for downstream collaborators

## Task 10: Real Download Test

1. Fill `search_url` values in `src/config.py` from Gale volume facet filter URLs
2. Test: `python -m scripts.run scrape --volume CO273_534` (verify docId discovery + PDF download)
3. Full run: `python -m scripts.run scrape --resume` (all 3 volumes)
4. Build: `python -m scripts.run build`
5. Upload: `python -m scripts.run upload`
6. Verify bucket contents in Cloud Console
