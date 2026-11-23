"""Validation and repeatable requirement coverage for resume preparation."""
import re

from backend.app.utils.skill_terms import find_terms


def normalize(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip().casefold()


# Canonical technology synonyms. Matching any member counts as evidence for
# the whole group (same fact, different spelling) - never for a different skill.
SYNONYM_GROUPS = [
    {'kubernetes', 'k8s'}, {'postgresql', 'postgres', 'psql'}, {'javascript', 'js', 'ecmascript'},
    {'typescript', 'ts'}, {'amazon web services', 'aws'}, {'google cloud platform', 'gcp', 'google cloud'},
    {'microsoft azure', 'azure'}, {'ci/cd', 'cicd', 'ci-cd', 'ci / cd'}, {'node.js', 'nodejs', 'node js'},
    {'react', 'react.js', 'reactjs'}, {'vue', 'vue.js', 'vuejs'}, {'next.js', 'nextjs'},
    {'c#', 'csharp', 'c sharp'}, {'.net', 'dotnet', 'dot net'}, {'c++', 'cpp'},
    {'machine learning', 'ml'}, {'artificial intelligence', 'ai'}, {'golang', 'go lang'},
    {'mongodb', 'mongo'}, {'elasticsearch', 'elastic search'}, {'github actions', 'gh actions'},
    {'infrastructure as code', 'iac'}, {'site reliability engineering', 'sre'}, {'amazon s3', 's3'},
    {'amazon ec2', 'ec2'}, {'microsoft sql server', 'sql server', 'mssql'}, {'scikit-learn', 'sklearn'},
]
_SYNONYMS = {}
for _group in SYNONYM_GROUPS:
    for _member in _group:
        _SYNONYMS[_member] = _group

# Token boundaries that understand technology names: "C" must not match
# "C++"/"C#", "Java" must not match "JavaScript", "R" must not match "R&D",
# while ".NET", "C++", "CI/CD", "Node.js" and slash/hyphen lists
# ("Terraform/Ansible", "Java-based") match as whole tokens.
_LEFT = r'(?<![a-z0-9_.+#&])'
_RIGHT = r'(?![a-z_+#&]|\.[a-z0-9])'


def _pattern(phrase):
    escaped = re.escape(phrase).replace(r'\ ', r'\s+')
    left = _LEFT if re.match(r'[a-z0-9]', phrase) else r'(?<![a-z0-9_])'
    return left + escaped + _RIGHT


def phrase_variants(phrase):
    key = normalize(phrase)
    return sorted(_SYNONYMS.get(key, {key}), key=len, reverse=True)


def contains(text, phrase):
    haystack = normalize(text)
    if not normalize(phrase):
        return False
    return any(re.search(_pattern(variant), haystack) for variant in phrase_variants(phrase))


def validate_resume(data):
    if not isinstance(data, dict) or not data.get('name') or not data.get('contact'):
        raise ValueError('Resume extraction did not preserve name and contact details.')
    for section in ('experience', 'projects', 'education', 'certifications'):
        if not isinstance(data.get(section), list):
            raise ValueError(f'Invalid {section} data.')
    if not isinstance(data.get('skills'), dict):
        raise ValueError('Invalid skills data.')
    return data


# ── Source evidence (anti-hallucination) ─────────────────────────────────────
# Everything that reaches the final resume must be traceable to the uploaded
# file. These checks are deterministic: the model is never trusted to police
# its own output.

_STOPWORDS = frozenset("""
a an and are as at be been being by for from has have in into is it its of on or our over per that the their
them they this to under up via was we were which while with within without will would your you i me my mine
also across all any both each more most other some such than then there these those through using used use
including include includes new well etc
""".split())
_TOKEN = re.compile(r"[^\W_][\w+#]*(?:[.'’][\w+#]+)*")


def _fold(text) -> str:
    """Case- and accent-insensitive form: "Ọlájídé" and "Olajide" compare equal, so
    names in any language (and PDFs that drop accents) are never rejected."""
    import unicodedata
    decomposed = unicodedata.normalize('NFKD', normalize(text))
    return ''.join(c for c in decomposed if not unicodedata.combining(c))


def _tokens(text) -> set:
    return set(_TOKEN.findall(_fold(text).replace('/', ' ').replace('-', ' ')))


def _content(text) -> set:
    return {t for t in _tokens(text) if t not in _STOPWORDS and (len(t) > 1 or t.isdigit())}


def _supported(value, source_tokens, minimum=1.0) -> bool:
    """Share of the value's content words found in the source, at least ``minimum``."""
    words = _content(value)
    if not words:
        return True
    return len(words & source_tokens) / len(words) >= minimum


_DIGITS = re.compile(r'\d+')


def _digits_supported(value, source) -> bool:
    found = set(_DIGITS.findall(str(source or '')))
    return all(d in found for d in _DIGITS.findall(str(value or '')))


def _contact_piece_supported(piece, source) -> bool:
    piece = piece.strip()
    if not piece:
        return False
    digits = re.sub(r'\D', '', piece)
    if len(digits) >= 7 and '@' not in piece and '.' not in piece.replace(' ', '')[:-1].split('/')[0]:
        return digits in re.sub(r'\D', '', source)          # phone numbers: any formatting
    bare = re.sub(r'^(https?://)?(www\.)?', '', piece.casefold()).rstrip('/')
    return bare in normalize(source).replace('https://', '').replace('http://', '').replace('www.', '')


BULLET_SUPPORT = 0.8      # extracted bullets are copied, not written: 80% of their words must be in the file


def verify_extraction(data: dict, source: str) -> tuple[dict, dict]:
    """Remove anything the extraction step produced that the uploaded file does
    not contain, and report what was removed. Identifying facts (employers,
    roles, schools, degrees, certifications, project names) must match the file
    word for word; bullets must be copied, not written."""
    tokens = _tokens(source)
    report = {'removed_roles': 0, 'removed_bullets': 0, 'removed_projects': 0, 'removed_education': 0,
              'removed_certifications': 0, 'removed_skills': 0, 'cleared_fields': 0}
    out = dict(data)

    if not _supported(out.get('name'), tokens):
        raise ValueError('The name on the resume could not be confirmed from the file. Please upload the original file.')
    pieces = [p for p in re.split(r'\s*[|•·,;]\s*|\s{2,}', str(out.get('contact') or '')) if p.strip()]
    kept = [p for p in pieces if _contact_piece_supported(p, source)]
    report['cleared_fields'] += len(pieces) - len(kept)
    out['contact'] = ' | '.join(kept)
    for field in ('title', 'summary', 'additional_information'):
        minimum = 1.0 if field == 'title' else BULLET_SUPPORT
        if out.get(field) and not _supported(out[field], tokens, minimum):
            out[field] = ''
            report['cleared_fields'] += 1

    def bullets(items):
        items = [b for b in (items or []) if isinstance(b, str)]
        good = [b for b in items if _supported(b, tokens, BULLET_SUPPORT) and _digits_supported(b, source)]
        report['removed_bullets'] += len(items) - len(good)
        return good

    roles = []
    for job in out.get('experience') or []:
        if not (_supported(job.get('role'), tokens) and _supported(job.get('company'), tokens)):
            report['removed_roles'] += 1
            continue
        job = dict(job)
        if not _digits_supported(job.get('dates'), source):
            job['dates'] = ''
            report['cleared_fields'] += 1
        for field in ('location', 'environment'):
            if job.get(field) and not _supported(job[field], tokens):
                job[field] = ''
                report['cleared_fields'] += 1
        job['bullets'] = bullets(job.get('bullets'))
        roles.append(job)
    out['experience'] = roles

    projects = []
    for project in out.get('projects') or []:
        if not _supported(project.get('title'), tokens):
            report['removed_projects'] += 1
            continue
        project = dict(project)
        for field in ('subtitle', 'tech'):
            if project.get(field) and not _supported(project[field], tokens):
                project[field] = ''
                report['cleared_fields'] += 1
        project['bullets'] = bullets(project.get('bullets'))
        projects.append(project)
    out['projects'] = projects

    schools = []
    for school in out.get('education') or []:
        if not (_supported(school.get('degree'), tokens) and _supported(school.get('institution'), tokens)):
            report['removed_education'] += 1
            continue
        school = dict(school)
        if not _digits_supported(school.get('year'), source):
            school['year'] = ''
            report['cleared_fields'] += 1
        schools.append(school)
    out['education'] = schools

    certs = [c for c in out.get('certifications') or [] if isinstance(c, str) and _supported(c, tokens)
             and _digits_supported(c, source)]
    report['removed_certifications'] = len(out.get('certifications') or []) - len(certs)
    out['certifications'] = certs

    skills = {}
    for category, values in (out.get('skills') or {}).items():
        good = [v for v in values if isinstance(v, str) and contains(source, v)]
        report['removed_skills'] += len(values) - len(good)
        if good:
            skills[category] = good
    out['skills'] = skills
    report['total_removed'] = sum(v for k, v in report.items() if k != 'total_removed')
    return validate_resume(out), report


# Claims of leadership or scope that must already be in the source for that role.
_LEADERSHIP = re.compile(
    r'\b(led|lead|leading|leads|managed|manage|manages|managing|manager|mentor|mentored|mentoring|mentors|'
    r'supervis\w*|oversaw|oversee\w*|spearhead\w*|head(?:ed)?|directed|direct reports?|team of|hired|hiring|'
    r'budget\w*|p&l|stakeholders?|cross functional|cross-functional)\b')
_SENIORITY = re.compile(r'\b(senior|sr|principal|staff|lead|head|chief|expert|architect|director|veteran|seasoned)\b')
# Words that name something specific: capitalised or containing digits/symbols.
_NAMED = re.compile(r"(?<![\w.])([A-Z][A-Za-z0-9+#.&'-]*[A-Za-z0-9+#]|[A-Za-z]*\d[A-Za-z0-9+#.]*|[a-z]+[+#]+)")


def _new_names(new_text, source) -> list:
    """Specific names (products, companies, acronyms) in new text that the source never mentions."""
    unknown = []
    for sentence in re.split(r'(?<=[.!?;:])\s+|\n', str(new_text or '')):
        words = sentence.strip().split()
        for index, match in enumerate(_NAMED.finditer(sentence.strip())):
            word = match.group(1).rstrip('.')
            # The first word of a sentence is capitalised for grammar, not because it is a name.
            if index == 0 and sentence.strip().startswith(word) and word[1:].islower() and not any(c.isdigit() for c in word):
                continue
            if len(word) < 2 or word.casefold() in _STOPWORDS:
                continue
            if not contains(source, word):
                unknown.append(word)
    return unknown


def _unsupported_claims(new_text, evidence_text, source) -> bool:
    """Leadership or seniority claims are allowed only when the evidence already makes them."""
    new, evidence = normalize(new_text), normalize(evidence_text)
    if _LEADERSHIP.search(new) and not _LEADERSHIP.search(evidence):
        return True
    return bool(set(_SENIORITY.findall(new)) - set(_SENIORITY.findall(normalize(source))))


_NUMBER = re.compile(r'\d+(?:[.,]\d+)*(?:\s*%)?')


def _numbers(text):
    return {normalize(n) for n in _NUMBER.findall(str(text or ''))}


def _introduces_claims(new_text, allowed_numbers, source_terms):
    """True when tailored text adds a number or a named tool/practice the source lacks."""
    return not _numbers(new_text) <= allowed_numbers or not set(find_terms(new_text)) <= source_terms


def merge_rewrite(original, rewritten, source):
    """Keep history, omit unsupported skill additions, revert invented claims.

    A tailored summary or role that adds a number or a tool absent from the
    source falls back to the original text instead of failing the upload.
    Removed skill additions become review questions; ``rewrite_guard`` in the
    rewrite metadata records what was reverted.
    """
    result = dict(original)
    experiences = rewritten.get('optimized_experience')
    if not isinstance(experiences, list) or len(experiences) != len(original['experience']):
        raise ValueError('Rewrite omitted experience entries.')
    source_numbers = _numbers(source)
    source_terms = set(find_terms(source))
    guard = {'summary_reverted': False, 'roles_reverted': 0}
    guarded = []
    for old, new in zip(original['experience'], experiences):
        for key in ('role', 'company', 'dates'):
            if normalize(old.get(key)) != normalize(new.get(key)):
                raise ValueError(f'Rewrite changed an employment {key}.')
        if not isinstance(new.get('bullets'), list) or not new['bullets'] or \
                any(not isinstance(b, str) for b in new['bullets']):
            raise ValueError('Rewrite omitted employment details.')
        # Everything in a role's bullets must be evidenced by that same role:
        # numbers, tools and leadership claims stay with the employer they were
        # written for, and no new names (products, clients, acronyms) appear.
        role_text = ' '.join([str(old.get('role', '')), str(old.get('environment', '')), *old.get('bullets', [])])
        new_text = ' '.join(new['bullets'])
        if (_introduces_claims(new_text, _numbers(role_text), set(find_terms(role_text)))
                or _new_names(new_text, role_text + ' ' + ' '.join(skill for values in original['skills'].values() for skill in values
                                                                    if contains(role_text, skill)))
                or _unsupported_claims(new_text, role_text, role_text)):
            new = {**new, 'bullets': list(old.get('bullets', []))}
            guard['roles_reverted'] += 1
        guarded.append(new)
    experiences = guarded
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
    if not isinstance(summary, str):
        summary = original.get('summary', '')
    if summary != original.get('summary', '') and (
            _introduces_claims(summary, source_numbers, source_terms) or _new_names(summary, source)
            or _unsupported_claims(summary, source, source)):
        summary = original.get('summary', '')
        guard['summary_reverted'] = True
    rewritten['rewrite_guard'] = guard
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
