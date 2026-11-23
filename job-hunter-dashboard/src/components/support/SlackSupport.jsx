import { useEffect, useState } from 'react';
import axios from 'axios';
import { CheckCircle2, Hash, Loader2 } from 'lucide-react';
import { errorText } from '../../lib/session';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });
const card = 'bg-white border border-slate-200 rounded-2xl';
const field = 'w-full px-3 py-2 rounded-xl border border-slate-200 bg-slate-50 text-sm outline-none focus:border-emerald-500';

const STEPS = { requested: 1, invited: 2, connected: 3 };

// Help & support → Dedicated Slack support (Enterprise).
export default function SlackSupport() {
  const [state, setState] = useState(null);
  const [form, setForm] = useState({ company: '', slack_plan: 'paid', emails: '', message: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    axios.get(`${API}/support/slack`, { headers: headers() }).then(r => setState(r.data)).catch(() => setState(null));
  }, []);
  if (!state) return null;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError('');
    const emails = form.emails.split(/[\s,;]+/).map(s => s.trim()).filter(Boolean);
    try {
      const { data } = await axios.post(`${API}/support/slack`, { ...form, emails, message: form.message || null }, { headers: headers() });
      setState(s => ({ ...s, request: data }));
    } catch (err) { setError(errorText(err, 'The request could not be sent. Please retry.')); }
    finally { setBusy(false); }
  };

  const request = state.request;
  return (
    <section className={`${card} p-5 md:p-6`} aria-labelledby="slack-title">
      <div className="flex items-center gap-2 mb-1">
        <span className="w-8 h-8 rounded-lg bg-violet-50 text-violet-700 grid place-items-center"><Hash size={16} /></span>
        <h2 id="slack-title" className="font-semibold text-slate-900">Dedicated Slack support</h2>
      </div>

      {!state.eligible && (
        <p className="text-sm text-slate-600 mt-2">Enterprise includes a shared Slack channel with our support team.{' '}
          <a href="/pricing" className="font-semibold text-emerald-700 hover:underline">See plans</a></p>)}

      {state.eligible && request && (
        <div className="mt-3 space-y-3">
          <ol className="flex flex-wrap gap-2 text-xs" aria-label="Progress">
            {[['Requested', 1], ['Invitation sent', 2], ['Connected', 3]].map(([label, n]) => (
              <li key={label} className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full ${STEPS[request.status] >= n ? 'bg-emerald-50 text-emerald-800 font-semibold' : 'bg-slate-100 text-slate-500'}`}>
                {STEPS[request.status] >= n && <CheckCircle2 size={13} />}{label}</li>))}
          </ol>
          <p className="text-sm text-slate-600">
            {request.status === 'requested' && <>We are setting up a channel for <strong>{request.company}</strong>. You will get an email, and an invitation from Slack, when it is ready.</>}
            {request.status === 'invited' && <>We invited {request.emails.join(', ')} to <strong>#{request.channel_name}</strong> with Slack Connect. Accept the invitation from Slack (check your email or Slack). A Slack admin at your company may need to approve it.</>}
            {request.status === 'connected' && <>Your team is connected in <strong>#{request.channel_name}</strong>. Message us there any time.</>}
          </p>
          {request.staff_note && <p className="text-sm text-slate-700 bg-slate-50 border-l-2 border-emerald-500 rounded-lg p-3 whitespace-pre-line">{request.staff_note}</p>}
        </div>)}

      {state.eligible && !request && !state.can_request && (
        <p className="text-sm text-slate-600 mt-2">Your team owner can request a shared Slack channel for your team. Once it is set up, it shows here.</p>)}

      {state.eligible && !request && state.can_request && (
        <form onSubmit={submit} className="mt-3 space-y-3">
          <p className="text-sm text-slate-600">Get a shared Slack channel with our support team, connected to your company&apos;s Slack through Slack Connect.</p>
          <label className="block text-sm"><span className="font-medium text-slate-700">Company name</span>
            <input required minLength={2} maxLength={120} value={form.company} onChange={e => setForm(f => ({ ...f, company: e.target.value }))} className={`${field} mt-1`} /></label>
          <label className="block text-sm"><span className="font-medium text-slate-700">Your company&apos;s Slack</span>
            <select value={form.slack_plan} onChange={e => setForm(f => ({ ...f, slack_plan: e.target.value }))} className={`${field} mt-1`}>
              <option value="paid">Paid plan (Pro, Business+ or Enterprise)</option>
              <option value="free">Free plan</option>
              <option value="none">We do not use Slack yet</option>
            </select></label>
          {form.slack_plan !== 'paid' && (
            <p className="text-xs text-amber-800 bg-amber-50 rounded-lg p-2.5">
              Slack requires a paid plan on both sides for shared channels. On a free plan or new to Slack, your workspace can join
              with Slack&apos;s one-time free 90-day trial; after it ends, the channel disconnects unless you upgrade. One-to-one Slack
              messages with us and email support keep working either way.</p>)}
          <label className="block text-sm"><span className="font-medium text-slate-700">Who should we invite? <span className="font-normal text-slate-500">(you are included; up to 9 more emails)</span></span>
            <textarea rows={2} value={form.emails} onChange={e => setForm(f => ({ ...f, emails: e.target.value }))} placeholder="colleague@company.com, cto@company.com" className={`${field} mt-1`} /></label>
          <label className="block text-sm"><span className="font-medium text-slate-700">Anything we should know? <span className="font-normal text-slate-500">(optional)</span></span>
            <textarea rows={2} maxLength={2000} value={form.message} onChange={e => setForm(f => ({ ...f, message: e.target.value }))} className={`${field} mt-1`} /></label>
          {error && <p role="alert" className="text-sm text-rose-700 bg-rose-50 rounded-xl p-3">{error}</p>}
          <button type="submit" disabled={busy}
            className="inline-flex items-center gap-2 text-sm font-semibold rounded-xl px-4 py-2.5 bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-60">
            {busy && <Loader2 size={15} className="animate-spin" />}Request Slack channel</button>
        </form>)}
    </section>
  );
}
