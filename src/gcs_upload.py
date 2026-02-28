# src/gcs_upload.py
"""
Upload downloaded volumes to Google Cloud Storage.
"""
from pathlib import Path
from google.cloud import storage
from src.config import GCS_BUCKET, GCS_KEY_PATH


def get_gcs_client() -> storage.Client:
    """Create authenticated GCS client."""
    if GCS_KEY_PATH:
        return storage.Client.from_service_account_json(GCS_KEY_PATH)
    return storage.Client()


def get_bucket(client: storage.Client = None) -> storage.bucket.Bucket:
    """Get the project's GCS bucket."""
    if client is None:
        client = get_gcs_client()
    return client.bucket(GCS_BUCKET)


def upload_file(bucket, local_path: Path, gcs_path: str) -> None:
    """Upload a single file to GCS."""
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(str(local_path))


def upload_volume(bucket, volume_dir: Path, volume_id: str) -> int:
    """
    Upload all files in a volume directory to GCS.

    Uploads:
    - pages/*.jpg → {volume_id}/pages/
    - manifest.json → {volume_id}/
    - *_full.pdf → {volume_id}/

    Returns count of files uploaded.
    """
    count = 0

    for file_path in sorted(volume_dir.rglob("*")):
        if not file_path.is_file():
            continue

        # Build GCS path preserving directory structure
        relative = file_path.relative_to(volume_dir)
        gcs_path = f"{volume_id}/{relative.as_posix()}"

        print(f"  Uploading {gcs_path}...")
        upload_file(bucket, file_path, gcs_path)
        count += 1

    print(f"  [{volume_id}] Uploaded {count} files")
    return count


def upload_all_volumes(download_dir: Path) -> None:
    """Upload all downloaded volumes to GCS."""
    bucket = get_bucket()

    for volume_dir in sorted(download_dir.iterdir()):
        if not volume_dir.is_dir():
            continue

        volume_id = volume_dir.name
        print(f"Uploading volume {volume_id}...")
        upload_volume(bucket, volume_dir, volume_id)

    print("All uploads complete.")


def list_bucket_contents() -> list[str]:
    """List all objects in the bucket (for verification)."""
    bucket = get_bucket()
    return [blob.name for blob in bucket.list_blobs()]
