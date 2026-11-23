/* eslint-disable react/prop-types -- the project does not use the prop-types package */
import { useCallback, useEffect, useState } from 'react';
import { ExternalLink, Hash } from 'lucide-react';
import { adminGet, adminPatch, ago, message } from '../adminApi';
import { Banner, Button, Chip, Empty, Spinner, card } from '../ui';

const TONE = { requested: 'amber', invited: 'blue', connected: 'green', closed: 'slate' };
const GUIDE = 'https://slack.com/help/articles/115004151203-Slack-Connect-guide--Work-with-external-organizations';

function Request({ item, onSaved, notify }) {
  const [channel, setChannel] = useState(item.channel_name || '');
  const [note, setNote] = useState(item.staff_note || '');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  const save = async (status) => {
    setBusy(status); setError('');
    try {
      await adminPatch(`/support/admin/slack/${item.id}`, { status, channel_name: channel || null, staff_note: note });
      notify?.(status === 'invited' ? `${item.company} was emailed that the channel is ready.` : 'Saved.');
      onSaved();
    } catch (err) { setError(message(err, 'Could not save.')); }
    finally { setBusy(''); }
  };

  return (
    <li className="p-5 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold text-slate-900">{item.company}</span>
        <Chip tone={TONE[item.status]}>{item.status_label}</Chip>
        <Chip tone={item.slack_plan === 'paid' ? 'green' : 'amber'}>{item.slack_plan_label}</Chip>
        <span className="ml-auto text-xs text-slate-400">Requested {ago(item.created_at)}</span>
      </div>
      <div className="text-sm text-slate-600"><span className="text-slate-500">Invite:</span> {item.emails.join(', ')}</div>
      {item.message && <p className="text-sm text-slate-700 bg-slate-50 rounded-lg p-3 whitespace-pre-line">{item.message}</p>}
      {item.slack_plan !== 'paid' && item.status !== 'closed' && (
        <p className="text-xs text-amber-800 bg-amber-50 rounded-lg p-2.5">Their Slack is not on a paid plan: they join with Slack&apos;s one-time 90-day
          trial, and the channel disconnects if they do not upgrade afterwards. Mention this in the note.</p>)}
      {item.status !== 'closed' && (<>
        <div className="grid sm:grid-cols-3 gap-2">
          <label className="text-xs text-slate-500">Channel you created
            <input value={channel} onChange={e => setChannel(e.target.value)} placeholder="acme-baalebos"
              className="mt-1 w-full px-3 py-2 rounded-lg border border-slate-200 text-sm text-slate-900" /></label>
          <label className="text-xs text-slate-500 sm:col-span-2">Note for the customer (optional, included in the email)
            <input value={note} onChange={e => setNote(e.target.value)} maxLength={2000}
              className="mt-1 w-full px-3 py-2 rounded-lg border border-slate-200 text-sm text-slate-900" /></label>
        </div>
        <div className="flex flex-wrap gap-2">
          {item.status === 'requested' && <Button variant="primary" size="sm" busy={busy === 'invited'} onClick={() => save('invited')}>Mark invited and email customer</Button>}
          {item.status === 'invited' && <Button variant="primary" size="sm" busy={busy === 'connected'} onClick={() => save('connected')}>Mark connected</Button>}
          {item.status !== 'requested' && <Button size="sm" busy={busy === item.status} onClick={() => save(item.status)}>Save changes</Button>}
          <Button variant="ghost" size="sm" busy={busy === 'closed'} onClick={() => save('closed')}>Close</Button>
        </div>
      </>)}
      {error && <Banner>{error}</Banner>}
    </li>
  );
}

export default function SlackTab({ notify }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    try { setData(await adminGet('/support/admin/slack')); }
    catch (err) { setError(message(err, 'Could not load Slack requests.')); }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 items-start">
      <div className={`${card} xl:col-span-2 overflow-hidden`}>
        <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-2">
          <Hash size={18} className="text-slate-400" />
          <h2 className="font-semibold text-slate-900">Slack channel requests</h2>
          {data && <span className="ml-auto text-xs text-slate-500">{data.counts.requested} waiting · {data.counts.invited} invited · {data.counts.connected} connected</span>}
        </div>
        {error && <div className="p-5"><Banner>{error}</Banner></div>}
        {!data ? <Spinner /> : data.items.length === 0 ? <Empty>No Slack requests yet. Enterprise customers ask from Help &amp; support.</Empty> : (
          <ul className="divide-y divide-slate-100">{data.items.map(item => <Request key={item.id} item={item} onSaved={load} notify={notify} />)}</ul>)}
      </div>
      <aside className={`${card} p-5 text-sm text-slate-600 space-y-3`} aria-label="Setup checklist">
        <h3 className="font-semibold text-slate-900">Checklist</h3>
        <p className="text-xs text-slate-500">Once: a Baalebos Slack workspace on a paid plan (Slack requires one for shared channels).</p>
        <ol className="list-decimal pl-5 space-y-1.5">
          <li>Create a channel for the customer in Slack, e.g. <code>#acme-baalebos</code>.</li>
          <li>Invite the listed emails to it with Slack Connect.</li>
          <li>Enter the channel name here and choose <strong>Mark invited</strong>: the customer is emailed.</li>
          <li>When they have joined, choose <strong>Mark connected</strong>.</li>
          <li>If they leave Enterprise, remove them in Slack and choose <strong>Close</strong>.</li>
        </ol>
        <a href={GUIDE} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-emerald-700 font-semibold hover:underline">Slack Connect guide <ExternalLink size={13} /></a>
        <p className="text-xs text-slate-500">The full checklist is in the repository at <code>docs/slack-support-checklist.md</code>.</p>
      </aside>
    </div>
  );
}
