// Role-focus presets: re-order what is already in the resume so the most
// relevant evidence for a kind of role comes first. They never add, invent or
// remove content, so switching presets can never lose the person's edits.
import type { ResumeData } from './types';
import { KEYWORD_GROUPS, containsKeyword } from './atsAnalyzer';

export interface RolePreset { id: string; label: string; group?: keyof typeof KEYWORD_GROUPS | string }

export const ROLE_PRESETS: RolePreset[] = [
  { id: 'as-is', label: 'As written' },
  { id: 'cloud', label: 'Cloud & DevOps', group: 'Cloud & DevOps Infrastructure' },
  { id: 'software', label: 'Software engineering', group: 'Full-Stack Software Engineering' },
  { id: 'ai', label: 'AI & MLOps', group: 'AI & MLOps Engineering' },
];

const hits = (text: string, keywords: string[]) => keywords.reduce((n, k) => n + (containsKeyword(text, k) ? 1 : 0), 0);

/** Stable sort: higher score first, original order kept for ties. */
function rank<T>(items: T[], score: (item: T) => number): T[] {
  return items.map((item, index) => ({ item, index, s: score(item) }))
    .sort((a, b) => b.s - a.s || a.index - b.index).map(x => x.item);
}

/** The headline's role (before the first " | ") followed by the person's own most relevant skills. */
function focusHeadline(data: ResumeData, keywords: string[]): string {
  const role = data.headline.split(' | ')[0];
  const own = [...data.coreCompetencies, ...data.technicalSkills.flatMap(g => g.items)]
    .map(s => s.replace(/\s*\(.*\)\s*$/, '').trim()).filter(Boolean);
  const relevant = [...new Set(own.filter(s => hits(s, keywords) > 0))].slice(0, 5);
  if (!role.trim() || !relevant.length) return data.headline;
  return `${role.trim()} | ${relevant.join(' · ')}`;
}

export function applyRolePreset(data: ResumeData, presetId: string): ResumeData {
  const preset = ROLE_PRESETS.find(p => p.id === presetId);
  const keywords = preset?.group ? KEYWORD_GROUPS[preset.group] ?? [] : [];
  if (!keywords.length) return structuredClone(data);
  const next = structuredClone(data);
  next.headline = focusHeadline(data, keywords);
  next.coreCompetencies = rank(data.coreCompetencies, c => hits(c, keywords));
  next.technicalSkills = rank(data.technicalSkills.map(g => ({ ...g, items: rank(g.items, i => hits(i, keywords)) })),
    g => hits(g.items.join(' '), keywords));
  next.projects = rank(data.projects, p => hits(`${p.title} ${p.tech} ${p.description}`, keywords));
  next.experience = data.experience.map(r => ({ ...r, bullets: rank(r.bullets, b => hits(b, keywords)) }));
  return next;
}
