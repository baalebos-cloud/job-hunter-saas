/* eslint-disable react/prop-types -- the project does not use the prop-types package */
import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { ExternalLink, FileText, Save, Send } from 'lucide-react';
import { adminGet, message } from '../adminApi';
import { Banner, Button, Chip, SectionHeader, Spinner, card } from '../ui';
import LegalText from '../../site/LegalText';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });
const when = (iso) => (iso ? new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '');

// Team console -> Legal (legal:manage): edit the legal documents, preview, publish versions.
export default function LegalTab({ notify, confirm }) {
  const [docs, setDocs] = useState(null);
  const [slug, setSlug] = useState('terms');
  const [draft, setDraft] = useState({ title: '', body: '' });
  const [view, setView] = useState('edit');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const doc = docs?.find(d => d.slug === slug);
  const dirty = doc && (draft.title !== doc.title || draft.body !== doc.body);

  const load = useCallback(() => adminGet('/console/legal').then(setDocs).catch(err => setError(message(err, 'Legal documents could not be loaded.'))), []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (doc) setDraft({ title: doc.title, body: doc.body }); }, [doc]);

  const replace = (updated) => setDocs(ds => ds.map(d => (d.slug === updated.slug ? updated : d)));
  const save = async () => {
    setBusy('save'); setError('');
    try { replace((await axios.put(`${API}/console/legal/${slug}`, draft, { headers: headers() })).data); notify('Draft saved. Visitors still see the published version.'); }
    catch (err) { setError(message(err, 'The draft could not be saved.')); }
    finally { setBusy(''); }
  };
  const publish = () => confirm({
    title: `Publish ${draft.title}?`,
    body: `Visitors see it straight away as version ${(doc.published_version || 0) + 1}. Earlier versions stay in the history.`,
    confirmLabel: 'Publish', reasonLabel: 'What changed (optional, shown in the history)', reasonPlaceholder: 'e.g. Added company registration details',
    errorText: (err) => message(err, 'The document could not be published.'),
    onConfirm: async (note) => {
      if (dirty) replace((await axios.put(`${API}/console/legal/${slug}`, draft, { headers: headers() })).data);
      replace((await axios.post(`${API}/console/legal/${slug}/publish`, { note: note || '' }, { headers: headers() })).data);
      notify(`${draft.title} published.`);
    },
  });

  if (!docs) return error ? <Banner>{error}</Banner> : <Spinner />;
  const placeholders = (draft.body.match(/\[[^\]]+\]/g) || []).length;
  return (
    <div className="grid grid-cols-1 xl:grid-cols-[16rem_minmax(0,1fr)] gap-4 items-start">
      <nav className={`${card} p-2`} aria-label="Legal documents">
        {docs.map(d => (
          <button key={d.slug} type="button" onClick={() => setSlug(d.slug)} aria-current={d.slug === slug ? 'page' : undefined}
            className={`w-full text-left px-3 py-2.5 rounded-lg ${d.slug === slug ? 'bg-emerald-50 text-emerald-800' : 'hover:bg-slate-50'}`}>
            <div className="flex items-center gap-2 text-sm font-medium"><FileText size={15} />{d.title}</div>
            <div className="mt-1 flex gap-1.5">{d.published_version ? <Chip tone="green">v{d.published_version} live</Chip> : <Chip tone="amber">Not published</Chip>}{d.has_draft && <Chip tone="violet">Draft</Chip>}</div>
          </button>))}
      </nav>
      <section className={`${card} overflow-hidden`}>
        <SectionHeader title={doc.title} subtitle={doc.published_version ? `Version ${doc.published_version} live since ${when(doc.published_at)}` : 'Not published yet: visitors see the starter draft, marked as pending legal review'}>
          <a href={`/legal/${slug}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm font-medium text-slate-600 hover:text-slate-900">Public page <ExternalLink size={13} /></a>
        </SectionHeader>
        <div className="px-5 pb-5 space-y-3">
          {error && <Banner onClose={() => setError('')}>{error}</Banner>}
          {placeholders > 0 && <p className="rounded-lg bg-amber-50 border border-amber-200 p-2.5 text-sm text-amber-900">{placeholders} [bracketed] placeholder{placeholders > 1 ? 's' : ''} still to fill in, such as the company name, address or refund window.</p>}
          <input aria-label="Title" value={draft.title} onChange={e => setDraft(d => ({ ...d, title: e.target.value }))} maxLength={120}
            className="w-full text-lg font-semibold border border-slate-200 rounded-lg px-3 py-2" />
          <div className="inline-flex rounded-lg bg-slate-100 p-0.5 text-sm">
            {[['edit', 'Edit'], ['preview', 'Preview']].map(([id, label]) => (
              <button key={id} type="button" onClick={() => setView(id)} className={`px-3 py-1 rounded-md ${view === id ? 'bg-white shadow-sm font-medium' : 'text-slate-600'}`}>{label}</button>))}
          </div>
          {view === 'edit'
            ? <textarea aria-label="Document text" value={draft.body} onChange={e => setDraft(d => ({ ...d, body: e.target.value }))} rows={24}
                className="w-full font-mono text-[13px] leading-6 border border-slate-200 rounded-lg p-3" />
            : <div className="border border-slate-200 rounded-lg p-5 max-h-[38rem] overflow-y-auto"><LegalText source={draft.body} /></div>}
          <p className="text-xs text-slate-500">Formatting: <code>## Heading</code>, <code>- bullet</code>, <code>**bold**</code>, and tables with <code>|</code>.</p>
          <div className="flex flex-wrap items-center gap-2">
            <Button icon={Save} busy={busy === 'save'} disabled={!dirty} onClick={save}>Save draft</Button>
            <Button variant="primary" icon={Send} disabled={!doc.has_draft && !dirty} onClick={publish}>Publish</Button>
            {doc.draft_updated_at && <span className="text-xs text-slate-500">Draft saved {when(doc.draft_updated_at)}</span>}
          </div>
          {doc.history.length > 0 && (
            <div className="pt-3 border-t border-slate-100">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Published versions</h3>
              <ul className="mt-2 text-sm space-y-1">{doc.history.map(h => <li key={h.version}>v{h.version} · {when(h.published_at)}{h.note ? ` · ${h.note}` : ''}</li>)}</ul>
            </div>)}
        </div>
      </section>
    </div>
  );
}
