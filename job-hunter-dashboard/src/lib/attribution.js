// First-touch campaign attribution: the UTM tags (and the referring site) of the
// link that first brought this visitor. Stored once on this device and sent with
// sign-up so the team can see which posts and campaigns bring people. Nothing
// else about the visitor is stored.
const KEY = 'first_touch';

export function captureFirstTouch() {
  try {
    if (localStorage.getItem(KEY)) return;
    const params = new URLSearchParams(window.location.search);
    let referrer = '';
    try {
      const ref = document.referrer ? new URL(document.referrer) : null;
      if (ref && ref.hostname !== window.location.hostname) referrer = ref.hostname;
    } catch { /* no usable referrer */ }
    const touch = {
      utm_source: params.get('utm_source') || '', utm_medium: params.get('utm_medium') || '',
      utm_campaign: params.get('utm_campaign') || '', referrer,
    };
    if (touch.utm_source || touch.referrer) localStorage.setItem(KEY, JSON.stringify(touch));
  } catch { /* storage blocked: attribution is optional */ }
}

export function firstTouch() {
  try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch { return {}; }
}

export function clearFirstTouch() {
  try { localStorage.removeItem(KEY); } catch { /* ignore */ }
}
