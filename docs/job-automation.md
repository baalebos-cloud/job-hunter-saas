# Job and application automation

This integration uses the existing scraper cron, the Job Hunter database and
`automation.baalebo.xyz`. No terminal commands or additional n8n service are needed.

| Event | Coverage | Recipient |
| --- | --- | --- |
| Scraper warning | Failed/partially failing sources, database errors and empty runs | Verified owner admin |
| Missing heartbeat | No recorded scrape within `SCRAPER_STALE_HOURS` | Verified owner admin |
| Daily platform summary | New external and employer-posted jobs, internal applications and external handoffs for the previous UTC day | Verified owner admin |
| Matching job digest | New external and employer-posted jobs matching role, country and work arrangement; at most one digest per UTC day | Verified, opted-in job seeker who is available for work |
| Internal application | New submission to an employer-posted job with no external application URL | Verified, approved job owner / owner admin |
| Maintenance failure | Failed scheduled backend maintenance request, including unavailable backend or incorrect secret; once per UTC day through Resend idempotency | Owner address configured in the n8n workflow |

An employer-posted listing with an external URL remains an external handoff. It
can appear in a matching digest and admin summary; applying does not email the
external recruiter. `submitted_external` is the user's tracker confirmation and
does not verify employer receipt. This integration does not submit external forms.

## Dashboard setup

1. Merge this pull request, then let Railway deploy the backend and your frontend
   host deploy the dashboard. The backend automatically creates the three new
   tables and adds opt-in / first-seen columns using the existing startup migration
   mechanism. An additive Alembic migration is also included for managed upgrades.
   Existing users stay opted out; existing jobs have no first-seen timestamp and
   are not announced as new on deployment.
2. Download `workflows/n8n/job-events.json` from GitHub. In n8n, import it from file.
   Keep it unpublished while assigning credentials:
   - **Baalebos Webhook**: Header Auth credential with name
     `X-Baalebos-Webhook-Key` and your private webhook secret.
   - **Send With Resend**: Header Auth credential with name `Authorization` and
     value `Bearer YOUR_RESEND_API_KEY`. Use the existing Resend credential if its
     sender domain is verified for `noreply@baalebo.xyz`.
   Credentials are deliberately absent from the workflow export.
3. The webhook path is still `baalebos-job-hunter-saas`. If the previous
   application-only workflow is published on that path, unpublish it and publish
   this replacement. Do not publish both workflows on the same path. The new
   workflow also accepts the old application payload.
4. In **Job Hunter backend → Variables** set:

   ```dotenv
   N8N_EVENTS_WEBHOOK_URL=https://automation.baalebo.xyz/webhook/baalebos-job-hunter-saas
   N8N_WEBHOOK_SECRET=YOUR_EXISTING_PRIVATE_WEBHOOK_SECRET
   SCRAPER_STALE_HOURS=8
   ```

   Set the same variables on any worker service that runs this scraper. Keep
   `N8N_APPLICATION_WEBHOOK_URL` if you want legacy application-only compatibility;
   `N8N_EVENTS_WEBHOOK_URL` takes precedence when configured. Set the stale threshold
   above the actual scraper interval plus its normal execution time. Eight hours
   suits the repository's six-hour schedule. The webhook secret is independent
   of `N8N_ENCRYPTION_KEY`; never change the encryption key to configure webhooks.
5. Download and import `workflows/n8n/maintenance.json` into the same n8n instance.
   Assign the webhook Header Auth credential to **Process Notifications** and the
   Resend Header Auth credential to **Report Maintenance Failure**. Confirm its
   backend URL matches your deployed Job Hunter API. The bundled URL is:
   `https://job-hunter-saas-production-bb41.up.railway.app/api/v1/automation/tick`.
   Confirm the fallback recipient is your owner address:
   `jayeolaoluwadamilare@gmail.com`. Publish the workflow.
6. Leave your existing scraper cron running. The new n8n schedule runs
   maintenance every 15 minutes; it does not scrape jobs. Avoid starting an
   additional Celery Beat scraper schedule if your cron already handles scraping.

