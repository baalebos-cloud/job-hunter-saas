"""Validation and repeatable requirement coverage for resume preparation."""
import re


def normalize(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip().casefold()


def contains(text, phrase):
    return bool(re.search(r'(?<!\w)' + re.escape(normalize(phrase)) + r'(?!\w)', normalize(text)))


def validate_resume(data):
    if not isinstance(data, dict) or not data.get('name') or not data.get('contact'):
        raise ValueError('Resume extraction did not preserve name and contact details.')
    for section in ('experience', 'projects', 'education', 'certifications'):
        if not isinstance(data.get(section), list):
            raise ValueError(f'Invalid {section} data.')
    if not isinstance(data.get('skills'), dict):
        raise ValueError('Invalid skills data.')
    return data


def merge_rewrite(original, rewritten, source):
    """Keep history, omit unsupported skill additions, reject invented numbers.

    Removed additions become review questions in the rewrite metadata.
    """
    result = dict(original)
    experiences = rewritten.get('optimized_experience')
    if not isinstance(experiences, list) or len(experiences) != len(original['experience']):
        raise ValueError('Rewrite omitted experience entries.')
    source_numbers = set(re.findall(r'\d+(?:[.,]\d+)*(?:\s*%)?', source))
    source_numbers = {normalize(n) for n in source_numbers}
    for old, new in zip(original['experience'], experiences):
        for key in ('role', 'company', 'dates'):
            if normalize(old.get(key)) != normalize(new.get(key)):
                raise ValueError(f'Rewrite changed an employment {key}.')
        if not isinstance(new.get('bullets'), list) or not new['bullets']:
            raise ValueError('Rewrite omitted employment details.')
        old_numbers = {normalize(n) for n in re.findall(r'\d+(?:[.,]\d+)*(?:\s*%)?', ' '.join(old.get('bullets', [])))}
        for number in re.findall(r'\d+(?:[.,]\d+)*(?:\s*%)?', ' '.join(new['bullets'])):
            if normalize(number) not in old_numbers:
                raise ValueError('Rewrite moved or invented a numeric achievement for an employer.')
    skills = rewritten.get('optimized_skills', original['skills'])
    if not isinstance(skills, dict) or any(not isinstance(v, list) for v in skills.values()):
        raise ValueError('Invalid rewritten skills.')
    filtered = {}; excluded = []
    for category, values in skills.items():
        filtered[category] = []
        for skill in values:
            if not isinstance(skill, str) or not skill.strip():
                raise ValueError('Invalid rewritten skill.')
            if contains(source, skill):
                filtered[category].append(skill)
            elif normalize(skill) not in {normalize(item) for item in excluded}:
                excluded.append(skill)
    skills = filtered
    # Tailoring can reorder skills; it must not silently delete documented skills.
    retained = {normalize(skill) for values in skills.values() for skill in values}
    for category, values in original['skills'].items():
        for skill in values:
            if normalize(skill) not in retained:
                if not contains(source, skill):
                    raise ValueError('Extracted skill is not evidenced in the source.')
                skills.setdefault(category, []).append(skill)
                retained.add(normalize(skill))
    summary = rewritten.get('optimized_summary', original.get('summary', ''))
    if excluded:
        questions = rewritten.get('confirmation_questions', [])
        questions = list(questions) if isinstance(questions, list) else []
        questions.extend(f'"{skill}" was omitted because no exact evidence was found in the source. Can you confirm relevant experience?' for skill in excluded)
        rewritten['confirmation_questions'] = questions
        # An omitted skill must not survive as a claim in the summary or bullets.
        if any(contains(summary, skill) for skill in excluded):
            summary = original.get('summary', '')
        experiences = [
            {**new, 'bullets': list(old.get('bullets', []))}
            if any(contains(' '.join(new['bullets']), skill) for skill in excluded) else new
            for old, new in zip(original['experience'], experiences)
        ]
    generated = str(summary) + ' ' + ' '.join(' '.join(e['bullets']) for e in experiences)
    for number in re.findall(r'\d+(?:[.,]\d+)*(?:\s*%)?', generated):
        if normalize(number) not in source_numbers:
            raise ValueError('Rewrite introduced an unsupported numeric achievement.')
    result.update(summary=summary, experience=[{**old, 'bullets': new['bullets']} for old,new in zip(original['experience'], experiences)], skills=skills)
    return validate_resume(result)


def score_requirements(resume_text, job_description, requirements):
    """Baalebos requirement phrase coverage, not an employer score or interview prediction."""
    seen = set(); details = []
    for item in requirements:
        if not isinstance(item, dict):
            continue
        phrase = str(item.get('phrase', '')).strip()
        key = normalize(phrase)
        if not key or key in seen or len(phrase) > 160 or not contains(job_description, phrase):
            continue
        seen.add(key)
        required = item.get('priority') != 'preferred'
        matched = contains(resume_text, phrase)
        details.append({'requirement': phrase, 'priority': 'required' if required else 'preferred',
                        'matched': matched, 'weight': 2 if required else 1,
                        'evidence': next((line.strip() for line in resume_text.splitlines() if contains(line, phrase)), '')[:500]})
    if not details:
        raise ValueError('No verifiable job requirements could be extracted.')
    weight = sum(d['weight'] for d in details)
    matched = [d for d in details if d['matched']]
    score = round(100 * sum(d['weight'] for d in matched) / weight, 1)
    return {'overall_score': score, 'keywords_matched': len(matched), 'keywords_missing': len(details)-len(matched),
            'total_keywords': len(details), 'missing_list': [d['requirement'] for d in details if not d['matched']],
            'requirements': details, 'breakdown': {},
            'scoring_method': 'Weighted requirement phrase coverage v1: required=2, preferred=1. Exact phrase evidence; paraphrases may be missed.',
            'score_notice': 'Baalebos assessment of documented coverage, not an employer ATS score or interview guarantee.',
            'suggestions': ['Confirm relevant missing qualifications before adding them.', 'Use only achievements and metrics you can substantiate.']}
