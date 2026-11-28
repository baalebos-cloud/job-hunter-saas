// Deterministic ATS checks for the Resume Studio. No AI and no network: the same
// resume always gives the same result, and missing keywords are suggestions only.
import type { ResumeData } from './types';

const SECTION_TITLES = ['CAREER SUMMARY', 'CORE COMPETENCIES', 'SOFT SKILLS', 'PROJECTS COMPLETED', 'TECHNICAL SKILLS',
  'PROFESSIONAL EXPERIENCE', 'EDUCATION', 'PROFESSIONAL CERTIFICATIONS'] as const;

const clean = (s: string | undefined) => String(s ?? '').replace(/\s+/g, ' ').trim();
const joinNonEmpty = (parts: Array<string | undefined>, sep: string) => parts.map(clean).filter(Boolean).join(sep);

/** The whole resume as canonical plain text, in reading order (what an ATS parser should extract). */
export function buildPlainTextResume(data: ResumeData): string {
  const lines: string[] = [];
  const section = (title: string, body: string[]) => {
    const content = body.filter(line => clean(line));
    if (content.length) lines.push('', title, ...content);
  };
  lines.push(clean(data.fullName).toUpperCase());
  if (clean(data.headline)) lines.push(clean(data.headline));
  const contact1 = joinNonEmpty([data.location, data.phone, data.email], ' | ');
  const contact2 = joinNonEmpty([data.linkedin, data.github, data.portfolio], ' | ');
  if (contact1) lines.push(contact1);
  if (contact2) lines.push(contact2);
  section(SECTION_TITLES[0], [data.summary]);
  section(SECTION_TITLES[1], [data.coreCompetencies.map(clean).filter(Boolean).join(' | ')]);
  section(SECTION_TITLES[2], [data.softSkills.map(clean).filter(Boolean).join(' | ')]);
  section(SECTION_TITLES[3], [data.projectsIntro, ...data.projects.map(p =>
    `- ${clean(p.title)}${clean(p.tech) ? ` (${clean(p.tech)})` : ''}${clean(p.description) ? `. ${clean(p.description)}` : ''}`)]);
  section(SECTION_TITLES[4], data.technicalSkills.filter(g => g.items.length).map(g => `${clean(g.label)}: ${g.items.map(clean).join(', ')}`));
  section(SECTION_TITLES[5], data.experience.flatMap(r => [
    `${joinNonEmpty([r.role, joinNonEmpty([r.company, r.location], ' · ')], ' | ')}${clean(r.dates) ? `    ${clean(r.dates)}` : ''}`,
    ...r.bullets.map(b => clean(b)).filter(Boolean).map(b => `- ${b}`)]));
  section(SECTION_TITLES[6], data.education.map(e => `${joinNonEmpty([e.degree, e.institution], ' | ')}${clean(e.date) ? `    ${clean(e.date)}` : ''}`));
  section(SECTION_TITLES[7], data.certifications.map(c => `- ${joinNonEmpty([c.name, c.issuer], ', ')}${clean(c.date) ? `    ${clean(c.date)}` : ''}`));
  return lines.join('\n').trim();
}

const escapeRegExp = (s: string) => s.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&');

/** Whole-term match: "java" does not match "javascript", "ci/cd" matches "CI/CD". */
export function containsKeyword(text: string, keyword: string): boolean {
  return new RegExp(`(^|[^a-z0-9])${escapeRegExp(keyword.toLowerCase())}([^a-z0-9]|$)`, 'i').test(text.toLowerCase());
}

