/* eslint-disable react/prop-types -- the project does not use the prop-types package */
// Accepting an invitation to a company's team on Baalebos (/hr/join?token=...).
// The single-use link proves the email address, so a new teammate only chooses a
// password. Someone who already has an employer account confirms its password.
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import AuthShell, { AsideEyebrow, ErrorNote, Spinner } from '../auth/AuthShell';
import { buttonCls, fieldCls, hintCls, labelCls, quietLinkCls } from '../auth/authStyles';
import PasswordInput from '../auth/PasswordInput';
import { errorText } from '../../lib/session';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const CAN_DO = {
  admin: ['See every job and applicant', 'Post and edit jobs', 'Invite teammates and set their roles', 'Move applicants through the pipeline'],
  recruiter: ['See every job and its applicants', 'Post and edit jobs', 'Review resumes, answers and job match', 'Move applicants through the pipeline'],
  hiring_manager: ['See the jobs you’re on the hiring team for', 'Review resumes, answers and job match', 'Move applicants through the pipeline'],
  interviewer: ['See the jobs you’re on the hiring team for', 'Review resumes, answers and job match'],
};

function Aside({ invite }) {
  const role = invite?.role_label?.toLowerCase();
  return (
    <>
      <AsideEyebrow dark>{role ? `As ${/^[aeiou]/.test(role) ? 'an' : 'a'} ${role}` : 'Employer portal'}</AsideEyebrow>
      <ul className="mt-6 space-y-4 text-[16px] leading-snug text-slate-200">
        {(CAN_DO[invite?.role] || CAN_DO.recruiter).map(line => <li key={line}>{line}</li>)}
      </ul>
      <p className="mt-10 text-[14px] text-slate-400">Your access ends if an admin removes you from the team.</p>
    </>
  );
}

export default function HRJoin() {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const [invite, setInvite] = useState(null);
  const [loadError, setLoadError] = useState(token ? '' : 'This invitation link is incomplete. Open the link from your email again.');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [joined, setJoined] = useState(null);

  useEffect(() => {
    if (!token) return;
    axios.get(`${API}/hr/team/invite`, { params: { token } })
      .then(r => setInvite(r.data))
      .catch(err => setLoadError(errorText(err, 'This invitation could not be opened. Please try again.')));
  }, [token]);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true); setError('');
    try {
      const r = await axios.post(`${API}/hr/team/accept`, { token, password, full_name: invite.has_account ? null : name.trim() });
      setJoined(r.data);
    } catch (err) {
      setError(errorText(err, 'You could not be added to the team. Please try again.'));
    } finally { setSubmitting(false); }
  };

  if (joined) return (
    <AuthShell employer title={`You’re on ${joined.company || 'the team'}`} intro="Sign in to the employer portal with your work email to get started." aside={<Aside invite={invite} />} asideTone="ink">
      <Link to="/hr/login" className={`${buttonCls} block text-center`}>Sign in to the employer portal</Link>
    </AuthShell>
  );

  if (loadError || !invite) return (
    <AuthShell employer title={loadError ? 'Invitation unavailable' : 'Opening your invitation…'} aside={<Aside invite={null} />} asideTone="ink">
      {loadError ? (<>
        <ErrorNote>{loadError}</ErrorNote>
        <p className="text-[14.5px] text-slate-600">Already on the team? <Link to="/hr/login" className={quietLinkCls}>Sign in</Link></p>
      </>) : <p className="text-[15px] text-slate-500"><Spinner />Checking the link…</p>}
    </AuthShell>
  );

  const intro = <>You’ve been invited as {/^[aeiou]/i.test(invite.role_label) ? 'an' : 'a'} <strong className="text-[#0b1324]">{invite.role_label}</strong>.</>;
  return (
    <AuthShell employer title={`Join ${invite.company || 'your team'}`} intro={intro} aside={<Aside invite={invite} />} asideTone="ink">
      {invite.candidate_account ? (
        <ErrorNote>{invite.email} is used by a candidate account, which can’t join a company. Ask your admin to invite your work email instead.</ErrorNote>
      ) : (
        <form onSubmit={submit} className="space-y-5" noValidate>
          {error && <ErrorNote>{error}</ErrorNote>}
          <div>
            <label htmlFor="join-email" className={labelCls}>Work email</label>
            <input id="join-email" className={fieldCls} style={{ backgroundColor: '#f3f1ec', color: '#475569' }} value={invite.email} readOnly />
          </div>
          {!invite.has_account && (
            <div>
              <label htmlFor="join-name" className={labelCls}>Full name</label>
              <input id="join-name" className={fieldCls} value={name} onChange={e => setName(e.target.value)} autoComplete="name" required maxLength={120} />
            </div>
          )}
          <div>
            <label htmlFor="join-password" className={labelCls}>{invite.has_account ? 'Password for your employer account' : 'Create a password'}</label>
            <PasswordInput id="join-password" className={fieldCls} value={password} onChange={e => setPassword(e.target.value)}
              autoComplete={invite.has_account ? 'current-password' : 'new-password'} required />
            {!invite.has_account && <p className={hintCls}>At least 8 characters.</p>}
          </div>
          <button type="submit" disabled={submitting || !password || (!invite.has_account && !name.trim())} className={buttonCls}>
            {submitting && <Spinner />}Join {invite.company || 'the team'}
          </button>
          {invite.has_account && (
            <p className="text-[13.5px] text-slate-500">Forgot it? <Link to="/forgot-password" className={quietLinkCls}>Reset your password</Link>, then open this link again.</p>
          )}
        </form>
      )}
    </AuthShell>
  );
}
