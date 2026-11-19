"""Resume PDF storage.

Production: private S3 bucket, SSE-KMS (``RESUME_S3_KMS_KEY_ID``), objects
addressed by an unguessable key, integrity checked with SHA-256 on every
read, short-lived presigned GET URLs. Without ``RESUME_S3_BUCKET`` (local
development, tests, or before the backfill) bytes stay in ``resumes.content``.
"""
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from functools import lru_cache

logger = logging.getLogger(__name__)
PRESIGNED_TTL_SECONDS = int(os.getenv('RESUME_URL_TTL_SECONDS', '300'))


class StorageIntegrityError(RuntimeError):
    pass


def _bucket() -> str:
    return os.getenv('RESUME_S3_BUCKET', '').strip()


def s3_enabled() -> bool:
    return bool(_bucket())


@lru_cache(maxsize=1)
def _client():
    import boto3
    from botocore.config import Config
    return boto3.client('s3', region_name=os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION') or None,
                        endpoint_url=os.getenv('RESUME_S3_ENDPOINT_URL') or None,
                        config=Config(signature_version='s3v4', retries={'max_attempts': 3, 'mode': 'standard'}))


def client():
    return _client()


def object_key(owner_id) -> str:
    return f"resumes/{owner_id or 'anonymous'}/{uuid.uuid4().hex}.pdf"


def store_pdf(record, pdf: bytes) -> None:
    """Persist bytes for ``record`` (object first; DB row is committed after)."""
    digest = hashlib.sha256(pdf).hexdigest()
    previous_key = record.storage_key
    record.sha256, record.size_bytes = digest, len(pdf)
    if not s3_enabled():
        record.content, record.storage_key = pdf, None
        return
    key = object_key(record.owner_id)
    extra = {'ServerSideEncryption': 'aws:kms'}
    if os.getenv('RESUME_S3_KMS_KEY_ID'):
        extra['SSEKMSKeyId'] = os.getenv('RESUME_S3_KMS_KEY_ID')
    client().put_object(Bucket=_bucket(), Key=key, Body=pdf, ContentType='application/pdf',
                        ChecksumAlgorithm='SHA256', Metadata={'sha256': digest}, **extra)
    record.storage_key, record.content = key, None
    record._previous_storage_key = previous_key  # removed after a successful commit


def load_pdf(record) -> bytes:
    if record.storage_key:
        body = client().get_object(Bucket=_bucket(), Key=record.storage_key)['Body'].read()
    else:
        body = record.content or b''
    if record.sha256 and hashlib.sha256(body).hexdigest() != record.sha256:
        logger.error('resume_integrity_mismatch resume_id=%s', record.id)
        raise StorageIntegrityError('Stored resume failed its integrity check.')
    return body


def presigned_url(record, ttl: int = PRESIGNED_TTL_SECONDS) -> str | None:
    if not record.storage_key:
        return None
    return client().generate_presigned_url(
        'get_object', ExpiresIn=max(30, min(ttl, 900)),
        Params={'Bucket': _bucket(), 'Key': record.storage_key, 'ResponseContentType': 'application/pdf'})


def delete_object(key: str | None) -> None:
    if key and s3_enabled():
        try:
            client().delete_object(Bucket=_bucket(), Key=key)
        except Exception as exc:  # orphan objects are swept by the bucket lifecycle rule
            logger.warning('resume_object_delete_failed error_type=%s', type(exc).__name__)


def commit_with_storage(db, record) -> None:
    """Commit ``record``; on failure remove the newly written object, on
    success remove the object it replaced. Keys are captured up front because
    a rollback expires the instance's attributes."""
    new_key = record.storage_key
    old_key = getattr(record, '_previous_storage_key', None)
    try:
        db.add(record)
        db.commit()
    except Exception:
        db.rollback()
        if new_key and new_key != old_key:
            delete_object(new_key)
        raise
    if old_key and old_key != new_key:
        delete_object(old_key)


def delete_pdf(record) -> None:
    delete_object(record.storage_key)