export const KEYWORD_GROUPS: Record<string, string[]> = {
  'Cloud & DevOps Infrastructure': ['aws', 'ec2', 'vpc', 'iam', 's3', 'lambda', 'cloudwatch', 'cloudtrail', 'gcp', 'azure',
    'terraform', 'ansible', 'cloudformation', 'docker', 'kubernetes', 'helm', 'ci/cd', 'github actions', 'jenkins', 'gitlab ci',
    'azure devops', 'linux', 'bash', 'python', 'prometheus', 'grafana', 'monitoring', 'networking', 'dns', 'incident management'],
  'Full-Stack Software Engineering': ['javascript', 'typescript', 'react', 'node.js', 'python', 'fastapi', 'django', 'java',
    'go', 'rest', 'graphql', 'postgresql', 'mysql', 'mongodb', 'redis', 'html', 'css', 'tailwind', 'git', 'unit testing',
    'microservices', 'api', 'docker', 'ci/cd', 'agile'],
  'AI & MLOps Engineering': ['machine learning', 'deep learning', 'llm', 'rag', 'prompt engineering', 'pytorch', 'tensorflow',
    'scikit-learn', 'hugging face', 'langchain', 'vector database', 'embeddings', 'mlops', 'mlflow', 'model deployment',
    'python', 'pandas', 'numpy', 'fastapi', 'docker', 'kubernetes', 'evaluation'],
};

export interface GroupCoverage { group: string; matched: string[]; missing: string[]; percent: number }
export interface Check { id: string; label: string; ok: boolean; detail: string }
export interface AtsReport { groups: GroupCoverage[]; matched: number; total: number; percent: number; checks: Check[]; wordCount: number }

const METRIC = /\b\d+%|\b\d+\s+(tests|services|members|requests|ports)/i;

