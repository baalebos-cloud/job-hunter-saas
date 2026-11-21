import { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, ChevronRight, Clock, Inbox, Loader2, Mail, MessageSquare, Paperclip, Send } from 'lucide-react';
import { errorText } from '../../lib/session';
import SupportForm from './SupportForm';
import {
  STATUS_TONE, SUPPORT_EMAIL, attachmentUrl, getTicket, listTickets, replyTicket, shortDate, signedIn, solveTicket,
} from './supportApi';

const card = 'bg-white border border-slate-200 rounded-2xl';

const FAQ = [
  ['How does resume tailoring work?',
    'Upload your resume and paste the job description (or start from a job on the Jobs page with “Tailor my resume”). We rewrite your resume around the role using only facts already in it, show you the result, and you download the PDF or Word copy only when you are happy with it.'],
  ['Why are some skills listed as “not found”?',
    'They appear in the job description but not in your resume. We never add them for you. If you genuinely have a skill, tick it on the result page and we regenerate the resume with it.'],
  ['My profile photo does not look right.',
    'Use the camera button on your profile, then drag, zoom or rotate the photo inside the circle before saving. JPG, PNG and WebP up to 5 MB are supported.'],
  ['Where do the jobs come from?',
    'Jobs posted by employers on Baalebos appear first. We also gather recent tech jobs from public company career boards and remote job sites, remove duplicates, and close listings older than 30 days.'],
  ['I did not get the verification email.',
    'Check your spam folder, then use “Resend verification” on your profile. If it still does not arrive, send us a request below and we will verify you manually.'],
  ['How do I delete my account and data?',
    'Go to My profile → Account → Delete account. Your resumes, applications, photo and support requests are erased.'],
];

function StatusChip({ ticket }) {
  return <span className={`inline-flex px-2 py-0.5 rounded-full text-[11px] font-semibold ring-1 ring-inset ${STATUS_TONE[ticket.status]}`}>{ticket.status_label}</span>;
}

