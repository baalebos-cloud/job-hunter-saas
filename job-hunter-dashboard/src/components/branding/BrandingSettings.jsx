import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { ImagePlus, Loader2, Palette, Trash2 } from 'lucide-react';
import { errorText } from '../../lib/session';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });
const HEX = /^#[0-9a-fA-F]{6}$/;

// Settings → Branding (Enterprise): brand name, logo and accent colour for branded downloads.
export default function BrandingSettings() {
  const fileRef = useRef(null);
  const [info, setInfo] = useState(null);
  const [form, setForm] = useState({ brand_name: '', accent_color: '#059669' });
  const [logoUrl, setLogoUrl] = useState(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const loadLogo = useCallback(async (has) => {
    setLogoUrl(old => { if (old) URL.revokeObjectURL(old); return null; });
    if (!has) return;
    try {
      const res = await axios.get(`${API}/branding/logo`, { headers: headers(), responseType: 'blob' });
      setLogoUrl(URL.createObjectURL(res.data));
    } catch { /* preview only */ }
  }, []);

  const apply = useCallback((data) => {
    setInfo(data);
    setForm({ brand_name: data.brand_name || '', accent_color: data.accent_color || '#059669' });
    loadLogo(data.has_logo);
  }, [loadLogo]);

  useEffect(() => {
    axios.get(`${API}/branding`, { headers: headers() })
      .then(r => apply(r.data)).catch(err => setError(errorText(err, 'Branding could not be loaded.')));
  }, [apply]);

  useEffect(() => {   // /settings#branding (link from My resumes) lands on this section once it has loaded
    if (info && window.location.hash === '#branding') document.getElementById('branding')?.scrollIntoView({ block: 'start' });
  }, [info]);

  const run = async (key, fn, success) => {
    setBusy(key); setError(''); setNotice('');
    try { const { data } = await fn(); apply(data); setNotice(success); }
    catch (err) { setError(errorText(err, 'That did not work. Please retry.')); }
    finally { setBusy(''); }
  };

  const save = (e) => {
    e.preventDefault();
    run('save', () => axios.put(`${API}/branding`, form, { headers: headers() }), 'Branding saved.');
  };
  const upload = (file) => {
    if (!file) return;
    const body = new FormData(); body.append('file', file);
    run('logo', () => axios.post(`${API}/branding/logo`, body, { headers: headers() }), 'Logo uploaded.');
  };

  const accent = HEX.test(form.accent_color) ? form.accent_color : '#059669';
  const editable = info?.can_edit;
  return (
    <section id="branding" className="bg-white border border-slate-200 rounded-3xl p-6 mb-6">
      <div className="flex items-center gap-2 mb-1">
        <Palette size={18} className="text-emerald-600" />
        <h3 className="text-slate-900 font-black text-base">Branding</h3>
      </div>
      {!info && !error && <div className="py-6 flex justify-center"><Loader2 className="animate-spin text-emerald-600" /></div>}

      {info && !info.enabled && (
        <p className="text-sm text-slate-600 mt-2">Custom branding is part of Enterprise: add your name and logo to downloaded resumes.{' '}
          <a href="/pricing" className="font-semibold text-emerald-700 hover:underline">See plans</a></p>)}

      {info?.enabled && (<>
        <p className="text-sm text-slate-600 mt-2">
          {info.managed_by
            ? <>Your team uses <strong>{info.managed_by}</strong>&apos;s branding. Only they can change it.</>
            : 'Add your brand to the header and footer of downloaded resumes. You choose per download in My resumes; the resume itself is not changed.'}
        </p>

        {editable && (
          <form onSubmit={save} className="mt-4 space-y-4">
            <label className="block">
              <span className="block text-xs font-black uppercase tracking-widest text-slate-500 mb-2">Brand name</span>
              <input value={form.brand_name} maxLength={60} onChange={e => setForm(f => ({ ...f, brand_name: e.target.value }))}
                placeholder="e.g. Acme Talent Partners" className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-sm outline-none focus:border-emerald-500" />
            </label>
            <div>
              <span className="block text-xs font-black uppercase tracking-widest text-slate-500 mb-2">Accent colour</span>
              <div className="flex items-center gap-2">
                <input type="color" value={accent} onChange={e => setForm(f => ({ ...f, accent_color: e.target.value }))}
                  aria-label="Accent colour picker" className="h-10 w-12 rounded-lg border border-slate-200 bg-white p-1" />
                <input value={form.accent_color} onChange={e => setForm(f => ({ ...f, accent_color: e.target.value }))} maxLength={7}
                  aria-label="Accent colour hex" className="w-28 px-3 py-2 rounded-xl border border-slate-200 bg-slate-50 text-sm font-mono outline-none focus:border-emerald-500" />
              </div>
            </div>
            <div>
              <span className="block text-xs font-black uppercase tracking-widest text-slate-500 mb-2">Logo</span>
              <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" aria-label="Logo file"
                onChange={e => { upload(e.target.files?.[0]); e.target.value = ''; }} />
              <div className="flex flex-wrap items-center gap-2">
                <button type="button" onClick={() => fileRef.current?.click()} disabled={!!busy}
                  className="inline-flex items-center gap-1.5 text-sm font-semibold rounded-xl px-3 py-2 border border-slate-200 bg-white text-slate-700 hover:bg-slate-50">
                  {busy === 'logo' ? <Loader2 size={15} className="animate-spin" /> : <ImagePlus size={15} />}{info.has_logo ? 'Replace logo' : 'Upload logo'}</button>
                {info.has_logo && (
                  <button type="button" disabled={!!busy} onClick={() => run('rmlogo', () => axios.delete(`${API}/branding/logo`, { headers: headers() }), 'Logo removed.')}
                    className="inline-flex items-center gap-1.5 text-sm font-semibold rounded-xl px-3 py-2 border border-slate-200 bg-white text-rose-700 hover:bg-rose-50"><Trash2 size={15} />Remove</button>)}
                <span className="text-xs text-slate-500">PNG, JPG or WebP, up to 1 MB. A wide logo on a transparent background works best.</span>
              </div>
            </div>
            <button type="submit" disabled={!!busy}
              className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold px-5 py-2.5 rounded-xl text-sm disabled:opacity-60">
              {busy === 'save' && <Loader2 size={15} className="animate-spin" />}Save branding</button>
          </form>)}

        {/* Preview of the header and footer as they appear on the page */}
        <div className="mt-5">
          <span className="block text-xs font-black uppercase tracking-widest text-slate-500 mb-2">Preview</span>
          <div className="relative mx-auto max-w-sm aspect-[1/1.29] bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden" aria-label="Branded resume preview">
            <div className="h-1" style={{ background: accent }} />
            <div className="flex justify-end px-3 pt-1 h-7 items-start">
              {logoUrl ? <img src={logoUrl} alt="Your logo" className="max-h-5 max-w-[30%] object-contain" />
                : form.brand_name ? <span className="text-[9px] font-semibold" style={{ color: accent }}>{form.brand_name}</span> : null}
            </div>
            <div className="px-6 space-y-2">
              <div className="mx-auto h-2.5 w-24 rounded bg-slate-300" /><div className="mx-auto h-1.5 w-32 rounded bg-slate-200" />
              {[0, 1, 2].map(i => (<div key={i} className="pt-2 space-y-1.5"><div className="h-1.5 w-20 rounded bg-slate-300" />
                <div className="h-1 w-full rounded bg-slate-100" /><div className="h-1 w-5/6 rounded bg-slate-100" /><div className="h-1 w-4/6 rounded bg-slate-100" /></div>))}
            </div>
            {form.brand_name && (
              <div className="absolute bottom-2 inset-x-0 flex justify-center">
                <span className="text-[8px] text-slate-500 border-t pt-0.5" style={{ borderColor: accent }}>Prepared by {form.brand_name}</span>
              </div>)}
          </div>
        </div>
      </>)}

      {notice && <p role="status" className="mt-3 text-sm text-emerald-800 bg-emerald-50 rounded-xl p-3">{notice}</p>}
      {error && <p role="alert" className="mt-3 text-sm text-rose-700 bg-rose-50 rounded-xl p-3">{error}</p>}
    </section>
  );
}
