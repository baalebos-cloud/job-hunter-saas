/* eslint-disable react/prop-types -- the project does not use the prop-types package */
import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Download, FileText, Loader2, Sparkles, Trash2, Upload, X } from 'lucide-react';
import { errorText } from '../../lib/session';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });
const STATUS = {
  new: ['New', 'bg-emerald-50 text-emerald-800'],
  keep: ['Keep yours', 'bg-slate-100 text-slate-700'],
  same: ['Already on profile', 'bg-slate-100 text-slate-500'],
  missing: ['Fill in yourself', 'bg-amber-50 text-amber-800'],
};
const show = (v) => (Array.isArray(v) ? v.join(' · ') : v);

// Review what the resume says before anything reaches the profile.
function ReviewDialog({ result, onClose, onSaved }) {
  const [ticked, setTicked] = useState(() => new Set(result.rows.filter(r => r.status === 'new').map(r => r.key)));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const toggle = (key) => setTicked(t => { const n = new Set(t); n.has(key) ? n.delete(key) : n.add(key); return n; });
  const save = async () => {
    setBusy(true); setError('');
    try {
      const r = await axios.post(`${API}/profile/resume/apply`, { keys: [...ticked] }, { headers: headers() });
      onSaved(r.data.profile, r.data.applied);
    } catch (err) { setError(errorText(err, 'Your profile could not be updated. Please retry.')); setBusy(false); }
  };
  const missing = result.rows.filter(r => r.status === 'missing').length;
  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 p-4 flex items-center justify-center" role="dialog" aria-modal="true" aria-labelledby="autofill-title">
      <section className="bg-white rounded-2xl w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl">
        <div className="flex items-start justify-between gap-3 px-6 py-5 border-b border-slate-200">
          <div>
            <h2 id="autofill-title" className="text-lg font-semibold text-slate-900">We read your resume. Check before we fill your profile.</h2>
            <p className="text-sm text-slate-500">{result.filename} · only details found in your file are shown. Nothing changes until you save.</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="p-2 rounded-lg text-slate-500 hover:bg-slate-100"><X size={18} /></button>
        </div>
        <ul className="overflow-y-auto px-6 divide-y divide-slate-100">
          {result.rows.map(r => {
            const [label, tone] = STATUS[r.status];
            const choosable = r.status === 'new' || r.status === 'keep';
            return (
              <li key={r.key} className="py-3 grid grid-cols-[1.5rem_8rem_minmax(0,1fr)_auto] gap-3 items-start">
                {choosable ? <input type="checkbox" aria-label={`Use ${r.label} from the resume`} checked={ticked.has(r.key)} onChange={() => toggle(r.key)} className="mt-1 accent-emerald-600 w-4 h-4" /> : <span />}
                <span className="text-sm text-slate-500 pt-0.5">{r.label}</span>
                <span className="text-sm text-slate-900 min-w-0 break-words">
                  {r.status === 'missing' ? <span className="text-amber-800">Not found in your resume. Add it on your profile.</span> : show(r.value)}
                  {r.status === 'keep' && <span className="block text-xs text-slate-500">Your profile says: {r.current}. Tick to replace it.</span>}
                  {r.count > 1 && <span className="block text-xs text-slate-500">{r.count} items</span>}
                </span>
                <span className={`text-[11.5px] font-semibold rounded-full px-2 py-0.5 whitespace-nowrap ${tone}`}>{label}</span>
              </li>);
          })}
        </ul>
        <div className="px-6 py-4 border-t border-slate-200 flex flex-wrap items-center justify-between gap-3">
          <span className="text-sm text-slate-500">{result.found} found · {missing} to fill in yourself</span>
          {error && <span role="alert" className="text-sm text-rose-700">{error}</span>}
          <button type="button" onClick={save} disabled={busy || ticked.size === 0}
            className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white text-sm font-semibold px-4 py-2.5">
            {busy && <Loader2 size={15} className="animate-spin" />}Save to my profile</button>
        </div>
      </section>
    </div>
  );
}

