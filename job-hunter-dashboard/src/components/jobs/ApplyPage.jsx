/* eslint-disable react/prop-types -- the project does not use the prop-types package */
import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { ArrowLeft, Building2, CheckCircle2, ExternalLink, FileText, Loader2, MapPin, Send, Sparkles } from 'lucide-react';
import { errorText } from '../../lib/session';
import { COUNTRIES } from '../../lib/signupOptions';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const auth = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });
const card = 'bg-white rounded-2xl border border-slate-200';
const input = 'w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 outline-none focus:border-emerald-600 focus:ring-4 focus:ring-emerald-600/10 disabled:bg-slate-50 disabled:text-slate-500';
const LIMITS = { short_text: 300, long_text: 5000, url: 500 };
const PHONE = /^\+?[0-9 ()\-.]{6,30}$/;
const empty = (v) => v === undefined || v === null || v === '' || (Array.isArray(v) && v.length === 0);
const shown = (v) => (empty(v) ? 'Not provided' : Array.isArray(v) ? v.join(', ') : v === 'yes' ? 'Yes' : v === 'no' ? 'No' : String(v));

// Same rules as the server (backend/app/services/application_form.py), checked here first for quick feedback.
function check(fields, details, answers, consent) {
  const errors = {};
  if ((details.full_name || '').trim().length < 2) errors.full_name = 'Enter your full name.';
  if (!PHONE.test((details.phone || '').trim())) errors.phone = 'Enter a phone number, e.g. +234 801 555 0101.';
  if ((details.country || '').trim().length < 2) errors.country = 'Enter the country you live in.';
  for (const f of fields) {
    const v = answers[f.id];
    if (empty(v)) { if (f.required) errors[f.id] = 'This answer is required.'; continue; }
    if (LIMITS[f.type] && String(v).length > LIMITS[f.type]) errors[f.id] = `Keep this under ${LIMITS[f.type].toLocaleString()} characters.`;
    if (f.type === 'url' && !/^https:\/\/\S+$/.test(String(v).trim())) errors[f.id] = 'Enter a full link starting with https://';
    if (f.type === 'number' && (Number.isNaN(Number(v)) || Number(v) < 0 || (f.id === 'std_experience_years' && Number(v) > 60))) {
      errors[f.id] = f.id === 'std_experience_years' ? 'Enter a number between 0 and 60.' : 'Enter a number of 0 or more.';
    }
  }
  if (!consent) errors.consent = 'Agree to share these details with the employer to apply.';
  return errors;
}

function Label({ htmlFor, children, required, help }) {
  return (
    <div className="mb-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-slate-800">{children}{required ? <span className="text-rose-600"> *</span> : <span className="font-normal text-slate-400"> (optional)</span>}</label>
      {help && <p className="text-xs text-slate-500 mt-0.5">{help}</p>}
    </div>
  );
}

function Err({ id, text }) {
  return text ? <p id={id} role="alert" className="mt-1.5 text-sm text-rose-700">{text}</p> : null;
}

