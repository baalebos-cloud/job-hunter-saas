# Platform quality rollout

This branch implements the first correction pass. It is not deployed. Railway is paused and live provider calls have not been validated.

## Resume preparation

Upload a text-based PDF or DOCX and the complete target description. Extraction includes roles, projects, skills, education and certifications. Rewriting retains the extracted history and identity. Unsupported listed skills and new numeric achievements fail validation; missing qualifications become questions for the candidate. No generic achievement templates are used by the mounted resume route.

The exported PDF is a single-column, selectable-text document. Preview and download return the same stored PDF with authenticated ownership checks. A completed scan is charged only when the resume is saved. Scanned image PDFs require text extraction/OCR outside the current flow.

The assessment measures weighted exact-phrase requirement coverage in the actual exported PDF (required=2, preferred=1). It includes per-requirement evidence. It is not an employer ATS score. AI requirement extraction can vary; synonyms, proficiency, years of experience, authorization and degree equivalence need human review. No interview guarantee is offered. Numeric and structural checks cannot prove every AI statement factual: candidates must review the PDF before submission. Live evaluation on representative resumes and JDs is required before release.

## Permissions and owner setup

The owner email defaults to `jayeolaoluwadamilare@gmail.com`. Backend authorization also requires verified email and an administrator flag. Hiding an admin URL is not the security boundary. Other accounts with old admin flags are denied owner operations. Set `ADMIN_EMAIL` consistently if intentionally changing ownership.

1. Back up the database, then run `alembic upgrade head` with the staging database URL. Confirm new columns, unique referral codes and resume attachment foreign keys.
2. Configure a strong random `SECRET_KEY` in the backend environment. There is no fallback signing key. Rotate any previously shared/default key; existing tokens will require sign-in again.
3. Register and verify the owner email using the ordinary verification flow.
4. From the repository root, run `python -m backend.scripts.provision_owner` against the intended database. This enables only the verified owner and does not change passwords.
5. HR users must separately verify email and receive owner approval. Review existing HR accounts before approving; old verification status does not imply employer approval.

The migration accommodates fields previously added by startup DDL. Downgrade deliberately refuses to destroy application evidence: roll back code while retaining fields or restore a backup. Run against a staging copy before production; the repository's older migration history and startup DDL need reconciliation for fresh installations.

## Applications, jobs and referrals

Employer vacancies without external URLs accept an explicit owned resume prepared for that exact description, retain its attachment and a job snapshot, and mark `submitted_internal`. Only the vacancy's approved employer or owner can open that submitted resume and update employer statuses.

External jobs create `external_started`, then link to the actual employer application page. Candidates can mark `submitted_external` after completing that page. This is candidate confirmation, not employer receipt. Direct submission needs a supported employer/ATS API, authorization, form mapping and a real receipt; universal automatic submission is not implemented.

Scraping retains full HTML-derived descriptions, line breaks and lists, updates existing descriptions, records checks, avoids assuming unknown work arrangements and fixes the Celery scheduled task identifier. Source coverage, pagination, rate limits, canonical URL deduplication, expiry checks and source publication dates still need a dedicated ingestion pass. Scrape time must not be represented as proof that an employer still accepts applications.

Referral attribution uses unpredictable stored codes, authenticated self-attribution during registration and prevents self-referrals. Public conversion is removed. Only signed paid Stripe events invoke conversion; already converted records are not rewarded again. Old sequential referral links should be regenerated. Rewards remain pending manual payout review; refund reversals, fraud controls, reconciliation and a payout ledger are follow-up work.

## Release checks

- Run `python -m pytest backend/test -q` and `npm ci && npm run build` inside `job-hunter-dashboard`.
- Configure AI provider, email, frontend API URL, database, Stripe price IDs/webhook signing secret and Celery/Redis in staging. Do not paste credentials in chat or commit them.
- Exercise upload → evidence review → PDF preview → download → internal application → employer resume review with test accounts. Compare every role, date, qualification, stack and numeric claim with the uploaded source.
- Verify other candidate and HR accounts cannot read private resumes or another employer's applicants. Confirm owner provisioning and HR approvals.
- Use Stripe test events to verify paid/unpaid/replayed events, cancellations, failed renewals and referral state. Test the event payload format used by the configured Stripe API version.
- Resume Railway in staging and validate scheduled scraping, external application links and email delivery. Confirm source terms and closing-date behavior.

The light dashboard follows the supplied reference's sidebar and card organization. It does not copy micro1 branding or imply micro1 certification. Existing auto-seeded profile certification badges are suppressed; credential verification needs its own evidence workflow. Saved-job tabs, structured JD field extraction, resume editing/version history, production migration cleanup and broader HR/admin UI polish remain subsequent work.
