import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import {
  BadgeCheck, Briefcase, Camera, FileText, GraduationCap, Linkedin, Loader2, MapPin, Pencil, Plus, Trash2, X,
} from 'lucide-react';
import { assetUrl, clearSession, errorText } from '../lib/session';
import PhotoCropper from './profile/PhotoCropper';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const PROFICIENCIES = ['Basic', 'Intermediate', 'Advanced', 'Fluent', 'Native'];
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });
const card = 'bg-white border border-slate-200 rounded-2xl';
const input = 'w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500/40';
const primary = 'inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60';
const secondary = 'inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50';

function Field({ label, children, hint }) {
  return (
    <label className="block text-sm font-medium text-slate-700">{label}
      <div className="mt-1.5">{children}</div>
      {hint && <span className="block mt-1 text-xs font-normal text-slate-500">{hint}</span>}
    </label>
  );
}

function Modal({ title, onClose, onSubmit, busy, error, children, submitLabel = 'Save' }) {
  useEffect(() => {
    const close = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <form onSubmit={(e) => { e.preventDefault(); onSubmit(); }} className="w-full max-w-lg max-h-[90vh] overflow-y-auto bg-white rounded-2xl shadow-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 id="modal-title" className="text-lg font-semibold text-slate-900">{title}</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="p-1 rounded-lg hover:bg-slate-100"><X size={20} /></button>
        </div>
        <div className="space-y-4">{children}</div>
        {error && <p role="alert" className="mt-4 text-sm text-rose-700 bg-rose-50 rounded-xl p-3">{error}</p>}
        <div className="mt-6 flex justify-end gap-2">
          <button type="button" onClick={onClose} className={secondary}>Cancel</button>
          <button type="submit" disabled={busy} className={primary}>{busy && <Loader2 size={16} className="animate-spin" />}{submitLabel}</button>
        </div>
      </form>
    </div>
  );
}

function Section({ title, action, children }) {
  return (
    <section className={`${card} p-5`}>
      <div className="flex items-center justify-between gap-3 mb-3">
        <h2 className="font-semibold text-slate-900">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

const AddButton = ({ onClick, label = 'Add' }) => (
  <button type="button" onClick={onClick} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 hover:text-emerald-800"><Plus size={14} />{label}</button>
);
const EditButton = ({ onClick, label = 'Edit' }) => (
  <button type="button" onClick={onClick} className="inline-flex items-center gap-1 text-xs font-semibold text-slate-600 hover:text-slate-900"><Pencil size={13} />{label}</button>
);
const IconAction = ({ onClick, label, icon: Icon }) => (
  <button type="button" onClick={onClick} aria-label={label} title={label} className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100"><Icon size={15} /></button>
);

function strength(p) {
  const checks = [
    [!!p.photo_url, 'a profile photo'], [!!p.career_track, 'a headline'], [!!(p.about || '').trim(), 'an About summary'],
    [p.experience.length > 0, 'your experience'], [p.education.length > 0, 'your education'],
    [p.certified_skills.length + p.other_skills.length >= 3, 'at least 3 skills'], [p.languages.length > 0, 'a language'],
    [!!p.linkedin_url, 'your LinkedIn'], [!!(p.city || p.country), 'your location'], [!!p.resume_url, 'a resume'],
  ];
  const done = checks.filter(([ok]) => ok).length;
  return { score: Math.round((done * 100) / checks.length), missing: checks.filter(([ok]) => !ok).map(([, l]) => l) };
}

function Avatar({ profile, size = 'w-28 h-28 text-3xl' }) {
  const initials = (profile.full_name || profile.email || 'U').split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();
  return profile.photo_url
    ? <img src={assetUrl(profile.photo_url)} alt={`${profile.full_name || 'Your'} profile photo`} className={`${size} rounded-full object-cover ring-4 ring-white bg-white`} />
    : <div className={`${size} rounded-full ring-4 ring-white bg-emerald-600 text-white grid place-items-center font-semibold`} aria-hidden="true">{initials}</div>;
}

export default function ProfilePage() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [modal, setModal] = useState(null);           // { kind, data }
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [cropFile, setCropFile] = useState(null);
  const [aboutDraft, setAboutDraft] = useState(null);
  const [newSkill, setNewSkill] = useState('');
  const [verification, setVerification] = useState('');
  const fileRef = useRef(null);

  const load = useCallback(() => axios.get(`${API}/profile/me`, { headers: headers() })
    .then(r => setProfile(r.data))
    .catch(err => setLoadError(errorText(err, 'Could not load your profile. Please sign in again.')))
    .finally(() => setLoading(false)), []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (!toast) return undefined; const t = setTimeout(() => setToast(''), 4000); return () => clearTimeout(t); }, [toast]);

  const run = async (fn, success) => {
    setBusy(true); setError('');
    try { await fn(); await load(); setModal(null); if (success) setToast(success); return true; }
    catch (err) { setError(errorText(err, 'Could not save. Please retry.')); return false; }
    finally { setBusy(false); }
  };
  const patch = (fields, success = 'Profile updated') => run(() => axios.patch(`${API}/profile/me`, fields, { headers: headers() }), success);

  const choosePhoto = (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { setToast(''); setError(''); setCropFile(null); alert('Choose an image smaller than 5 MB.'); return; }
    setError(''); setCropFile(file);
  };
  const savePhoto = async (blob) => {
    const form = new FormData();
    form.append('file', blob, 'photo.jpg');
    const ok = await run(() => axios.post(`${API}/profile/photo`, form, { headers: headers() }), 'Profile photo updated');
    if (ok) { setCropFile(null); window.dispatchEvent(new Event('profile:updated')); }
  };
  const removePhoto = async () => {
    if (!confirm('Remove your profile photo?')) return;
    if (await run(() => axios.delete(`${API}/profile/photo`, { headers: headers() }), 'Profile photo removed')) {
      window.dispatchEvent(new Event('profile:updated'));
    }
  };
  const resendVerification = async () => {
    try { const { data } = await axios.post(`${API}/auth/resend-verification`, {}, { headers: headers() }); setVerification(data.message); }
    catch (err) { setVerification(errorText(err, 'Could not send the email. Please retry.')); }
  };
  const addSkill = async (e) => {
    e.preventDefault();
    if (!newSkill.trim()) return;
    if (await run(() => axios.post(`${API}/profile/skills/other`, { name: newSkill.trim() }, { headers: headers() }))) setNewSkill('');
  };
  const remove = (path, what) => { if (confirm(`Remove ${what}?`)) run(() => axios.delete(`${API}/profile/${path}`, { headers: headers() }), `${what[0].toUpperCase()}${what.slice(1)} removed`); };
  const deleteAccount = async () => {
    if (prompt('This permanently deletes your account, resumes and applications. Type DELETE to confirm.') !== 'DELETE') return;
    try { await axios.delete(`${API}/profile/me`, { headers: headers() }); clearSession(); window.location.href = '/login'; }
    catch (err) { setToast(''); alert(errorText(err, 'Could not delete the account.')); }
  };

  if (loading) return <div className="py-32 flex justify-center"><Loader2 className="animate-spin text-emerald-600" size={32} /></div>;
  if (!profile) return <p className="py-32 text-center text-slate-500">{loadError}</p>;

  const { score, missing } = strength(profile);
  const skills = [...profile.certified_skills.map(s => ({ ...s, verified: true })), ...profile.other_skills];
  const place = [profile.city, profile.country].filter(Boolean).join(', ');
  const form = modal?.data || {};
  const setForm = (change) => setModal(m => ({ ...m, data: { ...m.data, ...change } }));

  return (
    <div className="space-y-4">
      {toast && <div role="status" className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-800">{toast}</div>}

      {/* Header */}
      <section className={`${card} overflow-hidden`}>
        <div className="h-28 bg-gradient-to-r from-emerald-600 to-teal-500" />
        <div className="px-5 sm:px-6 pb-6">
          <div className="flex flex-col sm:flex-row sm:items-end gap-4 -mt-12">
            <div className="relative w-fit">
              <Avatar profile={profile} />
              <button type="button" onClick={() => fileRef.current?.click()} aria-label="Change profile photo"
                className="absolute bottom-1 right-1 w-9 h-9 rounded-full bg-slate-900 text-white grid place-items-center ring-2 ring-white hover:bg-slate-700"><Camera size={16} /></button>
              <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={choosePhoto} />
            </div>
            <div className="flex-1 min-w-0 sm:pt-14">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-semibold text-slate-900 break-words">{profile.full_name || 'Add your name'}</h1>
                {profile.is_verified
                  ? <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700"><BadgeCheck size={12} />Email verified</span>
                  : <button type="button" onClick={resendVerification} className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-800 hover:bg-amber-100">Verify email</button>}
              </div>
              <p className="text-slate-600">{profile.career_track || <span className="text-slate-400">Add a headline, e.g. Senior DevOps Engineer</span>}</p>
              <p className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
                {place && <span className="inline-flex items-center gap-1"><MapPin size={14} />{place}{profile.timezone ? ` (${profile.timezone})` : ''}</span>}
                {profile.linkedin_url && <a href={profile.linkedin_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-700"><Linkedin size={14} />{profile.linkedin_url.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')}</a>}
              </p>
              {verification && <p className="mt-1 text-xs text-slate-600">{verification}</p>}
            </div>
            <div className="flex flex-wrap items-center gap-3 sm:pt-14">
              {!profile.is_hr && (
                <label className="inline-flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                  <input type="checkbox" role="switch" className="peer sr-only" checked={!!profile.available_for_work}
                    onChange={e => patch({ available_for_work: e.target.checked }, e.target.checked ? 'You are open to work' : 'Open to work turned off')} />
                  <span className="relative w-10 h-6 rounded-full bg-slate-200 peer-checked:bg-emerald-500 transition-colors after:absolute after:top-0.5 after:left-0.5 after:w-5 after:h-5 after:rounded-full after:bg-white after:transition-transform peer-checked:after:translate-x-4 peer-focus-visible:ring-2 peer-focus-visible:ring-emerald-400" />
                  Open to work
                </label>
              )}
              <button type="button" className={secondary} onClick={() => { setError(''); setModal({ kind: 'basics', data: {
                full_name: profile.full_name || '', career_track: profile.career_track || '', city: profile.city || '', country: profile.country || '',
                timezone: profile.timezone || '', phone: profile.phone || '', linkedin_url: profile.linkedin_url || '' } }); }}>Edit profile</button>
            </div>
          </div>
          <div className="mt-5">
            <div className="flex flex-wrap justify-between gap-2 text-xs text-slate-500">
              <span>Profile strength: <b className="text-slate-800">{score}%</b></span>
              {missing.length > 0 && <span>Add {missing.slice(0, 2).join(' and ')} to strengthen your profile</span>}
            </div>
            <div className="h-2 mt-1 rounded-full bg-slate-100" role="progressbar" aria-valuenow={score} aria-valuemin={0} aria-valuemax={100} aria-label="Profile strength">
              <div className="h-2 rounded-full bg-emerald-500 transition-all" style={{ width: `${score}%` }} /></div>
          </div>
          {profile.photo_url && <button type="button" onClick={removePhoto} className="mt-3 text-xs text-slate-500 hover:text-rose-700">Remove photo</button>}
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4 min-w-0">
          <Section title="About" action={aboutDraft === null && <EditButton onClick={() => setAboutDraft(profile.about || '')} />}>
            {aboutDraft === null
              ? <p className="text-sm leading-6 text-slate-700 whitespace-pre-line">{profile.about || <span className="text-slate-400">Write 2–3 sentences about what you do and what you are looking for.</span>}</p>
              : <form onSubmit={async e => { e.preventDefault(); if (await patch({ about: aboutDraft.trim() }, 'About updated')) setAboutDraft(null); }} className="space-y-2">
                  <textarea value={aboutDraft} onChange={e => setAboutDraft(e.target.value)} rows={5} maxLength={2000} className={input} aria-label="About" autoFocus />
                  <div className="flex justify-between items-center"><span className="text-xs text-slate-400">{aboutDraft.length}/2000</span>
                    <div className="flex gap-2"><button type="button" onClick={() => setAboutDraft(null)} className={secondary}>Cancel</button><button type="submit" disabled={busy} className={primary}>Save</button></div></div>
                </form>}
          </Section>

          <Section title="Experience" action={<AddButton onClick={() => { setError(''); setModal({ kind: 'experience', data: { title: '', company: '', start_date: '', end_date: '', description: '' } }); }} />}>
            {profile.experience.length === 0 && <p className="text-sm text-slate-400">Add your roles so employers can see your track record.</p>}
            <ul className="divide-y divide-slate-100">
              {profile.experience.map(x => (
                <li key={x.id} className="py-3 first:pt-0 flex gap-3">
                  <div className="w-10 h-10 shrink-0 rounded-lg bg-slate-100 grid place-items-center text-slate-500"><Briefcase size={18} /></div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-slate-900">{x.title}</div>
                    <div className="text-sm text-slate-600">{x.company}</div>
                    {(x.start_date || x.end_date) && <div className="text-xs text-slate-500">{[x.start_date, x.end_date || 'Present'].filter(Boolean).join(' – ')}</div>}
                    {x.description && <p className="mt-1 text-sm text-slate-600 whitespace-pre-line">{x.description}</p>}
                  </div>
                  <div className="flex items-start">
                    <IconAction icon={Pencil} label={`Edit ${x.title}`} onClick={() => { setError(''); setModal({ kind: 'experience', data: { ...x, start_date: x.start_date || '', end_date: x.end_date || '', description: x.description || '' } }); }} />
                    <IconAction icon={Trash2} label={`Remove ${x.title}`} onClick={() => remove(`experience/${x.id}`, 'this role')} />
                  </div>
                </li>))}
            </ul>
          </Section>

          <Section title="Education" action={<AddButton onClick={() => { setError(''); setModal({ kind: 'education', data: { degree: '', institution: '', start_date: '', end_date: '' } }); }} />}>
            {profile.education.length === 0 && <p className="text-sm text-slate-400">Add degrees, diplomas or bootcamps.</p>}
            <ul className="divide-y divide-slate-100">
              {profile.education.map(x => (
                <li key={x.id} className="py-3 first:pt-0 flex gap-3">
                  <div className="w-10 h-10 shrink-0 rounded-lg bg-slate-100 grid place-items-center text-slate-500"><GraduationCap size={18} /></div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-slate-900">{x.degree}</div>
                    <div className="text-sm text-slate-600">{x.institution}</div>
                    {(x.start_date || x.end_date) && <div className="text-xs text-slate-500">{[x.start_date, x.end_date].filter(Boolean).join(' – ')}</div>}
                  </div>
                  <div className="flex items-start">
                    <IconAction icon={Pencil} label={`Edit ${x.degree}`} onClick={() => { setError(''); setModal({ kind: 'education', data: { ...x, start_date: x.start_date || '', end_date: x.end_date || '' } }); }} />
                    <IconAction icon={Trash2} label={`Remove ${x.degree}`} onClick={() => remove(`education/${x.id}`, 'this education entry')} />
                  </div>
                </li>))}
            </ul>
          </Section>

          <Section title="Skills">
            <div className="flex flex-wrap gap-2">
              {skills.length === 0 && <p className="text-sm text-slate-400">Add the tools and practices you use.</p>}
              {skills.map(s => (
                <span key={`${s.verified ? 'c' : 'o'}${s.id}`} className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${s.verified ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-700'}`}>
                  {s.verified && <BadgeCheck size={12} aria-label="Verified" />}{s.name}
                  {!s.verified && <button type="button" onClick={() => remove(`skills/other/${s.id}`, `the skill ${s.name}`)} aria-label={`Remove ${s.name}`} className="ml-0.5 text-slate-400 hover:text-rose-600"><X size={12} /></button>}
                </span>))}
            </div>
            <form onSubmit={addSkill} className="mt-3 flex gap-2">
              <input value={newSkill} onChange={e => setNewSkill(e.target.value)} maxLength={60} placeholder="Add a skill, e.g. Kubernetes" aria-label="New skill" className={input} />
              <button type="submit" disabled={busy || !newSkill.trim()} className={primary}>Add</button>
            </form>
          </Section>
        </div>

        <aside className="space-y-4">
          <Section title="Job preferences" action={<EditButton onClick={() => { setError(''); setModal({ kind: 'preferences', data: {
            expected_pay_hourly: profile.expected_pay_hourly ?? '', notice_period_days: profile.notice_period_days ?? '',
            job_alert_work_type: profile.job_alert_work_type || 'all', job_alerts_enabled: !!profile.job_alerts_enabled } }); }} />}>
            <dl className="space-y-2 text-sm">
              {[['Headline', profile.career_track || '—'],
                ['Work type', { all: 'Any', remote: 'Remote', hybrid: 'Hybrid', onsite: 'On-site' }[profile.job_alert_work_type] || 'Any'],
                ['Expected pay', profile.expected_pay_hourly ? `$${profile.expected_pay_hourly} / hour` : '—'],
                ['Notice period', profile.notice_period_days != null ? `${profile.notice_period_days} days` : '—'],
                ['Job alerts', profile.job_alerts_enabled ? 'On' : 'Off']].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-3"><dt className="text-slate-500">{k}</dt><dd className={`text-right ${v === 'On' ? 'text-emerald-700' : 'text-slate-900'}`}>{v}</dd></div>))}
            </dl>
          </Section>

          <Section title="Resume">
            {profile.resume_url
              ? <a href={profile.resume_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 rounded-xl border border-slate-200 p-3 hover:bg-slate-50">
                  <FileText size={18} className="text-slate-500" /><span className="flex-1 min-w-0 truncate text-sm font-medium">{profile.resume_filename || 'My resume'}</span><span className="text-xs font-semibold">View</span></a>
              : <p className="text-sm text-slate-500">No resume linked yet. <a href="/optimizer" className="font-semibold text-emerald-700 hover:underline">Create a tailored resume →</a></p>}
          </Section>

          <Section title="Languages" action={<AddButton onClick={() => { setError(''); setModal({ kind: 'language', data: { name: '', proficiency: 'Advanced' } }); }} />}>
            {profile.languages.length === 0 && <p className="text-sm text-slate-400">Add the languages you work in.</p>}
            <ul className="space-y-1.5 text-sm">
              {profile.languages.map(l => (
                <li key={l.id} className="flex items-center justify-between gap-2"><span>{l.name} <span className="text-slate-500">— {l.proficiency}</span></span>
                  <IconAction icon={Trash2} label={`Remove ${l.name}`} onClick={() => remove(`languages/${l.id}`, l.name)} /></li>))}
            </ul>
          </Section>

          <Section title="Account">
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between gap-3"><dt className="text-slate-500">Email</dt><dd className="truncate">{profile.email}</dd></div>
              {profile.phone && <div className="flex justify-between gap-3"><dt className="text-slate-500">Phone</dt><dd>{profile.phone}</dd></div>}
              {profile.created_at && <div className="flex justify-between gap-3"><dt className="text-slate-500">Member since</dt><dd>{new Date(profile.created_at).toLocaleDateString(undefined, { month: 'short', year: 'numeric' })}</dd></div>}
            </dl>
            <button type="button" onClick={deleteAccount} className="mt-4 text-xs font-semibold text-rose-700 hover:underline">Delete my account…</button>
          </Section>
        </aside>
      </div>

      {cropFile && <PhotoCropper file={cropFile} saving={busy} error={error} onCancel={() => { setCropFile(null); setError(''); }} onSave={savePhoto} />}

      {modal?.kind === 'basics' && (
        <Modal title="Edit profile" busy={busy} error={error} onClose={() => setModal(null)} onSubmit={() => patch(form)}>
          <Field label="Full name"><input required maxLength={120} value={form.full_name} onChange={e => setForm({ full_name: e.target.value })} className={input} /></Field>
          <Field label="Headline" hint="Shown under your name, e.g. Senior DevOps Engineer · Kubernetes · AWS"><input maxLength={120} value={form.career_track} onChange={e => setForm({ career_track: e.target.value })} className={input} /></Field>
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="City"><input maxLength={80} value={form.city} onChange={e => setForm({ city: e.target.value })} className={input} /></Field>
            <Field label="Country"><input maxLength={80} value={form.country} onChange={e => setForm({ country: e.target.value })} className={input} /></Field>
            <Field label="Time zone"><input maxLength={40} value={form.timezone} onChange={e => setForm({ timezone: e.target.value })} placeholder="e.g. WAT" className={input} /></Field>
            <Field label="Phone"><input maxLength={40} value={form.phone} onChange={e => setForm({ phone: e.target.value })} className={input} /></Field>
          </div>
          <Field label="LinkedIn URL"><input type="url" maxLength={200} value={form.linkedin_url} onChange={e => setForm({ linkedin_url: e.target.value })} placeholder="https://linkedin.com/in/…" className={input} /></Field>
        </Modal>)}

      {modal?.kind === 'experience' && (
        <Modal title={form.id ? 'Edit experience' : 'Add experience'} busy={busy} error={error} onClose={() => setModal(null)}
          onSubmit={() => {
            const body = { title: form.title, company: form.company, start_date: form.start_date || null, end_date: form.end_date || null, description: form.description || null };
            return run(() => (form.id ? axios.patch(`${API}/profile/experience/${form.id}`, body, { headers: headers() })
              : axios.post(`${API}/profile/experience`, body, { headers: headers() })), form.id ? 'Experience updated' : 'Experience added');
          }}>
          <Field label="Job title"><input required maxLength={120} value={form.title} onChange={e => setForm({ title: e.target.value })} className={input} /></Field>
          <Field label="Company"><input required maxLength={120} value={form.company} onChange={e => setForm({ company: e.target.value })} className={input} /></Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Start"><input maxLength={20} value={form.start_date} onChange={e => setForm({ start_date: e.target.value })} placeholder="Jan 2022" className={input} /></Field>
            <Field label="End" hint="Leave empty if current"><input maxLength={20} value={form.end_date} onChange={e => setForm({ end_date: e.target.value })} placeholder="Present" className={input} /></Field>
          </div>
          <Field label="What you did"><textarea rows={4} maxLength={2000} value={form.description} onChange={e => setForm({ description: e.target.value })} className={input} /></Field>
        </Modal>)}

      {modal?.kind === 'education' && (
        <Modal title={form.id ? 'Edit education' : 'Add education'} busy={busy} error={error} onClose={() => setModal(null)}
          onSubmit={() => {
            const body = { degree: form.degree, institution: form.institution, start_date: form.start_date || null, end_date: form.end_date || null };
            return run(() => (form.id ? axios.patch(`${API}/profile/education/${form.id}`, body, { headers: headers() })
              : axios.post(`${API}/profile/education`, body, { headers: headers() })), form.id ? 'Education updated' : 'Education added');
          }}>
          <Field label="Degree or qualification"><input required maxLength={120} value={form.degree} onChange={e => setForm({ degree: e.target.value })} className={input} /></Field>
          <Field label="School"><input required maxLength={120} value={form.institution} onChange={e => setForm({ institution: e.target.value })} className={input} /></Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Start"><input maxLength={20} value={form.start_date} onChange={e => setForm({ start_date: e.target.value })} placeholder="2014" className={input} /></Field>
            <Field label="End"><input maxLength={20} value={form.end_date} onChange={e => setForm({ end_date: e.target.value })} placeholder="2018" className={input} /></Field>
          </div>
        </Modal>)}

      {modal?.kind === 'language' && (
        <Modal title="Add language" busy={busy} error={error} onClose={() => setModal(null)}
          onSubmit={() => run(() => axios.post(`${API}/profile/languages`, form, { headers: headers() }), 'Language added')}>
          <Field label="Language"><input required maxLength={40} value={form.name} onChange={e => setForm({ name: e.target.value })} className={input} /></Field>
          <Field label="Proficiency"><select value={form.proficiency} onChange={e => setForm({ proficiency: e.target.value })} className={input}>
            {PROFICIENCIES.map(p => <option key={p}>{p}</option>)}</select></Field>
        </Modal>)}

      {modal?.kind === 'preferences' && (
        <Modal title="Job preferences" busy={busy} error={error} onClose={() => setModal(null)}
          onSubmit={() => patch({
            expected_pay_hourly: form.expected_pay_hourly === '' ? null : Number(form.expected_pay_hourly),
            notice_period_days: form.notice_period_days === '' ? null : Number(form.notice_period_days),
            job_alert_work_type: form.job_alert_work_type, job_alerts_enabled: form.job_alerts_enabled,
          }, 'Preferences saved')}>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Expected pay (USD / hour)"><input type="number" min="0" step="1" value={form.expected_pay_hourly} onChange={e => setForm({ expected_pay_hourly: e.target.value })} className={input} /></Field>
            <Field label="Notice period (days)"><input type="number" min="0" max="365" value={form.notice_period_days} onChange={e => setForm({ notice_period_days: e.target.value })} className={input} /></Field>
          </div>
          <Field label="Preferred work type"><select value={form.job_alert_work_type} onChange={e => setForm({ job_alert_work_type: e.target.value })} className={input}>
            <option value="all">Any</option><option value="remote">Remote</option><option value="hybrid">Hybrid</option><option value="onsite">On-site</option></select></Field>
          {!profile.is_hr && !profile.is_admin && (
            <label className="flex items-start gap-3 text-sm text-slate-700">
              <input type="checkbox" className="mt-0.5 accent-emerald-600" disabled={!profile.is_verified} checked={form.job_alerts_enabled} onChange={e => setForm({ job_alerts_enabled: e.target.checked })} />
              <span>Email me a daily digest of new jobs matching my headline and work type.
                {!profile.is_verified && <span className="block text-xs text-amber-700">Verify your email first.</span>}
                {!profile.career_track && <span className="block text-xs text-amber-700">Add a headline in Edit profile first.</span>}</span>
            </label>)}
        </Modal>)}
    </div>
  );
}
