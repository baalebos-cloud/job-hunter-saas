// =============================================================================
// job-hunter-dashboard/src/components/auth/Signup.jsx
// Wired with referral tracking — captures ?ref= from URL and calls /referral/track
// =============================================================================
import { useState, useEffect } from 'react';
import axios from 'axios';
import { clearFirstTouch, firstTouch } from '../../lib/attribution';
import { deviceHeaders } from '../../lib/device';
import { errorText } from '../../lib/session';
import VerifyEmailNotice from './VerifyEmailNotice';
import PasswordInput from './PasswordInput';
import ChipInput from './ChipInput';
import { COUNTRIES, TECH_TRACKS, cleanTrack, matchCountry } from '../../lib/signupOptions';
import AuthShell, { AsideEyebrow, ErrorNote, Spinner } from './AuthShell';
import { buttonCls, fieldCls, hintCls, labelCls, linkCls, optional, quietLinkCls } from './authStyles';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';


export default function Signup() {
  const [form, setForm]     = useState({ name: '', email: '', password: '', country: '' });
  const [tracks, setTracks] = useState([]);              // up to 3, first = main track
  const [workTypes, setWorkTypes] = useState([]);        // remote | hybrid | onsite
  const [workCountries, setWorkCountries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState('');
  const [refCode, setRefCode] = useState('');
  const [sentTo, setSentTo] = useState('');
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  // ── Capture referral code from URL or localStorage ────────────────────────
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ref    = params.get('ref') || localStorage.getItem('ref_code') || '';
    if (ref) setRefCode(ref);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const pending = document.getElementById('signup-track')?.value?.trim();
    const chosen = pending && tracks.length < 3 && !tracks.some(t => t.toLowerCase() === cleanTrack(pending).toLowerCase())
      ? [...tracks, cleanTrack(pending)] : tracks;
    if (!chosen.length) { setError('Type or choose at least one career track.'); return; }
    const track = chosen[0];
    const country = form.country.trim() ? matchCountry(form.country) : null;
    if (form.country.trim() && !country) { setError('Choose your country from the list (start typing to see suggestions).'); return; }
    setLoading(true);

    try {
      // The account can sign in only after its email address is verified;
      // the referral is recorded server-side at signup.
      const res = await axios.post(`${API_BASE_URL}/auth/signup`, {
        full_name:    form.name,
        email:        form.email,
        password:     form.password,
        career_track: track,
        career_tracks: chosen,
        work_types:   workTypes.length ? workTypes : null,
        work_countries: workCountries.length ? workCountries : null,
        country:      country,
        ref_code:     refCode || null,
        ...firstTouch(),
      }, { headers: deviceHeaders() });
      if (refCode) localStorage.removeItem('ref_code');
      clearFirstTouch();
      setSentTo(res.data?.email || form.email);

    } catch (err) {
      setError(errorText(err, 'Signup failed. Please try again.'));
    } finally {
      setLoading(false);
    }
  };

  const aside = (
    <>
      <AsideEyebrow>On the free plan</AsideEyebrow>
      <ul className="mt-6 space-y-6">
        {[['3 tailored resumes a month', 'Rewritten around each job description, as PDF and Word.'],
          ['Nothing invented', 'Every line is checked against your own resume. Anything it can’t confirm is left out.'],
          ['See your match before you apply', 'Which requirements your resume covers, and which it doesn’t.'],
          ['Job board and alerts', 'Tech jobs, with daily or weekly email alerts for your tracks.']].map(([t, d]) => (
          <li key={t}><p className="text-[16px] font-semibold">{t}</p><p className="mt-1 text-[14.5px] text-slate-600">{d}</p></li>))}
      </ul>
      <p className="mt-10 border-t border-[#e2ddd2] pt-5 text-[13.5px] text-slate-600">No card needed. <a href="/pricing" className={quietLinkCls}>Compare plans</a></p>
    </>
  );
  const chipField = `${fieldCls} cursor-text py-2.5`;

  return (
    <AuthShell wide title={sentTo ? 'Check your inbox' : 'Create your account'} aside={aside}
      intro={sentTo ? null : 'Free to start. Tell us what you’re looking for and we’ll tailor your resume to each job you apply to.'}>
      {error && <ErrorNote>{error}</ErrorNote>}
      {sentTo ? <VerifyEmailNotice email={sentTo} title="Verify your email to finish" /> : (
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className={labelCls} htmlFor="signup-name">Full name</label>
            <input id="signup-name" type="text" required autoComplete="name" placeholder="Oluwadare Jayeola" className={fieldCls}
              value={form.name} onChange={e => set('name', e.target.value)} />
          </div>
          <div>
            <label className={labelCls} htmlFor="signup-email">Email</label>
            <input id="signup-email" type="email" required autoComplete="email" placeholder="you@example.com" className={fieldCls}
              value={form.email} onChange={e => set('email', e.target.value)} />
            <p className={hintCls}>We’ll send a link to confirm it. Temporary email addresses can’t be used.</p>
          </div>
          <div>
            <label className={labelCls} htmlFor="signup-password">Password</label>
            <PasswordInput id="signup-password" required minLength={8} autoComplete="new-password" placeholder="At least 8 characters"
              className={fieldCls} value={form.password} onChange={e => set('password', e.target.value)} />
          </div>

          <div className="border-t border-[#e7e3da] pt-6">
            <p className="text-[12.5px] font-semibold uppercase tracking-[.12em] text-slate-500">The work you want</p>
            <p className="mt-1 text-[13.5px] text-slate-600">Used to match jobs and alerts. You can change it later in your profile.</p>
          </div>
          <div>
            <label className={labelCls} htmlFor="signup-track">Career tracks <span className="font-normal text-slate-500">(up to 3)</span></label>
            <ChipInput id="signup-track" values={tracks} onChange={setTracks} suggestions={TECH_TRACKS} max={3}
              placeholder="Type or pick, e.g. DevOps Engineer" normalize={v => cleanTrack(v) || null}
              className={chipField} chipClass="bg-[#0b1324] text-white" />
            <p className={hintCls}>Pick from the list or type your own. The first one is your main track.</p>
          </div>
          <div>
            <span className={labelCls} id="signup-work-label">Work type</span>
            <div role="group" aria-labelledby="signup-work-label" className="grid grid-cols-3 gap-2">
              {[['remote', 'Remote'], ['hybrid', 'Hybrid'], ['onsite', 'On-site']].map(([id, label]) => {
                const on = workTypes.includes(id);
                return <button key={id} type="button" aria-pressed={on} onClick={() => setWorkTypes(w => (on ? w.filter(x => x !== id) : [...w, id]))}
                  className={`rounded-[10px] border py-2.5 text-[14.5px] font-semibold transition ${on ? 'border-[#0b1324] bg-[#0b1324] text-white' : 'border-[#d6d3cc] bg-white text-slate-700 hover:border-slate-400'}`}>
                  {label}</button>;
              })}
            </div>
            <p className={hintCls}>Choose any that suit you.</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className={labelCls} htmlFor="signup-country">Country you live in</label>
              <input id="signup-country" list="signup-country-options" maxLength={60} autoComplete="country-name"
                placeholder="Start typing, e.g. Nigeria" className={fieldCls}
                value={form.country} onChange={e => set('country', e.target.value)} />
              <datalist id="signup-country-options">
                {COUNTRIES.map(c => <option key={c} value={c} />)}
              </datalist>
            </div>
            <div>
              <label className={labelCls} htmlFor="signup-work-countries">Also open to {optional}</label>
              <ChipInput id="signup-work-countries" values={workCountries} onChange={setWorkCountries} suggestions={COUNTRIES} max={5}
                placeholder="Other countries" normalize={v => matchCountry(v)}
                onInvalid={(raw, why) => setError(why === 'max' ? 'Choose up to 5 countries.' : `Choose "${raw}" from the country list.`)}
                className={chipField} chipClass="bg-slate-100 text-slate-800" />
            </div>
          </div>
          <button type="submit" disabled={loading} className={buttonCls}>{loading ? <><Spinner />Creating your account…</> : 'Create account'}</button>
          <p className="text-[12.5px] text-slate-500">By creating an account you agree to the <a href="/legal/terms" className="underline">Terms</a> and <a href="/legal/privacy" className="underline">Privacy Policy</a>.</p>
        </form>)}
      <p className="mt-6 text-[14.5px] text-slate-600">Already have an account? <a href="/login" className={linkCls}>Sign in</a></p>
      <div className="mt-10 border-t border-[#e7e3da] pt-5 text-[13.5px] text-slate-600">
        Hiring? <a href="/hr/signup" className={quietLinkCls}>Apply for an employer account</a>
      </div>
    </AuthShell>
  );
}
