import axios from 'axios';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
export const SUPPORT_EMAIL = 'support@baalebo.xyz';

const auth = () => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};
export const signedIn = () => Boolean(localStorage.getItem('token'));

export const CATEGORIES = [
  ['question', 'General question'], ['bug', 'Something is not working'], ['feedback', 'Feedback or idea'],
  ['resume', 'Resume tailoring'], ['jobs', 'Jobs and applications'], ['account', 'Account and sign-in'],
  ['billing', 'Plans and billing'], ['other', 'Something else'],
];

export const STATUS_TONE = {
  open: 'bg-amber-50 text-amber-800 ring-amber-200',
  answered: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  solved: 'bg-slate-100 text-slate-600 ring-slate-200',
};

// Context support needs to reproduce a problem, captured automatically.
export function pageContext() {
  const { pathname, search } = window.location;
  return `${pathname}${search}`.slice(0, 300);
}

export async function createTicket({ category, subject, message, email, name, screenshot, website }) {
  const form = new FormData();
  Object.entries({ category, subject, message, email, name, website, page: pageContext() })
    .forEach(([k, v]) => { if (v) form.append(k, v); });
  if (screenshot) form.append('screenshot', screenshot);
  const { data } = await axios.post(`${API}/support/tickets`, form, { headers: auth() });
  return data;
}

export const listTickets = () => axios.get(`${API}/support/tickets`, { headers: auth() }).then(r => r.data);
export const getTicket = (id) => axios.get(`${API}/support/tickets/${id}`, { headers: auth() }).then(r => r.data);
export const replyTicket = (id, body) =>
  axios.post(`${API}/support/tickets/${id}/messages`, { body }, { headers: auth() }).then(r => r.data);
export const solveTicket = (id) => axios.post(`${API}/support/tickets/${id}/solve`, {}, { headers: auth() }).then(r => r.data);

// Screenshots need the bearer token, so load them as a blob URL.
export async function attachmentUrl(path) {
  const { data } = await axios.get(`${API}${path}`, { headers: auth(), responseType: 'blob' });
  return URL.createObjectURL(data);
}

export function screenshotProblem(file) {
  if (!file) return '';
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) return 'Attach a PNG, JPG or WebP screenshot.';
  if (file.size > 5 * 1024 * 1024) return 'The screenshot is too large. Max 5 MB.';
  return '';
}

export const shortDate = (iso) => (iso ? new Date(iso).toLocaleString(undefined, {
  day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '');
