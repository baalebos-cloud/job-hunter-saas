import { useEffect, useState } from 'react';
import axios from 'axios';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Real platform figures for public pages. Returns null until loaded or when
// the request fails, so callers hide the figure instead of showing a guess.
export function useLiveStats() {
  const [stats, setStats] = useState(null);
  useEffect(() => {
    let active = true;
    axios.get(`${API}/jobs/stats`, { timeout: 8000 })
      .then(r => { if (active && typeof r.data?.open_jobs === 'number') setStats(r.data); })
      .catch(() => {});
    return () => { active = false; };
  }, []);
  return stats;
}

export function updatedAgo(iso) {
  if (!iso) return null;
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 60) return minutes <= 1 ? 'just now' : `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}
