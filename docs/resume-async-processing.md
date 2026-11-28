# Resume processing: sync vs async (Railway)

Tailoring a resume can take 30–90 seconds: OCR, two or three AI calls, PDF
rendering and re-scoring. In the default **sync** mode the API does this
inside the upload request. Edge proxies, Railway's included, may close
requests that run longer than about 60–100 seconds, so slow runs can fail for
the user even though they would have finished.

In **async** mode the API answers `202 Accepted` at once and a Celery worker
does the work. The dashboard polls `GET /api/v1/resume/status/{task_id}`, as it
already does, until the resume is ready.

## What the code guarantees
- Async is used only when a worker answers a ping. The check is cached for 30
  seconds and capped at 2 seconds, so a down Redis cannot stall uploads.
- If no worker answers, requests are tailored in the API process exactly as in
  sync mode. Nothing gets stuck in "processing", and the logs show
  `resume_async_no_worker fallback=sync`.
- Paid jobs go to the front of the queue (Redis priority 0; free jobs use 6).

## Turning async on in Railway
1. **Redis:** add a Redis service if the project does not have one yet.
2. **Worker service:** create a service from this repository using
   `railway.worker.toml`. It uses the same image (`backend/Dockerfile`) and
   starts `/app/start-worker.sh`.
3. **Shared variables:** give the API and the worker the same
   `DATABASE_URL`, `REDIS_URL` (`${{Redis.REDIS_URL}}`), `SECRET_KEY`, AI
   provider keys and resume storage settings (`RESUME_S3_*`, if used).
4. **Switch the API:** on the API service only, set
   `RESUME_PROCESSING_MODE=async`.
5. **Deploy order:** deploy the worker first, then the API.
6. **Check it works:**
   - tailor one resume; the upload should return immediately and the result
     appear a little later;
   - the worker logs should show `process_resume_upload` succeeding;
   - the API logs should **not** show `resume_async_no_worker`.

## Rolling back
Set `RESUME_PROCESSING_MODE=sync` on the API service and redeploy it. Jobs
already queued are still finished by the worker.
