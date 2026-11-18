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
