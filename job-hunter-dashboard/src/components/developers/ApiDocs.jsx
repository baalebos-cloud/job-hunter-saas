/* eslint-disable react/prop-types -- the project does not use the prop-types package; these are local layout helpers */
import { Link } from 'react-router-dom';
import SEO from '../SEO';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const BASE = `${new URL(API).origin}/api/public/v1`;

function Code({ children }) {
  return <pre className="mt-3 text-xs leading-relaxed bg-slate-900 text-slate-100 rounded-xl p-4 overflow-x-auto"><code>{children}</code></pre>;
}

function Endpoint({ method, path, children }) {
  const color = method === 'GET' ? 'bg-sky-100 text-sky-800' : 'bg-emerald-100 text-emerald-800';
  return (
    <div className="border-t border-slate-100 pt-6 mt-6">
      <h3 className="flex flex-wrap items-center gap-2 font-mono text-sm text-slate-900">
        <span className={`px-2 py-0.5 rounded-md text-xs font-bold ${color}`}>{method}</span>{path}
      </h3>
      <div className="mt-2 text-sm text-slate-600 space-y-2">{children}</div>
    </div>
  );
}

const SECTIONS = [['auth', 'Authentication'], ['limits', 'Limits'], ['jobs', 'Jobs'], ['resumes', 'Resumes'], ['errors', 'Errors']];