function Thread({ id, onBack, onChanged }) {
  const [ticket, setTicket] = useState(null);
  const [reply, setReply] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [image, setImage] = useState('');

  useEffect(() => {
    let url = '';
    getTicket(id).then(async t => {
      setTicket(t);
      if (t.has_attachment) { url = await attachmentUrl(`/support/tickets/${id}/attachment`).catch(() => ''); setImage(url); }
    }).catch(err => setError(errorText(err, 'Could not load this request.')));
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [id]);

  const send = async (e) => {
    e.preventDefault();
    if (!reply.trim()) return;
    setBusy(true); setError('');
    try { setTicket(await replyTicket(id, reply.trim())); setReply(''); onChanged(); }
    catch (err) { setError(errorText(err, 'Your reply could not be sent.')); }
    finally { setBusy(false); }
  };
  const solve = async () => { setTicket(await solveTicket(id)); onChanged(); };

  return (
    <div className={`${card} p-5`}>
      <button type="button" onClick={onBack} className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"><ArrowLeft size={16} />All requests</button>
      {!ticket ? (error ? <p role="alert" className="mt-4 text-sm text-rose-700">{error}</p> : <div className="py-10 flex justify-center"><Loader2 className="animate-spin text-emerald-600" /></div>) : (
        <>
          <div className="mt-3 flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="text-xs text-slate-400">{ticket.number} · {ticket.category_label}</div>
              <h3 className="font-semibold text-slate-900 break-words">{ticket.subject}</h3>
            </div>
            <StatusChip ticket={ticket} />
          </div>
          <ol className="mt-4 space-y-3">
            {ticket.messages.map(m => (
              <li key={m.id} className={`rounded-xl p-3.5 text-sm ${m.author === 'support' ? 'bg-emerald-50 border border-emerald-100 sm:ml-8' : 'bg-slate-50 border border-slate-100 sm:mr-8'}`}>
                <div className="flex justify-between gap-2 text-xs text-slate-500 mb-1">
                  <span className="font-semibold text-slate-700">{m.author === 'support' ? 'Baalebos support' : 'You'}</span>{shortDate(m.created_at)}
                </div>
                <p className="whitespace-pre-wrap break-words text-slate-700">{m.body}</p>
              </li>
            ))}
          </ol>
          {image && <a href={image} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800"><Paperclip size={14} />View your screenshot</a>}
          <form onSubmit={send} className="mt-4">
            <label htmlFor="reply" className="text-sm font-medium text-slate-700">{ticket.status === 'solved' ? 'Need more help? Reply to reopen' : 'Add a reply'}</label>
            <textarea id="reply" rows={3} value={reply} onChange={e => setReply(e.target.value)} maxLength={5000}
              className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40" />
            {error && <p role="alert" className="text-sm text-rose-700 mt-1">{error}</p>}
            <div className="mt-2 flex flex-wrap gap-2 justify-between">
              <button type="submit" disabled={busy || !reply.trim()} className="inline-flex items-center gap-2 text-sm font-semibold rounded-xl px-4 py-2 bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50">
                {busy ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}Send reply</button>
              {ticket.status !== 'solved' && <button type="button" onClick={solve} className="text-sm font-medium text-slate-500 hover:text-slate-800">My problem is solved</button>}
            </div>
          </form>
        </>
      )}
    </div>
  );
}

function MyRequests({ refreshKey }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState('');
  const [open, setOpen] = useState(() => Number(new URLSearchParams(window.location.search).get('request')) || null);
  const load = useCallback(() => listTickets().then(d => setItems(d.items)).catch(err => setError(errorText(err, 'Could not load your requests.'))), []);
  useEffect(() => { load(); }, [load, refreshKey]);

  if (open) return <Thread id={open} onBack={() => setOpen(null)} onChanged={load} />;
  return (
    <div className={card}>
      <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-2"><Inbox size={18} className="text-slate-400" /><h2 className="font-semibold text-slate-900">My requests</h2></div>
      {error ? <p role="alert" className="p-5 text-sm text-rose-700">{error}</p>
        : !items ? <div className="py-10 flex justify-center"><Loader2 className="animate-spin text-emerald-600" /></div>
        : items.length === 0 ? <p className="p-5 text-sm text-slate-500">You have not sent any requests yet. Answers to your requests will appear here.</p>
        : <ul className="divide-y divide-slate-100">{items.map(t => (
          <li key={t.id}>
            <button type="button" onClick={() => setOpen(t.id)} className="w-full text-left px-5 py-3.5 hover:bg-slate-50 flex items-center gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2"><span className="font-medium text-slate-900 truncate">{t.subject}</span></div>
                <div className="text-xs text-slate-500 mt-0.5 truncate">{t.number} · {t.category_label} · updated {shortDate(t.updated_at)}</div>
              </div>
              <StatusChip ticket={t} /><ChevronRight size={16} className="text-slate-300 shrink-0" />
            </button>
          </li>))}
        </ul>}
    </div>
  );
}

export default function HelpPage() {
  const [refreshKey, setRefreshKey] = useState(0);
  const member = signedIn();
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-slate-900">How can we help?</h2>
        <p className="text-sm text-slate-500 mt-1">Questions, problems or ideas: real people read every request.</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {[[MessageSquare, 'Send a request', 'Use the form below. You get a request number by email.'],
          [Mail, 'Email us', <a key="m" href={`mailto:${SUPPORT_EMAIL}`} className="text-emerald-700 font-medium hover:underline">{SUPPORT_EMAIL}</a>],
          [Clock, 'Response time', 'Usually within one business day, Monday to Friday.']].map(([Icon, title, text]) => (
          <div key={title} className={`${card} p-4 flex gap-3`}>
            <span className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-700 grid place-items-center shrink-0"><Icon size={18} /></span>
            <div className="min-w-0"><div className="font-semibold text-sm text-slate-900">{title}</div><div className="text-sm text-slate-500 break-words">{text}</div></div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 items-start">
        <div className="lg:col-span-3 space-y-6 min-w-0">
          <section className={`${card} p-5 md:p-6`} aria-labelledby="contact-title">
            <h2 id="contact-title" className="font-semibold text-slate-900 mb-4">Contact support</h2>
            <SupportForm onSent={() => setRefreshKey(k => k + 1)} />
          </section>
          {member && <MyRequests refreshKey={refreshKey} />}
        </div>
        <section className="lg:col-span-2 min-w-0" aria-labelledby="faq-title">
          <h2 id="faq-title" className="font-semibold text-slate-900 mb-3">Common questions</h2>
          <div className={`${card} divide-y divide-slate-100`}>
            {FAQ.map(([q, a]) => (
              <details key={q} className="group px-5 py-3.5">
                <summary className="cursor-pointer list-none flex items-center justify-between gap-3 text-sm font-medium text-slate-800">
                  {q}<ChevronRight size={16} className="text-slate-400 shrink-0 transition-transform group-open:rotate-90" />
                </summary>
                <p className="mt-2 text-sm text-slate-600 leading-relaxed">{a}</p>
              </details>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
