import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Check, Copy, KeyRound, Loader2, Trash2 } from 'lucide-react';
import { errorText } from '../../lib/session';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });
const when = iso => (iso ? new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : 'Never');

// Settings → API keys (Enterprise). The full key is shown once, right after it is created.
export default function ApiKeys() {
  const [data, setData] = useState(null);
  const [name, setName] = useState('');
  const [created, setCreated] = useState(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const [confirm, setConfirm] = useState(null);

  const load = useCallback(() => {
    axios.get(`${API}/api-keys`, { headers: headers() })
      .then(r => setData(r.data)).catch(err => setError(errorText(err, 'Your API keys could not be loaded.')));
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {   // /settings#api (link from the API docs) lands on this section once it has loaded
    if (data && window.location.hash === '#api') document.getElementById('api')?.scrollIntoView({ block: 'start' });
  }, [data]);

  const create = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy('create'); setError(''); setCopied(false);
    try {
      const { data: key } = await axios.post(`${API}/api-keys`, { name: name.trim() }, { headers: headers() });
      setCreated(key); setName(''); load();
    } catch (err) { setError(errorText(err, 'The key could not be created. Please retry.')); }
    finally { setBusy(''); }
  };

  const revoke = async (key) => {
    setBusy(`rv${key.id}`); setError('');
    try {
      await axios.delete(`${API}/api-keys/${key.id}`, { headers: headers() });
      setConfirm(null); if (created?.id === key.id) setCreated(null); load();
    } catch (err) { setError(errorText(err, 'The key could not be revoked. Please retry.')); }
    finally { setBusy(''); }
  };

  const copy = async () => {
    try { await navigator.clipboard.writeText(created.key); setCopied(true); } catch { setCopied(false); }
  };

  const active = data?.keys?.length || 0;
  const full = data && active >= data.max_keys;
  return (
    <section id="api" className="bg-white border border-slate-200 rounded-3xl p-6 mb-6">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
        <div className="flex items-center gap-2">
          <KeyRound size={18} className="text-emerald-600" />
          <h3 className="text-slate-900 font-black text-base">API keys</h3>
        </div>
        <Link to="/developers" className="text-sm font-semibold text-emerald-700 hover:underline">API documentation</Link>
      </div>

      {!data && !error && <div className="py-6 flex justify-center"><Loader2 className="animate-spin text-emerald-600" /></div>}

      {data && !data.enabled && (
        <p className="text-sm text-slate-600 mt-2">
          {active ? 'Your keys are paused because this account does not have Enterprise right now. ' : ''}
          API access is part of Enterprise: connect your own tools to tailor resumes and search the job board.{' '}
          <a href="/pricing" className="font-semibold text-emerald-700 hover:underline">See plans</a></p>)}

      {data?.enabled && (<>
        <p className="text-sm text-slate-600 mt-2">
          Use a key to call the Baalebos API from your own tools. Up to {data.max_keys} active keys, {data.rate_limit_per_minute} requests per minute each.
          Treat keys like passwords: anyone with a key can tailor resumes and download them from this account.
        </p>
        <form onSubmit={create} className="mt-4 flex flex-col sm:flex-row gap-2">
          <input value={name} onChange={e => setName(e.target.value)} maxLength={60} placeholder="Key name, e.g. Recruiting CRM"
            aria-label="New key name" disabled={full}
            className="flex-1 px-4 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-sm outline-none focus:border-emerald-500" />
          <button type="submit" disabled={full || busy === 'create' || !name.trim()}
            className="inline-flex items-center justify-center gap-2 text-sm font-semibold rounded-xl px-4 py-2.5 bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50">
            {busy === 'create' && <Loader2 size={16} className="animate-spin" />}Create key</button>
        </form>
        {full && <p className="mt-2 text-xs text-slate-500">You have {data.max_keys} active keys. Revoke one to create another.</p>}
      </>)}

      {created && (
        <div role="status" className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <p className="text-sm font-semibold text-amber-900">Copy your new key now. It will not be shown again.</p>
          <div className="mt-2 flex flex-col sm:flex-row gap-2">
            <code className="flex-1 min-w-0 break-all text-xs bg-white border border-amber-200 rounded-lg px-3 py-2 text-slate-800" aria-label="New API key">{created.key}</code>
            <button type="button" onClick={copy}
              className="inline-flex items-center justify-center gap-1.5 text-xs font-semibold rounded-lg px-3 py-2 border border-amber-300 bg-white text-amber-900 hover:bg-amber-100">
              {copied ? <><Check size={14} />Copied</> : <><Copy size={14} />Copy</>}</button>
          </div>
          <button type="button" onClick={() => setCreated(null)} className="mt-2 text-xs font-semibold text-amber-900 underline">I have saved it</button>
        </div>)}

      {data?.keys?.length > 0 && (
        <ul className="mt-5 divide-y divide-slate-100 border border-slate-100 rounded-2xl">
          {data.keys.map(key => (
            <li key={key.id} className="p-3 flex flex-col sm:flex-row sm:items-center gap-2">
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-slate-900 truncate">{key.name}</div>
                <div className="text-xs text-slate-500 truncate"><code>{key.prefix}…</code> · created {when(key.created_at)} · last used {when(key.last_used_at)}</div>
              </div>
              {confirm === key.id ? (
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-slate-600">Revoke? Apps using it stop working at once.</span>
                  <button type="button" disabled={!!busy} onClick={() => revoke(key)} className="font-semibold rounded-lg px-2.5 py-1.5 border border-rose-200 text-rose-700">Revoke</button>
                  <button type="button" onClick={() => setConfirm(null)} className="font-semibold rounded-lg px-2.5 py-1.5 border border-slate-200">Cancel</button>
                </div>
              ) : (
                <button type="button" onClick={() => setConfirm(key.id)} aria-label={`Revoke ${key.name}`}
                  className="self-start sm:self-auto inline-flex items-center gap-1 text-xs font-semibold rounded-lg px-2.5 py-1.5 border border-slate-200 text-rose-700 hover:bg-rose-50"><Trash2 size={13} />Revoke</button>)}
            </li>))}
        </ul>)}

      {error && <p role="alert" className="mt-3 text-sm text-rose-700 bg-rose-50 rounded-xl p-3">{error}</p>}
    </section>
  );
}