export function wordCount(text: string): number {
  return (text.match(/[\p{L}\p{N}][\p{L}\p{N}'’.+#/-]*/gu) || []).length;
}

export function analyzeResumeAts(data: ResumeData): AtsReport {
  const text = buildPlainTextResume(data);
  const groups = Object.entries(KEYWORD_GROUPS).map(([group, words]) => {
    const matched = words.filter(w => containsKeyword(text, w));
    return { group, matched, missing: words.filter(w => !matched.includes(w)), percent: Math.round((100 * matched.length) / words.length) };
  });
  const unique = [...new Set(Object.values(KEYWORD_GROUPS).flat())];
  const matched = unique.filter(w => containsKeyword(text, w)).length;
  const words = wordCount(text);
  const sections: Array<[string, boolean]> = [['Career summary', !!clean(data.summary)], ['Core competencies', data.coreCompetencies.length > 0],
    ['Technical skills', data.technicalSkills.some(g => g.items.length)], ['Professional experience', data.experience.length > 0],
    ['Education', data.education.length > 0]];
  const emptySections = sections.filter(([, ok]) => !ok).map(([name]) => name);
  const missingContact = ([['full name', data.fullName], ['location', data.location], ['email', data.email]] as const)
    .filter(([, v]) => !clean(v)).map(([k]) => k);
  const bullets = data.experience.flatMap(r => r.bullets.map(clean).filter(Boolean));
  const quantified = bullets.filter(b => /\d/.test(b)).length;
  const hasMetric = METRIC.test(text);
  const checks: Check[] = [
    { id: 'layout', label: 'Single-column linear layout', ok: true, detail: 'No tables, columns, text boxes or graphics in the document.' },
    { id: 'sections', label: 'Standard section headings', ok: emptySections.length === 0,
      detail: emptySections.length ? `Add: ${emptySections.join(', ')}.` : 'Summary, competencies, skills, experience and education are present.' },
    { id: 'contact', label: 'Plain-text contact header', ok: missingContact.length === 0,
      detail: missingContact.length ? `Add your ${missingContact.join(', ')}.` : 'Contact details are readable text, not an image.' },
    { id: 'metrics', label: 'Quantified impact metrics', ok: hasMetric,
      detail: `${bullets.length ? `${quantified} of ${bullets.length} achievements include a number. ` : ''}${hasMetric
        ? 'At least one result is quantified.' : 'Add a real number to a result you achieved (for example "cut release time by 40%").'}` },
    { id: 'length', label: 'Optimal length (350–950 words)', ok: words >= 350 && words <= 950,
      detail: `${words.toLocaleString()} words${words < 350 ? ': add detail to your strongest roles.' : words > 950 ? ': shorten older or less relevant roles.' : '.'}` },
  ];
  return { groups, matched, total: unique.length, percent: Math.round((100 * matched) / unique.length), checks, wordCount: words };
}

// Terms looked for in a job description: multi-word phrases first, then single words.
export const JD_DICTIONARY: string[] = [
  'systems manager', 'auto scaling', 'google cloud', 'google artifact registry', 'github actions', 'azure devops', 'gitlab ci',
  'root cause analysis', 'infrastructure as code', 'incident management', 'machine learning', 'deep learning', 'prompt engineering',
  'vector database', 'unit testing', 'rest api', 'hugging face', 'model deployment', 'site reliability', 'load balancing',
  'disaster recovery', 'cost optimization', 'access management', 'data pipelines', 'event driven',
  'aws', 'ec2', 'vpc', 'iam', 's3', 'lambda', 'cloudwatch', 'cloudtrail', 'cloudformation', 'gcp', 'azure', 'docker', 'kubernetes',
  'helm', 'argocd', 'terraform', 'ansible', 'pulumi', 'ci/cd', 'jenkins', 'linux', 'windows', 'python', 'bash', 'powershell', 'go',
  'java', 'javascript', 'typescript', 'node.js', 'react', 'fastapi', 'django', 'flask', 'graphql', 'postgresql', 'mysql', 'mongodb',
  'redis', 'kafka', 'rabbitmq', 'tcp/ip', 'dns', 'dhcp', 'infoblox', 'ipam', 'vpn', 'firewall', 'prometheus', 'grafana', 'datadog',
  'splunk', 'elk', 'runbooks', 'sre', 'devops', 'devsecops', 'security', 'compliance', 'networking', 'monitoring', 'observability',
  'microservices', 'serverless', 'llm', 'rag', 'pytorch', 'tensorflow', 'mlops', 'mlflow', 'pandas', 'numpy', 'sql', 'agile', 'scrum',
  'jira', 'git', 'api',
];

const STOPWORDS = new Set(('a an and are as at be been being but by can could do does for from had has have how i if in into is it its ' +
  'may more must not of on or our out over per should so such than that the their them then there these they this those to under up ' +
  'us was we were what when where which who will with within without would you your yours about across after all also any based both ' +
  'each etc every few including like make new other own same some well work working role team teams years year experience ' +
  'ability able strong excellent good great skills skill knowledge using use used help support responsibilities requirements ' +
  'required preferred plus join company candidate candidates opportunity looking environment ensure provide including').split(' '));

export interface JdMatch { extractedKeywords: string[]; matchedKeywords: string[]; missingKeywords: string[]; matchPercent: number }

export function analyzeJobDescription(data: ResumeData, jdText: string): JdMatch {
  const jd = String(jdText ?? '').toLowerCase();
  if (!jd.trim()) return { extractedKeywords: [], matchedKeywords: [], missingKeywords: [], matchPercent: 0 };
  const found = JD_DICTIONARY.filter(term => containsKeyword(jd, term));
  // Frequent domain words the dictionary does not know (mentioned at least twice).
  const counts = new Map<string, number>();
  for (const token of jd.match(/[a-z][a-z0-9+#./-]{2,}/g) || []) {
    const word = token.replace(/[.\-/]+$/, '');
    if (!STOPWORDS.has(word) && word.length > 2) counts.set(word, (counts.get(word) || 0) + 1);
  }
  const covered = (word: string) => found.some(term => term === word || term.split(/\s+/).includes(word));
  const frequent = [...counts.entries()].filter(([word, n]) => n >= 2 && !covered(word))
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([word]) => word);
  const extractedKeywords = [...found, ...frequent].slice(0, 60);
  const resume = buildPlainTextResume(data);
  const matchedKeywords = extractedKeywords.filter(k => containsKeyword(resume, k));
  const missingKeywords = extractedKeywords.filter(k => !matchedKeywords.includes(k));
  return { extractedKeywords, matchedKeywords, missingKeywords,
    matchPercent: extractedKeywords.length ? Math.round((100 * matchedKeywords.length) / extractedKeywords.length) : 0 };
}

export { SECTION_TITLES };
