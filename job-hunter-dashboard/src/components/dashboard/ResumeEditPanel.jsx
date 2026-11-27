import { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, Lock, PencilLine, X } from 'lucide-react';
import { apiErrorMessage } from '../../lib/session';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });
const LAYOUTS = [['classic', 'Classic', 'Centred header, capital headings'], ['modern', 'Modern', 'Left-aligned header, title-case headings'],
  ['compact', 'Compact', 'Tighter spacing, fits more on a page']];
const input = 'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-600/20';

// Pro/Enterprise: edit the summary and bullets, choose length and layout, then re-render.
// Employers, job titles and dates are shown but cannot be changed here.
export default function ResumeEditPanel({ resumeId, paid, onSaved }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open || !resumeId) return;
    setError(''); setForm(null);
    axios.get(`${API}/resume/${resumeId}/edit`, { headers: headers() })
      .then(r => setForm({ summary: r.data.resume.summary, roles: r.data.resume.experience.map(e => ({ ...e, text: e.bullets.join('\n') })),
        pages: String(r.data.max_pages ?? 1), template: r.data.template || 'classic' }))
      .catch(async err => setError(await apiErrorMessage(err, 'Your resume could not be loaded for editing.')));
  }, [open, resumeId]);

  if (!paid) {
    return (
      <p className="flex items-start gap-2 text-xs text-slate-500"><Lock size={14} className="mt-0.5 shrink-0" />
        <span>Edit wording, choose 1 or 2 pages and a layout before downloading with <a href="/pricing" className="font-semibold text-emerald-700 hover:underline">Pro</a>.</span></p>
    );
  }
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)}
        className="w-full inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-800 hover:bg-slate-50">
        <PencilLine size={16} />Edit before download</button>
    );
  }

  const save = async () => {
    setSaving(true); setError('');
    try {
      const res = await axios.patch(`${API}/resume/${resumeId}/edit`, {
        summary: form.summary,
        experience: form.roles.map(r => ({ bullets: r.text.split('\n').map(b => b.replace(/^\s*[-•*]\s?/, '').trim()).filter(Boolean) })),
        max_pages: form.pages, template: form.template,
      }, { headers: headers() });
      onSaved(res.data.result);
      setOpen(false);
    } catch (err) {
      setError(await apiErrorMessage(err, 'Your changes could not be saved. Please retry.'));
    } finally { setSaving(false); }
  };

  return (
    <div className="rounded-xl border border-slate-200 p-4 space-y-4" role="region" aria-label="Edit before download">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-slate-900 text-sm">Edit before download</h3>
        <button type="button" onClick={() => setOpen(false)} aria-label="Close editor" className="p-1 rounded hover:bg-slate-100"><X size={16} /></button>
      </div>
      {error && <p role="alert" className="text-sm text-rose-700 bg-rose-50 rounded-lg p-2">{error}</p>}
      {!form ? (!error && <div className="py-6 grid place-items-center"><Loader2 className="animate-spin text-slate-400" /></div>) : (
        <>
          <div className="grid grid-cols-2 gap-3">
            <label className="text-xs font-semibold text-slate-700">Length
              <select value={form.pages} onChange={e => setForm({ ...form, pages: e.target.value })} className={`${input} mt-1`}>
                <option value="1">1 page</option><option value="auto">1 page if it fits, otherwise 2</option><option value="2">Up to 2 pages</option>
              </select></label>
            <label className="text-xs font-semibold text-slate-700">Layout
              <select value={form.template} onChange={e => setForm({ ...form, template: e.target.value })} className={`${input} mt-1`}>
                {LAYOUTS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
              </select></label>
          </div>
          <p className="text-xs text-slate-500 -mt-2">{LAYOUTS.find(l => l[0] === form.template)?.[2]}. All layouts are single-column text that applicant tracking systems read.</p>
          <label className="block text-xs font-semibold text-slate-700">Summary
            <textarea rows={4} maxLength={1500} value={form.summary} onChange={e => setForm({ ...form, summary: e.target.value })} className={`${input} mt-1`} /></label>
          {form.roles.map((role, i) => (
            <label key={i} className="block text-xs font-semibold text-slate-700">
              <span className="block text-slate-900">{role.role}</span>
              <span className="block font-normal text-slate-500">{[role.company, role.dates].filter(Boolean).join(' · ')} (not editable)</span>
              <textarea rows={Math.min(8, Math.max(3, role.bullets.length + 1))} value={role.text}
                onChange={e => setForm({ ...form, roles: form.roles.map((r, n) => (n === i ? { ...r, text: e.target.value } : r)) })}
                className={`${input} mt-1`} aria-describedby="bullet-hint" /></label>
          ))}
          <p id="bullet-hint" className="text-xs text-slate-500">One achievement per line, up to 15 per role. Only write what is true; your edits are your own words.</p>
          <button type="button" onClick={save} disabled={saving}
            className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
            {saving && <Loader2 size={16} className="animate-spin" />}{saving ? 'Saving…' : 'Save and update preview'}</button>
        </>
      )}
    </div>
  );
}
