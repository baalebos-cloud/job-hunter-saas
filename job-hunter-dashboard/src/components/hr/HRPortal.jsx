import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Briefcase, Users, CalendarCheck, Plus, MapPin, Wallet, Building2, Globe2, Trash2, Eye,
  FileText, BadgeCheck, CheckCircle2, AlertCircle, X, ExternalLink, ChevronLeft, Inbox, ClipboardList, ChevronDown, UsersRound,
} from 'lucide-react';
import { errorText } from '../../lib/session';
import ApplicationFormBuilder from './ApplicationFormBuilder';
import TeamPanel from './TeamPanel';
import HiringTeamDialog from './HiringTeamDialog';
import { defaultApplicationForm, formProblems } from '../../lib/applicationForm';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const h = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });

const WORK_TYPES = [
  { id: 'remote', label: 'Remote' },
  { id: 'hybrid', label: 'Hybrid' },
  { id: 'onsite', label: 'On-site' },
];
const CATEGORIES = [
  'Software Engineer', 'Frontend Developer', 'Backend Engineer', 'Full Stack Developer',
  'DevOps Engineer', 'Cloud Engineer', 'Data Engineer', 'Data Scientist',
  'Machine Learning Engineer', 'Mobile Developer', 'QA Engineer', 'Product Manager',
  'UI/UX Designer', 'Cybersecurity Engineer', 'Platform Engineer',
  'Sales', 'Marketing', 'Customer Support', 'Finance', 'Operations',
  'Human Resources', 'Legal', 'Content Writer', 'Graphic Designer',
  'Business Analyst', 'Project Manager', 'Scrum Master',
];
// Application stages accepted by PATCH /hr/applications/{id}/status.
const STAGES = [
  { id: 'pending', label: 'New', cls: 'bg-slate-100 text-slate-700' },
  { id: 'reviewed', label: 'Reviewed', cls: 'bg-sky-50 text-sky-700' },
  { id: 'interview', label: 'Interview', cls: 'bg-violet-50 text-violet-700' },
  { id: 'offer', label: 'Offer', cls: 'bg-emerald-50 text-emerald-700' },
  { id: 'rejected', label: 'Not progressing', cls: 'bg-rose-50 text-rose-700' },
];
// Statuses an application can have before the employer acts on it.
const NEW_STATUSES = new Set(['pending', 'submitted_internal', 'submitted_external', 'external_started', 'applied']);
const stageId = status => (!status || NEW_STATUSES.has(status) ? 'pending' : status);
const stage = status => STAGES.find(s => s.id === stageId(status)) || { id: status, label: status, cls: 'bg-slate-100 text-slate-700' };
const workTypeLabel = id => WORK_TYPES.find(w => w.id === id)?.label || id;
const EMPTY_FORM = { title: '', company: '', location: '', description: '', salary_range: '', work_type: 'remote', category: 'Software Engineer', url: '', application_form: null };
const answerText = (v) => (v == null || v === '' ? 'Not provided' : Array.isArray(v) ? v.join(', ') : v === 'yes' ? 'Yes' : v === 'no' ? 'No' : String(v));
const isLink = (v) => typeof v === 'string' && v.startsWith('https://');

// What the candidate sent with an application on Baalebos.
function AnswersPanel({ app }) {
  const d = app.details || {};
  const rows = [['Phone', d.phone], ['Country', d.country], ...app.answers.map(a => [a.label, a.value])];
  return (
    <dl className="mt-3 grid sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)] gap-x-4 gap-y-2 rounded-xl bg-slate-50 p-4 text-sm">
      {rows.filter(([, v]) => v !== undefined).map(([label, value], i) => (
        <div key={i} className="contents">
          <dt className="text-slate-500">{label}</dt>
          <dd className={`break-words whitespace-pre-line ${value == null || value === '' ? 'text-slate-400' : 'text-slate-900'}`}>
            {isLink(value) ? <a href={value} target="_blank" rel="noopener noreferrer nofollow" className="text-emerald-700 hover:underline">{value}</a> : answerText(value)}
          </dd>
        </div>))}
    </dl>
  );
}

const inputCls = 'w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-emerald-600 focus:ring-4 focus:ring-emerald-600/10';
const labelCls = 'block text-sm font-medium text-slate-700 mb-1.5';
const card = 'bg-white rounded-2xl border border-slate-200';

