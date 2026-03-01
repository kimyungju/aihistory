# Concurrent Downloads Implementation Plan

**Status**: COMPLETE (5/5 tasks, 2026-03-01). Committed as `9ec2532`..`ca155a1`.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Speed up page image downloads from ~60 minutes to ~10 minutes using concurrent requests.

**Architecture:** Extract single-page download into a helper, wrap it with `ThreadPoolExecutor(max_workers=5)` in `download_document_pages()`. `requests.Session` is thread-safe. Reduce inter-request delays since concurrency provides natural throttling. Keep resume/skip-existing logic intact.

**Tech Stack:** `concurrent.futures.ThreadPoolExecutor` (stdlib), existing `requests.Session`

---

### Task 1: Add MAX_WORKERS config constant

**Files:**
- Modify: `src/config.py:54-55`

**Step 1: Add constant**

Add `MAX_WORKERS` after the existing scraper settings block:

```python
# Scraper settings
DOWNLOAD_DELAY = 0.5   # seconds between documents (was 1.5)
MAX_WORKERS = 5         # concurrent page image downloads per document
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30  # seconds
PDF_DOWNLOAD_TIMEOUT = 120  # seconds; multi-page PDFs take longer
SEARCH_RESULTS_PER_PAGE = 25  # Gale's default pagination size
```

Note: `DOWNLOAD_DELAY` reduced from 1.5 to 0.5. This is the delay between *documents*, not pages. Pages are now throttled by concurrency (5 workers) instead of sleep.

**Step 2: Commit**

```bash
git add src/config.py
git commit -m "add MAX_WORKERS config, reduce DOWNLOAD_DELAY to 0.5s"
```

---

### Task 2: Extract single-page download helper

**Files:**
- Modify: `src/scraper.py:154-202`
- Test: `tests/test_scraper.py`

**Step 1: Write the failing test**

Add to `tests/test_scraper.py`:

```python
from src.scraper import _download_single_page

def test_download_single_page_success(tmp_path):
    """Downloads one page image and returns True."""
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.content = b"\xff\xd8\xff" + b"x" * 5000
    response.ok = True
    session.get.return_value = response

    page_info = {"pageNumber": "1", "recordId": "ENCODED_TOKEN_PAGE1"}
    result = _download_single_page(session, page_info, tmp_path)
    assert result is True
    assert (tmp_path / "page_0001.jpg").exists()


def test_download_single_page_skips_existing(tmp_path):
    """Returns True without network call when file exists."""
    (tmp_path / "page_0001.jpg").write_bytes(b"\xff\xd8\xff" + b"x" * 5000)

    session = MagicMock()
    page_info = {"pageNumber": "1", "recordId": "ENCODED_TOKEN_PAGE1"}
    result = _download_single_page(session, page_info, tmp_path)
    assert result is True
    assert session.get.call_count == 0


def test_download_single_page_rejects_small(tmp_path):
    """Returns False for images under 1000 bytes."""
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.content = b"tiny"
    response.ok = True
    session.get.return_value = response

    page_info = {"pageNumber": "1", "recordId": "ENCODED_TOKEN_PAGE1"}
    result = _download_single_page(session, page_info, tmp_path)
    assert result is False


def test_download_single_page_handles_error(tmp_path):
    """Returns False on network error."""
    session = MagicMock()
    session.get.side_effect = Exception("timeout")

    page_info = {"pageNumber": "1", "recordId": "ENCODED_TOKEN_PAGE1"}
    result = _download_single_page(session, page_info, tmp_path)
    assert result is False
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scraper.py -k "test_download_single_page" -v`
Expected: FAIL with ImportError (function doesn't exist yet)

**Step 3: Implement `_download_single_page`**

In `src/scraper.py`, add this function *before* `download_document_pages`:

```python
def _download_single_page(
    session: requests.Session,
    page_info: dict,
    output_dir: Path,
) -> bool:
    """Download a single page image. Returns True on success or skip."""
    page_num = int(page_info["pageNumber"])
    record_id = page_info["recordId"]
    filename = f"page_{page_num:04d}.jpg"
    filepath = output_dir / filename

    # Skip if already downloaded
    if filepath.exists() and filepath.stat().st_size > 1000:
        return True

    try:
        url = f"{IMAGE_DOWNLOAD_URL}/{record_id}"
        params = {"legacy": "no", "scale": "1.0", "format": "jpeg"}
        response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        if len(response.content) < 1000:
            print(f"    Warning: page {page_num} too small ({len(response.content)} bytes)")
            return False

        with open(filepath, "wb") as f:
            f.write(response.content)
        return True

    except Exception as e:
        print(f"    Failed page {page_num}: {e}")
        return False
```

Also update the import in `tests/test_scraper.py` to include `_download_single_page`.

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scraper.py -k "test_download_single_page" -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add src/scraper.py tests/test_scraper.py
git commit -m "extract _download_single_page helper"
```

---

### Task 3: Rewrite download_document_pages with ThreadPoolExecutor

**Files:**
- Modify: `src/scraper.py:154-202`
- Test: `tests/test_scraper.py`

**Step 1: Write the failing test for concurrency**

Add to `tests/test_scraper.py`:

```python
from unittest.mock import call
import time

def test_download_document_pages_concurrent(tmp_path):
    """Downloads pages concurrently using multiple workers."""
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.content = b"\xff\xd8\xff" + b"x" * 5000
    response.ok = True
    session.get.return_value = response

    # Use a larger image list to verify concurrency
    doc_data = {
        "imageList": [
            {"pageNumber": str(i), "recordId": f"TOKEN_{i}"}
            for i in range(1, 11)  # 10 pages
        ]
    }

    result = download_document_pages(session, doc_data, tmp_path, max_workers=3)
    assert result == 10
    # All 10 pages should exist
    for i in range(1, 11):
        assert (tmp_path / f"page_{i:04d}.jpg").exists()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scraper.py::test_download_document_pages_concurrent -v`
Expected: FAIL (max_workers parameter doesn't exist)

**Step 3: Rewrite `download_document_pages`**

Replace the existing function in `src/scraper.py`:

```python
from concurrent.futures import ThreadPoolExecutor


def download_document_pages(
    session: requests.Session,
    doc_data: dict,
    output_dir: Path,
    max_workers: int | None = None,
) -> int:
    """Download all page images concurrently using recordId tokens.

    Uses ThreadPoolExecutor for parallel downloads. requests.Session is
    thread-safe so the same session is shared across workers.

    Returns the number of pages successfully downloaded or skipped.
    """
    if max_workers is None:
        max_workers = MAX_WORKERS

    image_list = doc_data.get("imageList", [])
    if not image_list:
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_download_single_page, session, page_info, output_dir)
            for page_info in image_list
        ]
        results = [f.result() for f in futures]

    return sum(1 for r in results if r)
