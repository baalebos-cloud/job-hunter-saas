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
    # Beyond engineering: data, product, finance, healthcare, sales/marketing, operations and HR.
    {'power bi', 'powerbi'}, {'microsoft excel', 'ms excel', 'excel'}, {'project management professional', 'pmp'},
    {'objectives and key results', 'okrs', 'okr'}, {'key performance indicators', 'kpis', 'kpi'},
    {'international financial reporting standards', 'ifrs'}, {'generally accepted accounting principles', 'gaap'},
    {'certified public accountant', 'cpa'}, {'chartered financial analyst', 'cfa'},
    {'financial modeling', 'financial modelling'}, {'electronic health records', 'electronic health record', 'ehr'},
    {'electronic medical records', 'emr'}, {'basic life support', 'bls'}, {'advanced cardiovascular life support', 'acls'},
    {'search engine optimization', 'search engine optimisation', 'seo'}, {'search engine marketing', 'sem'},
    {'customer relationship management', 'crm'}, {'google analytics', 'ga4'}, {'google ads', 'adwords'},
    {'human resources', 'hr'}, {'lean six sigma', 'six sigma'},
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


# Seniority prefixes that would claim a level: kept in the headline only when
# the resume already shows that level somewhere.
_LEVEL_PREFIX = re.compile(r'^(?:(senior|sr\.?|staff|principal|lead|chief|distinguished|head of)\s+)+', re.I)
_TITLE_NOISE = re.compile(r'\s+(?:[-–—|/(:@]|\bat\b).*$', re.I)


def target_headline(job_title, source, fallback=''):
    """The resume headline for a tailored resume: the job's own role title.

    "Staff System Architect - SNSPD Systems" -> "System Architect" for a resume
    that never shows staff-level work; "Senior DevOps Engineer (Remote)" stays
    "Senior DevOps Engineer" when the resume already says Senior. Falls back to
    the resume's own title when the job title is unusable."""
    title = re.sub(r'\s+', ' ', str(job_title or '')).strip()
    title = _TITLE_NOISE.sub('', title).strip(' -–—|,') if len(title) > 3 else title
    words = normalize(source)
    match = _LEVEL_PREFIX.match(title)
    if match:
        claimed = [w.lower().rstrip('.') for w in re.findall(r'senior|sr\.?|staff|principal|lead|chief|distinguished|head', match.group(0), re.I)]
        claimed = ['senior' if w == 'sr' else w for w in claimed]
        if any(not re.search(rf'\b{w}\b', words) for w in claimed):
            title = title[match.end():].strip()
    if not (3 <= len(title) <= 80) or not re.search(r'[A-Za-z]', title):
        return fallback
    return title[0].upper() + title[1:]


_DASHES = re.compile(r'\s*[\u2010-\u2015\u2212-]\s*')


