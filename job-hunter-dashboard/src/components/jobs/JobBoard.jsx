import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import {
  BadgeCheck, Briefcase, Calendar, Clock, ExternalLink, Globe, Loader2, MapPin, Search, Sparkles, Wallet, X,
} from 'lucide-react';
import { errorText } from '../../lib/session';
import PartnerBanner from './PartnerBanner';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const auth = () => (localStorage.getItem('token') ? { Authorization: `Bearer ${localStorage.getItem('token')}` } : {});

const PAGE_SIZE = 20;
const MAX_PAGES = 200;   // the API serves pages 1-200; narrow the search to see more

// Page numbers to show: always first and last, the current page and two
// neighbours either side, with gaps marked as null ("…").
function pageWindow(current, total) {
  const pages = new Set([1, total, current - 2, current - 1, current, current + 1, current + 2].filter(n => n >= 1 && n <= total));
  const sorted = [...pages].sort((a, b) => a - b);
  return sorted.flatMap((n, i) => (i && n - sorted[i - 1] > 1 ? [null, n] : [n]));
}

function Pagination({ page, totalPages, onPage, disabled }) {
  if (totalPages <= 1) return null;
  const btn = 'min-w-[36px] h-9 px-2.5 rounded-lg text-sm font-medium border transition-colors disabled:opacity-40 disabled:cursor-not-allowed';
  return (
    <nav aria-label="Job results pages" className="flex flex-wrap items-center justify-center gap-1.5 pt-1">
      <button type="button" onClick={() => onPage(page - 1)} disabled={disabled || page <= 1} aria-label="Previous page" title="Previous page"
        className={`${btn} bg-white border-slate-200 text-slate-700 hover:bg-slate-50`}>‹</button>
      {pageWindow(page, totalPages).map((n, i) => (n === null
        ? <span key={`gap-${i}`} className="px-1 text-slate-400" aria-hidden="true">…</span>
        : <button key={n} type="button" onClick={() => onPage(n)} disabled={disabled} aria-current={n === page ? 'page' : undefined}
            aria-label={`Page ${n}`}
            className={`${btn} ${n === page ? 'bg-slate-900 border-slate-900 text-white' : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'}`}>{n}</button>))}
      <button type="button" onClick={() => onPage(page + 1)} disabled={disabled || page >= totalPages} aria-label="Next page" title="Next page"
        className={`${btn} bg-white border-slate-200 text-slate-700 hover:bg-slate-50`}>›</button>
      <span className="w-full text-center text-xs text-slate-500 mt-1">Page {page} of {totalPages.toLocaleString()}</span>
    </nav>
  );
}

const CATEGORIES = [['', 'All categories'], ['engineering', 'Software engineering'], ['devops', 'DevOps & cloud'],
  ['data', 'Data & AI'], ['security', 'Security'], ['mobile', 'Mobile'], ['qa', 'QA & testing'], ['product', 'Product & design']];
const REGIONS = [['', 'Anywhere'], ['worldwide', 'Worldwide remote'], ['africa', 'Africa'], ['europe', 'Europe'],
  ['uk', 'United Kingdom'], ['us', 'United States'], ['canada', 'Canada'], ['asia', 'Asia-Pacific']];
const POSTED = [['', 'Any time'], ['1', 'Last 24 hours'], ['3', 'Last 3 days'], ['7', 'Last 7 days'], ['14', 'Last 14 days']];
const WORK = [['', 'All work types'], ['remote', 'Remote'], ['hybrid', 'Hybrid'], ['onsite', 'On-site']];
const LOGO_COLORS = ['bg-blue-600', 'bg-emerald-600', 'bg-violet-600', 'bg-orange-500', 'bg-rose-600', 'bg-sky-600', 'bg-amber-600', 'bg-teal-600'];

