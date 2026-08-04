// =============================================================================
// job-hunter-dashboard/src/components/ProfilePage.jsx
// Matches reference layout: header card, certified skills, other skills,
// about, education, experience, languages, delete account.
// =============================================================================
import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const PROFICIENCIES = ['Basic', 'Intermediate', 'Advanced', 'Fluent', 'Native'];

// ── Small reusable pieces ─────────────────────────────────────────────────────
function ChevronIcon({ open }) {
  return (
    <svg className={`w-4 h-4 text-slate-500 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
    </svg>
  );
}

function SectionCard({ title, badge, defaultOpen = true, actions, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-800/40 transition-colors">
        <div className="flex items-center gap-2">
          <span className="text-sm font-black text-white">{title}</span>
          {badge}
        </div>
        <div className="flex items-center gap-3">
          {actions}
          <ChevronIcon open={open} />
        </div>
      </button>
      {open && <div className="px-6 pb-6">{children}</div>}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function ProfilePage() {
  const [profile, setProfile]     = useState(null);
  const [loading, setLoading]     = useState(true);
  const [editingAbout, setEditingAbout] = useState(false);
  const [aboutDraft, setAboutDraft]     = useState('');
  const [newSkill, setNewSkill]         = useState('');
  const [newLang, setNewLang]           = useState('');
  const [newLangProf, setNewLangProf]   = useState('Advanced');
  const [showEduForm, setShowEduForm]   = useState(false);
  const [eduForm, setEduForm]           = useState({ degree: '', institution: '', start_date: '', end_date: '' });
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [saving, setSaving]             = useState(false);
  const photoInputRef = useRef(null);
  const token = localStorage.getItem('token');

  const fetchProfile = () => {
    axios.get(`${API_BASE_URL}/profile/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => { setProfile(r.data); setAboutDraft(r.data.about || ''); })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { if (token) fetchProfile(); else setLoading(false); }, [token]);

  const patchProfile = async (fields) => {
    setSaving(true);
    try {
      const res = await axios.patch(`${API_BASE_URL}/profile/me`, fields, { headers: { Authorization: `Bearer ${token}` } });
      setProfile(res.data);
    } catch (e) { alert('Failed to save changes.'); }
    finally { setSaving(false); }
  };

  const handlePhotoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await axios.post(`${API_BASE_URL}/profile/photo`, formData, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' }
      });
      setProfile(p => ({ ...p, photo_url: res.data.photo_url }));
    } catch { alert('Failed to upload photo.'); }
  };

  const saveAbout = async () => {
    await patchProfile({ about: aboutDraft });
    setEditingAbout(false);
  };

  const addOtherSkill = async () => {
    if (!newSkill.trim()) return;
    try {
      const res = await axios.post(`${API_BASE_URL}/profile/skills/other`, { name: newSkill.trim() }, { headers: { Authorization: `Bearer ${token}` } });
      setProfile(p => ({ ...p, other_skills: [...p.other_skills, res.data] }));
      setNewSkill('');
    } catch (e) { alert(e.response?.data?.detail || 'Failed to add skill.'); }
  };

  const removeOtherSkill = async (id) => {
    try {
      await axios.delete(`${API_BASE_URL}/profile/skills/other/${id}`, { headers: { Authorization: `Bearer ${token}` } });
      setProfile(p => ({ ...p, other_skills: p.other_skills.filter(s => s.id !== id) }));
    } catch { alert('Failed to remove skill.'); }
  };

  const addLanguage = async () => {
    if (!newLang.trim()) return;
    try {
      const res = await axios.post(`${API_BASE_URL}/profile/languages`, { name: newLang.trim(), proficiency: newLangProf }, { headers: { Authorization: `Bearer ${token}` } });
      setProfile(p => ({ ...p, languages: [...p.languages, res.data] }));
      setNewLang('');
    } catch (e) { alert(e.response?.data?.detail || 'Failed to add language.'); }
  };

  const removeLanguage = async (id) => {
    try {
      await axios.delete(`${API_BASE_URL}/profile/languages/${id}`, { headers: { Authorization: `Bearer ${token}` } });
      setProfile(p => ({ ...p, languages: p.languages.filter(l => l.id !== id) }));
    } catch { alert('Failed to remove language.'); }
  };

  const submitEducation = async () => {
    if (!eduForm.degree.trim() || !eduForm.institution.trim()) return;
    try {
      const res = await axios.post(`${API_BASE_URL}/profile/education`, eduForm, { headers: { Authorization: `Bearer ${token}` } });
      setProfile(p => ({ ...p, education: [res.data, ...p.education] }));
      setEduForm({ degree: '', institution: '', start_date: '', end_date: '' });
      setShowEduForm(false);
    } catch { alert('Failed to add education.'); }
  };

  const removeEducation = async (id) => {
    try {
      await axios.delete(`${API_BASE_URL}/profile/education/${id}`, { headers: { Authorization: `Bearer ${token}` } });
      setProfile(p => ({ ...p, education: p.education.filter(e => e.id !== id) }));
    } catch { alert('Failed to remove education entry.'); }
  };

  const deleteAccount = async () => {
    try {
      await axios.delete(`${API_BASE_URL}/profile/me`, { headers: { Authorization: `Bearer ${token}` } });
      localStorage.removeItem('token');
      window.location.href = '/login';
    } catch { alert('Failed to delete account.'); }
  };

  if (loading) return (
    <div className="flex items-center justify-center py-32">
      <div className="w-10 h-10 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
    </div>
  );

  if (!profile) return (
    <div className="text-center py-32 text-slate-400">Could not load profile. Please login again.</div>
  );

  const initials = (profile.full_name || profile.email || 'U').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
  const createdDate = profile.created_at
    ? new Date(profile.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : '';

  return (
    <div className="max-w-4xl mx-auto space-y-5" style={{ fontFamily: "'Inter', sans-serif" }}>

      {/* Page header */}
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-2xl font-black text-white" style={{ fontFamily: "'Playfair Display', serif" }}>My Profile</h1>
        <span className="text-xs text-slate-500">Account created on {createdDate}</span>
      </div>

      {/* ── Profile header card ── */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
          <div className="flex items-start gap-4">
            {/* Avatar */}
            <div className="relative shrink-0">
              <div className="w-20 h-20 rounded-2xl overflow-hidden bg-slate-800 border border-slate-700">
                {profile.photo_url ? (
                  <img src={profile.photo_url} alt="" className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-2xl font-black text-emerald-400 bg-emerald-500/10">
                    {initials}
                  </div>
                )}
              </div>
              <button onClick={() => photoInputRef.current?.click()}
                className="absolute -bottom-1 -right-1 w-7 h-7 rounded-full bg-emerald-600 hover:bg-emerald-500 border-2 border-slate-900 flex items-center justify-center transition-all">
                <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"/>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"/>
                </svg>
              </button>
              <input ref={photoInputRef} type="file" accept="image/*" className="hidden" onChange={handlePhotoUpload} />
            </div>

            {/* Name + meta */}
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-black text-white">{profile.full_name || 'Unnamed User'}</h2>
                {profile.is_verified && (
                  <svg className="w-4 h-4 text-emerald-400" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
                  </svg>
                )}
              </div>
              <p className="text-slate-400 text-sm font-medium mt-0.5">{profile.career_track || 'Add your career track'}</p>
              {profile.linkedin_url && (
                <a href={profile.linkedin_url} target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 font-bold mt-1">
                  <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                  </svg>
                  LinkedIn profile ↗
                </a>
              )}
              <div className="flex flex-wrap items-center gap-3 mt-3 text-xs text-slate-500">
                {profile.country && <span>🌍 {profile.country}</span>}
                <span>✉️ {profile.email}</span>
                {profile.phone && <span>📞 {profile.phone}</span>}
              </div>
            </div>
          </div>

          {/* Availability + pay */}
          <div className="flex flex-col items-end gap-2 shrink-0">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">Available for new opportunities</span>
              <button onClick={() => patchProfile({ available_for_work: !profile.available_for_work })}
                className={`text-xs font-black px-3 py-1 rounded-full border transition-all ${
                  profile.available_for_work
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                    : 'bg-slate-800 border-slate-700 text-slate-400'
                }`}>
                {profile.available_for_work ? 'Yes' : 'No'}
              </button>
            </div>
            <div className="text-right">
              <p className="text-xs text-slate-500">Expected pay</p>
              <div className="flex items-center gap-1.5">
                <span className="text-white font-black text-sm">
                  {profile.expected_pay_hourly ? `$${profile.expected_pay_hourly}/hour` : 'Not set'}
                </span>
                <button onClick={() => {
                  const val = prompt('Expected hourly rate (USD)', profile.expected_pay_hourly || '');
                  if (val !== null && !isNaN(parseFloat(val))) patchProfile({ expected_pay_hourly: parseFloat(val) });
                }} className="text-slate-500 hover:text-emerald-400 transition-colors">
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Certified skills ── */}
      <SectionCard title="Certified skills" badge={
        <span className="text-slate-600" title="Auto-verified based on your ATS scans and platform activity">ⓘ</span>
      }>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {(profile.certified_skills || []).map(skill => (
            <div key={skill.id} className="flex items-center gap-2.5 bg-emerald-500/5 border border-emerald-500/20 rounded-xl px-4 py-3">
              <span className="w-6 h-6 rounded-full bg-emerald-500/15 flex items-center justify-center shrink-0">
                <svg className="w-3.5 h-3.5 text-emerald-400" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
                </svg>
              </span>
              <span className="text-sm font-bold text-slate-200">{skill.name}</span>
            </div>
          ))}
        </div>
      </SectionCard>

      {/* ── Other skills ── */}
      <SectionCard title="Other Skills" defaultOpen={false}>
        <div className="flex flex-wrap gap-2 mb-3">
          {(profile.other_skills || []).map(skill => (
            <span key={skill.id} className="flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-full bg-slate-800 border border-slate-700 text-slate-300">
              {skill.name}
              <button onClick={() => removeOtherSkill(skill.id)} className="text-slate-500 hover:text-rose-400 transition-colors">×</button>
            </span>
          ))}
          {(!profile.other_skills || profile.other_skills.length === 0) && (
            <p className="text-xs text-slate-600">No additional skills added yet.</p>
          )}
        </div>
        <div className="flex gap-2">
          <input value={newSkill} onChange={e => setNewSkill(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && addOtherSkill()}
            placeholder="e.g. Docker, Terraform, Kubernetes"
            className="flex-1 px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white outline-none focus:border-emerald-500 transition-all" />
          <button onClick={addOtherSkill} className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black transition-all">Add</button>
        </div>
      </SectionCard>

      {/* ── About ── */}
      <SectionCard title="About" actions={
        !editingAbout && (
          <button onClick={(e) => { e.stopPropagation(); setEditingAbout(true); }} className="text-slate-500 hover:text-emerald-400 transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
            </svg>
          </button>
        )
      }>
        {editingAbout ? (
          <div>
            <textarea value={aboutDraft} onChange={e => setAboutDraft(e.target.value)} rows={4}
              className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white outline-none focus:border-emerald-500 transition-all resize-none"
              placeholder="Tell recruiters about your experience, focus areas, and what you're looking for..." />
            <div className="flex gap-2 mt-3">
              <button onClick={saveAbout} disabled={saving}
                className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black transition-all">
                {saving ? 'Saving...' : 'Save'}
              </button>
              <button onClick={() => { setEditingAbout(false); setAboutDraft(profile.about || ''); }}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-black transition-all">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <>
            <p className="text-sm text-slate-400 leading-relaxed mb-3">
              {profile.about || 'No bio added yet. Click the edit icon to introduce yourself.'}
            </p>
            {profile.id_verified && (
              <div className="flex items-center gap-1.5 mb-3">
                <svg className="w-3.5 h-3.5 text-emerald-400" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
                </svg>
                <span className="text-xs font-bold text-emerald-400">ID Verified</span>
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              {profile.resume_filename && (
                <span className="flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400">
                  📄 {profile.resume_filename}
                </span>
              )}
              {profile.notice_period_days != null && (
                <span className="text-xs font-bold px-3 py-1.5 rounded-full bg-slate-800 border border-slate-700 text-slate-300">
                  Notice period: {profile.notice_period_days} days
                </span>
              )}
              {profile.city && (
                <span className="text-xs font-bold px-3 py-1.5 rounded-full bg-slate-800 border border-slate-700 text-slate-300">
                  City: {profile.city}
                </span>
              )}
              {profile.timezone && (
                <span className="text-xs font-bold px-3 py-1.5 rounded-full bg-slate-800 border border-slate-700 text-slate-300">
                  Timezone: {profile.timezone}
                </span>
              )}
            </div>
          </>
        )}
      </SectionCard>

      {/* ── Experience ── */}
      <SectionCard title="Experience" defaultOpen={false}>
        {(profile.experience || []).length === 0 ? (
          <p className="text-xs text-slate-600">No experience added yet.</p>
        ) : (
          <div className="space-y-3">
            {profile.experience.map(exp => (
              <div key={exp.id} className="flex items-start justify-between bg-slate-950 border border-slate-800 rounded-xl p-4">
                <div>
                  <p className="text-sm font-black text-white">{exp.title}</p>
                  <p className="text-xs text-emerald-400 font-bold">{exp.company}</p>
                  <p className="text-[10px] text-slate-500 mt-0.5">{exp.start_date} – {exp.end_date || 'Present'}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      {/* ── Education ── */}
      <SectionCard title="Education">
        <div className="space-y-3">
          {(profile.education || []).map(edu => (
            <div key={edu.id} className="flex items-center justify-between bg-slate-950 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-slate-800 flex items-center justify-center shrink-0">
                  🎓
                </div>
                <div>
                  <p className="text-sm font-black text-white">{edu.degree}</p>
                  <p className="text-xs text-emerald-400 font-bold">{edu.institution}</p>
                  <p className="text-[10px] text-slate-500 mt-0.5">{edu.start_date} – {edu.end_date || 'Present'}</p>
                </div>
              </div>
              <button onClick={() => removeEducation(edu.id)} className="text-slate-600 hover:text-rose-400 transition-colors">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                </svg>
              </button>
            </div>
          ))}

          {showEduForm ? (
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3">
              <input value={eduForm.degree} onChange={e => setEduForm(f => ({ ...f, degree: e.target.value }))}
                placeholder="Degree — e.g. B.Sc Computer Science"
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white outline-none focus:border-emerald-500" />
              <input value={eduForm.institution} onChange={e => setEduForm(f => ({ ...f, institution: e.target.value }))}
                placeholder="Institution"
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white outline-none focus:border-emerald-500" />
              <div className="grid grid-cols-2 gap-2">
                <input value={eduForm.start_date} onChange={e => setEduForm(f => ({ ...f, start_date: e.target.value }))}
                  placeholder="Start (e.g. Jan 2020)"
                  className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white outline-none focus:border-emerald-500" />
                <input value={eduForm.end_date} onChange={e => setEduForm(f => ({ ...f, end_date: e.target.value }))}
                  placeholder="End (e.g. Dec 2023)"
                  className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white outline-none focus:border-emerald-500" />
              </div>
              <div className="flex gap-2">
                <button onClick={submitEducation} className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black transition-all">Save</button>
                <button onClick={() => setShowEduForm(false)} className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-black transition-all">Cancel</button>
              </div>
            </div>
          ) : (
            <button onClick={() => setShowEduForm(true)}
              className="w-full py-3 rounded-xl bg-slate-800/50 hover:bg-slate-800 border border-dashed border-slate-700 text-slate-400 hover:text-white text-xs font-black transition-all flex items-center justify-center gap-1.5">
              + Add more
            </button>
          )}
        </div>
      </SectionCard>

      {/* ── Languages ── */}
      <SectionCard title="Languages">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          {(profile.languages || []).map(lang => (
            <span key={lang.id} className="flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-full bg-slate-800 border border-slate-700 text-slate-300">
              {lang.name} <span className="text-emerald-400">· {lang.proficiency}</span>
              <button onClick={() => removeLanguage(lang.id)} className="text-slate-500 hover:text-rose-400 transition-colors ml-1">×</button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <input value={newLang} onChange={e => setNewLang(e.target.value)}
            placeholder="Language — e.g. French"
            className="flex-1 px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white outline-none focus:border-emerald-500 transition-all" />
          <select value={newLangProf} onChange={e => setNewLangProf(e.target.value)}
            className="px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white outline-none focus:border-emerald-500">
            {PROFICIENCIES.map(p => <option key={p} value={p} style={{ background: '#0f172a' }}>{p}</option>)}
          </select>
          <button onClick={addLanguage} className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black transition-all shrink-0">+ Add more</button>
        </div>
      </SectionCard>

      {/* ── Delete account ── */}
      <div className="text-center py-6">
        {!deleteConfirm ? (
          <button onClick={() => setDeleteConfirm(true)} className="text-xs font-bold text-rose-500 hover:text-rose-400 transition-colors">
            Delete my account
          </button>
        ) : (
          <div className="inline-flex items-center gap-3 bg-rose-950/30 border border-rose-900/40 rounded-2xl px-5 py-3">
            <span className="text-xs font-bold text-rose-300">Are you sure? This cannot be undone.</span>
            <button onClick={deleteAccount} className="text-xs font-black px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white transition-all">Yes, delete</button>
            <button onClick={() => setDeleteConfirm(false)} className="text-xs font-black px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-all">Cancel</button>
          </div>
        )}
      </div>
    </div>
  );
}