// Profile → My resume: keep one resume, reuse it for every job, fill the profile from it.
export default function ProfileResume({ onProfile, notify, card }) {
  const [meta, setMeta] = useState(undefined);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [review, setReview] = useState(null);
  const input = useRef(null);
  useEffect(() => { axios.get(`${API}/profile/resume`, { headers: headers() }).then(r => setMeta(r.data.resume)).catch(() => setMeta(null)); }, []);

  const read = async () => {
    setBusy('read'); setError('');
    try { setReview((await axios.post(`${API}/profile/resume/read`, {}, { headers: headers(), timeout: 180000 })).data); }
    catch (err) { setError(errorText(err, 'Your resume could not be read. Please retry.')); }
    finally { setBusy(''); }
  };
  const upload = async (file) => {
    if (!file) return;
    setBusy('upload'); setError('');
    const data = new FormData(); data.append('file', file);
    try {
      setMeta((await axios.post(`${API}/profile/resume`, data, { headers: headers() })).data.resume);
      setBusy(''); await read();
    } catch (err) { setError(errorText(err, 'The file could not be uploaded.')); setBusy(''); }
    finally { if (input.current) input.current.value = ''; }
  };
  const download = async () => {
    const r = await axios.get(`${API}/profile/resume/file`, { headers: headers(), responseType: 'blob' });
    const url = URL.createObjectURL(r.data);
    Object.assign(document.createElement('a'), { href: url, download: meta.filename }).click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const remove = async () => {
    if (!window.confirm('Remove the resume from your profile? Your tailored resumes are kept.')) return;
    await axios.delete(`${API}/profile/resume`, { headers: headers() }); setMeta(null);
  };

  return (
    <section className={`${card} p-5`} aria-labelledby="profile-resume-title">
      <h2 id="profile-resume-title" className="font-semibold text-slate-900">My resume</h2>
      <p className="text-sm text-slate-500 mt-0.5">Upload once: we fill your profile from it and use it for every job you tailor.</p>
      <input ref={input} type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className="hidden" onChange={e => upload(e.target.files?.[0])} aria-label="Choose a resume file" />
      {meta === undefined ? <Loader2 className="mt-4 animate-spin text-emerald-600" size={18} /> : meta ? (
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 p-3">
          <FileText size={20} className="text-slate-500" />
          <div className="flex-1 min-w-[10rem]"><div className="text-sm font-medium text-slate-900 truncate">{meta.filename}</div>
            <div className="text-xs text-slate-500">Uploaded {new Date(meta.uploaded_at).toLocaleDateString()} · {Math.max(1, Math.round(meta.size_bytes / 1024))} KB · used for tailoring</div></div>
          <button type="button" onClick={download} className="p-2 rounded-lg text-slate-500 hover:bg-slate-100" aria-label="Download"><Download size={16} /></button>
          <button type="button" onClick={() => input.current?.click()} disabled={!!busy} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-50">Replace</button>
          <button type="button" onClick={remove} className="p-2 rounded-lg text-slate-400 hover:bg-rose-50 hover:text-rose-600" aria-label="Remove resume"><Trash2 size={16} /></button>
        </div>
      ) : (
        <button type="button" onClick={() => input.current?.click()} disabled={!!busy}
          className="mt-4 w-full rounded-xl border-2 border-dashed border-slate-300 p-6 text-center text-sm text-slate-600 hover:border-emerald-500 hover:bg-emerald-50/40">
          <Upload className="mx-auto mb-2 text-slate-400" size={22} />Upload your resume, <span className="font-semibold text-emerald-700">PDF or Word</span>
          <span className="block text-xs text-slate-500 mt-1">Up to 10 MB. Only you can see it.</span></button>
      )}
      {meta && (
        <button type="button" onClick={read} disabled={!!busy}
          className="mt-3 inline-flex items-center gap-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 disabled:opacity-60 text-white text-sm font-semibold px-4 py-2.5">
          {busy === 'read' ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
          {busy === 'read' ? 'Reading your resume…' : 'Fill my profile from my resume'}</button>)}
      {busy === 'upload' && <p className="mt-3 text-sm text-slate-500 flex items-center gap-2"><Loader2 size={14} className="animate-spin" />Uploading…</p>}
      {error && <p role="alert" className="mt-3 rounded-lg bg-rose-50 p-2.5 text-sm text-rose-800">{error}</p>}
      {review && <ReviewDialog result={review} onClose={() => setReview(null)}
        onSaved={(profile, applied) => { setReview(null); onProfile(profile); notify?.(applied.length ? 'Your profile was updated from your resume.' : 'Nothing was changed.'); }} />}
    </section>
  );
}