function Field({ label, required, hint, children, htmlFor }) {
  return (
    <div>
      <label htmlFor={htmlFor} className={labelCls}>
        {label}{required && <span className="text-rose-600"> *</span>}
      </label>
      {children}
      {hint && <p className="text-xs text-slate-500 mt-1.5">{hint}</p>}
    </div>
  );
}

function Stat({ icon: Icon, label, value, tone }) {
  return (
    <div className={`${card} p-5 flex items-center gap-4`}>
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${tone}`}><Icon size={20} /></div>
      <div>
        <p className="text-sm text-slate-500">{label}</p>
        <p className="text-2xl font-semibold text-slate-900 leading-tight">{value ?? '—'}</p>
      </div>
    </div>
  );
}

function initials(name) {
  return (name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map(p => p[0].toUpperCase()).join('');
}

export default function HRPortal() {
  const [dashboard, setDashboard] = useState(null);
  const [myJobs, setMyJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [applications, setApplications] = useState([]);
  const [resumePreview, setResumePreview] = useState(null);
  const [loadingResume, setLoadingResume] = useState(null);
  const [resumeError, setResumeError] = useState('');
  useEffect(() => {
    if (!resumePreview) return;
    const close = e => { if (e.key === 'Escape') setResumePreview(null); };
    window.addEventListener('keydown', close);
    return () => { URL.revokeObjectURL(resumePreview.url); window.removeEventListener('keydown', close); };
  }, [resumePreview]);
  const [tab, setTab] = useState('post');
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);
  const [notice, setNotice] = useState(null);   // { type: 'success' | 'error', text }
  const [categoryQuery, setCategoryQuery] = useState('Software Engineer');
  const [showCatSuggestions, setShowCatSuggestions] = useState(false);
  const catRef = useRef(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [formEditor, setFormEditor] = useState(null);   // { job, value, saving, error }
  const [openAnswers, setOpenAnswers] = useState(null);
  const [answerFilter, setAnswerFilter] = useState('');   // "label||yes" or ''
  const [workspace, setWorkspace] = useState(null);       // { company, role, role_label, permissions }
  const [hiringTeamJob, setHiringTeamJob] = useState(null);

  useEffect(() => {
    if (!localStorage.getItem('token')) { window.location.href = '/login'; return; }
    axios.get(`${API}/hr/workspace`, { headers: h() })
      .then(r => { setWorkspace(r.data); if (!r.data.permissions.post_jobs) setTab('my-jobs'); })
      // If this fails the portal shows every action; the API still enforces the person's role.
      .catch(() => setWorkspace({ permissions: { post_jobs: true, all_jobs: true, move_candidates: true, manage_team: false } }));
    axios.get(`${API}/hr/dashboard`, { headers: h() })
      .then(r => {
        setDashboard(r.data);
        if (r.data?.company) setForm(f => (f.company ? f : { ...f, company: r.data.company }));
      })
      .catch(e => { if (e.response?.status === 403) { alert('HR access required. Contact admin.'); window.location.href = '/'; } })
      .finally(() => setLoading(false));
    loadJobs();
  }, []);

  const loadJobs = async () => {
    try {
      const r = await axios.get(`${API}/hr/jobs`, { headers: h() });
      setMyJobs(r.data);
    } catch { /* the list simply stays empty */ }
  };

  const loadApplications = async (jobId) => {
    setSelectedJob(jobId);
    setResumeError(''); setOpenAnswers(null); setAnswerFilter('');
    const r = await axios.get(`${API}/hr/jobs/${jobId}/applications`, { headers: h() });
    setApplications(r.data);
    setTab('applications');
  };

  const postJob = async (e) => {
    e.preventDefault();
    const appForm = form.application_form || defaultApplicationForm();
    const problems = form.url ? [] : formProblems(appForm);
    if (problems.length) { setNotice({ type: 'error', text: `Application form: ${problems[0]}` }); return; }
    setPosting(true);
    setNotice(null);
    try {
      await axios.post(`${API}/hr/jobs`, { ...form, url: form.url || null, application_form: form.url ? null : appForm }, { headers: h() });
      setNotice({ type: 'success', text: `“${form.title}” is live in the job feed.` });
      setForm({ ...EMPTY_FORM, company: dashboard?.company || '' });
      setCategoryQuery(EMPTY_FORM.category);
      loadJobs();
      setTab('my-jobs');
    } catch (err) {
      setNotice({ type: 'error', text: errorText(err, 'The job could not be posted. Please try again.') });
    } finally { setPosting(false); }
  };

  const deleteJob = async (job) => {
    if (!confirm(`Delete “${job.title}”? Candidates will no longer see it.`)) return;
    try {
      await axios.delete(`${API}/hr/jobs/${job.id}`, { headers: h() });
      setNotice({ type: 'success', text: `“${job.title}” was deleted.` });
      if (selectedJob === job.id) { setSelectedJob(null); setApplications([]); }
      loadJobs();
    } catch (err) {
      setNotice({ type: 'error', text: errorText(err, 'The job could not be deleted.') });
    }
  };

  const saveForm = async () => {
    const problems = formProblems(formEditor.value);
    if (problems.length) { setFormEditor(f => ({ ...f, error: problems[0] })); return; }
    setFormEditor(f => ({ ...f, saving: true, error: '' }));
    try {
      await axios.put(`${API}/hr/jobs/${formEditor.job.id}/application-form`, formEditor.value, { headers: h() });
      setNotice({ type: 'success', text: `Application form for “${formEditor.job.title}” saved. It applies to new applications.` });
      setFormEditor(null); loadJobs();
    } catch (err) {
      setFormEditor(f => ({ ...f, saving: false, error: errorText(err, 'The application form could not be saved.') }));
    }
  };

  const updateStatus = async (appId, status) => {
    try {
      await axios.patch(`${API}/hr/applications/${appId}/status?new_status=${status}`, {}, { headers: h() });
      if (selectedJob) loadApplications(selectedJob);
    } catch (err) {
      setNotice({ type: 'error', text: errorText(err, 'The application stage could not be updated.') });
    }
  };

  const viewResume = async (app) => {
    setLoadingResume(app.application_id);
    setResumeError('');
    try {
      const response = await axios.get(`${API}/hr/applications/${app.application_id}/resume`, {
        headers: h(), responseType: 'blob', timeout: 30000,
      });
      setResumePreview({ url: URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' })), name: app.applicant_name });
    } catch {
      setResumeError('The submitted resume could not be loaded. Please retry.');
    } finally { setLoadingResume(null); }
  };

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const yesNoLabels = [...new Set(applications.flatMap(a => (a.answers || []).filter(x => x.type === 'yes_no').map(x => x.label)))];
  const shown = !answerFilter ? applications : applications.filter(a => {
    const [label, value] = answerFilter.split('||');
    return (a.answers || []).some(x => x.label === label && x.value === value);
  });
  const selectedJobInfo = myJobs.find(j => j.id === selectedJob);

  if (loading || !workspace) return (
    <div className="p-6 md:p-9 space-y-6 animate-pulse" aria-busy="true">
      <div className="h-20 bg-white rounded-2xl border border-slate-200" />
      <div className="grid sm:grid-cols-3 gap-4">{[0, 1, 2].map(i => <div key={i} className="h-24 bg-white rounded-2xl border border-slate-200" />)}</div>
      <div className="h-96 bg-white rounded-2xl border border-slate-200" />
    </div>
  );

  // What this person's company role allows (hidden until known, so nothing flashes and then disappears).
  const can = p => Boolean(workspace?.permissions?.[p]);
  const TABS = [
    ...(can('post_jobs') ? [{ id: 'post', label: 'Post a job', icon: Plus }] : []),
    { id: 'my-jobs', label: 'Job postings', icon: Briefcase, count: myJobs.length },
    { id: 'applications', label: 'Applicants', icon: Users, count: selectedJob ? applications.length : undefined },
    { id: 'team', label: 'Team', icon: UsersRound },
  ];

  return (
    <div className="p-6 md:p-9 space-y-6 max-w-7xl">
      {resumePreview && (
        <div className="fixed inset-0 z-[60] bg-slate-900/50 backdrop-blur-sm p-4 flex items-center justify-center">
          <section role="dialog" aria-modal="true" aria-labelledby="applicant-resume-title" className="bg-white rounded-2xl w-full max-w-5xl h-[85vh] flex flex-col shadow-2xl">
            <div className="flex items-center justify-between gap-3 px-6 py-4 border-b border-slate-200">
              <div>
                <h2 id="applicant-resume-title" className="font-semibold text-slate-900">Submitted resume</h2>
                <p className="text-sm text-slate-500">{resumePreview.name}</p>
              </div>
              <div className="flex items-center gap-2">
                <a href={resumePreview.url} download="Applicant_Resume.pdf" className="text-sm font-medium text-emerald-700 hover:text-emerald-800 px-3 py-2">Download PDF</a>
                <button autoFocus onClick={() => setResumePreview(null)} aria-label="Close preview" className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X size={18} /></button>
              </div>
            </div>
            <iframe title={`Submitted resume for ${resumePreview.name}`} src={resumePreview.url} className="w-full flex-1 rounded-b-2xl bg-slate-50" />
          </section>
        </div>
      )}

      {formEditor && (
        <div className="fixed inset-0 z-[60] bg-slate-900/50 backdrop-blur-sm p-4 flex items-center justify-center">
          <section role="dialog" aria-modal="true" aria-labelledby="form-editor-title" className="bg-white rounded-2xl w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl">
            <div className="flex items-start justify-between gap-3 px-6 py-4 border-b border-slate-200">
              <div>
                <h2 id="form-editor-title" className="font-semibold text-slate-900">Application form</h2>
                <p className="text-sm text-slate-500">{formEditor.job.title} · changes apply to new applications; ones already received keep their answers.</p>
              </div>
              <button onClick={() => setFormEditor(null)} aria-label="Close" className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X size={18} /></button>
            </div>
            <div className="p-6 overflow-y-auto">
              <ApplicationFormBuilder value={formEditor.value} onChange={v => setFormEditor(f => ({ ...f, value: v, error: '' }))}
                copyFrom={myJobs.filter(j => j.id !== formEditor.job.id && !j.url && j.application_form)} />
            </div>
            <div className="px-6 py-4 border-t border-slate-200 flex flex-wrap items-center justify-end gap-3">
              {formEditor.error && <p role="alert" className="mr-auto text-sm text-rose-700">{formEditor.error}</p>}
              <button onClick={() => setFormEditor(null)} className="rounded-xl px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-100">Cancel</button>
              <button onClick={saveForm} disabled={formEditor.saving}
                className="rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-medium px-5 py-2.5 disabled:opacity-60">{formEditor.saving ? 'Saving…' : 'Save form'}</button>
            </div>
          </section>
        </div>
      )}

      {hiringTeamJob && (
        <HiringTeamDialog job={hiringTeamJob} onClose={() => setHiringTeamJob(null)}
          onSaved={text => { setHiringTeamJob(null); setNotice({ type: 'success', text }); }} />
      )}

      {/* Company bar */}
      <section className={`${card} p-6 flex flex-wrap items-center gap-4`}>
        <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center"><Building2 size={22} /></div>
        <div className="flex-1 min-w-[12rem]">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-lg font-semibold text-slate-900">{workspace?.company?.name || dashboard?.company || 'Your company'}</h2>
            {workspace && <span className="text-xs font-medium text-slate-600 bg-slate-100 rounded-full px-2.5 py-1">{workspace.role_label}</span>}
            <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-50 rounded-full px-2.5 py-1">
              <BadgeCheck size={14} /> Verified employer
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-0.5">
            {workspace && !can('all_jobs')
              ? 'You see the jobs you’re on the hiring team for. Ask your admin to add you to others.'
              : 'Post roles, review applicants and move candidates through your pipeline.'}
          </p>
        </div>
        {can('post_jobs') && <button onClick={() => setTab('post')} className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-medium px-4 py-2.5">
          <Plus size={16} /> Post a job
        </button>}
      </section>

      {/* KPIs */}
      <div className="grid sm:grid-cols-3 gap-4">
        <Stat icon={Briefcase} label="Open roles" value={dashboard?.total_jobs_posted} tone="bg-emerald-50 text-emerald-700" />
        <Stat icon={Users} label="Total applicants" value={dashboard?.total_applications} tone="bg-sky-50 text-sky-700" />
        <Stat icon={CalendarCheck} label="In interview" value={dashboard?.interviews_scheduled} tone="bg-violet-50 text-violet-700" />
      </div>

      {notice && (
        <div role={notice.type === 'error' ? 'alert' : 'status'}
          className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-sm ${notice.type === 'success' ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : 'bg-rose-50 border-rose-200 text-rose-800'}`}>
          {notice.type === 'success' ? <CheckCircle2 size={18} className="mt-0.5 shrink-0" /> : <AlertCircle size={18} className="mt-0.5 shrink-0" />}
          <p className="flex-1">{notice.text}</p>
          <button onClick={() => setNotice(null)} aria-label="Dismiss" className="opacity-60 hover:opacity-100"><X size={16} /></button>
        </div>
      )}

      {/* Tabs */}
      <div role="tablist" aria-label="Employer portal sections" className="flex w-fit max-w-full overflow-x-auto overscroll-x-contain rounded-xl bg-slate-100 p-1 gap-1">
        {TABS.map(({ id, label, icon: Icon, count }) => (
          <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
            className={`shrink-0 inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition ${tab === id ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}>
            <Icon size={16} />{label}
            {count !== undefined && <span className={`rounded-full px-2 py-0.5 text-xs ${tab === id ? 'bg-emerald-50 text-emerald-700' : 'bg-white/70 text-slate-500'}`}>{count}</span>}
          </button>
        ))}
      </div>

      {/* Post a job */}
      {tab === 'team' && (
        <TeamPanel company={workspace?.company?.name || dashboard?.company} onNotice={setNotice} />
      )}

      {tab === 'post' && can('post_jobs') && (
        <div className="grid lg:grid-cols-[minmax(0,1fr)_22rem] gap-6 items-start">
          <form onSubmit={postJob} className={`${card} divide-y divide-slate-100`}>
            <div className="p-6">
              <h3 className="font-semibold text-slate-900">Role details</h3>
              <p className="text-sm text-slate-500 mt-0.5">Your listing goes live in the job feed as soon as you publish.</p>
              <div className="grid md:grid-cols-2 gap-4 mt-5">
                <Field label="Job title" required htmlFor="job-title">
                  <input id="job-title" required className={inputCls} placeholder="e.g. Senior DevOps Engineer"
                    value={form.title} onChange={e => set('title', e.target.value)} />
                </Field>
                <Field label="Company" required htmlFor="job-company">
                  <input id="job-company" required className={inputCls} placeholder="Your company name"
                    value={form.company} onChange={e => set('company', e.target.value)} />
                </Field>
                <Field label="Category" hint="Pick a suggestion or type your own." htmlFor="job-category">
                  <div className="relative" ref={catRef}>
                    <input id="job-category" className={inputCls} placeholder="e.g. DevOps Engineer" value={categoryQuery} autoComplete="off"
                      onChange={e => { setCategoryQuery(e.target.value); set('category', e.target.value); setShowCatSuggestions(true); }}
                      onFocus={() => setShowCatSuggestions(true)}
                      onBlur={() => setTimeout(() => setShowCatSuggestions(false), 150)} />
                    {showCatSuggestions && (
                      <div className="absolute z-30 w-full mt-1 bg-white border border-slate-200 rounded-xl shadow-lg max-h-56 overflow-y-auto py-1">
                        {CATEGORIES.filter(c => c.toLowerCase().includes(categoryQuery.toLowerCase())).map(c => (
                          <button key={c} type="button"
                            onMouseDown={() => { setCategoryQuery(c); set('category', c); setShowCatSuggestions(false); }}
                            className="w-full text-left px-3.5 py-2 text-sm text-slate-700 hover:bg-slate-50">{c}</button>
                        ))}
                        {categoryQuery && !CATEGORIES.some(c => c.toLowerCase() === categoryQuery.toLowerCase()) && (
                          <button type="button" onMouseDown={() => { set('category', categoryQuery); setShowCatSuggestions(false); }}
                            className="w-full text-left px-3.5 py-2 text-sm font-medium text-emerald-700 hover:bg-emerald-50">
                            Use “{categoryQuery}”
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </Field>
                <Field label="Work arrangement">
                  <div role="radiogroup" aria-label="Work arrangement" className="grid grid-cols-3 gap-2">
                    {WORK_TYPES.map(w => (
                      <button key={w.id} type="button" role="radio" aria-checked={form.work_type === w.id} onClick={() => set('work_type', w.id)}
                        className={`rounded-xl border px-3 py-2.5 text-sm font-medium transition ${form.work_type === w.id ? 'border-emerald-600 bg-emerald-50 text-emerald-800 ring-4 ring-emerald-600/10' : 'border-slate-300 text-slate-600 hover:border-slate-400'}`}>
                        {w.label}
                      </button>
                    ))}
                  </div>
                </Field>
              </div>
            </div>

            <div className="p-6">
              <h3 className="font-semibold text-slate-900">Location & compensation</h3>
              <div className="grid md:grid-cols-2 gap-4 mt-5">
                <Field label="Location" required htmlFor="job-location">
                  <input id="job-location" required className={inputCls} placeholder="e.g. Lagos, Nigeria or Remote (EMEA)"
                    value={form.location} onChange={e => set('location', e.target.value)} />
                </Field>
                <Field label="Salary range" hint="Listings with pay attract more qualified applicants." htmlFor="job-salary">
                  <input id="job-salary" className={inputCls} placeholder="e.g. ₦800k – ₦1.2M / month"
                    value={form.salary_range} onChange={e => set('salary_range', e.target.value)} />
                </Field>
              </div>
            </div>

            <div className="p-6">
              <h3 className="font-semibold text-slate-900">Description</h3>
              <div className="mt-5 space-y-4">
                <Field label="Full job description" required htmlFor="job-description"
                  hint={`${form.description.length.toLocaleString()} characters. Include responsibilities, requirements and benefits.`}>
                  <textarea id="job-description" required rows={9} className={`${inputCls} resize-y min-h-[10rem]`}
                    placeholder={'About the role…\n\nResponsibilities…\n\nRequirements…\n\nWhat we offer…'}
                    value={form.description} onChange={e => set('description', e.target.value)} />
                </Field>
                <Field label="External application link" hint="Optional. If set, candidates apply on your careers page instead of on Baalebos." htmlFor="job-url">
                  <input id="job-url" type="url" className={inputCls} placeholder="https://yourcompany.com/careers/job-id"
                    value={form.url} onChange={e => set('url', e.target.value)} />
                </Field>
              </div>
            </div>

            <div className="p-6">
              <h3 className="font-semibold text-slate-900">Application form</h3>
              {form.url ? (
                <p className="text-sm text-slate-500 mt-1">Candidates apply on your careers page, so they are not asked any questions on Baalebos.</p>
              ) : (<>
                <p className="text-sm text-slate-500 mt-0.5">Choose what applicants for this job must tell you, and add your own questions.</p>
                <div className="mt-5">
                  <ApplicationFormBuilder value={form.application_form || defaultApplicationForm()} onChange={v => set('application_form', v)}
                    copyFrom={myJobs.filter(j => !j.url && j.application_form)} />
                </div>
              </>)}
            </div>

            <div className="p-6 flex flex-wrap items-center justify-end gap-3 bg-slate-50/60 rounded-b-2xl">
              <button type="button" onClick={() => { setForm({ ...EMPTY_FORM, company: dashboard?.company || '' }); setCategoryQuery(EMPTY_FORM.category); }}
                className="rounded-xl px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-100">Clear form</button>
              <button type="submit" disabled={posting}
                className="rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-medium px-5 py-2.5 disabled:opacity-60 disabled:cursor-not-allowed">
                {posting ? 'Publishing…' : 'Publish job'}
              </button>
            </div>
          </form>

          {/* Live preview */}
          <aside className="lg:sticky lg:top-6 space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Preview · how candidates see it</p>
            <article className={`${card} p-5`}>
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg bg-slate-100 text-slate-600 flex items-center justify-center font-semibold">
                  {(form.company || 'C').slice(0, 1).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <h4 className="font-semibold text-slate-900 truncate">{form.title || 'Job title'}</h4>
                  <p className="text-sm text-slate-500 truncate">{form.company || 'Company'}</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2 mt-4 text-xs">
                <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-slate-600"><MapPin size={12} />{form.location || 'Location'}</span>
                <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-slate-600"><Globe2 size={12} />{workTypeLabel(form.work_type)}</span>
                {form.salary_range && <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700"><Wallet size={12} />{form.salary_range}</span>}
              </div>
              <p className="text-sm text-slate-600 mt-4 line-clamp-5 whitespace-pre-line">{form.description || 'Your description will appear here.'}</p>
              <p className="text-xs text-slate-400 mt-4">{form.category}</p>
            </article>
          </aside>
        </div>
      )}

      {/* Job postings */}
      {tab === 'my-jobs' && (
        myJobs.length === 0 ? (
          <div className={`${card} border-dashed p-12 text-center`}>
            <div className="mx-auto w-12 h-12 rounded-xl bg-slate-100 text-slate-500 flex items-center justify-center"><Briefcase size={22} /></div>
            <p className="font-medium text-slate-900 mt-4">No job postings yet</p>
            {can('post_jobs') ? (<>
              <p className="text-sm text-slate-500 mt-1">Publish your first role to start receiving applicants.</p>
              <button onClick={() => setTab('post')} className="mt-5 inline-flex items-center gap-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-medium px-4 py-2.5"><Plus size={16} />Post a job</button>
            </>) : <p className="text-sm text-slate-500 mt-1">You’re not on the hiring team for any job yet. Ask your company admin to add you.</p>}
          </div>
        ) : (
          <div className={`${card} divide-y divide-slate-100`}>
            {myJobs.map(job => (
              <div key={job.id} className="p-5 flex flex-wrap items-center gap-4">
                <div className="flex-1 min-w-[16rem]">
                  <h3 className="font-semibold text-slate-900">{job.title}</h3>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5 text-sm text-slate-500">
                    <span className="inline-flex items-center gap-1.5"><Building2 size={14} />{job.company}</span>
                    <span className="inline-flex items-center gap-1.5"><MapPin size={14} />{job.location}</span>
                    <span className="inline-flex items-center gap-1.5"><Globe2 size={14} />{workTypeLabel(job.work_type)}</span>
                    {job.salary_range && <span className="inline-flex items-center gap-1.5"><Wallet size={14} />{job.salary_range}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {job.url && (
                    <a href={job.url} target="_blank" rel="noopener noreferrer" title="External application page"
                      className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><ExternalLink size={16} /></a>
                  )}
                  {can('post_jobs') && (
                    <button onClick={() => setHiringTeamJob(job)}
                      className="inline-flex items-center gap-2 rounded-xl border border-slate-300 px-3.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
                      <UsersRound size={16} />Hiring team
                    </button>)}
                  {!job.url && can('post_jobs') && (
                    <button onClick={() => setFormEditor({ job, value: job.application_form || defaultApplicationForm(), saving: false, error: '' })}
                      className="inline-flex items-center gap-2 rounded-xl border border-slate-300 px-3.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
                      <ClipboardList size={16} />Application form
                    </button>)}
                  <button onClick={() => loadApplications(job.id)}
                    className="inline-flex items-center gap-2 rounded-xl border border-slate-300 px-3.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
                    <Users size={16} />View applicants
                  </button>
                  {can('post_jobs') && <button onClick={() => deleteJob(job)} aria-label={`Delete ${job.title}`}
                    className="rounded-xl p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-600"><Trash2 size={16} /></button>}
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {/* Applicants */}
      {tab === 'applications' && (
        <div className="space-y-4">
          {!selectedJob ? (
            <div className={`${card} border-dashed p-12 text-center`}>
              <div className="mx-auto w-12 h-12 rounded-xl bg-slate-100 text-slate-500 flex items-center justify-center"><Inbox size={22} /></div>
              <p className="font-medium text-slate-900 mt-4">Choose a job to review its applicants</p>
              <button onClick={() => setTab('my-jobs')} className="mt-4 text-sm font-medium text-emerald-700 hover:text-emerald-800">Go to job postings →</button>
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-3">
                <button onClick={() => setTab('my-jobs')} className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"><ChevronLeft size={16} />All postings</button>
                <h3 className="text-lg font-semibold text-slate-900">{selectedJobInfo?.title || 'Applicants'}</h3>
                <span className="text-sm text-slate-500">{applications.length} applicant{applications.length === 1 ? '' : 's'}</span>
              </div>
              <p className="text-sm text-slate-500">The match score is a screening aid based on the resume and the job description, not a verified qualification or a hiring decision.</p>
              {yesNoLabels.length > 0 && (
                <label className="flex flex-wrap items-center gap-2 text-sm text-slate-600">Filter by answer
                  <select value={answerFilter} onChange={e => setAnswerFilter(e.target.value)} aria-label="Filter applicants by answer"
                    className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700">
                    <option value="">Everyone ({applications.length})</option>
                    {yesNoLabels.flatMap(label => ['yes', 'no'].map(v => (
                      <option key={`${label}||${v}`} value={`${label}||${v}`}>{label} Answered {v === 'yes' ? 'Yes' : 'No'}</option>)))}
                  </select>
                  {answerFilter && <span className="text-slate-500">{shown.length} of {applications.length}</span>}
                </label>)}
              {resumeError && <p role="alert" className="rounded-xl bg-rose-50 border border-rose-200 px-4 py-3 text-sm text-rose-800">{resumeError}</p>}
              {applications.length === 0 ? (
                <div className={`${card} border-dashed p-12 text-center`}>
                  <p className="font-medium text-slate-900">No applicants yet</p>
                  <p className="text-sm text-slate-500 mt-1">New applications appear here as candidates apply.</p>
                </div>
              ) : (
                <div className={`${card} divide-y divide-slate-100`}>
                  {shown.length === 0 && <p className="p-5 text-sm text-slate-500">No applicants gave that answer.</p>}
                  {shown.map(app => {
                    const score = app.ats_score;
                    const bar = score >= 80 ? 'bg-emerald-600' : score >= 60 ? 'bg-amber-500' : 'bg-slate-400';
                    const current = stage(app.status);
                    return (
                      <div key={app.application_id} className="p-5">
                      <div className="grid md:grid-cols-[minmax(0,1fr)_11rem_auto] gap-4 items-center">
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="w-10 h-10 shrink-0 rounded-full bg-emerald-50 text-emerald-800 flex items-center justify-center text-sm font-semibold">{initials(app.applicant_name)}</div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <p className="font-medium text-slate-900">{app.applicant_name}</p>
                              <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${current.cls}`}>{current.label}</span>
                            </div>
                            <p className="text-sm text-slate-500 truncate">{app.applicant_email}</p>
                            <p className="text-xs text-slate-400 mt-0.5">
                              {[app.career_track, app.applicant_country, `Applied ${new Date(app.applied_at).toLocaleDateString()}`].filter(Boolean).join(' · ')}
                            </p>
                          </div>
                        </div>
                        <div>
                          <div className="flex justify-between text-xs text-slate-500 mb-1">
                            <span>Job match</span><span className="font-medium text-slate-700">{score == null ? 'Not assessed' : `${score}%`}</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
                            {score != null && <div className={`h-full rounded-full ${bar}`} style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 md:justify-end flex-wrap">
                          {app.resume_available ? (
                            <button onClick={() => viewResume(app)} disabled={loadingResume !== null}
                              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50">
                              {loadingResume === app.application_id ? <FileText size={15} /> : <Eye size={15} />}
                              {loadingResume === app.application_id ? 'Loading…' : 'Resume'}
                            </button>
                          ) : <span className="text-xs text-slate-400">Applied externally</span>}
                          {can('move_candidates') ? (<>
                            <label className="sr-only" htmlFor={`stage-${app.application_id}`}>Stage for {app.applicant_name}</label>
                            <select id={`stage-${app.application_id}`} value={stageId(app.status)}
                              onChange={e => updateStatus(app.application_id, e.target.value)}
                              className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-emerald-600">
                              {STAGES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
                            </select>
                          </>) : null}
                        </div>
                      </div>
                      {(app.details || app.answers?.length > 0) && (<>
                        <button type="button" onClick={() => setOpenAnswers(o => (o === app.application_id ? null : app.application_id))}
                          aria-expanded={openAnswers === app.application_id}
                          className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-emerald-700 hover:text-emerald-800">
                          <ChevronDown size={15} className={openAnswers === app.application_id ? 'rotate-180' : ''} />
                          {openAnswers === app.application_id ? 'Hide application' : `View application (${app.answers?.length || 0} answer${app.answers?.length === 1 ? '' : 's'})`}
                        </button>
                        {openAnswers === app.application_id && <AnswersPanel app={app} />}
                      </>)}
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
