import { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, CheckCircle2, Mail, Paperclip, Send } from 'lucide-react';
import axios from 'axios';
import { adminGet, adminPatch, adminPost, ago, device, message, when } from '../adminApi';
import { Banner, Button, Chip, Empty, Pager, SearchInput, Segmented, Spinner, card } from '../ui';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const STATUS_TONE = { open: 'amber', answered: 'green', solved: 'slate' };

function Screenshot({ id }) {
  const [url, setUrl] = useState('');
  useEffect(() => {
    let made = '';
    axios.get(`${API}/support/admin/tickets/${id}/attachment`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }, responseType: 'blob',
    }).then(r => { made = URL.createObjectURL(r.data); setUrl(made); }).catch(() => {});
    return () => { if (made) URL.revokeObjectURL(made); };
  }, [id]);
  if (!url) return null;
  return (
    <a href={url} target="_blank" rel="noreferrer" className="block mt-3">
      <img src={url} alt="Screenshot attached to the request" className="max-h-56 rounded-lg border border-slate-200" />
    </a>
  );
}

function Detail({ id, onBack, onChanged, notify }) {
  const [ticket, setTicket] = useState(null);
  const [reply, setReply] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    setTicket(null); setReply(''); setError('');
    adminGet(`/support/admin/tickets/${id}`).then(setTicket).catch(err => setError(message(err, 'Could not load the request.')));
  }, [id]);

  const send = async (solve) => {
    if (!reply.trim()) return;
    setBusy(solve ? 'solve' : 'send'); setError('');
    try {
      setTicket(await adminPost(`/support/admin/tickets/${id}/reply`, { body: reply.trim(), solve }));
      setReply('');
      notify(solve ? 'Reply sent and request marked solved' : 'Reply sent to the requester');
      onChanged();
    } catch (err) { setError(message(err, 'The reply could not be sent.')); }
    finally { setBusy(''); }
  };
  const setStatus = async (status) => {
    try { setTicket(await adminPatch(`/support/admin/tickets/${id}`, { status })); onChanged(); }
    catch (err) { setError(message(err, 'Could not change the status.')); }
  };

  if (error && !ticket) return <div className="p-5"><Banner>{error}</Banner></div>;
  if (!ticket) return <Spinner />;
  return (
    <div className="p-5">
      <button type="button" onClick={onBack} className="lg:hidden mb-3 inline-flex items-center gap-1 text-sm text-slate-500"><ArrowLeft size={16} />Back to inbox</button>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs text-slate-400">{ticket.number} · {ticket.category_label} · opened {when(ticket.created_at)}</div>
          <h3 className="text-lg font-semibold text-slate-900 break-words">{ticket.subject}</h3>
        </div>
        <Chip tone={STATUS_TONE[ticket.status]}>{ticket.status_label}</Chip>
      </div>
      <dl className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-sm">
        <div className="flex gap-2 min-w-0"><dt className="text-slate-500">From</dt>
          <dd className="truncate"><a href={`mailto:${ticket.email}`} className="text-emerald-700 hover:underline">{ticket.name ? `${ticket.name} · ` : ''}{ticket.email}</a></dd></div>
        <div className="flex gap-2"><dt className="text-slate-500">Account</dt><dd>{ticket.user_id ? `User #${ticket.user_id}` : 'Not signed in'}</dd></div>
        <div className="flex gap-2 min-w-0"><dt className="text-slate-500">Page</dt><dd className="truncate font-mono text-xs leading-5">{ticket.page || '—'}</dd></div>
        <div className="flex gap-2"><dt className="text-slate-500">Browser</dt><dd>{device(ticket.user_agent)}</dd></div>
      </dl>
      {ticket.has_attachment && <Screenshot id={ticket.id} />}
      <ol className="mt-5 space-y-3">
        {ticket.messages.map(m => (
          <li key={m.id} className={`rounded-xl p-3.5 text-sm ${m.author === 'support' ? 'bg-emerald-50 border border-emerald-100 sm:ml-10' : 'bg-slate-50 border border-slate-100 sm:mr-10'}`}>
            <div className="flex justify-between gap-2 text-xs text-slate-500 mb-1">
              <span className="font-semibold text-slate-700">{m.author === 'support' ? 'Support' : (ticket.name || ticket.email)}</span>{when(m.created_at)}
            </div>
            <p className="whitespace-pre-wrap break-words text-slate-700">{m.body}</p>
          </li>
        ))}
      </ol>
      <div className="mt-5">
        <label htmlFor="staff-reply" className="text-sm font-medium text-slate-700">Reply to {ticket.email}</label>
        <textarea id="staff-reply" rows={5} value={reply} onChange={e => setReply(e.target.value)} maxLength={5000}
          placeholder="Your answer is emailed to the requester and shown under their requests."
          className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40" />
        {error && <div className="mt-2"><Banner>{error}</Banner></div>}
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Button variant="primary" icon={Send} busy={busy === 'send'} disabled={!reply.trim() || !!busy} onClick={() => send(false)}>Send reply</Button>
          <Button icon={CheckCircle2} busy={busy === 'solve'} disabled={!reply.trim() || !!busy} onClick={() => send(true)}>Send and mark solved</Button>
          <span className="flex-1" />
          {ticket.status !== 'solved'
            ? <Button size="sm" onClick={() => setStatus('solved')}>Mark solved</Button>
            : <Button size="sm" onClick={() => setStatus('open')}>Reopen</Button>}
        </div>
      </div>
    </div>
  );
}

