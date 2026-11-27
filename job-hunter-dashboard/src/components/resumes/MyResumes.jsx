import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Download, ExternalLink, Eye, FileText, Loader2, PencilLine, RefreshCw, Trash2, X } from 'lucide-react';
import { errorText, filenameFromDisposition } from '../../lib/session';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });

function when(iso) {
  return iso ? new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '';
}

// Pro and Enterprise keep their last 30 tailored resumes; Free sees the latest.
export default function MyResumes() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [preview, setPreview] = useState(null);   // { url, title }
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.url); }, [preview]);

  const load = useCallback(() => {
    setError('');
    axios.get(`${API}/resume/history`, { headers: headers() })
      .then(r => setData(r.data)).catch(err => setError(errorText(err, 'Could not load your resumes.')));
  }, []);
  useEffect(() => { load(); }, [load]);

  // Enterprise: add the account's branding to PDF and Word downloads (remembered on this device).
  const [branding, setBranding] = useState(null);
  const [branded, setBranded] = useState(() => { try { return localStorage.getItem('brandedDownloads') === '1'; } catch { return false; } });
  useEffect(() => {
    axios.get(`${API}/branding`, { headers: headers() }).then(r => setBranding(r.data)).catch(() => {});
  }, []);
  const brandingReady = branding?.enabled && branding?.configured;
  const toggleBranded = (on) => {
    setBranded(on);
    try { localStorage.setItem('brandedDownloads', on ? '1' : '0'); } catch { /* ignore */ }
  };

  const fetchFile = async (item, kind) => {
    const base = kind === 'docx' ? `/resume/download/${item.task_id}/docx`
      : kind === 'preview' ? `/resume/preview/${item.task_id}` : `/resume/download/${item.task_id}`;
    const path = kind !== 'preview' && brandingReady && branded ? `${base}?branded=true` : base;
    setBusy(`${item.task_id}:${kind}`); setError('');
    try {
      const res = await axios.get(`${API}${path}`, { headers: headers(), responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      if (kind === 'preview') {
        setPreview({ url, title: `${item.job_title}${item.company ? ` · ${item.company}` : ''}` });
        return;
      } else {
        const link = Object.assign(document.createElement('a'), {
          href: url, download: filenameFromDisposition(res.headers['content-disposition'], kind === 'docx' ? 'Resume.docx' : 'Resume.pdf') });
        document.body.appendChild(link); link.click(); link.remove();
      }
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      setError(errorText(err, 'That file could not be opened. Please retry.'));
    } finally { setBusy(''); }
  };

  const tailorAgain = (item) => {
    if (item.job_id) { navigate(`/optimizer?job=${item.job_id}`); return; }
    try { sessionStorage.setItem('tailorAgain', JSON.stringify({ title: item.job_title, description: item.job_description })); } catch { /* ignore */ }
    navigate('/optimizer');
  };

  const remove = async (item) => {
    setBusy(`${item.task_id}:delete`);
    try {
      await axios.delete(`${API}/resume/${item.task_id}`, { headers: headers() });
      setConfirmDelete(null); load();
    } catch (err) { setError(errorText(err, 'Could not delete this resume.')); }
    finally { setBusy(''); }
  };

  const btn = 'inline-flex items-center gap-1.5 text-xs font-semibold rounded-lg px-2.5 py-1.5 border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-50';
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">My resumes</h2>
          <p className="text-sm text-slate-500 mt-1">
            {data?.history_enabled ? `Your last ${data.limit} tailored resumes are kept here.` : 'Your latest tailored resume.'}
          </p>
        </div>
        <button type="button" onClick={() => navigate('/optimizer')}
          className="text-sm font-semibold rounded-xl px-4 py-2 bg-emerald-600 text-white hover:bg-emerald-700">Tailor a new resume</button>
      </div>

      {brandingReady && (
        <label className="flex items-center gap-2 text-sm text-slate-700 bg-white border border-slate-200 rounded-xl px-4 py-3 cursor-pointer">
          <input type="checkbox" className="accent-emerald-600" checked={branded} onChange={e => toggleBranded(e.target.checked)} />
          Add {branding.brand_name ? <strong>{branding.brand_name}</strong> : 'your'} branding to PDF and Word downloads
          <a href="/settings#branding" className="ml-auto text-xs font-semibold text-emerald-700 hover:underline">Edit branding</a>
        </label>)}

      {error && <p role="alert" className="text-sm text-rose-700 bg-rose-50 rounded-xl p-3">{error}</p>}
      {!data && !error && <div className="py-16 flex justify-center"><Loader2 className="animate-spin text-emerald-600" /></div>}

      {data && data.items.length === 0 && (
        <div className="bg-white border border-dashed border-slate-300 rounded-2xl p-10 text-center text-sm text-slate-500">
          No tailored resumes yet. Tailor your resume to a job and it will appear here.</div>)}

      {data && data.items.length > 0 && (
        <ul className="bg-white border border-slate-200 rounded-2xl divide-y divide-slate-100">
          {data.items.map(item => (
            <li key={item.task_id} className="p-4 flex flex-col md:flex-row md:items-center gap-3">
              <div className="flex items-start gap-3 min-w-0 flex-1">
                <span className="w-10 h-10 shrink-0 rounded-xl bg-emerald-50 text-emerald-700 grid place-items-center"><FileText size={18} /></span>
                <div className="min-w-0">
                  <div className="font-semibold text-slate-900 truncate">{item.job_title}{item.company ? ` · ${item.company}` : ''}</div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {when(item.created_at)}
                    {item.score_after != null && <> · match {item.score_before != null ? `${Math.round(item.score_before)}% → ` : ''}<span className="font-semibold text-emerald-700">{Math.round(item.score_after)}%</span></>}
                  </div>
                </div>
              </div>
              {confirmDelete === item.task_id ? (
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="text-slate-600">Delete this resume for good?</span>
                  <button type="button" className={`${btn} border-rose-200 text-rose-700`} disabled={!!busy} onClick={() => remove(item)}>Delete</button>
                  <button type="button" className={btn} onClick={() => setConfirmDelete(null)}>Cancel</button>
                </div>
              ) : (
                <div className="flex flex-wrap gap-2">
                  <button type="button" className={btn} disabled={!!busy} onClick={() => fetchFile(item, 'preview')}><Eye size={14} />Preview</button>
                  <button type="button" className={btn} disabled={!!busy} onClick={() => fetchFile(item, 'pdf')}><Download size={14} />PDF</button>
                  <button type="button" className={btn} disabled={!!busy} onClick={() => fetchFile(item, 'docx')}><Download size={14} />Word</button>
                  <button type="button" className={btn} onClick={() => navigate(`/studio?from=${encodeURIComponent(item.task_id)}`)}><PencilLine size={14} />Studio</button>
                  <button type="button" className={btn} onClick={() => tailorAgain(item)}><RefreshCw size={14} />Tailor again</button>
                  <button type="button" className={`${btn} text-rose-700`} aria-label="Delete resume" onClick={() => setConfirmDelete(item.task_id)}><Trash2 size={14} /></button>
                </div>)}
            </li>))}
        </ul>)}

      {data && !data.history_enabled && data.total > data.items.length && (
        <p className="text-sm text-slate-600 bg-slate-50 border border-slate-200 rounded-xl p-4">
          You have {data.total} tailored resumes. Pro and Enterprise keep your last 30 here.{' '}
          <a href="/pricing" className="font-semibold text-emerald-700 hover:underline">See plans</a></p>)}

      {preview && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 p-3 sm:p-6 flex" role="dialog" aria-modal="true" aria-label="Resume preview">
          <div className="m-auto w-full max-w-4xl h-full bg-white rounded-2xl flex flex-col overflow-hidden">
            <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-100">
              <span className="font-semibold text-slate-900 truncate flex-1">{preview.title}</span>
              <a href={preview.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 hover:underline"><ExternalLink size={14} />Open in new tab</a>
              <button type="button" onClick={() => setPreview(null)} aria-label="Close preview" className="p-1 rounded-lg hover:bg-slate-100"><X size={18} /></button>
            </div>
            <iframe title="Tailored resume preview" src={`${preview.url}#toolbar=0&navpanes=0&view=FitH`} className="flex-1 w-full bg-slate-100" />
          </div>
        </div>)}
    </div>
  );
}
