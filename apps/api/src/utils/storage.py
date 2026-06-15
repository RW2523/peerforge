"""
Object storage for uploaded materials.

Two interchangeable backends, selected by STORAGE_BACKEND:

  minio (default) — self-hosted MinIO (local dev via docker, or a MinIO
                    service on Railway). Zero-config with the existing env.
  s3              — any S3-compatible endpoint via boto3. Used for
                    Supabase Storage (free tier) whose endpoint includes a
                    path (https://<ref>.storage.supabase.co/storage/v1/s3),
                    which minio-py cannot address. Also works with R2/S3.

Both expose the same interface: ensure_bucket_exists, upload_file,
download_file, delete_file, file_exists.
"""

import logging
from typing import BinaryIO, Optional, Union

from src.config import settings

logger = logging.getLogger(__name__)


class StorageClient:
    """MinIO S3-compatible storage client (default backend)."""

    def __init__(self):
        from minio import Minio

        self.client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure
        )
        self.bucket_name = settings.minio_bucket

    def ensure_bucket_exists(self) -> None:
        """Create bucket if it doesn't exist"""
        from minio.error import S3Error
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except S3Error as e:
            # Avoid breaking app import / startup if MinIO isn't reachable yet.
            logger.warning("MinIO bucket ensure failed (bucket=%s): %s", self.bucket_name, e)

    def upload_file(self, file_key: str, file_data: BinaryIO, file_size: int, content_type: str) -> str:
        from minio.error import S3Error
        try:
            self.ensure_bucket_exists()
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=file_key,
                data=file_data,
                length=file_size,
                content_type=content_type
            )
            return file_key
        except S3Error as e:
            raise Exception(f"Failed to upload file: {e}")

    def download_file(self, file_key: str) -> bytes:
        from minio.error import S3Error
        try:
            response = self.client.get_object(
                bucket_name=self.bucket_name,
                object_name=file_key
            )
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            raise Exception(f"Failed to download file: {e}")

    def delete_file(self, file_key: str) -> None:
        from minio.error import S3Error
        try:
            self.client.remove_object(
                bucket_name=self.bucket_name,
                object_name=file_key
            )
        except S3Error as e:
            logger.warning("Error deleting MinIO object (key=%s): %s", file_key, e)

    def file_exists(self, file_key: str) -> bool:
        from minio.error import S3Error
        try:
            self.client.stat_object(
                bucket_name=self.bucket_name,
                object_name=file_key
            )
            return True
        except S3Error:
            return False


class S3StorageClient:
    """boto3-based client for S3-compatible endpoints (Supabase Storage, R2, AWS).

    Supabase Storage: create the bucket in the dashboard first, generate S3
    access keys under Storage → Settings, and set:
      STORAGE_BACKEND=s3
      S3_ENDPOINT_URL=https://<project-ref>.storage.supabase.co/storage/v1/s3
      S3_REGION=<project region, e.g. us-east-1>
      S3_ACCESS_KEY / S3_SECRET_KEY / S3_BUCKET
    """

    def __init__(self):
        import boto3

        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region or "us-east-1",
        )
        self.bucket_name = settings.s3_bucket

    def ensure_bucket_exists(self) -> None:
        # Managed providers (Supabase, R2) pre-create buckets in their
        # dashboards and may not permit CreateBucket via the S3 API.
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except Exception:
            try:
                self.client.create_bucket(Bucket=self.bucket_name)
            except Exception as e:
                logger.warning("S3 bucket ensure failed (bucket=%s): %s", self.bucket_name, e)

    def upload_file(self, file_key: str, file_data: BinaryIO, file_size: int, content_type: str) -> str:
        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=file_data.read(),
                ContentType=content_type,
            )
            return file_key
        except Exception as e:
            raise Exception(f"Failed to upload file: {e}")

    def download_file(self, file_key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=file_key)
            return response["Body"].read()
        except Exception as e:
            raise Exception(f"Failed to download file: {e}")

    def delete_file(self, file_key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=file_key)
        except Exception as e:
            logger.warning("Error deleting S3 object (key=%s): %s", file_key, e)

    def file_exists(self, file_key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=file_key)
            return True
        except Exception:
            return False


_storage_client: Optional[Union[StorageClient, "S3StorageClient"]] = None


def get_storage_client() -> Union[StorageClient, "S3StorageClient"]:
    """
    Lazy singleton: avoids storage network calls at import time.
    Backend selected by STORAGE_BACKEND (minio | s3).
    """
    global _storage_client
    if _storage_client is None:
        backend = (getattr(settings, "storage_backend", "minio") or "minio").lower()
        _storage_client = S3StorageClient() if backend == "s3" else StorageClient()
        logger.info("Storage backend: %s", backend)
    return _storage_client