def _identity(value) -> str:
    """Role, company or dates compared without formatting: "&"/"and", dash styles,
    spacing and trailing punctuation do not count as a change."""
    text = _fold(value).replace('&', ' and ')
    text = _DASHES.sub('-', text)
    text = re.sub(r'[.,;:]+(?=\s|$)', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def _bullet_problem(bullet, role_text, role_numbers, role_terms, name_source):
    """Why a rewritten bullet cannot be used, in words a candidate understands; None if it can."""
    extra_numbers = _numbers(bullet) - role_numbers
    if extra_numbers:
        return f'it added a number this role does not mention ({", ".join(sorted(extra_numbers)[:3])})'
    extra_terms = set(find_terms(bullet)) - role_terms
    if extra_terms:
        return f'it named a tool or practice this role does not mention ({", ".join(sorted(extra_terms)[:3])})'
    names = _new_names(bullet, name_source)
    if names:
        return f'it named something your resume does not mention ({", ".join(names[:3])})'
    if _unsupported_claims(bullet, role_text, role_text):
        return 'it claimed leadership or seniority this role does not show'
    return None


def _pair(new_bullets, old_bullets):
    """Index of the source bullet each rewritten bullet came from (None when unknown).

    Matched by shared words, not position, so reordered bullets pair correctly."""
    pairs, used = [], set()
    for bullet in new_bullets:
        words = _content(bullet)
        scored = [(len(words & _content(old)) / max(1, len(words | _content(old))), i)
                  for i, old in enumerate(old_bullets) if i not in used]
        best = max(scored, default=(0, None))
        if best[1] is not None and best[0] > 0:
            used.add(best[1])
            pairs.append(best[1])
        else:
            pairs.append(None)
    return pairs


def _guard_bullets(old, new_bullets, check):
    """Keep each rewritten bullet that passes ``check``; put back the source bullet for one that fails.

    Returns (bullets, [(reason, kept_text_or_None)])."""
    sources = list(old.get('bullets', []))
    result, reverted, used = [], [], set()
    for bullet, index in zip(new_bullets, _pair(new_bullets, sources)):
        reason = check(bullet)
        if reason is None:
            result.append(bullet)
            continue
        original = sources[index] if index is not None and index not in used else None
        if original is not None:
            used.add(index)
            result.append(original)
        reverted.append((reason, original))
    return result, reverted


def merge_rewrite(original, rewritten, source, target_title=''):
    """Keep history, omit unsupported skill additions, revert invented claims.

    A tailored bullet that adds a number, tool, name or leadership claim absent
    from that role's source falls back to its own source bullet; the other
    bullets of the role keep their tailoring. A summary that does the same falls
    back to the original summary. Removed skill additions become review
    questions; ``rewrite_guard`` records each reverted bullet and why.
    """
    result = dict(original)
    experiences = rewritten.get('optimized_experience')
    if not isinstance(experiences, list) or len(experiences) != len(original['experience']):
        raise ValueError('Rewrite omitted experience entries.')
    source_numbers = _numbers(source)
    source_terms = set(find_terms(source))
    guard = {'summary_reverted': False, 'roles_reverted': 0, 'bullets_reverted': 0, 'reverted': []}
    guarded = []
    for old, new in zip(original['experience'], experiences):
        for key in ('role', 'company', 'dates'):
            if _identity(old.get(key)) != _identity(new.get(key)):
                raise ValueError(f'Rewrite changed an employment {key}.')
        if not isinstance(new.get('bullets'), list) or not new['bullets'] or \
                any(not isinstance(b, str) for b in new['bullets']):
            raise ValueError('Rewrite omitted employment details.')
        # Everything in a role's bullets must be evidenced by that same role:
        # numbers, tools and leadership claims stay with the employer they were
        # written for, and no new names (products, clients, acronyms) appear.
        role_text = ' '.join([str(old.get('role', '')), str(old.get('environment', '')), *old.get('bullets', [])])
        role_numbers, role_terms = _numbers(role_text), set(find_terms(role_text))
        name_source = role_text + ' ' + ' '.join(skill for values in original['skills'].values() for skill in values
                                                 if contains(role_text, skill))
        bullets, reverted = _guard_bullets(
            old, new['bullets'], lambda b: _bullet_problem(b, role_text, role_numbers, role_terms, name_source))
        _record_reverted(guard, old, reverted)
        guarded.append({**new, 'bullets': bullets})
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
    # The summary may name the role being applied for ("seeking a System
    # Architect role"); everything else must come from the resume.
    summary_source = f'{source}\n{target_title}' if target_title else source
    if summary != original.get('summary', '') and (
            _introduces_claims(summary, source_numbers, source_terms) or _new_names(summary, summary_source)
            or _unsupported_claims(summary, source, summary_source)):
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
            guard['summary_reverted'] = True
        checked = []
        for old, new in zip(original['experience'], experiences):
            def mentions_excluded(bullet):
                found = [skill for skill in excluded if contains(bullet, skill) and not contains(' '.join(old.get('bullets', [])), skill)]
                return f'it mentioned a skill your resume does not show ({", ".join(found[:3])})' if found else None
            bullets, reverted = _guard_bullets(old, new['bullets'], mentions_excluded)
            _record_reverted(guard, old, reverted)
            checked.append({**new, 'bullets': bullets})
        experiences = checked
    generated = str(summary) + ' ' + ' '.join(' '.join(e['bullets']) for e in experiences)
    for number in re.findall(r'\d+(?:[.,]\d+)*(?:\s*%)?', generated):
        if normalize(number) not in source_numbers:
            raise ValueError('Rewrite introduced an unsupported numeric achievement.')
    result.update(summary=summary, experience=[{**old, 'bullets': new['bullets']} for old,new in zip(original['experience'], experiences)], skills=skills)
    return validate_resume(result)


def _record_reverted(guard, role, reverted):
    if not reverted:
        return
    already = any(r['role'] == role.get('role') and r['company'] == role.get('company') for r in guard['reverted'])
    guard['roles_reverted'] += 0 if already else 1
    guard['bullets_reverted'] += len(reverted)
    for reason, kept in reverted:
        guard['reverted'].append({'role': role.get('role', ''), 'company': role.get('company', ''), 'reason': reason,
                                  'kept': kept or ''})


# ── Requirements: skills to confirm vs. other conditions ─────────────────────
_NON_SKILL = re.compile(
    r"\b(years?|yrs|degree|bachelor'?s?|master'?s?|ph\.?d|doctorate|diploma|graduate|authori[sz]ed|authori[sz]ation|"
    r"eligib\w*|visa|sponsor\w*|clearance|citizen\w*|relocat\w*|travel|willing|able to|ability to|must|should|"
    r"required|preferred|proficien\w*|knowledge of|understanding of|familiar\w*|strong|excellent|fluent|native|"
    r"background check|driver'?s licen[cs]e|experience (?:in|with|of)|hands-on|track record)\b", re.I)


def is_skill_phrase(phrase) -> bool:
    """A short skill, tool or certification a candidate can tick, not a condition or sentence."""
    text = str(phrase or '').strip()
    if not text or len(text) > 40 or len(text.split()) > 5 or text.endswith('.'):
        return False
    return not _NON_SKILL.search(text)


def split_missing(missing) -> tuple[list[str], list[str]]:
    """Missing requirements as (skills to offer as tick boxes, questions for everything else)."""
    skills, questions = [], []
    for phrase in missing or []:
        if not isinstance(phrase, str) or not phrase.strip():
            continue
        if is_skill_phrase(phrase):
            skills.append(phrase.strip())
        else:
            questions.append(f'The job asks for: "{phrase.strip()}". If that is true for you, add it to your resume '
                             'in your own words; it was not added for you.')
    return skills, questions


# ── Scoring ──────────────────────────────────────────────────────────────────
_YEARS = re.compile(r'(\d{1,2})\s*\+?\s*(?:years?|yrs)\b', re.I)
# Degree levels: a higher level satisfies a lower one. HND and B.Eng/B.Tech count as bachelor-level.
_DEGREE_LEVELS = (
    (3, re.compile(r"\b(ph\.?\s?d|doctorate|doctoral|d\.?phil)\b", re.I)),
    (2, re.compile(r"\b(master'?s?|m\.?\s?sc|m\.?\s?eng|m\.?\s?tech|mba|m\.?a\.|m\.?s\.|msc|meng|mphil)\b", re.I)),
    (1, re.compile(r"\b(bachelor'?s?|b\.?\s?sc|b\.?\s?eng|b\.?\s?tech|b\.?a\.|b\.?s\.|bsc|beng|btech|hnd|"
                   r"higher national diploma|undergraduate degree|university degree)\b", re.I)),
)
_YEARS_FILLER = {'years', 'year', 'yrs', 'experience', 'minimum', 'least', 'plus', 'professional', 'relevant',
                 'work', 'working', 'hands', 'on', 'proven', 'industry', 'demonstrated', 'over', 'more'}
_DEGREE_FILLER = {'degree', 'bachelor', "bachelor's", 'bachelors', 'master', "master's", 'masters', 'equivalent',
                  'related', 'field', 'similar', 'discipline', 'relevant', 'university', 'phd', 'or', 'bsc', 'msc',
                  'ba', 'bs', 'ms', 'technical', 'quantitative', 'preferred', 'required'}


def _degree_level(text) -> int:
    return max((level for level, pattern in _DEGREE_LEVELS if pattern.search(str(text or ''))), default=0)


def _field_matches(phrase, line, filler) -> bool:
    """The requirement names no field, says "related field", or the line shares a field word."""
    words = {w for w in _content(phrase) if not w.isdigit()} - filler
    if not words or re.search(r'\b(related|equivalent|similar)\b', phrase, re.I):
        return True
    return bool(words & _tokens(line))


def _equivalent_evidence(phrase, resume_text) -> str:
    """A resume line that meets the requirement by a recognised equivalence, or ''."""
    lines = [line.strip() for line in str(resume_text or '').splitlines() if line.strip()]
    needed = _YEARS.search(phrase)
    if needed:
        for line in lines:
            if any(int(y) >= int(needed.group(1)) for y in _YEARS.findall(line)) and _field_matches(phrase, line, _YEARS_FILLER):
                return line
        return ''
    level = _degree_level(phrase)
    if level or re.search(r'\bdegree\b', phrase, re.I):
        level = level or 1
        for line in lines:
            if _degree_level(line) >= level and _field_matches(phrase, line, _DEGREE_FILLER):
                return line
    return ''


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
        evidence = next((line.strip() for line in resume_text.splitlines() if contains(line, phrase)), '')
        match = 'exact' if contains(resume_text, phrase) else None
        if not match:
            evidence = _equivalent_evidence(phrase, resume_text)
            match = 'equivalent' if evidence else None
        details.append({'requirement': phrase, 'priority': 'required' if required else 'preferred',
                        'matched': bool(match), 'match': match, 'weight': 2 if required else 1,
                        'evidence': evidence[:500]})
    if not details:
        raise ValueError('No verifiable job requirements could be extracted.')
    weight = sum(d['weight'] for d in details)
    matched = [d for d in details if d['matched']]
    score = round(100 * sum(d['weight'] for d in matched) / weight, 1)
    return {'overall_score': score, 'keywords_matched': len(matched), 'keywords_missing': len(details)-len(matched),
            'total_keywords': len(details), 'missing_list': [d['requirement'] for d in details if not d['matched']],
            'requirements': details,
            'breakdown': {'exact': sum(1 for d in details if d['match'] == 'exact'),
                          'equivalent': sum(1 for d in details if d['match'] == 'equivalent'),
                          'missing': len(details) - len(matched)},
            'scoring_method': ('Weighted requirement coverage v2: required=2, preferred=1. A requirement counts when the '
                               'resume states it (exact) or meets it by a recognised equivalent (e.g. 7 years for '
                               '"5+ years", an MSc for a bachelor\'s degree, B.Eng/B.Sc/HND for a bachelor\'s); '
                               'other paraphrases may be missed.'),
            'score_notice': 'Baalebos assessment of documented coverage, not an employer ATS score or interview guarantee.',
            'suggestions': ['Confirm relevant missing qualifications before adding them.', 'Use only achievements and metrics you can substantiate.']}