function ago(iso) {
  if (!iso) return null;
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (days <= 0) return 'Posted today';
  if (days === 1) return 'Posted yesterday';
  if (days < 30) return `Posted ${days} days ago`;
  return `Posted ${new Date(iso).toLocaleDateString()}`;
}
const workLabel = (w) => ({ remote: 'Remote', hybrid: 'Hybrid', onsite: 'On-site' }[w] || null);
// "Remote · Europe" -> "Europe" when the work type already says Remote.
const placeLabel = (job) => {
  const loc = (job.location || '').trim();
  const stripped = job.work_type === 'remote' ? loc.replace(/^remote\s*[·\-–:,]\s*/i, '').trim() : loc;
  return stripped && stripped.toLowerCase() !== 'remote' ? stripped : null;
};

function Logo({ job, size = 'md' }) {
  const [failed, setFailed] = useState(false);
  const dims = size === 'lg' ? 'w-14 h-14 text-xl rounded-2xl' : 'w-11 h-11 text-base rounded-xl';
  const color = LOGO_COLORS[(job.company || '?').charCodeAt(0) % LOGO_COLORS.length];
  if (job.company_logo && !failed) {
    return <img src={job.company_logo} alt="" referrerPolicy="no-referrer" onError={() => setFailed(true)}
      className={`${dims} object-contain bg-white border border-slate-200 shrink-0`} />;
  }
  return <div className={`${dims} ${color} text-white grid place-items-center font-bold shrink-0`} aria-hidden="true">
    {(job.company || '?').trim().charAt(0).toUpperCase()}</div>;
}

function MatchChip({ match }) {
  if (!match) return null;
  const tone = match.score >= 75 ? 'bg-emerald-600 text-white' : match.score >= 50 ? 'bg-emerald-50 text-emerald-800' : 'bg-amber-50 text-amber-800';
  return <span className={`shrink-0 h-fit text-[11px] font-semibold px-2 py-0.5 rounded-full ${tone}`}>{match.score}% match</span>;
}

// Plain-text job descriptions become headed sections and bullet lists.
function Description({ text }) {
  const blocks = useMemo(() => {
    const out = [];
    for (const raw of (text || '').split('\n')) {
      const line = raw.trim();
      if (!line) continue;
      const bullet = /^[-•*·]\s+/.test(line);
      const heading = !bullet && line.length < 70 && (/:$/.test(line) || (/^[A-Z][^.!?]*$/.test(line) && line.split(' ').length <= 7));
      if (heading) out.push({ type: 'h', text: line.replace(/:$/, '') });
      else if (bullet) {
        const last = out[out.length - 1];
        const item = line.replace(/^[-•*·]\s+/, '');
        if (last?.type === 'ul') last.items.push(item); else out.push({ type: 'ul', items: [item] });
      } else out.push({ type: 'p', text: line });
    }
    return out;
  }, [text]);
  if (!blocks.length) return <p className="text-sm text-slate-500">The full description is on the original posting.</p>;
  return (
    <div className="space-y-3 text-sm leading-6 text-slate-700">
      {blocks.map((b, i) => b.type === 'h' ? <h3 key={i} className="font-semibold text-slate-900 pt-2">{b.text}</h3>
        : b.type === 'ul' ? <ul key={i} className="list-disc pl-5 space-y-1">{b.items.map((it, j) => <li key={j}>{it}</li>)}</ul>
          : <p key={i}>{b.text}</p>)}
    </div>
  );
}

function JobCard({ job, selected, onSelect }) {
  return (
    <button type="button" onClick={() => onSelect(job)} aria-current={selected ? 'true' : undefined}
      className={`w-full min-w-0 overflow-hidden text-left bg-white border rounded-2xl p-4 transition-colors ${selected ? 'border-emerald-500 ring-2 ring-emerald-500' : 'border-slate-200 hover:border-emerald-300'}`}>
      <div className="flex gap-3">
        <Logo job={job} />
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-slate-900 truncate">{job.title}</h3>
          <p className="text-[13px] text-slate-600 flex flex-wrap items-center gap-x-2">
            <span className="truncate">{job.company}</span>
            {job.is_employer && <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 rounded-full px-2 py-0.5"><BadgeCheck size={12} />Hiring on Baalebos</span>}
          </p>
          <p className="text-xs text-slate-500 mt-1 line-clamp-1">
            {[workLabel(job.work_type), placeLabel(job), job.salary_range || null].filter(Boolean).join(' · ')}
          </p>
        </div>
        <MatchChip match={job.match} />
      </div>
      {job.skills?.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {job.skills.slice(0, 5).map(s => <span key={s} className="text-[11px] font-medium bg-slate-100 text-slate-700 rounded-full px-2 py-0.5">{s}</span>)}
        </div>
      )}
      <div className="mt-3 flex justify-between text-xs text-slate-400">
        <span>{[ago(job.posted_at), !job.is_employer && job.source ? `via ${job.source}` : null].filter(Boolean).join(' · ')}</span>
        <span>{job.employment_type || ''}</span>
      </div>
    </button>
  );
}

