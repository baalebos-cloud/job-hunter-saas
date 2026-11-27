// Resume Studio: edit a single-column ATS resume by hand, check it, and download a
// real-text PDF built in the browser. Saved to the account (and as a local draft).
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle2, ClipboardCopy, Columns2, Download, FileSearch, FileText, Loader2, PencilLine, Printer, RotateCcw, ScanSearch, UserRound } from 'lucide-react';
import type { Paper, ResumeData } from '../types';
import { emptyResume } from '../types';
import { analyzeJobDescription, analyzeResumeAts, buildPlainTextResume } from '../atsAnalyzer';
import { ROLE_PRESETS, applyRolePreset } from '../presets';
import { needsUnicodeFont } from '../text';
import * as studioApi from './studioApi';
import type { TailoredSource } from './studioApi';
import Editor, { EDITOR_TABS } from './Editor';
import type { EditorTab } from './Editor';
import PaperPreview from './PaperPreview';

type View = 'split' | 'edit' | 'ats' | 'preview';
const VIEWS: Array<[View, string, typeof Columns2]> = [
  ['split', 'Split Studio', Columns2], ['edit', 'Edit Sections', PencilLine], ['ats', 'ATS Audit', ScanSearch], ['preview', 'Full Preview', FileSearch],
];
const DRAFT_KEY = 'studioDraft:v1';
interface Draft { data: ResumeData; paper: Paper; preset: string; jd: string; savedAt: number }

const readDraft = (): Draft | null => {
  try { const raw = localStorage.getItem(DRAFT_KEY); return raw ? JSON.parse(raw) as Draft : null; } catch { return null; }
};
const writeDraft = (d: Draft) => { try { localStorage.setItem(DRAFT_KEY, JSON.stringify(d)); } catch { /* storage full or blocked */ } };
const clearDraft = () => { try { localStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ } };
const withDefaults = (d: Partial<ResumeData> | null | undefined): ResumeData => ({ ...emptyResume(), ...(d ?? {}) });

function fileName(name: string) {
  const base = name.trim().replace(/[^\p{L}\p{N}]+/gu, '_').replace(/^_+|_+$/g, '');
  return `${base || 'Resume'}_Resume.pdf`;
}

async function buildPdf(data: ResumeData, paper: Paper): Promise<Blob> {
  const [{ generateResumePdf }, { loadUnicodeFonts }] = await Promise.all([import('../pdfEngine'), import('../fonts')]);
  const unicodeFonts = needsUnicodeFont(JSON.stringify(data)) ? await loadUnicodeFonts() : undefined;
  const bytes = await generateResumePdf(data, { paper, unicodeFonts });
  return new Blob([bytes as BlobPart], { type: 'application/pdf' });
}

function StartScreen({ onStart, busy, error }: { onStart: (kind: 'profile' | 'blank' | string) => void; busy: string; error: string }) {
  const [sources, setSources] = useState<TailoredSource[] | null>(null);
  useEffect(() => { studioApi.listSources().then(s => setSources(s.tailored)).catch(() => setSources([])); }, []);
  const card = 'w-full text-left rounded-xl border border-slate-200 bg-white p-4 hover:border-emerald-600 hover:shadow-sm disabled:opacity-50 flex gap-3';
  return (
    <div className="max-w-2xl mx-auto py-6 space-y-5">
      <div>
        <p className="text-sm text-slate-600">Edit your resume section by section, check it against a job description, and download a PDF whose text every ATS can read. Choose where to start; you can change everything afterwards.</p>
      </div>
      {error && <p className="text-sm text-rose-700 bg-rose-50 rounded-xl p-3">{error}</p>}
      <button type="button" className={card} disabled={!!busy} onClick={() => onStart('profile')}>
        <UserRound className="shrink-0 text-emerald-700" size={20} />
        <span><span className="block font-semibold text-slate-900">From my profile</span>
          <span className="block text-sm text-slate-500">Copies your name, contact details, about, experience, education and skills.</span></span>
        {busy === 'profile' && <Loader2 className="ml-auto animate-spin text-slate-400" size={18} />}
      </button>
      {sources === null ? <p className="text-sm text-slate-500 flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Loading your tailored resumes…</p>
        : sources.map(s => (
          <button key={s.task_id} type="button" className={card} disabled={!!busy} onClick={() => onStart(s.task_id)}>
            <FileText className="shrink-0 text-emerald-700" size={20} />
            <span className="min-w-0"><span className="block font-semibold text-slate-900 truncate">Tailored for {s.job_title}{s.company ? ` · ${s.company}` : ''}</span>
              <span className="block text-sm text-slate-500">Copies that resume and its job description{s.created_at ? ` · ${new Date(s.created_at).toLocaleDateString()}` : ''}.</span></span>
            {busy === s.task_id && <Loader2 className="ml-auto animate-spin text-slate-400" size={18} />}
          </button>
        ))}
      <button type="button" className={card} disabled={!!busy} onClick={() => onStart('blank')}>
        <PencilLine className="shrink-0 text-slate-500" size={20} />
        <span><span className="block font-semibold text-slate-900">Blank resume</span><span className="block text-sm text-slate-500">Start with empty sections.</span></span>
      </button>
    </div>
  );
}

