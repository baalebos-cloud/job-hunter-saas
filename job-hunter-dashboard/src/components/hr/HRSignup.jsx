// =============================================================================
// job-hunter-dashboard/src/components/hr/HRSignup.jsx
// Company email validation + honest pending approval flow
// =============================================================================
import { useState } from 'react';
import axios from 'axios';
import PasswordInput from '../auth/PasswordInput';
import { deviceHeaders } from '../../lib/device';
import { errorText } from '../../lib/session';
import AuthShell, { AsideEyebrow, ErrorNote, Spinner } from '../auth/AuthShell';
import { buttonCls, fieldCls, hintCls, labelCls, linkCls, optional, quietLinkCls } from '../auth/authStyles';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const BLOCKED_DOMAINS = new Set([
  'gmail.com','yahoo.com','yahoo.co.uk','yahoo.co.in','ymail.com',
  'hotmail.com','hotmail.co.uk','outlook.com','outlook.co.uk',
  'live.com','live.co.uk','msn.com','icloud.com','me.com',
  'aol.com','protonmail.com','proton.me','tutanota.com',
  'zoho.com','mail.com','gmx.com','gmx.net','inbox.com',
  'yandex.com','yandex.ru','qq.com','163.com','126.com',
]);


const validateCompanyEmail = (email) => {
  const domain = email.toLowerCase().split('@')[1] || '';
  if (BLOCKED_DOMAINS.has(domain)) {
    return `Use your company email. ${domain} addresses can't be used for employer accounts.`;
  }
  return null;
};

