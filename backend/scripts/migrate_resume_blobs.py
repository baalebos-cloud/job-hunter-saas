"""Backfill: move resume PDFs from ``resumes.content`` to S3.

    RESUME_S3_BUCKET=... RESUME_S3_KMS_KEY_ID=... python -m backend.scripts.migrate_resume_blobs [--batch 100] [--dry-run]

Idempotent and resumable: each row is uploaded, verified by SHA-256 read-back,
then ``content`` is cleared in its own transaction. Run until it reports 0
remaining, then deploy the contract migration that drops the column.
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("migrate_resume_blobs")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    from backend.app.database import SessionLocal
    from backend.app.models.registry import import_all_models
    from backend.app.models.resume import Resume
    from backend.app.services import resume_storage

    import_all_models()
    if not resume_storage.s3_enabled():
        log.error("RESUME_S3_BUCKET is not set; nothing to do")
        return 2
    db = SessionLocal()
    moved = failed = 0
    try:
        while True:
            rows = (db.query(Resume).filter(Resume.content.isnot(None), Resume.storage_key.is_(None))
                    .order_by(Resume.id).limit(args.batch).all())
            if not rows:
                break
            for record in rows:
                pdf = bytes(record.content)
                if args.dry_run:
                    moved += 1
                    continue
                try:
                    resume_storage.store_pdf(record, pdf)
                    if hashlib.sha256(resume_storage.load_pdf(record)).hexdigest() != hashlib.sha256(pdf).hexdigest():
                        raise resume_storage.StorageIntegrityError("read-back mismatch")
                    resume_storage.commit_with_storage(db, record)
                    moved += 1
                except Exception as exc:
                    db.rollback()
                    failed += 1
                    log.error("resume_blob_move_failed resume_id=%s error_type=%s", record.id, type(exc).__name__)
            if args.dry_run or failed:
                break
        remaining = db.query(Resume).filter(Resume.content.isnot(None), Resume.storage_key.is_(None)).count()
    finally:
        db.close()
    log.info("moved=%s failed=%s remaining=%s%s", moved, failed, remaining, " (dry run)" if args.dry_run else "")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
