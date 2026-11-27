// Saving the Studio document to the account and loading starting points.
import axios from 'axios';
import type { Paper, ResumeData } from '../types';

const API: string = (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_URL || 'http://localhost:8000/api/v1';
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('token') ?? ''}` });

export interface Saved { document: ResumeData | null; paper: Paper; preset: string; updated_at: string | null }
export interface TailoredSource { task_id: string; job_title: string; company: string | null; created_at: string | null }

export const loadSaved = async (): Promise<Saved> => (await axios.get(`${API}/studio`, { headers: headers() })).data;
export const save = async (data: ResumeData, paper: Paper, preset: string): Promise<Saved> =>
  (await axios.put(`${API}/studio`, { data, paper, preset }, { headers: headers() })).data;
export const removeSaved = async (): Promise<void> => { await axios.delete(`${API}/studio`, { headers: headers() }); };
export const listSources = async (): Promise<{ profile: boolean; tailored: TailoredSource[] }> =>
  (await axios.get(`${API}/studio/sources`, { headers: headers() })).data;
export const fromProfile = async (): Promise<ResumeData> =>
  (await axios.get(`${API}/studio/sources/profile`, { headers: headers() })).data.data;
export const fromTailored = async (taskId: string): Promise<{ data: ResumeData; job_description: string; job_title: string | null }> =>
  (await axios.get(`${API}/studio/sources/resume/${encodeURIComponent(taskId)}`, { headers: headers() })).data;

/** A readable message from an API error (FastAPI detail may be a string, object or list). */
export function apiError(err: unknown, fallback: string): string {
  const e = err as { response?: { status?: number; data?: { detail?: unknown } } };
  const detail = e?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail[0] && typeof detail[0] === 'object' && 'msg' in detail[0]) return String((detail[0] as { msg: unknown }).msg);
  if (e?.response?.status === 401) return 'Your session has expired. Please sign in again.';
  return fallback;
}