```

Add `MAX_WORKERS` to the imports from config at the top:

```python
from src.config import (
    ...
    MAX_WORKERS,
)
```

Also add `from concurrent.futures import ThreadPoolExecutor` at the top of the file.

**Step 4: Run ALL scraper tests**

Run: `python -m pytest tests/test_scraper.py -v`
Expected: ALL pass (existing tests still work since `max_workers` defaults to `MAX_WORKERS`)

**Step 5: Commit**

```bash
git add src/scraper.py tests/test_scraper.py
git commit -m "concurrent page downloads with ThreadPoolExecutor"
```

---

### Task 4: Remove per-page sleep, update scrape_volume delay

**Files:**
- Modify: `src/scraper.py` (verify no leftover `time.sleep(0.3)`)

The old `time.sleep(0.3)` was in `download_document_pages` which we replaced in Task 3. Verify it's gone.

The `DOWNLOAD_DELAY` between documents was already reduced to 0.5s in Task 1.

**Step 1: Verify no stale sleep calls**

Search `src/scraper.py` for `time.sleep` -- should only appear in `scrape_volume` (the inter-document delay). The per-page 0.3s sleep should be gone since `_download_single_page` doesn't sleep.

**Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ALL pass

**Step 3: Commit (if any cleanup was needed)**

```bash
git add src/scraper.py
git commit -m "remove per-page sleep, rely on concurrency throttling"
```

---

### Task 5: Add --workers CLI flag

**Files:**
- Modify: `scripts/run.py`
- Modify: `src/scraper.py` (pass through `max_workers` in `scrape_volume`)

**Step 1: Add max_workers parameter to scrape_volume**

In `src/scraper.py`, update `scrape_volume` signature and the `download_document_pages` call:

```python
def scrape_volume(
    session: requests.Session,
    volume_id: str,
    doc_ids: list[str],
    output_dir: Path,
    resume: bool = True,
    max_workers: int | None = None,
) -> dict:
```

And pass it through:

```python
            pages = download_document_pages(session, doc_data, doc_images_dir, max_workers=max_workers)
```

**Step 2: Add --workers flag to CLI**

In `scripts/run.py`, add to the scrape and all subparsers:

```python
sp_scrape.add_argument("--workers", type=int, default=None, help="Concurrent download workers (default: 5)")
```

And pass it in `cmd_scrape`:

```python
        scrape_volume(
            session=session,
            volume_id=volume_id,
            doc_ids=vol_config["doc_ids"],
            output_dir=DOWNLOAD_DIR,
            resume=args.resume,
            max_workers=args.workers,
        )
```

Same for `sp_all`.

**Step 3: Run tests**

Run: `python -m pytest tests/ -v`
Expected: ALL pass

**Step 4: Commit**

```bash
git add src/scraper.py scripts/run.py
git commit -m "add --workers CLI flag for concurrent downloads"
```

---

## Time estimate after changes

| Before | After (5 workers) |
|--------|--------------------|
| 0.3s sleep/page x 2,738 = 14 min | 0s (no per-page sleep) |
| ~1s network/page x 2,738 = 46 min | ~1s x 2,738 / 5 = 9 min |
| 1.5s/doc x 52 = 78s | 0.5s/doc x 52 = 26s |
| **~60 min total** | **~10 min total** |

Usage: `python -m scripts.run scrape --resume --workers 8` (override to 8 if aggressive)
