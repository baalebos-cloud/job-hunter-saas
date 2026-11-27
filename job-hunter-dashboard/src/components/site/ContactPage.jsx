import { useState } from 'react';
import axios from 'axios';
import { CheckCircle2, Loader2, Mail } from 'lucide-react';
import { errorText } from '../../lib/session';
import PublicPage from './PublicPage';
import SEO from '../SEO';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const TOPICS = [['question', 'A question'], ['billing', 'Billing or a refund'], ['bug', 'Something is not working'], ['jobs', 'Hiring or jobs on Baalebos'], ['other', 'Something else']];
const input = 'w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm outline-none focus:border-emerald-600 focus:ring-4 focus:ring-emerald-600/10';

// /contact  Sends a support request (the same queue as Help & support), answered by email.
export default function ContactPage() {
  const signedIn = (() => { try { return !!localStorage.getItem('token'); } catch { return false; } })();
  const [form, setForm] = useState({ name: '', email: '', category: 'question', subject: '', message: '', website: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState(null);
  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setError('');
    const data = new FormData();
    Object.entries({ ...form, page: '/contact' }).forEach(([k, v]) => data.append(k, v));
    try {
      const headers = signedIn ? { Authorization: `Bearer ${localStorage.getItem('token')}` } : {};
      const r = await axios.post(`${API}/support/tickets`, data, { headers });
      setSent(r.data);
    } catch (err) { setError(errorText(err, 'Your message could not be sent. Please retry, or email support@baalebo.xyz.')); }
    finally { setBusy(false); }
  };

  return (
    <PublicPage>
      <SEO path="/contact" title="Contact" description="Contact Baalebos support." />
      <section className="max-w-5xl mx-auto px-5 sm:px-8 py-16 grid md:grid-cols-[1fr_1.3fr] gap-10">
        <div>
          <p className="text-sm font-bold uppercase tracking-widest text-emerald-700">Contact</p>
          <h1 className="mt-3 text-4xl font-extrabold tracking-tight">Talk to us</h1>
          <p className="mt-4 text-slate-700 leading-7">Questions about your account, billing, hiring on Baalebos or your data: write to us and we reply by email.</p>
          <a href="mailto:support@baalebo.xyz" className="mt-6 inline-flex items-center gap-2 font-semibold text-emerald-800"><Mail size={18} />support@baalebo.xyz</a>
          <p className="mt-6 text-sm text-slate-500">Already using Baalebos? <a href="/help" className="font-semibold text-slate-800 underline">Help &amp; support</a> shows the status of your requests.</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          {sent ? (
            <div role="status">
              <CheckCircle2 className="text-emerald-600" size={32} />
              <h2 className="mt-3 text-xl font-semibold">Message sent</h2>
              <p className="mt-2 text-sm text-slate-600">Your reference is <b>{sent.number}</b>. We sent a confirmation to {sent.email} and will reply there.</p>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              {!signedIn && <div className="grid sm:grid-cols-2 gap-4">
                <label className="text-sm font-medium">Name<input className={`${input} mt-1.5`} value={form.name} onChange={set('name')} maxLength={120} autoComplete="name" /></label>
                <label className="text-sm font-medium">Email<input type="email" required className={`${input} mt-1.5`} value={form.email} onChange={set('email')} autoComplete="email" /></label>
              </div>}
              <label className="block text-sm font-medium">Topic
                <select className={`${input} mt-1.5`} value={form.category} onChange={set('category')}>{TOPICS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
              <label className="block text-sm font-medium">Subject<input required minLength={3} maxLength={160} className={`${input} mt-1.5`} value={form.subject} onChange={set('subject')} /></label>
              <label className="block text-sm font-medium">Message<textarea required minLength={10} rows={6} className={`${input} mt-1.5 resize-y`} value={form.message} onChange={set('message')} /></label>
              <input type="text" tabIndex={-1} autoComplete="off" aria-hidden="true" className="hidden" value={form.website} onChange={set('website')} />
              {error && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
              <button type="submit" disabled={busy} className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 disabled:opacity-60 text-white font-semibold px-5 py-3">
                {busy && <Loader2 size={16} className="animate-spin" />}Send message</button>
            </form>)}
        </div>
      </section>
    </PublicPage>
  );
}
