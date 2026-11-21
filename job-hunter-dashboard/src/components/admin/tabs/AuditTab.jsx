import { useCallback, useEffect, useState } from 'react';
import { Download } from 'lucide-react';
import { adminGet, ago, downloadCsv, eventTone, message, when } from '../adminApi';
import { Banner, Button, Chip, Empty, SectionHeader, Spinner, Td, Th, card } from '../ui';

const describe = (details) => (details ? Object.entries(details)
  .filter(([k, v]) => v && typeof v !== 'object' && k !== 'target_user_id')
  .map(([k, v]) => `${k.replace(/^target_/, '').replace(/_/g, ' ')}: ${String(v).replace(/_/g, ' ')}`).join(' · ') : '');

export default function AuditTab() {
  const [events, setEvents] = useState(null);
  const [next, setNext] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async (before = null) => {
    setLoading(true); setError('');
    try {
      const data = await adminGet('/admin/security/events', { category: 'audit', limit: 50, ...(before ? { before_id: before } : {}) });
      setEvents(prev => (before ? [...(prev || []), ...data.events] : data.events));
      setNext(data.next_before_id);
    } catch (err) { setError(message(err, 'Could not load the audit log.')); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <div className={`${card} overflow-hidden`}>
      <SectionHeader title="Admin audit log" subtitle="Every admin action, security alert and view of security data">
        <Button icon={Download} onClick={() => downloadCsv('/admin/security/events.csv', { category: 'audit' }, 'audit-log.csv')
          .catch(err => setError(message(err, 'Could not export the audit log.')))}>Export</Button>
      </SectionHeader>
      {error && <div className="px-5 pb-3"><Banner onClose={() => setError('')}>{error}</Banner></div>}
      {!events && !error && <Spinner />}
      {events && <>
        <div className="overflow-x-auto"><table className="w-full">
          <thead><tr><Th>Time</Th><Th>Admin</Th><Th>Action</Th><Th>Details</Th><Th>IP / location</Th></tr></thead>
          <tbody>{events.map(e => (
            <tr key={e.id} className="hover:bg-slate-50/60">
              <Td className="text-slate-500 whitespace-nowrap" title={when(e.ts)}>{ago(e.ts)}</Td>
              <Td>{e.email || 'System'}</Td>
              <Td><Chip tone={eventTone(e.event)}>{e.label}</Chip></Td>
              <Td className="text-slate-600 text-xs max-w-md">{describe(e.details)}</Td>
              <Td className="text-xs whitespace-nowrap"><span className="font-mono">{e.ip || '—'}</span>{e.location ? ` · ${e.location}` : ''}</Td>
            </tr>))}
          </tbody>
        </table></div>
        {events.length === 0 && <Empty>No admin actions recorded yet.</Empty>}
        {next && <div className="px-5 py-3 border-t border-slate-100 text-right"><Button size="sm" busy={loading} onClick={() => load(next)}>Load older</Button></div>}
      </>}
    </div>
  );
}