function Question({ field, value, onChange, error }) {
  const id = `field-${field.id}`;
  const described = error ? `${id}-error` : undefined;
  const common = { id, 'aria-invalid': !!error, 'aria-describedby': described };
  let control;
  if (field.type === 'long_text') {
    control = <><textarea {...common} rows={field.id === 'std_cover_letter' ? 7 : 4} className={`${input} resize-y`} value={value || ''} maxLength={5000} onChange={e => onChange(e.target.value)} />
      <p className="mt-1 text-xs text-slate-400 text-right">{(value || '').length.toLocaleString()}/5,000</p></>;
  } else if (field.type === 'yes_no' || field.type === 'single_choice') {
    const options = field.type === 'yes_no' ? [['yes', 'Yes'], ['no', 'No']] : field.options.map(o => [o, o]);
    control = (
      <div role="radiogroup" aria-labelledby={`${id}-label`} aria-describedby={described} className="flex flex-wrap gap-2">
        {options.map(([v, text]) => (
          <label key={v} className={`inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-sm cursor-pointer ${value === v ? 'border-emerald-600 bg-emerald-50 text-emerald-900' : 'border-slate-300 text-slate-700 hover:border-slate-400'}`}>
            <input type="radio" name={id} value={v} checked={value === v} onChange={() => onChange(v)} className="accent-emerald-600" />{text}
          </label>))}
      </div>);
  } else if (field.type === 'multi_choice') {
    const picked = Array.isArray(value) ? value : [];
    control = (
      <div role="group" aria-labelledby={`${id}-label`} aria-describedby={described} className="flex flex-wrap gap-2">
        {field.options.map(o => (
          <label key={o} className={`inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-sm cursor-pointer ${picked.includes(o) ? 'border-emerald-600 bg-emerald-50 text-emerald-900' : 'border-slate-300 text-slate-700 hover:border-slate-400'}`}>
            <input type="checkbox" checked={picked.includes(o)} className="accent-emerald-600"
              onChange={() => onChange(picked.includes(o) ? picked.filter(x => x !== o) : [...picked, o])} />{o}
          </label>))}
      </div>);
  } else {
    const type = { number: 'number', date: 'date', url: 'url' }[field.type] || 'text';
    control = <input {...common} type={type} className={input} value={value ?? ''} onChange={e => onChange(e.target.value)}
      min={type === 'number' ? 0 : undefined} step={type === 'number' ? 'any' : undefined} maxLength={LIMITS[field.type]}
      placeholder={field.type === 'url' ? 'https://' : undefined} />;
  }
  return (
    <div>
      <span id={`${id}-label`} className="sr-only">{field.label}</span>
      <Label htmlFor={id} required={field.required} help={field.help}>{field.label}</Label>
      {control}
      <Err id={described} text={error} />
    </div>
  );
}