export default function StudioPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const fromTask = params.get('from');
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<ResumeData | null>(null);
  const [paper, setPaper] = useState<Paper>('A4');
  const [preset, setPreset] = useState('as-is');
  const [jd, setJd] = useState('');
  const [jdTitle, setJdTitle] = useState<string | null>(null);
  const [view, setView] = useState<View>('split');
  const [tab, setTab] = useState<EditorTab>('profile');
  const [mobilePane, setMobilePane] = useState<'edit' | 'paper'>('edit');
  const [status, setStatus] = useState<{ kind: 'idle' | 'saving' | 'saved' | 'error'; at?: string; message?: string }>({ kind: 'idle' });
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [replaceFrom, setReplaceFrom] = useState<string | null>(null);
  const dirty = useRef(false);

  const startFrom = useCallback(async (kind: string) => {
    setBusy(kind); setError('');
    try {
      if (kind === 'profile') { setData(withDefaults(await studioApi.fromProfile())); setJd(''); setJdTitle(null); }
      else if (kind === 'blank') { setData(emptyResume()); setJd(''); setJdTitle(null); }
      else {
        const res = await studioApi.fromTailored(kind);
        setData(withDefaults(res.data)); setJd(res.job_description || ''); setJdTitle(res.job_title);
      }
      setPreset('as-is'); setTab('profile'); dirty.current = true;
    } catch (err) {
      setError(studioApi.apiError(err, 'That starting point could not be loaded. Please try again.'));
    } finally { setBusy(''); }
  }, []);

  // Load: the account copy, unless this browser holds newer unsaved edits.
  useEffect(() => {
    let live = true;
    (async () => {
      const draft = readDraft();
      try {
        const saved = await studioApi.loadSaved();
        if (!live) return;
        const savedAt = saved.updated_at ? Date.parse(saved.updated_at) : 0;
        if (draft && draft.savedAt > savedAt) {
          setData(withDefaults(draft.data)); setPaper(draft.paper); setPreset(draft.preset); setJd(draft.jd || ''); dirty.current = true;
        } else if (saved.document) {
          setData(withDefaults(saved.document)); setPaper(saved.paper); setPreset(saved.preset);
          setJd(draft?.jd || ''); setStatus({ kind: 'saved', at: saved.updated_at ?? undefined });
        }
        if (fromTask) {
          if (saved.document || draft) setReplaceFrom(fromTask);
          else await startFrom(fromTask);
          setParams({}, { replace: true });
        }
      } catch (err) {
        if (!live) return;
        if (draft) { setData(withDefaults(draft.data)); setPaper(draft.paper); setPreset(draft.preset); setJd(draft.jd || ''); }
        setError(studioApi.apiError(err, 'Your saved resume could not be loaded. Edits are kept on this device until saving works again.'));
      } finally { if (live) setLoading(false); }
    })();
    return () => { live = false; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Local draft right away; account save shortly after typing stops.
  useEffect(() => {
    if (!data || !dirty.current) return;
    const local = setTimeout(() => writeDraft({ data, paper, preset, jd, savedAt: Date.now() }), 300);
    const remote = setTimeout(async () => {
      setStatus({ kind: 'saving' });
      try {
        const saved = await studioApi.save(data, paper, preset);
        dirty.current = false;
        writeDraft({ data, paper, preset, jd, savedAt: saved.updated_at ? Date.parse(saved.updated_at) : Date.now() });
        setStatus({ kind: 'saved', at: saved.updated_at ?? undefined });
      } catch (err) {
        setStatus({ kind: 'error', message: studioApi.apiError(err, 'Not saved to your account. Your edits are kept on this device.') });
      }
    }, 2000);
    return () => { clearTimeout(local); clearTimeout(remote); };
  }, [data, paper, preset, jd]);

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => { if (dirty.current) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, []);

  const set = useCallback(<K extends keyof ResumeData>(key: K, value: ResumeData[K]) => {
    dirty.current = true;
    setData(d => (d ? { ...d, [key]: value } : d));
  }, []);
  const change = <T,>(setter: (v: T) => void) => (v: T) => { dirty.current = true; setter(v); };

  // What the preview, checks and PDF use: the person's text, re-ordered by the chosen focus.
  const display = useMemo(() => (data ? (preset === 'as-is' ? data : applyRolePreset(data, preset)) : null), [data, preset]);
  const report = useMemo(() => (display ? analyzeResumeAts(display) : null), [display]);
  const jdMatch = useMemo(() => (display && jd.trim() ? analyzeJobDescription(display, jd) : null), [display, jd]);

  // Full Preview: the actual PDF.
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState('');
  useEffect(() => {
    if (view !== 'preview' || !display) return;
    let url: string | null = null;
    const t = setTimeout(async () => {
      try { url = URL.createObjectURL(await buildPdf(display, paper)); setPdfUrl(url); setPdfError(''); }
      catch { setPdfError('The PDF could not be built. Please try again.'); }
    }, 300);
    return () => { clearTimeout(t); if (url) URL.revokeObjectURL(url); };
  }, [view, display, paper]);

  const flash = (text: string) => { setNotice(text); setTimeout(() => setNotice(''), 2500); };
  const download = async () => {
    if (!display) return;
    setBusy('pdf');
    try {
      const url = URL.createObjectURL(await buildPdf(display, paper));
      const a = Object.assign(document.createElement('a'), { href: url, download: fileName(display.fullName) });
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch { setError('The PDF could not be built. Please try again.'); }
    finally { setBusy(''); }
  };
  const copyText = async () => {
    if (!display) return;
    try { await navigator.clipboard.writeText(buildPlainTextResume(display)); flash('Plain text copied'); }
    catch { setError('Copying is blocked in this browser. Use Download PDF instead.'); }
  };
  const reset = async () => {
    if (!window.confirm('Clear the Studio and start again? Your saved Studio resume will be deleted. Tailored resumes and your profile are not affected.')) return;
    try { await studioApi.removeSaved(); } catch { /* local reset still applies */ }
    clearDraft(); dirty.current = false;
    setData(null); setJd(''); setJdTitle(null); setPreset('as-is'); setStatus({ kind: 'idle' });
  };

  if (loading) return <div className="py-16 flex justify-center"><Loader2 className="animate-spin text-slate-400" /></div>;
  if (!data || !display || !report) return <StartScreen onStart={startFrom} busy={busy} error={error} />;

  const keywordStat = jdMatch ? `${jdMatch.matchedKeywords.length}/${jdMatch.extractedKeywords.length} job keywords` : `${report.matched}/${report.total} common keywords`;
  const btn = 'inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50';
  const editor = (
    <div className="space-y-4">
      <div role="tablist" aria-label="Sections" className="flex flex-wrap gap-1">
        {EDITOR_TABS.map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id} type="button" onClick={() => setTab(id)}
            className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-semibold ${tab === id ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>{label}</button>
        ))}
      </div>
      <Editor tab={tab} data={data} set={set} jd={jd} onJd={change(setJd)} jdTitle={jdTitle} />
    </div>
  );

  return (
    <div className="studio-root space-y-4">
      <style>{`@media print {
        @page { size: ${paper === 'A4' ? 'A4' : 'letter'}; margin: 0; }
        body * { visibility: hidden !important; }
        .studio-paper, .studio-paper * { visibility: visible !important; }
        .studio-paper-wrap { position: absolute; inset: 0; width: 100%; }
        .studio-paper { box-shadow: none !important; width: 100%; }
      }`}</style>

      {replaceFrom && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 flex flex-col sm:flex-row sm:items-center gap-3">
          <p className="flex-1 text-sm text-amber-900">Replace what is in the Studio with the tailored resume you opened? Your current Studio resume will be overwritten.</p>
          <div className="flex gap-2">
            <button type="button" className={btn} onClick={() => setReplaceFrom(null)}>Keep current</button>
            <button type="button" className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-700"
              onClick={() => { const id = replaceFrom; setReplaceFrom(null); startFrom(id); }}>Replace</button>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <nav aria-label="Studio views" className="mr-auto flex rounded-lg border border-slate-200 bg-white p-0.5 overflow-x-auto">
          {VIEWS.map(([id, label, Icon]) => (
            <button key={id} type="button" aria-pressed={view === id} onClick={() => setView(id)}
              className={`shrink-0 inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium ${view === id ? 'bg-emerald-600 text-white' : 'text-slate-600 hover:bg-slate-50'}`}>
              <Icon size={15} /> <span className="hidden sm:inline">{label}</span><span className="sm:hidden">{label.split(' ')[0]}</span>
            </button>
          ))}
        </nav>
        <button type="button" onClick={download} disabled={busy === 'pdf'}
          className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {busy === 'pdf' ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />} Download PDF
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-2.5">
        <label className="flex items-center gap-2 text-sm text-slate-600">Focus
          <select value={preset} onChange={e => change(setPreset)(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-900">
            {ROLE_PRESETS.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
        </label>
        <div className="flex rounded-lg border border-slate-300 p-0.5" role="group" aria-label="Paper size">
          {(['A4', 'Letter'] as Paper[]).map(p => (
            <button key={p} type="button" aria-pressed={paper === p} onClick={() => change(setPaper)(p)}
              className={`rounded-md px-2.5 py-1 text-xs font-semibold ${paper === p ? 'bg-slate-900 text-white' : 'text-slate-600'}`}>{p}</button>
          ))}
        </div>
        <p className="text-xs text-slate-500 px-1">
          {report.wordCount.toLocaleString()} words · {keywordStat} · <span className="text-emerald-700 font-medium">Standard selectable PDF</span>
        </p>
        <div className="ml-auto flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-slate-500 mr-1" aria-live="polite">
            {status.kind === 'saving' ? 'Saving…' : status.kind === 'saved' ? <span className="inline-flex items-center gap-1"><CheckCircle2 size={12} className="text-emerald-600" />Saved</span>
              : status.kind === 'error' ? <span className="text-rose-700">{status.message}</span> : ''}
          </span>
          {notice && <span className="text-xs text-emerald-700 mr-1">{notice}</span>}
          <button type="button" className={btn} onClick={() => window.print()} title="Print" aria-label="Print"><Printer size={15} /><span className="hidden md:inline">Print</span></button>
          <button type="button" className={btn} onClick={copyText} title="Copy plain text" aria-label="Copy plain text"><ClipboardCopy size={15} /><span className="hidden md:inline">Copy text</span></button>
          <button type="button" className={btn} onClick={reset} title="Reset" aria-label="Reset"><RotateCcw size={15} /><span className="hidden md:inline">Reset</span></button>
        </div>
      </div>
      {preset !== 'as-is' && <p className="text-xs text-slate-500">Focus re-orders your skills, projects and bullets in the preview and PDF so the most relevant come first. Your text is unchanged and nothing is added.</p>}
      {error && <p className="text-sm text-rose-700 bg-rose-50 rounded-xl p-3">{error}</p>}

      {view === 'split' && (
        <>
          <div className="flex lg:hidden rounded-lg border border-slate-200 bg-white p-0.5 w-fit" role="group" aria-label="Show">
            {(['edit', 'paper'] as const).map(p => (
              <button key={p} type="button" aria-pressed={mobilePane === p} onClick={() => setMobilePane(p)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium ${mobilePane === p ? 'bg-slate-900 text-white' : 'text-slate-600'}`}>{p === 'edit' ? 'Edit' : 'Preview'}</button>
            ))}
          </div>
          <div className="lg:grid lg:grid-cols-[440px_minmax(0,1fr)] lg:gap-6 lg:items-start">
            <aside aria-label="Editor" className={`${mobilePane === 'edit' ? 'block' : 'hidden'} lg:block lg:sticky lg:top-4 lg:max-h-[calc(100dvh-2rem)] lg:overflow-y-auto overscroll-contain rounded-2xl border border-slate-200 bg-white p-4`}>
              {editor}
            </aside>
            <div className={`${mobilePane === 'paper' ? 'block' : 'hidden'} lg:block print:block rounded-2xl bg-slate-100 p-3 sm:p-6`}>
              <div className="max-w-[820px] mx-auto"><PaperPreview data={display} paper={paper} /></div>
            </div>
          </div>
        </>
      )}
      {view === 'edit' && <div className="max-w-3xl rounded-2xl border border-slate-200 bg-white p-4 sm:p-6">{editor}</div>}
      {view === 'ats' && (
        <div className="max-w-3xl rounded-2xl border border-slate-200 bg-white p-4 sm:p-6">
          <Editor tab="ats" data={display} set={set} jd={jd} onJd={change(setJd)} jdTitle={jdTitle} />
        </div>
      )}
      {view === 'preview' && (
        <div className="space-y-2">
          <div className="hidden print:block"><PaperPreview data={display} paper={paper} /></div>
          {pdfError ? <p className="text-sm text-rose-700 bg-rose-50 rounded-xl p-3">{pdfError}</p>
            : pdfUrl ? (
              <>
                <iframe title="Resume PDF" src={pdfUrl} className="w-full h-[80dvh] rounded-2xl border border-slate-200 bg-white" />
                <p className="text-xs text-slate-500">This is the exact PDF you download. If it does not show here, <a href={pdfUrl} target="_blank" rel="noreferrer" className="font-semibold text-emerald-700 hover:underline">open it in a new tab</a>.</p>
              </>
            ) : <div className="py-16 flex justify-center"><Loader2 className="animate-spin text-slate-400" /></div>}
        </div>
      )}
      {view !== 'split' && view !== 'preview' && <div className="hidden print:block"><PaperPreview data={display} paper={paper} /></div>}
      <p className="text-xs text-slate-400">
        Need the job-tailored version instead? <button type="button" className="font-semibold text-emerald-700 hover:underline" onClick={() => navigate('/optimizer')}>Open the resume workspace</button>.
      </p>
    </div>
  );
}
