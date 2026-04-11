"""S3-compatible object storage client for PM file attachments.

Wraps boto3 with a thin interface. Configured via environment variables:
  GARAGE_S3_ENDPOINT  — S3 endpoint URL (default: http://localhost:3900)
  GARAGE_ACCESS_KEY   — AWS-style access key ID
  GARAGE_SECRET_KEY   — AWS-style secret access key
  GARAGE_BUCKET       — bucket name (default: evoscientist)

If access/secret keys are not set the module is importable but upload/download
operations will raise RuntimeError with a clear message.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import BinaryIO

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
    _BOTO3_AVAILABLE = True
except ImportError:
    _BOTO3_AVAILABLE = False

# ── Configuration ────────────────────────────────────────────────────────────

_ENDPOINT = os.environ.get("GARAGE_S3_ENDPOINT", "http://localhost:3900")
_ACCESS_KEY = os.environ.get("GARAGE_ACCESS_KEY", "")
_SECRET_KEY = os.environ.get("GARAGE_SECRET_KEY", "")
_BUCKET = os.environ.get("GARAGE_BUCKET", "evoscientist")
_REGION = "garage"  # Garage uses a fixed pseudo-region

# Thread pool for running sync boto3 calls in async contexts
_executor = ThreadPoolExecutor(max_workers=4)


def _client():
    """Build and return a boto3 S3 client."""
    if not _BOTO3_AVAILABLE:
        raise RuntimeError(
            "boto3 is not installed. "
            "Install it with: pip install boto3"
        )
    if not _ACCESS_KEY or not _SECRET_KEY:
        raise RuntimeError(
            "S3 storage is not configured. "
            "Set GARAGE_ACCESS_KEY and GARAGE_SECRET_KEY environment variables."
        )
    return boto3.client(
        "s3",
        endpoint_url=_ENDPOINT,
        aws_access_key_id=_ACCESS_KEY,
        aws_secret_access_key=_SECRET_KEY,
        region_name=_REGION,
        config=Config(signature_version="s3v4"),
    )


# ── Public API ────────────────────────────────────────────────────────────────


def upload_file(file_obj: BinaryIO, key: str, content_type: str) -> str:
    """Upload *file_obj* to S3 at *key*.

    Args:
        file_obj: Readable binary file-like object.
        key: S3 object key (e.g. ``entries/{entry_id}/{uuid}/{filename}``).
        content_type: MIME type string.

    Returns:
        The S3 key on success.

    Raises:
        RuntimeError: If S3 credentials are not configured.
        ClientError: If the upload fails.
    """
    client = _client()
    client.upload_fileobj(
        file_obj,
        _BUCKET,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return key


def generate_presigned_url(key: str, expires: int = 3600) -> str:
    """Return a pre-signed GET URL for *key* valid for *expires* seconds."""
    client = _client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": _BUCKET, "Key": key},
        ExpiresIn=expires,
    )


def delete_object(key: str) -> None:
    """Permanently delete the object at *key*.

    Does not raise if the key does not exist.
    """
    client = _client()
    try:
        client.delete_object(Bucket=_BUCKET, Key=key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in ("NoSuchKey", "404"):
            raise


def get_object_stream(key: str) -> BytesIO:
    """Download *key* and return its contents as a BytesIO buffer."""
    client = _client()
    buf = BytesIO()
    client.download_fileobj(_BUCKET, key, buf)
    buf.seek(0)
    return buf
