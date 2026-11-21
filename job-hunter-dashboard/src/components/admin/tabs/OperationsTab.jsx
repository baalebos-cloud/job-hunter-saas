import { useCallback, useEffect, useState } from 'react';
import { Activity, Copy, Play, RefreshCw, Send } from 'lucide-react';
import { adminGet, adminPost, ago, message, num, when } from '../adminApi';
import { Banner, Button, Chip, SectionHeader, Spinner, Td, Th, card } from '../ui';

export default function OperationsTab({ system, grafanaUrl, notify, onScrape, scraping }) {
  const [automation, setAutomation] = useState(null);
  const [error, setError] = useState('');
  const [processing, setProcessing] = useState(false);
  const [testing, setTesting] = useState(false);
  const [report, setReport] = useState(null);
  const [aiError, setAiError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try { setAutomation(await adminGet('/admin/automation')); } catch (err) { setError(message(err, 'Could not load automation status.')); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const processQueue = async () => {
    setProcessing(true); setError('');
    try {
      const data = await adminPost('/admin/automation/run', {}, { timeout: 90000 });
      notify(`Notifications accepted: ${data.accepted}. Retrying: ${data.retrying}. Failed: ${data.failed}.`);
      await load();
    } catch (err) { setError(message(err, 'Could not process notifications. Check Railway and n8n executions.')); }
    finally { setProcessing(false); }
  };
  const runDiagnostic = async () => {
    setTesting(true); setReport(null); setAiError('');
    try { setReport(await adminPost('/admin/resume-diagnostic', {}, { timeout: 300000 })); }
    catch (err) { setAiError(message(err, 'The diagnostic could not complete. Please try again.')); }
    finally { setTesting(false); }
  };

  const last = automation?.last_scrape;
  const summary = last?.summary || {};
  const counts = automation?.notification_counts || {};
  return (
    <div className="space-y-4">
      {error && <Banner onClose={() => setError('')}>{error}</Banner>}
      <div className="grid lg:grid-cols-3 gap-4">
        <div className={`${card} p-5 flex flex-col`}>
          <div className="flex items-center justify-between"><h2 className="font-semibold">Job scraper</h2>
            {last ? <Chip tone={last.status === 'success' ? 'green' : last.status === 'partial' ? 'amber' : 'red'}>{last.status}</Chip> : <Chip>No runs yet</Chip>}</div>
          <dl className="mt-4 space-y-2 text-[13px]">
            <div className="flex justify-between"><dt className="text-slate-500">Last run</dt><dd>{last ? ago(`${last.started_at}Z`) : '—'}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Fetched / saved</dt><dd>{num(summary.total_scraped)} / {num(summary.total_saved)}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Failing sources</dt><dd>{num(summary.failed_sources)}</dd></div>
          </dl>
          <div className="mt-auto pt-4"><Button variant="primary" icon={Play} busy={scraping} onClick={onScrape} className="w-full">Run now</Button></div>
        </div>
        <div className={`${card} p-5 flex flex-col`}>
          <div className="flex items-center justify-between"><h2 className="font-semibold">Notifications (n8n)</h2>
            <Chip tone={automation?.events_configured ? 'green' : 'slate'}>{automation?.events_configured ? 'Configured' : 'Not configured'}</Chip></div>
          <div className="mt-4 grid grid-cols-3 gap-2 text-center">
            {[['pending', 'Queued'], ['sent', 'Accepted'], ['failed', 'Failed']].map(([k, label]) => (
              <div key={k} className="rounded-xl bg-slate-50 py-2"><div className="text-lg font-semibold">{num(counts[k])}</div><div className="text-[11px] text-slate-500">{label}</div></div>
            ))}
          </div>
          {!automation?.events_configured && <p className="mt-3 text-xs text-slate-500">Set N8N_EVENTS_WEBHOOK_URL and N8N_WEBHOOK_SECRET on Railway.</p>}
          <div className="mt-auto pt-4 flex gap-2">
            <Button icon={RefreshCw} onClick={load} className="flex-1">Refresh</Button>
            <Button icon={Send} busy={processing} onClick={processQueue} className="flex-1">Process queue</Button>
          </div>
        </div>
        <div className={`${card} p-5`}>
          <div className="flex items-center justify-between"><h2 className="font-semibold">System health</h2>
            {grafanaUrl && <a href={grafanaUrl} target="_blank" rel="noopener noreferrer" className="text-xs font-semibold text-emerald-700 hover:underline">Grafana ↗</a>}</div>
          <dl className="mt-4 space-y-2 text-[13px]">
            <div className="flex justify-between"><dt className="text-slate-500">Requests (15 min)</dt><dd>{num(system?.requests_15m)}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">5xx error rate</dt><dd className={system?.error_rate > 1 ? 'text-rose-700' : 'text-emerald-700'}>{system?.error_rate ?? 0}%</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">p95 latency</dt><dd>{system?.p95_ms != null ? `${Math.round(system.p95_ms)} ms` : '—'}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Database pool in use</dt><dd>{system?.db_pool_pct != null ? `${system.db_pool_pct}%` : '—'}</dd></div>
          </dl>
          {!grafanaUrl && <p className="mt-3 text-xs text-slate-500 flex items-center gap-1"><Activity size={12} />Set VITE_GRAFANA_URL on Vercel to link Grafana.</p>}
        </div>
      </div>

      {last?.summary?.source_results?.length > 0 && (
        <div className={`${card} overflow-hidden`}>
          <SectionHeader title="Scraper sources" subtitle={`Run started ${when(`${last.started_at}Z`)}`} />
          <div className="max-h-80 overflow-auto"><table className="w-full">
            <thead><tr><Th>Source</Th><Th>Result</Th><Th>Jobs fetched</Th></tr></thead>
            <tbody>{last.summary.source_results.map(s => (
              <tr key={s.name}><Td>{s.name}</Td><Td><Chip tone={s.status === 'ok' || s.status === 'success' ? 'green' : s.status === 'partial' ? 'amber' : 'red'}>{s.status}</Chip></Td><Td>{num(s.job_count)}</Td></tr>))}
            </tbody>
          </table></div>
        </div>
      )}
      {automation?.failed_notifications?.length > 0 && (
        <div className={`${card} p-5`}>
          <h2 className="font-semibold text-rose-800">Notifications needing attention</h2>
          <ul className="mt-2 text-sm text-slate-600 space-y-1">{automation.failed_notifications.map(e => (
            <li key={e.event_id}>{e.event_type} · {e.last_error} · {e.attempts} attempt(s)</li>))}</ul>
        </div>
      )}

      <div className={`${card} p-5`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><h2 className="font-semibold">AI resume test</h2>
            <p className="text-sm text-slate-500 mt-1">Runs resume extraction on a fictional candidate with your AI provider. Nothing is saved and no scan is used. It can take a few minutes.</p></div>
          <Button variant="dark" busy={testing} onClick={runDiagnostic}>{testing ? 'Testing…' : 'Run AI test'}</Button>
        </div>
        <div role="status" aria-live="polite" className="mt-3">
          {aiError && <Banner>{aiError}</Banner>}
          {report && <Banner tone={report.passed ? 'green' : 'amber'}>{report.passed ? 'Synthetic extraction passed. A real resume still needs checking.' : 'Synthetic extraction failed. Copy the report below for investigation.'}</Banner>}
        </div>
        {report && <>
          <Button size="sm" icon={Copy} className="mt-3" onClick={async () => {
            try { await navigator.clipboard.writeText(JSON.stringify(report, null, 2)); notify('Diagnostic report copied'); }
            catch { setAiError('Could not copy automatically. Select and copy the report below.'); }
          }}>Copy report</Button>
          <pre className="mt-3 p-4 bg-slate-50 border border-slate-200 rounded-xl text-xs whitespace-pre-wrap break-words overflow-auto max-h-[28rem]">{JSON.stringify(report, null, 2)}</pre>
        </>}
      </div>
      {!automation && !error && <Spinner />}
    </div>
  );
}
