// The Resume Studio document: one person's resume in the single-column ATS layout.
export interface Project { title: string; tech: string; description: string }
export interface SkillGroup { label: string; items: string[] }
export interface Role { role: string; company: string; location: string; dates: string; bullets: string[] }
export interface School { degree: string; institution: string; date: string }
export interface Certification { name: string; issuer: string; date: string }

export interface ResumeData {
  fullName: string;
  headline: string;            // target role, then " | " separated focus areas
  location: string;
  phone: string;
  email: string;
  linkedin: string;
  github: string;
  portfolio: string;
  summary: string;
  coreCompetencies: string[];
  softSkills: string[];
  projectsIntro: string;
  projects: Project[];
  technicalSkills: SkillGroup[];
  experience: Role[];
  education: School[];
  certifications: Certification[];
}

export type Paper = 'A4' | 'Letter';
export const PAPER_SIZES: Record<Paper, [number, number]> = { A4: [595.28, 841.89], Letter: [612, 792] };

/** Type sizes in points, shared by the PDF engine and the on-screen paper. */
export const TYPE = { name: 17, headline: 10, contact: 9.5, heading: 11, body: 9.8, entry: 10.2 } as const;

export function emptyResume(): ResumeData {
  return {
    fullName: '', headline: '', location: '', phone: '', email: '', linkedin: '', github: '', portfolio: '',
    summary: '', coreCompetencies: [], softSkills: [], projectsIntro: '', projects: [], technicalSkills: [],
    experience: [], education: [], certifications: [],
  };
}
