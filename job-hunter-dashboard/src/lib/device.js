// A random id for this browser, sent only when creating an account so one
// device cannot open a new free account every time the free scans run out.
// The server stores a keyed hash of it, never the id itself.
const KEY = 'bb_device_id';

export function deviceId() {
  try {
    let id = localStorage.getItem(KEY);
    if (!id || !/^[A-Za-z0-9_-]{16,64}$/.test(id)) {
      const bytes = new Uint8Array(16);
      crypto.getRandomValues(bytes);
      id = `dv_${Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('')}`;
      localStorage.setItem(KEY, id);
    }
    return id;
  } catch {
    return null;   // private mode or blocked storage: the network check still applies
  }
}

export const deviceHeaders = () => {
  const id = deviceId();
  return id ? { 'X-Device-Id': id } : {};
};
