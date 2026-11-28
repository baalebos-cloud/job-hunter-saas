import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { AlertTriangle, Check, Download, ExternalLink, FileText, Loader2, PencilLine, Send, Sparkles, X } from 'lucide-react';
import { apiErrorMessage, filenameFromDisposition } from '../../lib/session';
import PdfPreview from '../common/PdfPreview';
import ResumeEditPanel from './ResumeEditPanel';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });
const card = 'bg-white border border-slate-200 rounded-2xl';

function Ring({ score }) {
  const value = Math.max(0, Math.min(100, Math.round(score || 0)));
  const tone = value >= 75 ? '#10b981' : value >= 55 ? '#f59e0b' : '#e11d48';
  return (
    <div className="relative w-20 h-20 shrink-0" role="img" aria-label={`Job match ${value}%`}>
      <svg viewBox="0 0 36 36" className="w-20 h-20 -rotate-90">
        <circle cx="18" cy="18" r="15.9" fill="none" stroke="#f1f5f9" strokeWidth="3.5" />
        <circle cx="18" cy="18" r="15.9" fill="none" stroke={tone} strokeWidth="3.5" strokeLinecap="round" strokeDasharray={`${value} 100`} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-lg font-semibold text-slate-900">{value}%</div>
    </div>
  );
}

// The exact PDF that downloads, always visible next to the download buttons.
function ResumePreview({ resumeId, version, onReady }) {
  const [url, setUrl] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!resumeId) return undefined;
    let active = true;
    let objectUrl;
    setUrl(null); setError(''); onReady(false);
    axios.get(`${API}/resume/preview/${resumeId}`, { headers: headers(), responseType: 'blob' })
      .then(r => {
        if (!r.headers['content-type']?.includes('application/pdf')) throw new Error('not a pdf');
        objectUrl = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
        if (active) { setUrl(objectUrl); onReady(true); } else URL.revokeObjectURL(objectUrl);
      })
      .catch(async err => { if (active) setError(err?.response ? await apiErrorMessage(err, 'The preview could not load.') : 'The preview could not load.'); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [resumeId, version, onReady]);
  if (error) return <div role="alert" className="h-[70vh] grid place-items-center text-sm text-rose-700 bg-rose-50 rounded-xl p-6 text-center">{error}</div>;
  if (!url) return <div role="status" className="h-[70vh] grid place-items-center bg-slate-50 rounded-xl"><Loader2 className="animate-spin text-emerald-600" /><span className="sr-only">Loading preview</span></div>;
  return <PdfPreview src={url} title="Tailored resume preview" className="rounded-xl bg-slate-100 p-2 sm:p-3" />;
}

