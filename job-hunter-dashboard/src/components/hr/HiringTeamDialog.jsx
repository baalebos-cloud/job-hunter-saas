/* eslint-disable react/prop-types -- the project does not use the prop-types package */
// Who works on one job. Hiring managers and interviewers only see jobs they are on.
import { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, X } from 'lucide-react';
import { errorText } from '../../lib/session';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const h = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });
const JOB_ROLES = [['recruiter', 'Recruiter'], ['coordinator', 'Coordinator'], ['hiring_manager', 'Hiring manager'], ['interviewer', 'Interviewer']];
const selectCls = 'rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-800 outline-none focus:border-emerald-600';

export default function HiringTeamDialog({ job, onClose, onSaved }) {
  const [people, setPeople] = useState(null);     // active company members
  const [rows, setRows] = useState([]);           // [{ user_id, role }]
  const [pick, setPick] = useState('');
  const [pickRole, setPickRole] = useState('interviewer');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([axios.get(`${API}/hr/team`, { headers: h() }), axios.get(`${API}/hr/jobs/${job.id}/team`, { headers: h() })])
      .then(([team, current]) => {
        setPeople(team.data.members.filter(m => m.status === 'active' && m.user_id));
        setRows(current.data.members.map(m => ({ user_id: m.user_id, role: m.role })));
      })
      .catch(err => { setPeople([]); setError(errorText(err, 'The hiring team could not be loaded.')); });
  }, [job.id]);

  useEffect(() => {
    const close = e => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [onClose]);

  const name = id => { const p = people?.find(m => m.user_id === id); return p ? (p.name || p.email) : 'Former teammate'; };
  const available = (people || []).filter(p => !rows.some(r => r.user_id === p.user_id));

  const add = () => {
    if (!pick) return;
    setRows(r => [...r, { user_id: Number(pick), role: pickRole }]);
    setPick('');
  };
  const save = async () => {
    setSaving(true); setError('');
    try {
      await axios.put(`${API}/hr/jobs/${job.id}/team`, { members: rows }, { headers: h() });
      onSaved(`Hiring team for “${job.title}” saved.`);
    } catch (err) { setError(errorText(err, 'The hiring team could not be saved.')); setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-[60] bg-slate-900/50 backdrop-blur-sm p-4 flex items-center justify-center">
      <section role="dialog" aria-modal="true" aria-labelledby="hiring-team-title" className="bg-white rounded-2xl w-full max-w-xl max-h-[90vh] flex flex-col shadow-2xl">
        <div className="flex items-start justify-between gap-3 px-6 py-4 border-b border-slate-200">
          <div>
            <h2 id="hiring-team-title" className="font-semibold text-slate-900">Hiring team · {job.title}</h2>
            <p className="text-sm text-slate-500">Who works on this job. Hiring managers and interviewers see only jobs they’re on.</p>
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X size={18} /></button>
        </div>
        <div className="p-6 overflow-y-auto space-y-2">
          {people === null ? <div className="py-6 flex justify-center"><Loader2 className="animate-spin text-slate-400" /></div> : (<>
            {rows.length === 0 && <p className="text-sm text-slate-500">No one is on this job’s hiring team yet. Admins and recruiters can always see it.</p>}
            {rows.map((r, i) => (
              <div key={r.user_id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2">
                <span className="text-sm text-slate-900 truncate">{name(r.user_id)}</span>
                <div className="flex items-center gap-2 shrink-0">
                  <select aria-label={`Role on this job for ${name(r.user_id)}`} className={selectCls} value={r.role}
                    onChange={e => setRows(all => all.map((x, j) => (j === i ? { ...x, role: e.target.value } : x)))}>
                    {JOB_ROLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                  <button type="button" aria-label={`Remove ${name(r.user_id)} from this job`} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                    onClick={() => setRows(all => all.filter((_, j) => j !== i))}><X size={16} /></button>
                </div>
              </div>
            ))}
            {available.length > 0 ? (
              <div className="flex flex-wrap items-center gap-2 pt-2">
                <select aria-label="Teammate to add" className={`${selectCls} flex-1 min-w-[12rem]`} value={pick} onChange={e => setPick(e.target.value)}>
                  <option value="">Add a teammate…</option>
                  {available.map(p => <option key={p.user_id} value={p.user_id}>{p.name || p.email} · {p.role_label}</option>)}
                </select>
                <select aria-label="Role on this job" className={selectCls} value={pickRole} onChange={e => setPickRole(e.target.value)}>
                  {JOB_ROLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
                <button type="button" onClick={add} disabled={!pick} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50">Add</button>
              </div>
            ) : rows.length > 0 && <p className="text-xs text-slate-500 pt-2">Everyone on your team is on this job. Invite more people in the Team tab.</p>}
          </>)}
        </div>
        <div className="px-6 py-4 border-t border-slate-200 flex flex-wrap items-center justify-end gap-3">
          {error && <p role="alert" className="mr-auto text-sm text-rose-700">{error}</p>}
          <button onClick={onClose} className="rounded-xl px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-100">Cancel</button>
          <button onClick={save} disabled={saving || people === null}
            className="rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-medium px-5 py-2.5 disabled:opacity-60">{saving ? 'Saving…' : 'Save hiring team'}</button>
        </div>
      </section>
    </div>
  );
}
