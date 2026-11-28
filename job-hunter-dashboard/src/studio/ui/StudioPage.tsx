// Resume Studio: edit a single-column ATS resume by hand, check it, and download a
// real-text PDF built in the browser. Saved to the account (and as a local draft).
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Check, ClipboardCopy, Download, FileText, Loader2, PencilLine, Printer, RotateCcw, UserRound } from 'lucide-react';
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
import PdfPreview from '../../components/common/PdfPreview';

type View = 'split' | 'edit' | 'ats' | 'preview';
// [id, label, short label for phones]
const VIEWS: Array<[View, string, string]> = [['split', 'Split Studio', 'Split'], ['edit', 'Edit Sections', 'Edit'], ['ats', 'ATS Audit', 'ATS'], ['preview', 'Full Preview', 'Preview']];
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
  const card = 'w-full text-left rounded-lg border border-slate-200 bg-white p-4 hover:border-[#1F4E79] hover:shadow-sm disabled:opacity-50 flex gap-3';
  return (
    <div className="max-w-2xl mx-auto py-6 space-y-5">
      <div>
        <p className="text-sm text-slate-600">Edit your resume section by section, check it against a job description, and download a PDF whose text every ATS can read. Choose where to start; you can change everything afterwards.</p>
      </div>
      {error && <p className="text-sm text-rose-700 bg-rose-50 rounded-xl p-3">{error}</p>}
      <button type="button" className={card} disabled={!!busy} onClick={() => onStart('profile')}>
        <UserRound className="shrink-0 text-[#1F4E79]" size={20} />
        <span><span className="block font-semibold text-slate-900">From my profile</span>
          <span className="block text-sm text-slate-500">Copies your name, contact details, about, experience, education and skills.</span></span>
        {busy === 'profile' && <Loader2 className="ml-auto animate-spin text-slate-400" size={18} />}
      </button>
      {sources === null ? <p className="text-sm text-slate-500 flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Loading your tailored resumes…</p>
        : sources.map(s => (
          <button key={s.task_id} type="button" className={card} disabled={!!busy} onClick={() => onStart(s.task_id)}>
            <FileText className="shrink-0 text-[#1F4E79]" size={20} />
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
  const [mobilePane, setMobilePane] = useState<'edit' | 'paper'>('paper');
  const [downloaded, setDownloaded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [status, setStatus] = useState<{ kind: 'idle' | 'saving' | 'saved' | 'error'; at?: string; message?: string }>({ kind: 'idle' });
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
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

  const download = async () => {
    if (!display) return;
    setBusy('pdf');
    try {
      const url = URL.createObjectURL(await buildPdf(display, paper));
      const a = Object.assign(document.createElement('a'), { href: url, download: fileName(display.fullName) });
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      setDownloaded(true); setTimeout(() => setDownloaded(false), 2500);
    } catch { setError('The PDF could not be built. Please try again.'); }
    finally { setBusy(''); }
  };
  const copyText = async () => {
    if (!display) return;
    try { await navigator.clipboard.writeText(buildPlainTextResume(display)); setCopied(true); setTimeout(() => setCopied(false), 2000); }
    catch { setError('Copying is blocked in this browser. Use Download PDF instead.'); }
  };
  const reset = async () => {
    if (!window.confirm('Clear the Studio and start again? Your saved Studio resume will be deleted. Tailored resumes and your profile are not affected.')) return;
    try { await studioApi.removeSaved(); } catch { /* local reset still applies */ }
    clearDraft(); dirty.current = false;
    setData(null); setJd(''); setJdTitle(null); setPreset('as-is'); setStatus({ kind: 'idle' });
  };

  const shell = (children: ReactNode, header?: ReactNode) => (
    <div className="studio-root min-h-[100dvh] bg-slate-100 text-slate-900" style={{ fontFamily: "'Plus Jakarta Sans', Inter, Arial, sans-serif" }}>
      <header className="sticky top-0 z-30 h-14 bg-white border-b border-slate-200 print:hidden">
        <div className="h-full max-w-[1440px] mx-auto px-4 lg:px-6 flex items-center gap-4">
          <span className="hidden md:block md:w-44 xl:w-52 shrink-0 whitespace-nowrap text-[17px] font-extrabold tracking-tight text-[#1F4E79]">Resume Studio</span>
          {header}
        </div>
      </header>
      {children}
    </div>
  );

  if (loading) return shell(<div className="py-16 flex justify-center"><Loader2 className="animate-spin text-slate-400" /></div>);
  if (!data || !display || !report) return shell(<main className="max-w-[1440px] mx-auto p-4 lg:p-6"><StartScreen onStart={startFrom} busy={busy} error={error} /></main>);

  const keywordStat = jdMatch
    ? `${jdMatch.matchedKeywords.length}/${jdMatch.extractedKeywords.length} ATS keywords`
    : `${report.matched}/${report.total} ATS keywords`;
  const btn = 'inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-[13px] font-semibold text-slate-700 hover:bg-slate-50';
  const editorPanel = (tabs: boolean, only?: EditorTab) => (
    <div className="bg-white border border-slate-200 rounded-lg">
      {tabs && (
        <div role="tablist" aria-label="Resume sections"
          className="sticky top-0 z-10 flex overflow-x-auto lg:grid lg:grid-cols-5 bg-slate-50 border-b border-slate-200 rounded-t-lg">
          {EDITOR_TABS.map(([id, label]) => (
            <button key={id} role="tab" aria-selected={tab === id} type="button" onClick={() => setTab(id)}
              className={`shrink-0 whitespace-nowrap lg:whitespace-normal px-3 lg:px-2 py-2.5 text-[12px] font-semibold leading-tight text-center border-b-2 -mb-px ${tab === id ? 'border-[#1F4E79] text-[#1F4E79] bg-white' : 'border-transparent text-slate-600 hover:text-slate-900'}`}>{label}</button>
          ))}
        </div>
      )}
      <div className="p-4 sm:p-5">
        <Editor tab={only ?? tab} data={only === 'ats' ? display : data} set={set} jd={jd} onJd={change(setJd)} jdTitle={jdTitle} />
      </div>
    </div>
  );
  const sheet = (
    <div className={`mx-auto w-full ${paper === 'A4' ? 'max-w-[794px]' : 'max-w-[816px]'}`}><PaperPreview data={display} paper={paper} /></div>
  );

  const header = (
    <>
      <nav aria-label="Studio views" className="flex-1 min-w-0 h-full flex md:justify-center gap-4 sm:gap-5 lg:gap-7 overflow-x-auto">
        {VIEWS.map(([id, label, short]) => (
          <button key={id} type="button" aria-current={view === id ? 'page' : undefined} onClick={() => setView(id)} aria-label={label}
            className={`h-full shrink-0 whitespace-nowrap border-b-2 text-[14px] font-semibold transition-colors ${view === id ? 'border-[#1F4E79] text-[#1F4E79]' : 'border-transparent text-slate-600 hover:text-slate-900'}`}>
            <span className="hidden sm:inline">{label}</span><span className="sm:hidden">{short}</span>
          </button>
        ))}
      </nav>
      <div className="md:w-44 xl:w-52 shrink-0 flex justify-end">
        <button type="button" onClick={download} disabled={busy === 'pdf'} aria-live="polite"
          className="inline-flex items-center gap-2 rounded-md bg-[#1F4E79] px-3 sm:px-4 py-2 text-[14px] font-semibold text-white hover:bg-[#173C5E] disabled:opacity-70 whitespace-nowrap">
          {busy === 'pdf' ? <Loader2 size={16} className="animate-spin" /> : downloaded ? <Check size={16} /> : <Download size={16} />}
          <span className="hidden sm:inline">{busy === 'pdf' ? 'Preparing…' : downloaded ? 'Downloaded' : 'Download PDF'}</span>
          <span className="sm:hidden">PDF</span>
        </button>
      </div>
    </>
  );

  return shell(
    <>
      <style>{`@media print {
        @page { size: ${paper === 'A4' ? 'A4' : 'letter'}; margin: 0; }
        body * { visibility: hidden !important; }
        .studio-paper, .studio-paper * { visibility: visible !important; }
        .studio-paper-wrap { position: absolute; inset: 0; width: 100%; }
        .studio-paper { box-shadow: none !important; border: 0 !important; width: 100%; }
      }`}</style>

      <div className="bg-white border-b border-slate-200 print:hidden">
        <div className="max-w-[1440px] mx-auto px-4 lg:px-6 py-2.5 flex flex-wrap items-center gap-x-3 gap-y-2">
          <Segmented label="Role focus" value={preset} onChange={change(setPreset)} options={ROLE_PRESETS.map(p => [p.id, p.label] as [string, string])} />
          <Segmented label="Paper size" value={paper} onChange={v => change(setPaper)(v as Paper)} options={[['A4', 'A4'], ['Letter', 'US Letter']]} />
          <p className="hidden lg:block ml-auto text-[12px] text-slate-500 font-[JetBrains_Mono,ui-monospace,monospace] tabular-nums">
            {report.wordCount.toLocaleString()} words · {keywordStat} · Standard selectable PDF
          </p>
          <div className="ml-auto lg:ml-0 flex flex-wrap items-center gap-2">
            <span className="text-[12px] text-slate-500" aria-live="polite">
              {status.kind === 'saving' ? 'Saving…' : status.kind === 'saved' ? 'Saved' : status.kind === 'error' ? <span className="text-rose-700">{status.message}</span> : ''}
            </span>
            <button type="button" className={btn} onClick={() => window.print()}><Printer size={15} />Print / Save PDF</button>
            <button type="button" className={`${btn} ${copied ? 'text-[#1F4E79]' : ''}`} onClick={copyText} aria-live="polite">
              {copied ? <Check size={15} /> : <ClipboardCopy size={15} />}{copied ? 'Copied ATS Text' : 'Copy Plain Text'}
            </button>
            <button type="button" className={btn} onClick={reset}><RotateCcw size={15} />Reset</button>
          </div>
        </div>
      </div>

      <main className="max-w-[1440px] mx-auto p-4 lg:p-6 space-y-4">
        {replaceFrom && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 flex flex-col sm:flex-row sm:items-center gap-3 print:hidden">
            <p className="flex-1 text-sm text-amber-900">Replace what is in the Studio with the tailored resume you opened? Your current Studio resume will be overwritten.</p>
            <div className="flex gap-2">
              <button type="button" className={btn} onClick={() => setReplaceFrom(null)}>Keep current</button>
              <button type="button" className="rounded-md bg-[#1F4E79] px-3 py-1.5 text-[13px] font-semibold text-white hover:bg-[#173C5E]"
                onClick={() => { const id = replaceFrom; setReplaceFrom(null); startFrom(id); }}>Replace</button>
            </div>
          </div>
        )}
        {preset !== 'as-is' && <p className="text-xs text-slate-500 print:hidden">Role focus re-orders your skills, projects and bullets in the preview and PDF so the most relevant come first. Your text is unchanged and nothing is added.</p>}
        {error && <p role="alert" className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-3 print:hidden">{error}</p>}

        {view === 'split' && (
          <>
            <div className="grid grid-cols-2 gap-2 lg:hidden print:hidden" role="group" aria-label="Show">
              {([['paper', 'Resume Preview'], ['edit', 'Edit & ATS Audit']] as const).map(([id, label]) => (
                <button key={id} type="button" aria-pressed={mobilePane === id} onClick={() => setMobilePane(id)}
                  className={`rounded-md py-2.5 text-[14px] font-semibold ${mobilePane === id ? 'bg-[#1F4E79] text-white' : 'bg-white border border-slate-300 text-slate-700'}`}>{label}</button>
              ))}
            </div>
            <div className="lg:grid lg:grid-cols-[440px_minmax(0,1fr)] lg:gap-6 lg:items-start">
              <aside aria-label="Editor and ATS audit" className={`${mobilePane === 'edit' ? 'block' : 'hidden'} lg:block lg:sticky lg:top-[72px] lg:max-h-[calc(100dvh-88px)] lg:overflow-y-auto overscroll-contain print:hidden`}>
                {editorPanel(true)}
              </aside>
              <div className={`${mobilePane === 'paper' ? 'block' : 'hidden'} lg:block print:block`}>{sheet}</div>
            </div>
          </>
        )}
        {view === 'edit' && <div className="max-w-3xl mx-auto print:hidden">{editorPanel(true)}</div>}
        {view === 'ats' && <div className="max-w-3xl mx-auto print:hidden">{editorPanel(false, 'ats')}</div>}
        {view === 'preview' && (
          <div className="max-w-[850px] mx-auto space-y-2">
            <div className="hidden print:block">{sheet}</div>
            {pdfError ? <p className="text-sm text-rose-700 bg-rose-50 rounded-lg p-3 print:hidden">{pdfError}</p>
              : pdfUrl ? (
                <div className="print:hidden">
                  <PdfPreview src={pdfUrl} title="Resume PDF" className="space-y-4" maxPages={4} />
                  <p className="mt-2 text-xs text-slate-500">This is the exact PDF you download: real, selectable text on {paper === 'A4' ? 'A4' : 'US Letter'} pages.</p>
                </div>
              ) : <div className="py-16 flex justify-center print:hidden"><Loader2 className="animate-spin text-slate-400" /></div>}
          </div>
        )}
        {(view === 'edit' || view === 'ats') && <div className="hidden print:block">{sheet}</div>}
        <p className="text-xs text-slate-500 print:hidden">
          Need the job-tailored version instead? <button type="button" className="font-semibold text-[#1F4E79] hover:underline" onClick={() => navigate('/optimizer')}>Open the resume workspace</button>.
        </p>
      </main>
    </>,
    header,
  );
}

/** A segmented control: one choice from a few, as radio buttons. */
function Segmented({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: Array<[string, string]> }) {
  return (
    <div role="radiogroup" aria-label={label} className="flex max-w-full overflow-x-auto bg-slate-100 p-1 rounded-lg">
      {options.map(([id, text]) => (
        <button key={id} type="button" role="radio" aria-checked={value === id} onClick={() => onChange(id)}
          className={`shrink-0 whitespace-nowrap rounded-md px-3 py-1 text-[13px] font-semibold transition-colors ${value === id ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'}`}>{text}</button>
      ))}
    </div>
  );
}