export default function AtsResultView({ data: initialData, jobId }) {
  const [data, setData] = useState(initialData);
  useEffect(() => { setData(initialData); }, [initialData]);
  const [version, setVersion] = useState(0);
  const [previewReady, setPreviewReady] = useState(false);
  const [selected, setSelected] = useState([]);
  const [regenerating, setRegenerating] = useState(false);
  const [notice, setNotice] = useState(null);
  const [downloading, setDownloading] = useState('');
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(null);
  const [job, setJob] = useState(null);   // the job this resume was tailored for, when started from one
  const [plan, setPlan] = useState(null);
  const [branding, setBranding] = useState(null);
  const [branded, setBranded] = useState(() => { try { return localStorage.getItem('brandedDownloads') === '1'; } catch { return false; } });
  useEffect(() => {
    axios.get(`${API}/billing/status`, { headers: headers() }).then(r => setPlan(r.data)).catch(() => {});
    axios.get(`${API}/branding`, { headers: headers() }).then(r => setBranding(r.data)).catch(() => {});
  }, []);
  const paid = !!plan && ['pro', 'enterprise'].includes(plan.plan) && plan.status === 'active';
  const brandingReady = branding?.enabled && branding?.configured;    // Enterprise with branding set up
  const toggleBranded = on => {
    setBranded(on);
    try { localStorage.setItem('brandedDownloads', on ? '1' : '0'); } catch { /* ignore */ }
  };
  useEffect(() => {
    if (!jobId) return;
    axios.get(`${API}/jobs/detail/${jobId}`).then(r => setJob(r.data)).catch(() => {});
  }, [jobId]);

  const resumeId = data?.resume_id || data?.task_id;
  const scores = data?.scores || {};
  const after = typeof scores.after === 'number' ? scores.after : data?.overall_score || 0;
  const before = typeof scores.before === 'number' ? scores.before : null;
  const requirements = useMemo(() => (data?.requirements || []).filter(r => r && typeof r === 'object'), [data]);
  const keywords = useMemo(() => {
    const seen = new Set();
    return requirements.map(r => ({ text: String(r.phrase || r.requirement || '').trim(), matched: !!r.matched }))
      .filter(k => k.text && k.text.length <= 40 && !seen.has(k.text.toLowerCase()) && seen.add(k.text.toLowerCase()))
      .sort((a, b) => Number(b.matched) - Number(a.matched)).slice(0, 16);
  }, [requirements]);
  const suggested = (data?.suggested_skills ?? data?.missing_list ?? []).filter(k => typeof k === 'string').slice(0, 12);
  const changes = (data?.suggestions_applied || []).map(String).filter(Boolean).slice(0, 6);
  const guard = data?.rewrite_guard || {};
  // Each bullet kept as written (newer results), else whole roles (older results), plus the summary.
  const reverted = (Number(guard.bullets_reverted ?? guard.roles_reverted) || 0) + (guard.summary_reverted ? 1 : 0);
  const revertedDetails = (Array.isArray(guard.reverted) ? guard.reverted : []).filter(r => r && typeof r === 'object').slice(0, 8);
  const leftOut = Number(data?.extraction_guard?.total_removed) || 0;   // items the AI read that are not in the file
  const doc = data?.document || {};
  const pageSize = typeof doc.page_size === 'string' ? doc.page_size : doc.region && ['US', 'CA'].includes(doc.region) ? 'Letter' : 'A4';

  const regenerate = async () => {
    if (!resumeId || !selected.length) return;
    setRegenerating(true); setNotice(null);
    try {
      const res = await axios.post(`${API}/resume/regenerate/${resumeId}`, { confirmed_keywords: selected }, { headers: headers() });
      setData(res.data.result); setSelected([]); setVersion(v => v + 1);
      setNotice({ ok: true, text: 'Regenerated with the skills you confirmed. Check the updated preview before downloading.' });
    } catch (err) {
      setNotice({ ok: false, text: await apiErrorMessage(err, 'The resume could not be regenerated. Please retry.') });
    } finally { setRegenerating(false); }
  };

  const download = async (kind) => {
    setDownloading(kind); setNotice(null);
    try {
      const base = kind === 'docx' ? `/resume/download/${resumeId}/docx` : `/resume/download/${resumeId}`;
      const path = brandingReady && branded ? `${base}?branded=true` : base;
      const res = await axios.get(`${API}${path}`, { headers: headers(), responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const link = Object.assign(document.createElement('a'), {
        href: url, download: filenameFromDisposition(res.headers['content-disposition'], kind === 'docx' ? 'Resume.docx' : 'Resume.pdf'),
      });
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      setNotice({ ok: false, text: await apiErrorMessage(err, 'The file could not be downloaded. Please retry.') });
    } finally { setDownloading(''); }
  };

  const apply = async () => {
    setApplying(true); setNotice(null);
    // Employer-hosted application: open their form now (before any await, so the browser allows the tab).
    if (job?.url) window.open(job.url, '_blank', 'noopener,noreferrer');
    try {
      const res = await axios.post(`${API}/jobs/${jobId}/apply`, { resume_id: resumeId }, { headers: headers() });
      setApplied(res.data);
    } catch (err) {
      setNotice({ ok: false, text: await apiErrorMessage(err, 'Could not apply with this resume. Please retry.') });
    } finally { setApplying(false); }
  };

  if (!data) return null;
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px] items-start">
      <section className={`${card} p-4 min-w-0`} aria-labelledby="preview-title">
        <div className="flex flex-wrap items-start justify-between gap-2 px-1 pb-3">
          <div>
            <h2 id="preview-title" className="font-semibold text-slate-900">Preview: tailored for {data.job_title || 'your target role'}</h2>
            <p className="text-xs text-slate-500">This is exactly the file you will download · {pageSize} · {doc.pages || 1} page{doc.pages > 1 ? 's' : ''}{doc.condensed ? ' · some lower-priority bullets were shortened to fit' : ''}</p>
          </div>
        </div>
        <ResumePreview resumeId={resumeId} version={version} onReady={setPreviewReady} />
      </section>

      <div className="space-y-4">
        <section className={`${card} p-5`} aria-labelledby="match-title">
          <div className="flex items-center gap-4">
            <Ring score={after} />
            <div>
              <h2 id="match-title" className="font-semibold text-slate-900">Job match</h2>
              {before !== null && <p className="text-xs text-slate-500">was {Math.round(before)}% before tailoring</p>}
            </div>
          </div>
          {keywords.length > 0 && <>
            <h3 className="mt-4 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Requirements from the job</h3>
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {keywords.map(k => (
                <li key={k.text} className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${k.matched ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>
                  {k.matched ? <Check size={11} aria-label="Found" /> : <X size={11} aria-label="Missing" />}{k.text}</li>))}
            </ul>
          </>}
          {suggested.length > 0 && (
            <div className="mt-4 rounded-xl bg-amber-50 ring-1 ring-amber-100 p-3 text-xs text-amber-900">
              <p><b>Not found in your resume:</b> tick only the ones you have genuinely used, and we will add them and regenerate.</p>
              <fieldset className="mt-2 flex flex-wrap gap-x-3 gap-y-1.5">
                <legend className="sr-only">Skills to confirm</legend>
                {suggested.map(s => (
                  <label key={s} className="inline-flex items-center gap-1.5 cursor-pointer">
                    <input type="checkbox" className="accent-emerald-600" checked={selected.includes(s)}
                      onChange={() => setSelected(c => (c.includes(s) ? c.filter(x => x !== s) : [...c, s]))} />{s}</label>))}
              </fieldset>
              <button type="button" onClick={regenerate} disabled={!selected.length || regenerating}
                className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-amber-900 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50">
                {regenerating ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
                {regenerating ? 'Regenerating…' : `Add ${selected.length || ''} and regenerate`}</button>
            </div>)}
        </section>

        <section className={`${card} p-5 text-sm`} aria-labelledby="changes-title">
          <h2 id="changes-title" className="font-semibold text-slate-900">What changed</h2>
          <ul className="mt-2 space-y-1.5 text-slate-600">
            {(changes.length ? changes : ['Summary and bullets re-ordered around the job’s main requirements',
              'Skills grouped to mirror the job’s wording']).map(c => <li key={c} className="flex gap-2"><Check size={14} className="mt-0.5 shrink-0 text-emerald-600" />{c}</li>)}
            <li className="flex gap-2"><Check size={14} className="mt-0.5 shrink-0 text-emerald-600" />Nothing invented: every claim comes from your original resume{reverted ? ` (${reverted} unsupported edit${reverted > 1 ? 's' : ''} reverted)` : ''}</li>
            {revertedDetails.length > 0 && (
              <li><details className="ml-6 text-xs text-slate-500"><summary className="cursor-pointer font-semibold text-slate-600">Why some lines were kept as written</summary>
                <ul className="mt-1.5 space-y-1.5">{revertedDetails.map((r, i) => (
                  <li key={i}><span className="font-medium text-slate-700">{[r.role, r.company].filter(Boolean).join(' · ')}</span>: the tailored line was not used because {String(r.reason || 'it could not be confirmed from your resume')}.{r.kept ? ` Your original line was kept: “${String(r.kept)}”` : ''}</li>))}</ul>
              </details></li>)}
            {leftOut > 0 && <li className="flex gap-2"><Check size={14} className="mt-0.5 shrink-0 text-emerald-600" />{leftOut} item{leftOut > 1 ? 's' : ''} that could not be found in your file {leftOut > 1 ? 'were' : 'was'} left out. Check the preview and add anything missing to your original resume.</li>}
          </ul>
        </section>

        <section className={`${card} p-5 space-y-2`} aria-label="Download">
          <button type="button" onClick={() => download('pdf')} disabled={!previewReady || !!downloading}
            className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
            {downloading === 'pdf' ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}Download PDF</button>
          <button type="button" onClick={() => download('docx')} disabled={!previewReady || !!downloading}
            className="w-full inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-60">
            {downloading === 'docx' ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}Download Word (.docx)</button>
          {brandingReady && (
            <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer px-1">
              <input type="checkbox" className="accent-emerald-600" checked={branded} onChange={e => toggleBranded(e.target.checked)} />
              Add my company branding to downloads</label>)}
          {resumeId && <ResumeEditPanel resumeId={resumeId} paid={paid} onSaved={result => {
            setData(result); setVersion(v => v + 1);
            setNotice({ ok: true, text: 'Saved. The preview shows your edited resume.' });
          }} />}
          {resumeId && (
            <a href={`/studio?from=${encodeURIComponent(resumeId)}`}
              className="w-full inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-800 hover:bg-slate-50">
              <PencilLine size={16} />Edit in Resume Studio</a>
          )}
          {!previewReady && <p className="text-xs text-slate-500 text-center">Downloads unlock once the preview has loaded.</p>}
          {jobId && job && !job.url && (
            <a href={`/apply/${jobId}?resume=${encodeURIComponent(resumeId)}`}
              className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800">
              <Send size={16} />Continue to the application form</a>)}
          {jobId && !applied && job?.url && (
            <button type="button" onClick={apply} disabled={applying || !previewReady}
              className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60">
              {applying ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}Apply on the employer’s site</button>)}
          {jobId && !applied && job?.url && <p className="text-xs text-slate-500 text-center">Opens {job.company ? `${job.company}’s` : 'the employer’s'} application form in a new tab and tracks it in Applications. Download your resume first to upload it there.</p>}
          {applied && (
            <div role="status" className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900">
              {applied.job_url ? `We opened ${job?.company ? `${job.company}’s` : 'the employer’s'} application form in a new tab and saved this job to Applications. Finish the form there, then mark it as submitted in Applications.`
                : applied.message || 'Application recorded.'}
              {applied.job_url && <a href={applied.job_url} target="_blank" rel="noopener noreferrer" className="mt-2 flex items-center gap-1 font-semibold">Tab didn’t open? Go to the employer’s form <ExternalLink size={13} /></a>}
              <a href="/applications" className="mt-1 block font-semibold">View my applications →</a>
            </div>)}
          {!jobId && <a href="/jobs" className="block text-center text-sm font-semibold text-slate-600 hover:text-slate-900">Find jobs that match this resume →</a>}
        </section>
        {notice && <p role={notice.ok ? 'status' : 'alert'} className={`rounded-xl p-3 text-sm ${notice.ok ? 'bg-emerald-50 text-emerald-800' : 'bg-rose-50 text-rose-700'}`}>{notice.text}</p>}
      </div>

      {(doc.warnings?.length > 0 || data.confirmation_questions?.length > 0 || requirements.length > 0) && (
        <div className="lg:col-span-2 space-y-4">
          {doc.warnings?.length > 0 && (
            <div role="note" className="flex gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              <AlertTriangle size={18} className="shrink-0 mt-0.5" /><div>{doc.warnings.map((w, i) => <p key={i}>{w}</p>)}</div></div>)}
          {data.confirmation_questions?.length > 0 && (
            <section className={`${card} p-5`}>
              <h2 className="font-semibold text-slate-900">Questions to strengthen your application</h2>
              <p className="text-sm text-slate-500 mt-1">The job asks for these. They are not in your resume, so nothing was added. Consider covering them in your cover letter or interview.</p>
              <ul className="mt-3 list-disc pl-5 space-y-1.5 text-sm text-slate-700">{data.confirmation_questions.map((q, i) => <li key={i}>{String(q)}</li>)}</ul>
            </section>)}
          {requirements.length > 0 && (
            <details className={`${card} p-5`}>
              <summary className="font-semibold text-slate-900 cursor-pointer">Requirement-by-requirement evidence</summary>
              <ul className="mt-3 divide-y divide-slate-100 text-sm">
                {requirements.map((r, i) => (
                  <li key={i} className="py-2.5">
                    <div className="flex flex-wrap items-center gap-2"><span className="font-medium text-slate-800">{r.requirement || r.phrase}</span>
                      {r.priority && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">{r.priority}</span>}
                      <span className={`text-[11px] font-semibold ${r.matched ? 'text-emerald-700' : 'text-rose-700'}`}>{r.match === 'equivalent' ? 'Met by an equivalent' : r.matched ? 'Evidence found' : 'Not found'}</span></div>
                    {r.evidence && <p className="mt-1 text-slate-500">{r.evidence}</p>}
                  </li>))}
              </ul>
            </details>)}
        </div>)}
    </div>
  );
}