export default function ApplyPage() {
  const { jobId } = useParams();
  const [params] = useSearchParams();
  const [data, setData] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [details, setDetails] = useState({ full_name: '', phone: '', country: '' });
  const [answers, setAnswers] = useState({});
  const [resume, setResume] = useState('');
  const [consent, setConsent] = useState(false);
  const [saveProfile, setSaveProfile] = useState(true);
  const [errors, setErrors] = useState({});
  const [step, setStep] = useState('form');   // form | review | done
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState('');

  useEffect(() => {
    axios.get(`${API}/jobs/${jobId}/application-form`, { headers: auth() })
      .then(({ data: d }) => {
        setData(d);
        setDetails({ full_name: d.profile.full_name, phone: d.profile.phone, country: d.profile.country });
        setAnswers(d.profile.answers || {});
        const wanted = params.get('resume');
        setResume(d.resumes.some(r => r.task_id === wanted) ? wanted : d.resumes[0]?.task_id || '');
      })
      .catch(err => setLoadError(errorText(err, 'This job could not be loaded.')));
  }, [jobId, params]);

  const fields = data?.fields || [];
  const selectedResume = useMemo(() => data?.resumes.find(r => r.task_id === resume), [data, resume]);
  const setAnswer = (id, v) => { setAnswers(a => ({ ...a, [id]: v })); setErrors(e => ({ ...e, [id]: undefined })); };
  const setDetail = (k, v) => { setDetails(d => ({ ...d, [k]: v })); setErrors(e => ({ ...e, [k]: undefined })); };

  const review = (e) => {
    e.preventDefault();
    const found = check(fields, details, answers, consent);
    setErrors(found); setSendError('');
    const first = Object.keys(found)[0];
    if (first) { document.getElementById(first === 'consent' ? 'apply-consent' : ['full_name', 'phone', 'country'].includes(first) ? `apply-${first}` : `field-${first}`)?.focus(); return; }
    setStep('review'); window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const submit = async () => {
    setSending(true); setSendError('');
    const clean = Object.fromEntries(Object.entries(answers).filter(([id, v]) => fields.some(f => f.id === id) && !empty(v)));
    try {
      await axios.post(`${API}/jobs/${jobId}/apply`, { resume_id: resume, details, answers: clean, consent, save_to_profile: saveProfile }, { headers: auth() });
      setStep('done'); window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      const fieldErrors = err?.response?.data?.detail?.fields;
      if (fieldErrors) { setErrors(fieldErrors); setStep('form'); }
      setSendError(errorText(err, 'Your application could not be sent. Please retry.'));
    } finally { setSending(false); }
  };

  if (loadError) return <div className="p-6 md:p-9"><p role="alert" className="rounded-xl bg-rose-50 p-4 text-sm text-rose-700">{loadError}</p></div>;
  if (!data) return <div className="py-24 flex justify-center"><Loader2 className="animate-spin text-emerald-600" /></div>;
  const { job } = data;
  const header = (
    <div className="flex items-start gap-4">
      <div className="w-12 h-12 shrink-0 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center"><Building2 size={22} /></div>
      <div className="min-w-0">
        <p className="text-sm text-slate-500">Apply on Baalebos</p>
        <h1 className="text-xl font-semibold text-slate-900">{job.title}</h1>
        <p className="text-sm text-slate-600 flex flex-wrap gap-x-3">{job.company}{job.location && <span className="inline-flex items-center gap-1"><MapPin size={13} />{job.location}</span>}</p>
      </div>
    </div>);
  const back = <Link to="/jobs" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"><ArrowLeft size={15} />Jobs</Link>;

  if (!data.internal) return (
    <div className="p-6 md:p-9 max-w-3xl space-y-4">{back}
      <section className={`${card} p-6 space-y-4`}>{header}
        <p className="text-sm text-slate-600">{job.company} takes applications on its own site. Track it from the job page, then complete their form.</p>
        {job.url && <a href={job.url} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white">Open the employer&apos;s form <ExternalLink size={15} /></a>}
      </section>
    </div>);

  if (step === 'done' || data.already_applied) return (
    <div className="p-6 md:p-9 max-w-3xl space-y-4">{back}
      <section className={`${card} p-8 text-center`} role="status">
        <CheckCircle2 size={40} className="mx-auto text-emerald-600" />
        <h1 className="mt-3 text-xl font-semibold text-slate-900">{step === 'done' ? 'Application sent' : 'You have already applied'}</h1>
        <p className="mt-2 text-sm text-slate-600">{step === 'done'
          ? `${job.company} received your application for ${job.title} on Baalebos. We emailed you a copy of what you sent.`
          : `Your application for ${job.title} at ${job.company} was already sent. You can follow its status in Applications.`}</p>
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          <Link to="/applications" className="rounded-xl bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-800">View my applications</Link>
          <Link to="/jobs" className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50">Find more jobs</Link>
        </div>
      </section>
    </div>);

  if (!data.resumes.length) return (
    <div className="p-6 md:p-9 max-w-3xl space-y-4">{back}
      <section className={`${card} p-6 space-y-4`}>{header}
        <p className="text-sm text-slate-600">{job.company} receives applications with a resume tailored for this job. Tailor yours first; it takes a minute or two, and you come straight back here.</p>
        <Link to={`/optimizer?job=${job.id}`} className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-700"><Sparkles size={16} />Tailor my resume to this job</Link>
      </section>
    </div>);

  if (step === 'review') {
    const rows = [['Full name', details.full_name], ['Email', data.profile.email], ['Phone', details.phone], ['Country', details.country],
      ['Resume', selectedResume ? `${selectedResume.job_title}${selectedResume.score != null ? ` · match ${Math.round(selectedResume.score)}%` : ''}` : ''],
      ...fields.map(f => [f.label, answers[f.id]])];
    return (
      <div className="p-6 md:p-9 max-w-3xl space-y-4">
        <button type="button" onClick={() => setStep('form')} className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"><ArrowLeft size={15} />Edit answers</button>
        <section className={`${card} p-6 space-y-5`}>{header}
          <div>
            <h2 className="font-semibold text-slate-900">Check what {job.company} will receive</h2>
            <dl className="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200 text-sm">
              {rows.map(([label, value]) => (
                <div key={label} className="grid sm:grid-cols-[14rem_minmax(0,1fr)] gap-1 sm:gap-4 px-4 py-2.5">
                  <dt className="text-slate-500">{label}</dt>
                  <dd className={`break-words whitespace-pre-line ${empty(value) ? 'text-slate-400' : 'text-slate-900'}`}>{shown(value)}</dd>
                </div>))}
            </dl>
          </div>
          {sendError && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{sendError}</p>}
          <div className="flex flex-wrap justify-end gap-2">
            <button type="button" onClick={() => setStep('form')} className="rounded-xl px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-100">Edit answers</button>
            <button type="button" onClick={submit} disabled={sending}
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-60">
              {sending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}{sending ? 'Sending…' : 'Submit application'}</button>
          </div>
        </section>
      </div>);
  }

  return (
    <div className="p-6 md:p-9 max-w-3xl space-y-4">{back}
      <form onSubmit={review} noValidate className={`${card} divide-y divide-slate-100`}>
        <div className="p-6">{header}</div>

        <fieldset className="p-6 space-y-4">
          <legend className="font-semibold text-slate-900">1. Your details</legend>
          <p className="text-sm text-slate-500 -mt-2">Filled in from your profile. Change anything that is out of date.</p>
          <div className="grid sm:grid-cols-2 gap-4">
            <div><Label htmlFor="apply-full_name" required>Full name</Label>
              <input id="apply-full_name" className={input} value={details.full_name} maxLength={120} autoComplete="name" aria-invalid={!!errors.full_name} onChange={e => setDetail('full_name', e.target.value)} />
              <Err text={errors.full_name} /></div>
            <div><Label htmlFor="apply-email" required>Email</Label>
              <input id="apply-email" className={input} value={data.profile.email} disabled />
              <p className="mt-1 text-xs text-slate-500">Your account email. The employer replies here.</p></div>
            <div><Label htmlFor="apply-phone" required>Phone</Label>
              <input id="apply-phone" type="tel" className={input} value={details.phone} maxLength={30} autoComplete="tel" placeholder="+234 801 555 0101" aria-invalid={!!errors.phone} onChange={e => setDetail('phone', e.target.value)} />
              <Err text={errors.phone} /></div>
            <div><Label htmlFor="apply-country" required>Country</Label>
              <input id="apply-country" list="apply-country-options" className={input} value={details.country} maxLength={60} autoComplete="country-name" aria-invalid={!!errors.country} onChange={e => setDetail('country', e.target.value)} />
              <datalist id="apply-country-options">{COUNTRIES.map(c => <option key={c} value={c} />)}</datalist>
              <Err text={errors.country} /></div>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" className="accent-emerald-600" checked={saveProfile} onChange={e => setSaveProfile(e.target.checked)} />Save these details to my profile</label>
        </fieldset>

        <fieldset className="p-6 space-y-3">
          <legend className="font-semibold text-slate-900">2. Resume</legend>
          <div className="space-y-2">
            {data.resumes.map(r => (
              <label key={r.task_id} className={`flex items-center gap-3 rounded-xl border p-3.5 cursor-pointer ${resume === r.task_id ? 'border-emerald-600 bg-emerald-50/60' : 'border-slate-200 hover:border-slate-300'}`}>
                <input type="radio" name="resume" checked={resume === r.task_id} onChange={() => setResume(r.task_id)} className="accent-emerald-600" />
                <FileText size={18} className="text-slate-400 shrink-0" />
                <span className="text-sm"><span className="font-medium text-slate-900">{r.job_title}</span>
                  <span className="block text-xs text-slate-500">Tailored for this job{r.score != null ? ` · match ${Math.round(r.score)}%` : ''}{r.created_at ? ` · ${new Date(r.created_at).toLocaleDateString()}` : ''}</span></span>
              </label>))}
          </div>
          <Link to={`/optimizer?job=${job.id}`} className="inline-flex items-center gap-1.5 text-sm font-medium text-emerald-700 hover:text-emerald-800"><Sparkles size={14} />Tailor a new one for this job</Link>
        </fieldset>

        {fields.length > 0 && (
          <fieldset className="p-6 space-y-5">
            <legend className="font-semibold text-slate-900">3. Questions from {job.company}</legend>
            {fields.map(f => <Question key={f.id} field={f} value={answers[f.id]} error={errors[f.id]} onChange={v => setAnswer(f.id, v)} />)}
          </fieldset>)}

        <div className="p-6 space-y-4 bg-slate-50/60 rounded-b-2xl">
          <label className="flex items-start gap-2 text-sm text-slate-700">
            <input id="apply-consent" type="checkbox" className="mt-0.5 accent-emerald-600" checked={consent} aria-invalid={!!errors.consent}
              onChange={e => { setConsent(e.target.checked); setErrors(x => ({ ...x, consent: undefined })); }} />
            <span>I agree to share these details and my resume with {job.company} for this role.<span className="text-rose-600"> *</span></span>
          </label>
          <Err text={errors.consent} />
          {sendError && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{sendError}</p>}
          {Object.values(errors).some(Boolean) && <p className="text-sm text-rose-700">Some answers need attention. They are marked above.</p>}
          <div className="flex justify-end">
            <button type="submit" className="rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-800">Review application</button>
          </div>
        </div>
      </form>
    </div>
  );
}