The event workflow acknowledges success only after Resend returns an email ID.
A generic `Workflow got started` response is insufficient. Workflow imports are
unpublished and need real credentials selected before they can operate. The
production `/webhook/` route is registered when the workflow is published; the
temporary `/webhook-test/` route is for listening to test events.

## Verify from the website

- Open **Admin → Automation → Process queued notifications**, or run the n8n
  maintenance workflow manually. The first enabled maintenance run queues the
  previous UTC day's admin summary, even if there are no internal jobs yet.
- Check **Admin → Automation** for queue totals and scrape source results. A
  `sent` event means provider acceptance, not guaranteed inbox delivery. Check
  Resend for delivery/bounces. n8n execution metadata shows whether the workflow
  succeeded; payload saving is disabled to avoid retaining authenticated webhook
  headers and recipient details in execution history.
- Let the existing cron run, or click **Run Scraper** in Admin. The next run
  appears as `success`, `partial`, `empty`, `failed` or `running`. Zero new inserts
  by itself is normal when every fetched job already exists.
- On a verified job-seeker account, open **My Profile → Job alerts**, choose a
  career track / country / work arrangement, enable emails and save. Future jobs
  are eligible. An existing refreshed listing is not treated as new. Turning
  alerts off cancels pending digests before delivery.
- When ready to test internal jobs, an approved employer can post a vacancy
  without an external URL. A job seeker attaches a resume tailored to that exact
  job description and submits. Repeated clicks create one application event.
  The job owner gets an email pointing to `/hr`; resumes and applicant contact
  details remain inside the authenticated platform.

The tests use synthetic external and internal jobs, mocked HTTP delivery and
temporary databases. They do not create live jobs, call your webhook or send mail.
Live n8n import, credentials, Railway deployment and final email delivery still
need verification in your environment.

## Delivery and matching behavior

Notifications are recorded in `automation_events`, with unique event IDs and
atomic claims to prevent concurrent dispatchers handling the same pending event.
Application events are committed with the application; a backend restart cannot
discard the stored event. A short background task attempts immediate delivery,
and n8n maintenance retries pending events. Processing leases can be recovered
after a crash. Five unsuccessful attempts mark an event failed. Failed events
appear in Admin; the ordinary processing button does not reset their history.

The event ID supplies Resend's `Idempotency-Key` (with the existing
`application-notification-` prefix for application emails), and the prepared email
stays unchanged between retries. Since Resend retains keys for 24 hours, automatic
retries stop 23 hours after the first attempt. This prevents indefinite retries
outside the provider's deduplication window; it is not an exactly-once delivery
guarantee. Failed/expired events require investigation instead of a blind resend.
HTTP failures never undo an already stored application. Unconfigured channels
remain pending without spending attempts. Changed recipient emails, withdrawn
consent, revoked HR access or unavailable listings cancel affected pending events.

Job matching uses role words in the job title/category, the selected work
arrangement, and an explicit country or worldwide/anywhere location. `Remote`
alone does not establish country eligibility. It is a preference match, not an
ATS score, resume assessment or promise of qualification. Up to ten job details
appear in each daily digest; further matches can be reviewed in the job feed.
Internal listings remain visible while active; externally scraped listings keep
their existing three-day refresh requirement.

Scraper results retain only source labels, request/error counts, statuses and job
counts. Scrape refreshes preserve `first_seen_at`. One invalid database row does
not roll back the valid rows from the same batch. The recorded source statistics
cover existing sources and fallbacks; they do not guarantee every job board's
API is available or every listing is complete.

The n8n schedule is needed for timely retries and heartbeat monitoring. If n8n is
down, database events stay pending; they can be processed after recovery. If the
backend or shared database is unavailable, backend monitoring cannot run; the
n8n maintenance failure branch attempts a fixed admin email via Resend. If both
services or Resend are unavailable, an independent uptime monitor is needed.

Reference documentation:
- [n8n Webhook](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/)
- [n8n Schedule Trigger](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.scheduletrigger/)
- [Resend idempotency keys](https://resend.com/docs/dashboard/emails/idempotency-keys)
