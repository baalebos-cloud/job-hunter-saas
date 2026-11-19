// Per-user browser state that must never leak to the next person who signs in
// on the same browser (e.g. the last tailored resume used for applications).
const USER_SCOPED_KEYS = ['lastTaskId'];

export function clearUserState() {
  for (const key of USER_SCOPED_KEYS) localStorage.removeItem(key);
}

export function startSession(token) {
  clearUserState();
  localStorage.setItem('token', token.trim());
}

export function clearSession() {
  localStorage.removeItem('token');
  clearUserState();
}

const STATUS_MESSAGES = {
  401: 'Your session has expired. Please sign in again.',
  403: 'You do not have access to this resume.',
  404: 'This resume could not be found. It may have been removed; please run a new analysis.',
  429: 'Too many requests. Please wait a moment and try again.',
};

// Readable message for an axios error, including responseType: 'blob' errors
// whose JSON body arrives as a Blob.
export async function apiErrorMessage(err, fallback = 'Something went wrong. Please retry.') {
  const status = err?.response?.status;
  let detail = err?.response?.data?.detail;
  const data = err?.response?.data;
  if (!detail && data instanceof Blob) {
    try { detail = JSON.parse(await data.text())?.detail; } catch { /* not JSON */ }
  }
  if (typeof detail === 'string' && status !== 401) return detail;
  if (STATUS_MESSAGES[status]) return STATUS_MESSAGES[status];
  if (status >= 500) return `The server could not complete this request (error ${status}). Please retry shortly.`;
  if (!err?.response) return 'Network error. Check your connection and retry.';
  return fallback;
}

// Filename from Content-Disposition. Prefers the ASCII `filename` (portable
// across browsers and file systems); falls back to RFC 5987 `filename*`.
export function filenameFromDisposition(header, fallback = 'Resume.pdf') {
  if (!header) return fallback;
  const plain = /(?:^|;)\s*filename="?([^";]+)"?/i.exec(header);
  if (plain) return plain[1];
  const star = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (star) { try { return decodeURIComponent(star[1]); } catch { /* fall through */ } }
  return fallback;
}

// ── Short-lived access tokens + HttpOnly refresh cookie ─────────────────────
// Access tokens expire after 15 minutes. On a 401 the client calls
// /auth/refresh once (the refresh token lives in an HttpOnly cookie the page
// cannot read), stores the new access token and retries the request.
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const NO_REFRESH = ['/auth/login', '/auth/signup', '/auth/refresh', '/auth/logout', '/hr-auth/login', '/auth/admin/login'];
let refreshing = null;

export function refreshAccessToken(axios) {
  if (!refreshing) {
    refreshing = axios.post(`${API_BASE}/auth/refresh`, null, { withCredentials: true, _skipAuthRefresh: true })
      .then(res => { localStorage.setItem('token', res.data.access_token); return res.data.access_token; })
      .finally(() => { refreshing = null; });
  }
  return refreshing;
}

export function installAuthInterceptors(axios) {
  // Lets the browser store/send the refresh cookie on cross-origin auth calls.
  axios.defaults.withCredentials = true;
  axios.interceptors.response.use(undefined, async error => {
    const config = error.config || {};
    const url = config.url || '';
    if (error.response?.status !== 401 || config._retried || config._skipAuthRefresh
        || NO_REFRESH.some(path => url.includes(path)) || !localStorage.getItem('token')) {
      return Promise.reject(error);
    }
    try {
      const token = await refreshAccessToken(axios);
      config._retried = true;
      config.headers = { ...(config.headers || {}), Authorization: `Bearer ${token}` };
      return axios(config);
    } catch {
      clearSession();
      if (!window.location.pathname.startsWith('/login')) window.location.href = '/login';
      return Promise.reject(error);
    }
  });
}

// Revokes the access token and refresh-token family server-side, then clears
// local state. Never blocks sign-out on a network error.
export async function signOut(axios, redirect = '/login') {
  const token = localStorage.getItem('token');
  try {
    if (token) await axios.post(`${API_BASE}/auth/logout`, null, { headers: { Authorization: `Bearer ${token}` }, _skipAuthRefresh: true });
  } catch { /* still sign out locally */ }
  clearSession();
  window.location.href = redirect;
}