export default function SupportTab({ notify }) {
  const [status, setStatus] = useState('open');
  const [q, setQ] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);

  const load = useCallback(async () => {
    setError('');
    try { setData(await adminGet('/support/admin/tickets', { status: status === 'all' ? undefined : status, q: query || undefined, page, page_size: 25 })); }
    catch (err) { setError(message(err, 'Could not load support requests.')); }
  }, [status, query, page]);
  useEffect(() => { load(); }, [load]);

  const counts = data?.counts || {};
  return (
    <div className={`${card} overflow-hidden`}>
      <div className="px-5 py-4 flex flex-wrap items-center justify-between gap-3 border-b border-slate-100">
        <div>
          <h2 className="font-semibold text-slate-900">Support inbox</h2>
          <p className="text-xs text-slate-500 mt-0.5 inline-flex items-center gap-1"><Mail size={12} />New requests are also emailed to {data?.support_email || 'the support inbox'}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Segmented value={status} onChange={v => { setStatus(v); setPage(1); }}
            options={[['open', `Waiting (${counts.open ?? 0})`], ['answered', `Answered (${counts.answered ?? 0})`], ['solved', `Solved (${counts.solved ?? 0})`], ['all', 'All']]} />
          <SearchInput value={q} onChange={setQ} onSubmit={() => { setQuery(q.trim()); setPage(1); }} placeholder="Search email, subject or BB-number" width="w-60" />
        </div>
      </div>
      {error && <div className="p-5"><Banner>{error}</Banner></div>}
      {!data ? <Spinner /> : (
        <div className="grid grid-cols-1 lg:grid-cols-5 min-h-[420px]">
          <div className={`lg:col-span-2 lg:border-r border-slate-100 ${selected ? 'hidden lg:block' : ''}`}>
            {data.items.length === 0 ? <Empty>{status === 'open' ? 'No one is waiting. Nice work.' : 'No requests here.'}</Empty> : (
              <ul className="divide-y divide-slate-100">
                {data.items.map(t => (
                  <li key={t.id}>
                    <button type="button" onClick={() => setSelected(t.id)} aria-current={selected === t.id ? 'true' : undefined}
                      className={`w-full text-left px-5 py-3.5 hover:bg-slate-50 ${selected === t.id ? 'bg-emerald-50/60' : ''}`}>
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium text-sm text-slate-900 truncate">{t.subject}</span>
                        <span className="text-[11px] text-slate-400 whitespace-nowrap">{ago(t.updated_at)}</span>
                      </div>
                      <div className="mt-0.5 text-xs text-slate-500 truncate">{t.number} · {t.name || t.email}</div>
                      <div className="mt-1 flex items-center gap-1.5">
                        <Chip tone={STATUS_TONE[t.status]}>{t.status_label}</Chip>
                        <Chip>{t.category_label}</Chip>
                        {t.has_attachment && <Paperclip size={12} className="text-slate-400" aria-label="Has screenshot" />}
                      </div>
                      {t.preview && <p className="mt-1 text-xs text-slate-500 line-clamp-2">{t.preview}</p>}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </div>
          <div className={`lg:col-span-3 min-w-0 ${selected ? '' : 'hidden lg:block'}`}>
            {selected ? <Detail id={selected} onBack={() => setSelected(null)} onChanged={load} notify={notify} />
              : <Empty>Select a request to read and reply.</Empty>}
          </div>
        </div>
      )}
    </div>
  );
}