export default function HRSignup() {
  const [form, setForm] = useState({
    name: '', email: '', password: '', company_name: '',
    job_title: '', country: '', linkedin_url: '', company_url: '',
  });
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');
  const [emailError, setEmailError] = useState('');
  const [success, setSuccess]   = useState(false);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleEmailChange = (e) => {
    const val = e.target.value;
    set('email', val);
    if (val.includes('@')) {
      const err = validateCompanyEmail(val);
      setEmailError(err || '');
    } else {
      setEmailError('');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const emailErr = validateCompanyEmail(form.email);
    if (emailErr) { setEmailError(emailErr); return; }
    if (form.password.length < 8) { setError('Password must be at least 8 characters.'); return; }
    if (!form.company_name.trim()) { setError('Company name is required.'); return; }

    setLoading(true); setError('');
    try {
      await axios.post(`${API_BASE_URL}/hr-auth/signup`, {
        full_name:    form.name,
        email:        form.email,
        password:     form.password,
        company_name: form.company_name,
        job_title:    form.job_title || 'HR Manager',
        country:      form.country.trim(),
        linkedin_url: form.linkedin_url || '',
        company_url:  form.company_url || '',
      }, { headers: deviceHeaders() });
      setSuccess(true);
    } catch (err) {
      setError(errorText(err, 'Registration failed. Please try again.'));
    } finally { setLoading(false); }
  };

  const steps = [
    ['Confirm your email', 'We send a link to your work address.'],
    ['We review your company', 'A person checks the company and your role. You’ll get an email with the decision.'],
    ['Post jobs and review applicants', 'Candidates apply with resumes tailored to your job description.'],
  ];
  const aside = (
    <>
      <AsideEyebrow>What happens next</AsideEyebrow>
      <ol className="mt-6 space-y-7">
        {steps.map(([t, d], i) => (
          <li key={t} className="flex gap-4">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#0b1324] text-[14px] font-semibold text-white">{i + 1}</span>
            <div><p className="text-[16px] font-semibold">{t}</p><p className="mt-1 text-[14.5px] text-slate-600">{d}</p></div>
          </li>))}
      </ol>
      <p className="mt-10 border-t border-[#e2ddd2] pt-5 text-[13.5px] text-slate-600">Questions? <a href="mailto:support@baalebo.xyz" className={quietLinkCls}>support@baalebo.xyz</a></p>
    </>
  );

  if (success) return (
    <AuthShell employer wide aside={aside} title="Check your inbox">
      <div className="rounded-md border border-[#e2ddd2] bg-white p-6 text-[15px]" role="status">
        <p className="leading-relaxed text-slate-600">We sent a verification link to <strong className="font-semibold text-[#0b1324] [overflow-wrap:anywhere]">{form.email}</strong>. Open it to confirm your email address. After that, we review your company and email you the decision.</p>
        <a href="/hr/login" className={`${buttonCls} mt-5 block text-center`}>Go to employer sign in</a>
      </div>
    </AuthShell>
  );

  return (
    <AuthShell employer wide aside={aside} title="Apply for an employer account"
      intro="We check every company before it can post jobs, so candidates know who they are applying to.">
      {error && <ErrorNote>{error}</ErrorNote>}
      <form onSubmit={handleSubmit} className="space-y-5">
        <p className="text-[12.5px] font-semibold uppercase tracking-[.12em] text-slate-500">About you</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelCls} htmlFor="hr-name">Full name</label>
            <input id="hr-name" type="text" required autoComplete="name" placeholder="Sarah Johnson" className={fieldCls}
              value={form.name} onChange={e => set('name', e.target.value)} />
          </div>
          <div>
            <label className={labelCls} htmlFor="hr-title">Job title {optional}</label>
            <input id="hr-title" type="text" autoComplete="organization-title" placeholder="HR Manager" className={fieldCls}
              value={form.job_title} onChange={e => set('job_title', e.target.value)} />
          </div>
        </div>
        <div>
          <label className={labelCls} htmlFor="hr-email">Work email</label>
          <input id="hr-email" type="email" required autoComplete="email" placeholder="you@yourcompany.com"
            className={`${fieldCls} ${emailError ? 'border-rose-400' : ''}`} aria-invalid={!!emailError}
            value={form.email} onChange={handleEmailChange} />
          {emailError ? <p className="mt-1.5 text-[12.5px] font-medium text-rose-700">{emailError}</p>
            : <p className={hintCls}>Must be on your company’s domain. Gmail, Yahoo, Outlook and similar addresses can’t be used.</p>}
        </div>
        <div>
          <label className={labelCls} htmlFor="hr-password">Password</label>
          <PasswordInput id="hr-password" autoComplete="new-password" required minLength={8} placeholder="At least 8 characters" className={fieldCls}
            value={form.password} onChange={e => set('password', e.target.value)} />
        </div>
        <div>
          <label className={labelCls} htmlFor="hr-linkedin">Your LinkedIn {optional}</label>
          <input id="hr-linkedin" type="url" placeholder="https://linkedin.com/in/…" className={fieldCls}
            value={form.linkedin_url} onChange={e => set('linkedin_url', e.target.value)} />
        </div>

        <p className="border-t border-[#e7e3da] pt-6 text-[12.5px] font-semibold uppercase tracking-[.12em] text-slate-500">About the company</p>
        <div>
          <label className={labelCls} htmlFor="hr-company">Company name</label>
          <input id="hr-company" type="text" required autoComplete="organization" placeholder="Acme Technologies Ltd" className={fieldCls}
            value={form.company_name} onChange={e => set('company_name', e.target.value)} />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelCls} htmlFor="hr-website">Website {optional}</label>
            <input id="hr-website" type="url" placeholder="https://yourcompany.com" className={fieldCls}
              value={form.company_url} onChange={e => set('company_url', e.target.value)} />
          </div>
          <div>
            <label className={labelCls} htmlFor="hr-country">Country {optional}</label>
            <input id="hr-country" type="text" autoComplete="country-name" placeholder="Nigeria" className={fieldCls}
              value={form.country} onChange={e => set('country', e.target.value)} />
          </div>
        </div>
        <button type="submit" disabled={loading || !!emailError} className={buttonCls}>{loading ? <><Spinner />Submitting…</> : 'Submit application'}</button>
        <p className="text-[12.5px] text-slate-500">By applying you agree to the <a href="/legal/terms" className="underline">Terms</a> and <a href="/legal/privacy" className="underline">Privacy Policy</a>.</p>
      </form>
      <p className="mt-6 text-[14.5px] text-slate-600">Already approved? <a href="/hr/login" className={linkCls}>Sign in</a></p>
      <div className="mt-10 border-t border-[#e7e3da] pt-5 text-[13.5px] text-slate-600">
        Looking for a job? <a href="/signup" className={quietLinkCls}>Candidate sign up</a>
      </div>
    </AuthShell>
  );
}
