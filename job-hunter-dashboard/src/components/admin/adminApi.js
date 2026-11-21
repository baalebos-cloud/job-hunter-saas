import axios from 'axios';
import { errorText } from '../../lib/session';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });

export const adminGet = (path, params) => axios.get(`${API}${path}`, { headers: headers(), params }).then(r => r.data);
export const adminPost = (path, body = {}, config = {}) =>
  axios.post(`${API}${path}`, body, { headers: headers(), ...config }).then(r => r.data);
export const adminPatch = (path, body = {}) => axios.patch(`${API}${path}`, body, { headers: headers() }).then(r => r.data);
export const adminDelete = (path) => axios.delete(`${API}${path}`, { headers: headers() }).then(r => r.data);

// True when the console refused access until two-step verification is on.
export const needsMfaEnrollment = (err) => err?.response?.status === 403
  && err?.response?.data?.detail?.code === 'mfa_enrollment_required';

export const message = (err, fallback) => errorText(err, fallback);

// Download a CSV export with the bearer token (a plain link cannot send it).
export async function downloadCsv(path, params, fallbackName) {
  const res = await axios.get(`${API}${path}`, { headers: headers(), params, responseType: 'blob' });
  const match = /filename="?([^";]+)"?/i.exec(res.headers['content-disposition'] || '');
  const url = URL.createObjectURL(res.data);
  const link = Object.assign(document.createElement('a'), { href: url, download: match?.[1] || fallbackName });
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ── Formatting ───────────────────────────────────────────────────────────────
export const num = (n) => (n ?? 0).toLocaleString();

export function ago(iso) {
  if (!iso) return '—';
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`;
  if (seconds < 86400 * 30) return `${Math.floor(seconds / 86400)} d ago`;
  return new Date(iso).toLocaleDateString();
}

export const when = (iso) => (iso ? new Date(iso).toLocaleString() : '—');

export function device(ua) {
  if (!ua) return '—';
  const os = /Windows/.test(ua) ? 'Windows' : /Android/.test(ua) ? 'Android' : /iPhone|iPad|iOS/.test(ua) ? 'iOS'
    : /Mac OS X/.test(ua) ? 'macOS' : /Linux/.test(ua) ? 'Linux' : '';
  const browser = /Edg\//.test(ua) ? 'Edge' : /OPR\//.test(ua) ? 'Opera' : /Chrome\//.test(ua) ? 'Chrome'
    : /Firefox\//.test(ua) ? 'Firefox' : /Safari\//.test(ua) ? 'Safari' : /curl|python|httpx|bot|spider/i.test(ua) ? 'Script/bot' : '';
  return [browser, os].filter(Boolean).join(' · ') || ua.slice(0, 40);
}

export const initials = (name, email) => ((name || email || '?').split(/[\s@.]+/).filter(Boolean)
  .slice(0, 2).map(p => p[0]).join('') || '?').toUpperCase();

export const eventTone = (event) => (event.startsWith('admin.') ? 'violet'
  : ['login.failed', 'login.blocked', 'signup.rejected'].includes(event) ? 'red'
  : ['login.denied', 'login.new_country', 'mfa.disabled', 'alert.sent'].includes(event) ? 'amber'
  : ['signup', 'hr.signup'].includes(event) ? 'blue'
  : ['login.success', 'mfa.enabled'].includes(event) ? 'green' : 'slate');
