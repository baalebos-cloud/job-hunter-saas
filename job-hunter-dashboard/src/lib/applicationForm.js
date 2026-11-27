// Application forms for jobs posted on Baalebos. The server re-checks everything
// (backend/app/services/application_form.py); these lists mirror it.
export const STANDARD_FIELDS = [
  ['cover_letter', 'Cover letter'],
  ['linkedin', 'LinkedIn profile'],
  ['portfolio', 'Portfolio or GitHub link'],
  ['city', 'City they live in'],
  ['experience_years', 'Years of relevant experience'],
  ['work_authorization', 'Authorised to work in a country'],
  ['sponsorship', 'Needs visa sponsorship'],
  ['notice_period', 'Notice period or start date'],
  ['expected_salary', 'Expected salary'],
  ['relocate', 'Willing to relocate'],
];
export const QUESTION_TYPES = [
  ['short_text', 'Short answer'], ['long_text', 'Paragraph'], ['yes_no', 'Yes / No'], ['single_choice', 'One choice'],
  ['multi_choice', 'Several choices'], ['number', 'Number'], ['date', 'Date'], ['url', 'Link'],
];
export const MAX_QUESTIONS = 20;
export const LEVELS = [['off', 'Off'], ['optional', 'Optional'], ['required', 'Required']];
export const CHOICE = new Set(['single_choice', 'multi_choice']);
export const ALWAYS = ['Full name', 'Email', 'Phone', 'Country', 'Resume tailored for this job'];

export const defaultApplicationForm = () => ({ standard: { cover_letter: 'optional', linkedin: 'optional' }, authorization_country: '', questions: [] });
export const newId = () => `q_${Math.random().toString(36).slice(2, 10).padEnd(8, '0')}`;

/** Problems to fix before saving, mirroring the server's checks. */
export function formProblems(form) {
  const problems = [];
  if (form.standard?.work_authorization && form.standard.work_authorization !== 'off' && !form.authorization_country?.trim()) {
    problems.push('Say which country the work authorisation question is about.');
  }
  const seen = new Set();
  form.questions.forEach((q, i) => {
    const label = q.label.trim();
    if (label.length < 3) problems.push(`Question ${i + 1} needs some text.`);
    else if (seen.has(label.toLowerCase())) problems.push(`Question ${i + 1} repeats an earlier question.`);
    seen.add(label.toLowerCase());
    if (CHOICE.has(q.type) && new Set((q.options || []).map(o => o.trim().toLowerCase()).filter(Boolean)).size < 2) {
      problems.push(`Question ${i + 1} needs at least two choices.`);
    }
  });
  return problems;
}

