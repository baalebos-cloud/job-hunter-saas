import { useRef, useState } from 'react';
import { CheckCircle2, ImagePlus, Loader2, Send, X } from 'lucide-react';
import { errorText } from '../../lib/session';
import { CATEGORIES, SUPPORT_EMAIL, createTicket, screenshotProblem, signedIn } from './supportApi';

const field = 'w-full border border-slate-200 rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/40';

// Shared by the Help page and the floating help button. `compact` trims the layout for the small panel.
export default function SupportForm({ compact = false, defaultCategory = 'question', onSent }) {
  const fileRef = useRef(null);
  const [form, setForm] = useState({ category: defaultCategory, subject: '', message: '', email: '', name: '', website: '' });
  const [screenshot, setScreenshot] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(null);
  const guest = !signedIn();
  const set = (key) => (e) => setForm(f => ({ ...f, [key]: e.target.value }));

  const pick = (e) => {
    const file = e.target.files?.[0] || null;
    e.target.value = '';
    const problem = screenshotProblem(file);
    setError(problem);
    if (!problem) setScreenshot(file);
  };

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    if (form.subject.trim().length < 3) return setError('Add a short subject.');
    if (form.message.trim().length < 10) return setError('Tell us a little more (at least 10 characters).');
    if (guest && !/^\S+@\S+\.\S+$/.test(form.email.trim())) return setError('Enter your email so we can reply.');
    setBusy(true);
    try {
      const result = await createTicket({ ...form, screenshot });
      setSent(result);
      onSent?.(result);
    } catch (err) {
      setError(errorText(err, 'Your request could not be sent. Please retry or email us.'));
    } finally {
      setBusy(false);
    }
  };

  if (sent) {
    return (
      <div className="text-center py-6" role="status">
        <CheckCircle2 className="mx-auto text-emerald-600" size={36} />
        <h3 className="mt-3 font-semibold text-slate-900">Request {sent.number} sent</h3>
        <p className="mt-1 text-sm text-slate-500 max-w-sm mx-auto">
          We emailed a confirmation to <strong className="text-slate-700">{sent.email}</strong> and usually reply within one business day.
          {!guest && ' Replies also appear under My requests.'}
        </p>
        <button type="button" onClick={() => { setSent(null); setScreenshot(null); setForm(f => ({ ...f, subject: '', message: '' })); }}
          className="mt-4 text-sm font-semibold text-emerald-700 hover:text-emerald-800">Send another request</button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} noValidate className={compact ? 'space-y-3' : 'space-y-4'}>
      {/* Honeypot: hidden from people, filled in by bots. */}
      <input type="text" name="website" tabIndex={-1} autoComplete="off" value={form.website} onChange={set('website')}
        className="hidden" aria-hidden="true" />
      {guest && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="block text-sm"><span className="font-medium text-slate-700">Your email</span>
            <input type="email" required autoComplete="email" value={form.email} onChange={set('email')} className={`${field} mt-1`} /></label>
          <label className="block text-sm"><span className="font-medium text-slate-700">Name <span className="text-slate-400 font-normal">(optional)</span></span>
            <input autoComplete="name" value={form.name} onChange={set('name')} className={`${field} mt-1`} /></label>
        </div>
      )}
      <label className="block text-sm"><span className="font-medium text-slate-700">What is it about?</span>
        <select value={form.category} onChange={set('category')} className={`${field} mt-1`}>
          {CATEGORIES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select></label>
      <label className="block text-sm"><span className="font-medium text-slate-700">Subject</span>
        <input value={form.subject} onChange={set('subject')} maxLength={160} placeholder="A short summary" className={`${field} mt-1`} /></label>
      <label className="block text-sm"><span className="font-medium text-slate-700">Message</span>
        <textarea value={form.message} onChange={set('message')} maxLength={5000} rows={compact ? 4 : 6}
          placeholder={form.category === 'bug' ? 'What did you do, what did you expect, and what happened instead?' : 'How can we help?'}
          className={`${field} mt-1 resize-y`} /></label>
      <div className="flex flex-wrap items-center gap-2">
        <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" onChange={pick} className="hidden" aria-label="Attach a screenshot" />
        {screenshot ? (
          <span className="inline-flex items-center gap-2 text-xs bg-slate-100 text-slate-700 rounded-lg px-2.5 py-1.5 max-w-full">
            <ImagePlus size={14} /><span className="truncate max-w-[180px]">{screenshot.name}</span>
            <button type="button" aria-label="Remove screenshot" onClick={() => setScreenshot(null)}><X size={14} /></button>
          </span>
        ) : (
          <button type="button" onClick={() => fileRef.current?.click()}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-slate-900 border border-dashed border-slate-300 rounded-lg px-2.5 py-1.5">
            <ImagePlus size={14} />Attach a screenshot <span className="text-slate-400">(optional)</span>
          </button>
        )}
      </div>
      <p className="text-xs text-slate-400">We include the page you are on and your browser so we can reproduce problems faster.</p>
      {error && <p role="alert" className="text-sm text-rose-700 bg-rose-50 rounded-xl px-3 py-2">{error}</p>}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button type="submit" disabled={busy}
          className="inline-flex items-center gap-2 text-sm font-semibold rounded-xl px-4 py-2.5 bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-60">
          {busy ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}Send request</button>
        <a href={`mailto:${SUPPORT_EMAIL}`} className="text-xs text-slate-500 hover:text-slate-700">or email {SUPPORT_EMAIL}</a>
      </div>
    </form>
  );
}
