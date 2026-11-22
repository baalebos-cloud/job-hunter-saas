import { useEffect, useState } from 'react';
import axios from 'axios';
import { errorText } from '../../lib/session';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Opened from the "Unsubscribe in one click" link in job alert emails. The
// request is sent by this page (not on link open), so email security scanners
// that pre-fetch links cannot unsubscribe people by accident.
export default function UnsubscribePage() {
  const [state, setState] = useState('working');   // working | done | error
  const [message, setMessage] = useState('');

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get('t') || '';
    if (!token) { setState('error'); setMessage('This unsubscribe link is incomplete.'); return; }
    axios.post(`${API}/alerts/unsubscribe`, { token })
      .then(() => setState('done'))
      .catch(err => { setState('error'); setMessage(errorText(err, 'We could not process this link.')); });
  }, []);

  return (
    <main className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <div className="w-full max-w-md bg-white border border-slate-200 rounded-2xl p-8 text-center" role="status">
        <div className="text-xl font-bold tracking-tight mb-6">baalebos<span className="text-emerald-600">.</span></div>
        {state === 'working' && <p className="text-slate-600">Turning off job alerts…</p>}
        {state === 'done' && (
          <>
            <h1 className="text-lg font-semibold text-slate-900">You&apos;re unsubscribed</h1>
            <p className="mt-2 text-sm text-slate-600">You won&apos;t receive job alert emails any more. Account emails, like password resets, still arrive.</p>
            <a href="/profile" className="mt-6 inline-block text-sm font-semibold text-emerald-700 hover:underline">Changed your mind? Turn alerts back on in My profile</a>
          </>
        )}
        {state === 'error' && (
          <>
            <h1 className="text-lg font-semibold text-slate-900">Link not valid</h1>
            <p className="mt-2 text-sm text-slate-600">{message} You can turn job alerts off in My profile → Job preferences.</p>
            <a href="/profile" className="mt-6 inline-block text-sm font-semibold text-emerald-700 hover:underline">Go to My profile</a>
          </>
        )}
      </div>
    </main>
  );
}
