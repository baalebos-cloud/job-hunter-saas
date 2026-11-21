import { useCallback, useEffect, useState } from 'react';
import { ExternalLink, RefreshCw, Trash2 } from 'lucide-react';
import { adminDelete, adminGet, adminPost, ago, message, num } from '../adminApi';
import { Banner, Button, Chip, Empty, Pager, SearchInput, Segmented, Select, Spinner, Stat, Td, Th, card } from '../ui';

const APP_STATUS_TONE = { applied: 'green', interview: 'blue', offer: 'green', rejected: 'red', pending: 'slate' };

function Applications() {
  const [page, setPage] = useState(1);
  const [rows, setRows] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    setRows(null);
    adminGet('/admin/applications', { skip: (page - 1) * 50, limit: 50 }).then(setRows)
      .catch(err => setError(message(err, 'Could not load applications.')));
  }, [page]);
  if (error) return <div className="p-5"><Banner>{error}</Banner></div>;
  if (!rows) return <Spinner />;
  return (
    <>
      <div className="overflow-x-auto"><table className="w-full">
        <thead><tr><Th>Applicant</Th><Th>Job</Th><Th>Company</Th><Th>ATS score</Th><Th>Status</Th><Th>Date</Th></tr></thead>
        <tbody>{rows.map(a => (
          <tr key={a.id} className="hover:bg-slate-50/60">
            <Td>{a.user_email || '—'}</Td><Td className="font-medium">{a.job_title || '—'}</Td><Td>{a.company || '—'}</Td>
            <Td><Chip tone={(a.ats_score || 0) >= 80 ? 'green' : (a.ats_score || 0) >= 60 ? 'amber' : 'slate'}>{a.ats_score || 0}%</Chip></Td>
            <Td><Chip tone={APP_STATUS_TONE[a.status] || 'slate'}>{String(a.status || '').replace(/_/g, ' ')}</Chip></Td>
            <Td className="text-slate-500">{a.created_at ? new Date(a.created_at).toLocaleDateString() : '—'}</Td>
          </tr>))}
        </tbody>
      </table></div>
      {rows.length === 0 && <Empty>No applications yet.</Empty>}
      <div className="px-5 py-3 border-t border-slate-100 flex justify-end gap-1">
        <Button size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Previous</Button>
        <Button size="sm" disabled={rows.length < 50} onClick={() => setPage(p => p + 1)}>Next</Button>
      </div>
    </>
  );
}

export default function JobsTab({ notify, confirm }) {
  const [view, setView] = useState('jobs');
  const [filters, setFilters] = useState({ q: '', source: '', status: 'active' });
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try { setData(await adminGet('/admin/jobs/search', { ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)), page, page_size: 25 })); }
    catch (err) { setError(message(err, 'Could not load jobs.')); }
  }, [filters, page]);
  useEffect(() => { if (view === 'jobs') load(); }, [view, load]);
  const setFilter = (change) => { setPage(1); setFilters(f => ({ ...f, ...change })); };

  const remove = (job) => confirm({
    title: `Remove “${job.title}”?`, tone: 'red', confirmLabel: 'Remove job',
    body: `${job.company || 'Unknown company'} · ${job.applicants} applicant(s). The listing is deleted for everyone.`,
    onConfirm: async () => { await adminDelete(`/admin/jobs/${job.id}`); notify('Job removed'); await load(); },
    errorText: (err) => message(err, 'Could not remove this job.'),
  });

  const clearAll = () => confirm({
    title: 'Clear all scraped jobs?', tone: 'red', confirmLabel: 'Clear and refresh',
    body: <>Every scraped listing is removed and the scraper runs straight away to fill the board with fresh jobs.
      Jobs posted by employers on Baalebos are kept, and listings people applied to stay in their application history.</>,
    reasonLabel: 'Type CLEAR JOBS to confirm', reasonPlaceholder: 'CLEAR JOBS',
    onConfirm: async (typed) => {
      const r = await adminPost('/admin/jobs/clear-scraped', { confirm: typed, refresh: true });
      notify(`${num(r.deleted)} scraped jobs removed${r.closed ? `, ${num(r.closed)} kept for application history` : ''}. Fresh jobs are loading (about a minute).`);
      setPage(1); await load();
    },
    errorText: (err) => message(err, 'Could not clear jobs.'),
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-500">Scraped jobs older than 30 days, or no longer at their source, close automatically.</p>
        <div className="flex gap-2">
          <Button icon={RefreshCw} onClick={load}>Refresh</Button>
          <Button variant="danger" icon={Trash2} onClick={clearAll}>Clear all scraped jobs…</Button>
        </div>
      </div>
      {data?.stats && (
        <div className="grid sm:grid-cols-3 gap-4">
          <Stat label="Live jobs" value={num(data.stats.live)} />
          <Stat label="Posted by employers" value={num(data.stats.employer_posted)} />
          <Stat label="Applications (7 days)" value={num(data.stats.applications_7d)} />
        </div>
      )}
      <div className={`${card} overflow-hidden`}>
        <div className="px-5 py-4 flex flex-wrap items-center gap-2">
          <Segmented size="md" value={view} onChange={setView} options={[['jobs', 'Jobs'], ['applications', 'Applications']]} />
          {view === 'jobs' && <>
            <SearchInput value={query} onChange={setQuery} onSubmit={() => setFilter({ q: query.trim() })} placeholder="Search title or company" width="w-72" />
            <Select label="Source" value={filters.source} onChange={source => setFilter({ source })}
              options={[['', 'All sources'], ['employer', 'Employer-posted'], ['scraped', 'Scraped']]} />
            <Select label="Status" value={filters.status} onChange={status => setFilter({ status })}
              options={[['active', 'Live'], ['expired', 'Expired'], ['', 'All']]} />
          </>}
        </div>
        {view === 'applications' ? <Applications /> : <>
          {error && <div className="px-5 pb-3"><Banner onClose={() => setError('')}>{error}</Banner></div>}
          {!data && !error ? <Spinner /> : data && <>
            <div className="overflow-x-auto"><table className="w-full">
              <thead><tr><Th>Job</Th><Th>Source</Th><Th>Applicants</Th><Th>Posted</Th><Th>Status</Th><Th right>Actions</Th></tr></thead>
              <tbody>{data.items.map(j => (
                <tr key={j.id} className="hover:bg-slate-50/60">
                  <Td><div className="font-medium">{j.title}</div><div className="text-xs text-slate-500">{[j.company, j.location, j.work_type].filter(Boolean).join(' · ')}</div></Td>
                  <Td><Chip tone={j.source === 'employer' ? 'blue' : 'slate'}>{j.source === 'employer' ? 'Employer' : j.source}</Chip></Td>
                  <Td>{num(j.applicants)}</Td>
                  <Td className="text-slate-500 whitespace-nowrap">{ago(j.posted_at)}</Td>
                  <Td><Chip tone={j.is_active ? 'green' : 'slate'}>{j.is_active ? 'Live' : 'Expired'}</Chip></Td>
                  <Td className="text-right whitespace-nowrap space-x-1">
                    {j.url && <a href={j.url} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50">View<ExternalLink size={12} /></a>}
                    <Button size="sm" variant="danger" icon={Trash2} onClick={() => remove(j)}>Remove</Button>
                  </Td>
                </tr>))}
              </tbody>
            </table></div>
            {data.items.length === 0 && <Empty>No jobs match these filters.</Empty>}
            <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </>}
        </>}
      </div>
    </div>
  );
}
