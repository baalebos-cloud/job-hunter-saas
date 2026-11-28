import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { CheckCircle2, Loader2, Plus, Search, Upload, X, XCircle } from 'lucide-react';
import { errorText } from '../../lib/session';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const MAX_JOBS = 10;
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });
const field = 'w-full border border-slate-200 rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/40';

// Enterprise: tailor one resume to up to 10 jobs at once. Each result is saved to My resumes.
export default function BulkTailor() {
  const fileRef = useRef(null);
  const [file, setFile] = useState(null);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [picked, setPicked] = useState([]);              // [{id, title, company}]
  const [pasted, setPasted] = useState([]);              // [{title, description}]
  const [draft, setDraft] = useState({ title: '', description: '' });
  const [error, setError] = useState('');
  const [starting, setStarting] = useState(false);
  const [batch, setBatch] = useState(null);              // status from /resume/bulk/{id}
  const [kept, setKept] = useState(null);                // the resume kept on the profile, if any
  const [region, setRegion] = useState('');
  const [pages, setPages] = useState('');
  useEffect(() => {
    axios.get(`${API}/profile/resume`, { headers: headers() }).then(r => setKept(r.data?.resume || null)).catch(() => {});
  }, []);
  const useKept = !!kept && !file;

  const count = picked.length + pasted.length;
  const full = count >= MAX_JOBS;

  const search = async (e) => {
    e?.preventDefault();
    setSearching(true);
    try {
      const { data } = await axios.get(`${API}/jobs/board`, { params: { q: query.trim(), page_size: 10 }, headers: headers() });
      setResults(data.items || []);
    } catch (err) { setError(errorText(err, 'Jobs could not be loaded.')); }
    finally { setSearching(false); }
  };
  useEffect(() => { search(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = (job) => setPicked(list => (list.some(j => j.id === job.id)
    ? list.filter(j => j.id !== job.id)
    : full ? list : [...list, { id: job.id, title: job.title, company: job.company }]));

  const addPasted = () => {
    if (!draft.title.trim() || draft.description.trim().length < 50) {
      setError('Add a job title and the full job description (at least 50 characters).'); return;
    }
    setPasted(list => [...list, { title: draft.title.trim(), description: draft.description.trim() }]);
    setDraft({ title: '', description: '' }); setError('');
  };

  const start = async () => {
    setError('');
    if (!file && !kept) return setError('Choose your resume first.');
    if (!count) return setError('Choose at least one job.');
    const form = new FormData();
    if (file) form.append('file', file);
    else form.append('use_profile_resume', 'true');      // the resume kept on the profile
    if (region) form.append('region', region);
    if (pages) form.append('max_pages', pages);
    if (picked.length) form.append('job_ids', picked.map(j => j.id).join(','));
    if (pasted.length) form.append('pasted_jobs', JSON.stringify(pasted));
    setStarting(true);
    try {
      const { data } = await axios.post(`${API}/resume/bulk`, form, { headers: headers(), timeout: 120000 });
      setBatch({ batch_id: data.batch_id, items: [], done: 0, total: data.count });
    } catch (err) { setError(errorText(err, 'Bulk tailoring could not start. Please retry.')); }
    finally { setStarting(false); }
  };

  useEffect(() => {
    if (!batch?.batch_id || (batch.total && batch.done >= batch.total)) return undefined;
    const timer = setInterval(async () => {
      try {
        const { data } = await axios.get(`${API}/resume/bulk/${batch.batch_id}`, { headers: headers() });
        setBatch(data);
      } catch { /* keep polling through brief network errors */ }
    }, 3000);
    return () => clearInterval(timer);
  }, [batch?.batch_id, batch?.done, batch?.total]);

  if (batch) {
    const finished = batch.total && batch.done >= batch.total;
    return (
      <div className="bg-white border border-slate-200 rounded-2xl p-5" role="status">
        <div className="flex items-center justify-between gap-3">
          <h3 className="font-semibold text-slate-900">Tailoring for {batch.total} jobs</h3>
          <span className="text-sm text-slate-500">{batch.done} of {batch.total} done</span>
        </div>
        <div className="mt-3 h-2 rounded-full bg-slate-100 overflow-hidden">
          <div className="h-full bg-emerald-500 transition-all" style={{ width: `${batch.total ? (100 * batch.done) / batch.total : 0}%` }} />
        </div>
        <ul className="mt-4 divide-y divide-slate-100">
          {(batch.items.length ? batch.items : Array.from({ length: batch.total }, (_, i) => ({ task_id: i, status: 'processing' }))).map(item => (
            <li key={item.task_id} className="py-2.5 flex items-center gap-3 text-sm">
              {item.status === 'completed' ? <CheckCircle2 size={18} className="text-emerald-600" />
                : item.status === 'failed' ? <XCircle size={18} className="text-rose-600" />
                : <Loader2 size={18} className="animate-spin text-slate-400" />}
              <span className="flex-1 min-w-0 truncate">{item.job_title || 'Preparing…'}{item.company ? ` · ${item.company}` : ''}</span>
              {item.status === 'completed' && item.score_after != null && <span className="font-semibold text-emerald-700">{Math.round(item.score_after)}% match</span>}
              {item.status === 'failed' && <span className="text-xs text-rose-700 truncate max-w-[45%]" title={item.error}>{item.error}</span>}
            </li>))}
        </ul>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link to="/resumes" className="text-sm font-semibold rounded-xl px-4 py-2 bg-emerald-600 text-white hover:bg-emerald-700">Open My resumes</Link>
          {finished && <button type="button" onClick={() => { setBatch(null); setPicked([]); setPasted([]); }}
            className="text-sm font-semibold rounded-xl px-4 py-2 border border-slate-200 hover:bg-slate-50">Start another batch</button>}
        </div>
        {!finished && <p className="mt-3 text-xs text-slate-500">You can leave this page; results keep arriving in My resumes.</p>}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <section className="bg-white border border-slate-200 rounded-2xl p-5">
        <h3 className="font-semibold text-slate-900">1 · Your resume</h3>
        <input ref={fileRef} type="file" accept=".pdf,.docx" className="hidden" aria-label="Resume file"
          onChange={e => setFile(e.target.files?.[0] || null)} />
        <button type="button" onClick={() => fileRef.current?.click()}
          className="mt-3 w-full flex items-center gap-3 border-2 border-dashed border-slate-200 rounded-xl p-4 text-left hover:border-emerald-300">
          <Upload size={18} className="text-slate-400" />
          <span className="text-sm">{file ? <strong>{file.name}</strong>
            : useKept ? <><strong>{kept.filename}</strong> <span className="text-slate-500">· the resume on your profile · click to use a different file</span></>
            : 'Choose your current resume (PDF or DOCX, up to 10 MB)'}</span>
        </button>
        {file && kept && <button type="button" onClick={() => { setFile(null); if (fileRef.current) fileRef.current.value = ''; }}
          className="mt-2 text-xs font-semibold text-emerald-700 hover:underline">Use the resume on my profile instead ({kept.filename})</button>}
        <div className="mt-4 grid sm:grid-cols-2 gap-3">
          <label className="block text-sm font-medium text-slate-700" htmlFor="bulk-region">Resume convention
            <select id="bulk-region" value={region} onChange={e => setRegion(e.target.value)} className={`${field} mt-1.5`}>
              <option value="">Auto (from my profile country)</option>
              <option value="US">United States (Letter)</option>
              <option value="CA">Canada (Letter)</option>
              <option value="UK">United Kingdom (A4)</option>
              <option value="EU">European Union (A4)</option>
              <option value="NG">Nigeria (A4)</option>
              <option value="OTHER">Other / international (A4)</option>
            </select></label>
          <label className="block text-sm font-medium text-slate-700" htmlFor="bulk-pages">Length
            <select id="bulk-pages" value={pages} onChange={e => setPages(e.target.value)} className={`${field} mt-1.5`}>
              <option value="">Usual for the convention</option>
              <option value="1">1 page</option>
              <option value="auto">1 page if it fits, otherwise 2</option>
              <option value="2">Up to 2 pages</option>
            </select></label>
        </div>
      </section>

      <section className="bg-white border border-slate-200 rounded-2xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-semibold text-slate-900">2 · Jobs to tailor for</h3>
          <span className={`text-sm ${full ? 'text-amber-700 font-semibold' : 'text-slate-500'}`}>{count} of {MAX_JOBS} chosen</span>
        </div>
        {count > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {picked.map(j => (
              <span key={`j${j.id}`} className="inline-flex items-center gap-1.5 text-xs bg-emerald-50 text-emerald-800 rounded-full px-3 py-1">
                {j.title} · {j.company}<button type="button" aria-label={`Remove ${j.title}`} onClick={() => toggle(j)}><X size={12} /></button></span>))}
            {pasted.map((p, i) => (
              <span key={`p${i}`} className="inline-flex items-center gap-1.5 text-xs bg-slate-100 text-slate-700 rounded-full px-3 py-1">
                {p.title} (pasted)<button type="button" aria-label={`Remove ${p.title}`} onClick={() => setPasted(l => l.filter((_, k) => k !== i))}><X size={12} /></button></span>))}
          </div>)}
        <form onSubmit={search} className="mt-4 relative">
          <Search size={16} className="absolute left-3 top-2.5 text-slate-400" />
          <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search the job board" aria-label="Search jobs" className={`${field} pl-9`} />
        </form>
        <ul className="mt-2 max-h-72 overflow-y-auto divide-y divide-slate-100 border border-slate-100 rounded-xl">
          {searching && <li className="p-4 flex justify-center"><Loader2 className="animate-spin text-emerald-600" /></li>}
          {!searching && results.map(job => {
            const on = picked.some(j => j.id === job.id);
            return (
              <li key={job.id}>
                <label className={`flex items-center gap-3 px-3 py-2.5 text-sm ${!on && full ? 'opacity-50' : 'cursor-pointer hover:bg-slate-50'}`}>
                  <input type="checkbox" className="accent-emerald-600" checked={on} disabled={!on && full} onChange={() => toggle(job)} />
                  <span className="flex-1 min-w-0 truncate"><strong>{job.title}</strong> · {job.company}</span>
                  {job.match?.score != null && <span className="text-xs text-emerald-700">{job.match.score}% match</span>}
                </label>
              </li>);
          })}
          {!searching && !results.length && <li className="p-4 text-sm text-slate-500">No jobs found.</li>}
        </ul>
        <details className="mt-4">
          <summary className="text-sm font-medium text-slate-700 cursor-pointer">Paste a job that isn&apos;t on the board</summary>
          <div className="mt-3 space-y-2">
            <input value={draft.title} onChange={e => setDraft(d => ({ ...d, title: e.target.value }))} placeholder="Job title" aria-label="Pasted job title" className={field} />
            <textarea value={draft.description} onChange={e => setDraft(d => ({ ...d, description: e.target.value }))} rows={4}
              placeholder="Full job description" aria-label="Pasted job description" className={field} />
            <button type="button" onClick={addPasted} disabled={full}
              className="inline-flex items-center gap-1.5 text-sm font-semibold rounded-xl px-3 py-2 border border-slate-200 hover:bg-slate-50 disabled:opacity-50"><Plus size={14} />Add this job</button>
          </div>
        </details>
      </section>

      {error && <p role="alert" className="text-sm text-rose-700 bg-rose-50 rounded-xl p-3">{error}</p>}
      <button type="button" onClick={start} disabled={starting}
        className="inline-flex items-center gap-2 text-sm font-semibold rounded-xl px-5 py-2.5 bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-60">
        {starting && <Loader2 size={16} className="animate-spin" />}Tailor for {count || ''} {count === 1 ? 'job' : 'jobs'}</button>
    </div>
  );
}