// Public reference for the Enterprise integrations API. Every endpoint, field and
// status code here matches backend/app/routes/public_api.py.
export default function ApiDocs() {
  return (
    <div className="max-w-4xl">
      <SEO title="API documentation" description="Tailor resumes and search the Baalebos job board from your own tools." />
      <p className="text-xs font-black uppercase tracking-widest text-emerald-600 mb-1">Enterprise</p>
      <h1 className="text-2xl font-black text-slate-900">Baalebos API</h1>
      <p className="mt-2 text-sm text-slate-600">
        Tailor a resume to a job, download the result as PDF or Word, and search the job board from your own
        tools. The API is part of the Enterprise plan. Results also appear in <Link to="/resumes" className="text-emerald-700 font-semibold hover:underline">My resumes</Link>.
      </p>
      <nav className="mt-4 flex flex-wrap gap-2 text-xs">
        {SECTIONS.map(([id, label]) => <a key={id} href={`#${id}`} className="px-3 py-1.5 rounded-full border border-slate-200 bg-white hover:bg-slate-50 font-semibold text-slate-700">{label}</a>)}
      </nav>

      <section className="bg-white border border-slate-200 rounded-2xl p-6 mt-6">
        <h2 className="font-bold text-slate-900">Base URL</h2>
        <Code>{BASE}</Code>
      </section>

      <section id="auth" className="bg-white border border-slate-200 rounded-2xl p-6 mt-6">
        <h2 className="font-bold text-slate-900">Authentication</h2>
        <p className="mt-2 text-sm text-slate-600">
          Create a key in <Link to="/settings#api" className="text-emerald-700 font-semibold hover:underline">Settings → API keys</Link>.
          The full key is shown once; copy it then. Send it in the <code>Authorization</code> header
          (or as <code>X-API-Key</code>). Keep keys on your server, never in a browser or mobile app.
        </p>
        <Code>{`curl ${BASE}/me \\
  -H "Authorization: Bearer bb_live_YOUR_KEY"`}</Code>
        <p className="mt-3 text-sm text-slate-600">Response:</p>
        <Code>{`{ "email": "you@company.com", "name": "Your Name", "plan": "enterprise", "rate_limit_per_minute": 60 }`}</Code>
        <p className="mt-3 text-sm text-slate-600">
          A key works only while the account has Enterprise (its own plan, or through a team). Revoking a key in
          Settings stops it at once.
        </p>
      </section>

      <section id="limits" className="bg-white border border-slate-200 rounded-2xl p-6 mt-6">
        <h2 className="font-bold text-slate-900">Limits</h2>
        <ul className="mt-2 text-sm text-slate-600 list-disc pl-5 space-y-1">
          <li>60 requests per minute per key. Over the limit you get <code>429</code> with a <code>Retry-After</code> header (seconds).</li>
          <li>Up to 10 resumes being prepared at once per account.</li>
          <li>Up to 5 active keys per account.</li>
          <li>Resume files: PDF or DOCX, up to 10 MB.</li>
        </ul>
      </section>

      <section id="jobs" className="bg-white border border-slate-200 rounded-2xl p-6 mt-6">
        <h2 className="font-bold text-slate-900">Jobs</h2>
        <Endpoint method="GET" path="/jobs">
          <p>Active jobs on the board, newest first, one listing per role per company. Jobs posted by employers on Baalebos come first.</p>
          <p>Query parameters (all optional): <code>q</code> (search text), <code>work_type</code> (<code>remote</code>, <code>hybrid</code> or <code>onsite</code>),
            <code>category</code>, <code>region</code>, <code>posted_within</code> (days, 1–90), <code>page</code> (from 1), <code>page_size</code> (1–50, default 20).</p>
          <Code>{`curl "${BASE}/jobs?q=devops&work_type=remote&page=1" \\
  -H "Authorization: Bearer bb_live_YOUR_KEY"`}</Code>
          <Code>{`{
  "total": 132, "page": 1, "page_size": 20,
  "items": [
    { "id": 4821, "title": "Senior DevOps Engineer", "company": "Contoso", "location": "Remote",
      "work_type": "remote", "url": "https://…", "posted_at": "2026-11-20T09:00:00Z",
      "skills": ["Kubernetes", "Terraform"], "match": { "score": 78, … }, "summary": "…", … }
  ]
}`}</Code>
          <p><code>match</code> compares the job with the skills on your profile and is <code>null</code> when there is nothing to compare.</p>
        </Endpoint>
        <Endpoint method="GET" path="/jobs/{job_id}">
          <p>One job, with the full <code>description</code>. <code>404</code> if it is no longer active.</p>
        </Endpoint>
      </section>

      <section id="resumes" className="bg-white border border-slate-200 rounded-2xl p-6 mt-6">
        <h2 className="font-bold text-slate-900">Resumes</h2>
        <Endpoint method="POST" path="/resumes">
          <p>Tailor a resume to one job. Send <code>multipart/form-data</code> with:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li><code>file</code>: the current resume (PDF or DOCX), required.</li>
            <li><code>job_id</code>: a job from <code>/jobs</code>; <strong>or</strong> <code>job_title</code> (up to 200 characters) and <code>job_description</code> (the full text, at least 50 characters).</li>
            <li><code>region</code>: optional resume format; by default the one for the country on your profile.</li>
          </ul>
          <p>Returns <code>202 Accepted</code> straight away. Tailoring runs with priority processing.</p>
          <Code>{`curl -X POST ${BASE}/resumes \\
  -H "Authorization: Bearer bb_live_YOUR_KEY" \\
  -F "file=@resume.pdf" \\
  -F "job_id=4821"`}</Code>
          <Code>{`{ "task_id": "3f6c…", "status": "processing",
  "links": { "self": "/api/public/v1/resumes/3f6c…", "pdf": "…/pdf", "docx": "…/docx" } }`}</Code>
        </Endpoint>
        <Endpoint method="GET" path="/resumes/{task_id}">
          <p>Poll every few seconds until <code>status</code> is <code>completed</code> or <code>failed</code>.</p>
          <Code>{`{ "task_id": "3f6c…", "status": "completed", "job_title": "Senior DevOps Engineer",
  "company": "Contoso", "job_id": 4821, "created_at": "2026-11-23T08:00:00Z",
  "match_before": 54, "match_after": 82, "missing_keywords": ["Helm"],
  "links": { "self": "…", "pdf": "…/pdf", "docx": "…/docx" } }`}</Code>
          <p>When it fails, <code>error</code> explains why and includes a reference for support. Nothing is charged for a failed run.
            <code> missing_keywords</code> are requirements from the job that the resume does not show; they are never added for you.</p>
        </Endpoint>
        <Endpoint method="GET" path="/resumes/{task_id}/pdf">
          <p>The tailored resume as a PDF file. <code>409</code> while it is still being prepared.</p>
          <Code>{`curl -o resume.pdf ${BASE}/resumes/TASK_ID/pdf \\
  -H "Authorization: Bearer bb_live_YOUR_KEY"`}</Code>
        </Endpoint>
        <Endpoint method="GET" path="/resumes/{task_id}/docx">
          <p>The same resume as an editable Word file.</p>
        </Endpoint>
      </section>

      <section id="errors" className="bg-white border border-slate-200 rounded-2xl p-6 mt-6 mb-10">
        <h2 className="font-bold text-slate-900">Errors</h2>
        <p className="mt-2 text-sm text-slate-600">Errors return JSON with a <code>detail</code> field: either a message, or an object with <code>error</code> and <code>message</code>.</p>
        <Code>{`{ "detail": { "error": "invalid_api_key", "message": "Missing, invalid or revoked API key." } }`}</Code>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead><tr className="text-slate-500 text-xs uppercase"><th className="py-2 pr-4">Status</th><th className="py-2">Meaning</th></tr></thead>
            <tbody className="text-slate-700 divide-y divide-slate-100">
              <tr><td className="py-2 pr-4 font-mono">400</td><td>The request is missing something or a value is not valid. The message says what.</td></tr>
              <tr><td className="py-2 pr-4 font-mono">401</td><td><code>invalid_api_key</code>: the key is missing, wrong or revoked.</td></tr>
              <tr><td className="py-2 pr-4 font-mono">403</td><td><code>enterprise_required</code>: the account does not have Enterprise right now.</td></tr>
              <tr><td className="py-2 pr-4 font-mono">404</td><td>The job or resume does not exist, or is not yours.</td></tr>
              <tr><td className="py-2 pr-4 font-mono">409</td><td>The resume is not ready yet.</td></tr>
              <tr><td className="py-2 pr-4 font-mono">429</td><td><code>rate_limited</code> (60 per minute) or <code>too_many_in_progress</code> (10 at once). Wait, then retry.</td></tr>
              <tr><td className="py-2 pr-4 font-mono">503</td><td>Processing is briefly unavailable. Retry later; nothing was charged.</td></tr>
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-sm text-slate-600">Questions? <Link to="/help" className="text-emerald-700 font-semibold hover:underline">Contact support</Link>.</p>
      </section>
    </div>
  );
}
