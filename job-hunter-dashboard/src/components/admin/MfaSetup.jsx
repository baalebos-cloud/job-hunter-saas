import { useEffect, useState } from 'react';
import QRCode from 'qrcode';
import { Copy, KeyRound, ShieldCheck } from 'lucide-react';
import { startSession } from '../../lib/session';
import { adminGet, adminPost, message } from './adminApi';
import { Banner, Button, card } from './ui';

function RecoveryCodes({ codes, onDone }) {
  const [copied, setCopied] = useState(false);
  const text = codes.join('\n');
  return (
    <div>
      <Banner tone="amber">
        Save these recovery codes somewhere safe (a password manager). Each code signs you in once if you lose your phone.
        They will not be shown again.
      </Banner>
      <ul className="mt-4 grid grid-cols-2 gap-2 font-mono text-sm">
        {codes.map(c => <li key={c} className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-center">{c}</li>)}
      </ul>
      <div className="mt-4 flex gap-2">
        <Button icon={Copy} onClick={async () => { try { await navigator.clipboard.writeText(text); setCopied(true); } catch { setCopied(false); } }}>
          {copied ? 'Copied' : 'Copy codes'}
        </Button>
        <Button variant="primary" onClick={onDone}>I have saved them</Button>
      </div>
    </div>
  );
}

// Enrol an authenticator app: QR code -> first code -> recovery codes.
export default function MfaSetup({ required, onEnabled }) {
  const [status, setStatus] = useState(null);
  const [setup, setSetup] = useState(null);
  const [qr, setQr] = useState('');
  const [code, setCode] = useState('');
  const [codes, setCodes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [disabling, setDisabling] = useState(false);

  const refresh = () => adminGet('/auth/2fa').then(setStatus).catch(err => setError(message(err, 'Could not load two-step verification status.')));
  useEffect(() => { refresh(); }, []);
  useEffect(() => {
    if (setup?.otpauth_uri) QRCode.toDataURL(setup.otpauth_uri, { width: 200, margin: 1 }).then(setQr).catch(() => setQr(''));
  }, [setup]);

  const begin = async () => {
    setBusy(true); setError('');
    try { setSetup(await adminPost('/auth/2fa/setup')); } catch (err) { setError(message(err, 'Could not start set-up.')); }
    finally { setBusy(false); }
  };
  const confirm = async (e) => {
    e.preventDefault();
    setBusy(true); setError('');
    try {
      const data = await adminPost('/auth/2fa/enable', { code });
      if (data.access_token) startSession(data.access_token);   // other sessions were signed out
      setCodes(data.recovery_codes); setSetup(null); setCode('');
    } catch (err) { setError(message(err, 'That code is not valid.')); }
    finally { setBusy(false); }
  };
  const turnOff = async (e) => {
    e.preventDefault();
    setBusy(true); setError('');
    try { await adminPost('/auth/2fa/disable', { code }); setCode(''); setDisabling(false); await refresh(); }
    catch (err) { setError(message(err, 'That code is not valid.')); }
    finally { setBusy(false); }
  };

  if (codes) return <div className={`${card} p-6`}><RecoveryCodes codes={codes} onDone={() => { setCodes(null); refresh(); onEnabled?.(); }} /></div>;

  return (
    <div className={`${card} p-6`}>
      <div className="flex items-start gap-4">
        <div className={`w-11 h-11 rounded-xl grid place-items-center ${status?.enabled ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
          {status?.enabled ? <ShieldCheck size={22} /> : <KeyRound size={22} />}
        </div>
        <div className="flex-1">
          <h2 className="font-semibold text-slate-900">Two-step verification</h2>
          <p className="text-sm text-slate-600 mt-1">
            {status?.enabled
              ? `On since ${new Date(status.enabled_at).toLocaleDateString()}. ${status.recovery_codes_left} recovery code(s) left.`
              : required
                ? 'Required for the Owner console. Use an authenticator app such as Google Authenticator, Microsoft Authenticator or 1Password.'
                : 'Protect this account with a code from an authenticator app.'}
          </p>
        </div>
        {status?.enabled && !disabling && <Button size="sm" onClick={() => { setDisabling(true); setError(''); }}>Turn off</Button>}
        {!status?.enabled && !setup && <Button variant="primary" busy={busy} onClick={begin}>Set up</Button>}
      </div>

      {error && <div className="mt-4"><Banner onClose={() => setError('')}>{error}</Banner></div>}

      {setup && (
        <form onSubmit={confirm} className="mt-6 grid md:grid-cols-[200px_1fr] gap-6 items-start">
          {qr ? <img src={qr} alt="QR code for your authenticator app" className="w-[200px] h-[200px] rounded-xl border border-slate-200" />
            : <div className="w-[200px] h-[200px] rounded-xl bg-slate-100" />}
          <div className="space-y-4 text-sm">
            <ol className="list-decimal pl-5 space-y-1.5 text-slate-700">
              <li>Open your authenticator app and scan the QR code.</li>
              <li>Can&apos;t scan? Enter this key: <code className="font-mono text-xs bg-slate-100 px-1.5 py-0.5 rounded break-all">{setup.secret}</code></li>
              <li>Type the 6-digit code the app shows.</li>
            </ol>
            <div className="flex gap-2">
              <input value={code} onChange={e => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code"
                placeholder="123456" aria-label="6-digit code" maxLength={6} required
                className="w-36 text-center tracking-[0.3em] font-mono text-lg border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-500/40" />
              <Button type="submit" variant="primary" busy={busy}>Turn on</Button>
            </div>
          </div>
        </form>
      )}

      {disabling && (
        <form onSubmit={turnOff} className="mt-5 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-slate-600">Enter a current code or a recovery code to turn it off:</span>
          <input value={code} onChange={e => setCode(e.target.value)} aria-label="Code" required
            className="w-40 font-mono border border-slate-200 rounded-lg px-3 py-2" />
          <Button type="submit" variant="danger" busy={busy}>Turn off</Button>
          <Button variant="ghost" onClick={() => { setDisabling(false); setCode(''); }}>Cancel</Button>
          {required && <p className="w-full text-xs text-amber-700">The Owner console will be locked until you turn it back on.</p>}
        </form>
      )}
    </div>
  );
}