function JobDetail({ jobId, onApply, lastTaskId, onClose }) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [applyError, setApplyError] = useState('');
  const [attach, setAttach] = useState(false);
  useEffect(() => {
    let active = true;
    setJob(null); setError(''); setResult(null); setApplyError(''); setAttach(false);
    axios.get(`${API}/jobs/board/${jobId}`, { headers: auth() })
      .then(r => { if (active) setJob(r.data); })
      .catch(err => { if (active) setError(errorText(err, 'This job could not be loaded.')); });
    return () => { active = false; };
  }, [jobId]);

  const apply = async () => {
    setBusy(true); setApplyError('');
    try { setResult(await onApply(job.id, job.url, attach ? lastTaskId : null)); }
    catch (err) { setApplyError(errorText(err, 'Could not prepare your application. Please retry.')); }
    finally { setBusy(false); }
  };

  if (error) return <div className="p-6 text-sm text-rose-700">{error}</div>;
  if (!job) return <div className="py-20 flex justify-center"><Loader2 className="animate-spin text-emerald-600" /></div>;
  const facts = [[MapPin, workLabel(job.work_type)], [Globe, placeLabel(job)], [Wallet, job.salary_range],
    [Clock, job.employment_type], [Calendar, ago(job.posted_at)]].filter(([, v]) => v);
  return (
    <article className="p-6" aria-labelledby="job-detail-title">
      <div className="flex gap-4">
        <Logo job={job} size="lg" />
        <div className="flex-1 min-w-0">
          <h2 id="job-detail-title" className="text-xl font-semibold text-slate-900">{job.title}</h2>
          <p className="text-slate-600">{job.company}{job.is_employer && <span className="text-emerald-700 font-medium"> · Verified employer</span>}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {facts.map(([Icon, v]) => <span key={v} className="inline-flex items-center gap-1 text-xs bg-slate-100 text-slate-700 rounded-full px-2.5 py-1"><Icon size={12} />{v}</span>)}
          </div>
        </div>
        {onClose && <button type="button" onClick={onClose} aria-label="Close job details" className="h-fit p-1 rounded-lg hover:bg-slate-100"><X size={20} /></button>}
      </div>

      {job.match ? (
        <div className="mt-5 rounded-xl bg-emerald-50 ring-1 ring-emerald-100 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2"><div className="font-semibold text-emerald-900">Your resume matches {job.match.score}%</div>
            <span className="text-xs text-emerald-800">based on your latest resume and profile skills</span></div>
          <p className="text-sm text-emerald-900 mt-1">
            {job.match.matched.length > 0 && <>Matches: {job.match.matched.join(', ')}</>}
            {job.match.missing.length > 0 && <span className="text-rose-700"> · Missing: {job.match.missing.join(', ')}</span>}
          </p>
        </div>
      ) : localStorage.getItem('token') ? (
        <p className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">Upload a resume in the Resume workspace to see how well you match each job.</p>
      ) : null}

      {result ? (
        <div className="mt-5 border border-emerald-200 bg-emerald-50 p-5 rounded-xl">
          <h3 className="font-semibold">{result.status === 'submitted_internal' ? 'Application sent on Baalebos' : 'Application tracked'}</h3>
          <p className="text-sm mt-2">{result.message}</p>
          {result.job_url && <a href={result.job_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 bg-emerald-700 text-white rounded-xl px-5 py-3 mt-4 text-sm font-semibold">Complete on the employer&apos;s site <ExternalLink size={16} /></a>}
        </div>
      ) : (
        <div className="mt-5 space-y-3">
          <div className="flex flex-wrap gap-2">
            <a href={`/optimizer?job=${job.id}`} className="inline-flex items-center gap-2 text-sm font-semibold rounded-xl px-4 py-2.5 bg-emerald-600 text-white hover:bg-emerald-700"><Sparkles size={16} />Tailor my resume to this job</a>
            <button type="button" disabled={busy} onClick={apply} className="inline-flex items-center gap-2 text-sm font-semibold rounded-xl px-4 py-2.5 bg-slate-900 text-white hover:bg-slate-800 disabled:opacity-60">
              {busy ? <Loader2 size={16} className="animate-spin" /> : <Briefcase size={16} />}
              {job.url ? 'Track and apply on employer site' : 'Apply on Baalebos'}</button>
            {job.url && <a href={job.url} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1.5 text-sm font-semibold rounded-xl px-4 py-2.5 border border-slate-200 hover:bg-slate-50">Original posting <ExternalLink size={14} /></a>}
          </div>
          {lastTaskId && <label className="flex gap-2 items-center text-sm text-slate-600"><input type="checkbox" checked={attach} onChange={e => setAttach(e.target.checked)} className="accent-emerald-600" />Attach my latest tailored resume</label>}
          {applyError && <p role="alert" className="text-sm text-rose-700 bg-rose-50 rounded-xl p-3">{applyError}</p>}
        </div>
      )}

      <hr className="my-6 border-slate-100" />
      <Description text={job.description} />
      <p className="mt-6 rounded-xl bg-slate-50 p-4 text-xs text-slate-500">Check location restrictions, work authorisation and requirements on the original posting before applying.</p>
    </article>
  );
}

export default function JobBoard({ onApply, lastTaskId }) {
  const [draft, setDraft] = useState({ q: '', category: '', region: '', posted_within: '' });
  const [filters, setFilters] = useState({ q: '', category: '', region: '', posted_within: '', work_type: '', employer_only: false, has_salary: false });
  const [sort, setSort] = useState('best');
  const [items, setItems] = useState([]);
  const [meta, setMeta] = useState(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);
  const [isWide, setIsWide] = useState(() => window.matchMedia('(min-width: 1024px)').matches);
  const wideRef = useRef(isWide);
  const listTop = useRef(null);
  wideRef.current = isWide;

  useEffect(() => {
    const media = window.matchMedia('(min-width: 1024px)');
    const update = () => setIsWide(media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  const load = useCallback(async (nextPage) => {
    setLoading(true); setError('');
    try {
      const params = { sort, page: nextPage, page_size: PAGE_SIZE, ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) };
      const { data } = await axios.get(`${API}/jobs/board`, { params, headers: auth() });
      setItems(data.items);            // one page at a time
      setMeta(data); setPage(nextPage);
      setSelected(sel => (wideRef.current ? (data.items[0] || null) : sel && data.items.find(j => j.id === sel.id) ? sel : null));
    } catch (err) { setError(errorText(err, 'Jobs could not be loaded. Please retry.')); }
    finally { setLoading(false); }
  }, [filters, sort]);
  useEffect(() => { load(1); }, [load]);

  const totalPages = meta ? Math.min(MAX_PAGES, Math.max(1, Math.ceil(meta.total / (meta.page_size || PAGE_SIZE)))) : 1;
  const goToPage = (next) => {
    if (next < 1 || next > totalPages || next === page) return;
    load(next);
    listTop.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
  const search = (e) => { e.preventDefault(); setFilters(f => ({ ...f, ...draft, q: draft.q.trim() })); };
  const toggle = (key) => setFilters(f => ({ ...f, [key]: !f[key] }));
  const select = (job) => { setSelected(job); if (!isWide) window.scrollTo({ top: 0 }); };
  const selectCls = 'text-sm border border-slate-200 rounded-xl px-3 py-2.5 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/40';
  const chip = (on) => `px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${on ? 'bg-slate-900 text-white border-slate-900' : 'bg-white border-slate-200 text-slate-700 hover:border-slate-400'}`;

  return (
    <div>
      <form onSubmit={search} className="bg-white border border-slate-200 rounded-2xl p-3 sm:p-4 flex flex-wrap items-center gap-2" role="search">
        <div className="relative flex-1 min-w-[220px]">
          <Search size={16} className="absolute left-3 top-3 text-slate-400" />
          <input value={draft.q} onChange={e => setDraft(d => ({ ...d, q: e.target.value }))} placeholder="Job title, skill or company"
            aria-label="Search jobs" className="w-full pl-9 pr-3 py-2.5 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500/40" />
        </div>
        <select aria-label="Category" value={draft.category} onChange={e => setDraft(d => ({ ...d, category: e.target.value }))} className={selectCls}>
          {CATEGORIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        <select aria-label="Location" value={draft.region} onChange={e => setDraft(d => ({ ...d, region: e.target.value }))} className={selectCls}>
          {REGIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        <select aria-label="Date posted" value={draft.posted_within} onChange={e => setDraft(d => ({ ...d, posted_within: e.target.value }))} className={selectCls}>
          {POSTED.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        <button type="submit" className="text-sm font-semibold rounded-xl px-5 py-2.5 bg-emerald-600 text-white hover:bg-emerald-700">Search</button>
      </form>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {WORK.map(([v, l]) => <button key={v} type="button" onClick={() => setFilters(f => ({ ...f, work_type: v }))} aria-pressed={filters.work_type === v} className={chip(filters.work_type === v)}>{l}</button>)}
        <span className="mx-1 text-slate-300 hidden sm:inline">|</span>
        <button type="button" onClick={() => toggle('employer_only')} aria-pressed={filters.employer_only}
          className={`px-3 py-1.5 rounded-full text-xs font-medium border ${filters.employer_only ? 'bg-emerald-600 text-white border-emerald-600' : 'bg-emerald-50 text-emerald-800 border-emerald-200'}`}>
          <BadgeCheck size={12} className="inline -mt-0.5 mr-1" />Hiring on Baalebos</button>
        <button type="button" onClick={() => toggle('has_salary')} aria-pressed={filters.has_salary} className={chip(filters.has_salary)}>Shows salary</button>
        <div className="ml-auto flex items-center gap-2 text-xs text-slate-500">
          {meta && <span>{meta.total.toLocaleString()} jobs{meta.updated_at ? ` · updated ${new Date(meta.updated_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}` : ''}</span>}
          <label className="flex items-center gap-1">Sort
            <select value={sort} onChange={e => setSort(e.target.value)} className="border border-slate-200 rounded-lg px-2 py-1 bg-white text-slate-800 font-medium">
              <option value="best">{meta?.personalised ? 'Best match' : 'Recommended'}</option><option value="newest">Newest</option></select></label>
        </div>
      </div>

      <PartnerBanner />

      {error && <p role="alert" className="mt-4 text-sm text-rose-700 bg-rose-50 rounded-xl p-4">{error} <button type="button" onClick={() => load(1)} className="font-semibold underline">Retry</button></p>}

      <div ref={listTop} className="mt-4 grid grid-cols-1 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)] gap-4 items-start scroll-mt-4">
        <div className={`min-w-0 space-y-3 ${!isWide && selected ? 'hidden' : ''}`}>
          {!loading && items.map(job => <JobCard key={job.id} job={job} selected={selected?.id === job.id} onSelect={select} />)}
          {!loading && !items.length && !error && (
            <div className="bg-white border border-dashed border-slate-300 rounded-2xl p-10 text-center text-sm text-slate-500">
              No jobs match these filters. Try a broader search or clear a filter.</div>)}
          {loading && <div className="py-10 flex justify-center"><Loader2 className="animate-spin text-emerald-600" /></div>}
          {meta && items.length > 0 && <Pagination page={page} totalPages={totalPages} onPage={goToPage} disabled={loading} />}
        </div>
        {selected && (
          <div className="min-w-0 bg-white border border-slate-200 rounded-2xl lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto">
            <JobDetail jobId={selected.id} onApply={onApply} lastTaskId={lastTaskId} onClose={isWide ? null : () => setSelected(null)} />
          </div>
        )}
      </div>
    </div>
  );
}
