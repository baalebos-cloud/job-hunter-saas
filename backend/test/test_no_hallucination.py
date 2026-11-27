"""The resume AI must not invent anything: every fact in the final resume has to
be traceable to the uploaded file. These tests feed the guards the kinds of
fabrication language models actually produce and check each one is removed,
while honest rewording is kept."""
import copy

import pytest

from backend.app.utils.resume_quality import merge_rewrite, verify_extraction

SOURCE = """Ọlájídé Adéwálé
DevOps Engineer
olajide@example.com | +234 803 123 4567 | linkedin.com/in/olajide
Summary
DevOps engineer focused on reliable cloud platforms and automation.
Experience
DevOps Engineer, Contoso Ltd, Lagos, Nigeria, Jan 2021 - Present
- Built CI/CD pipelines with GitHub Actions that cut release time by 40%.
- Ran production workloads on K8s and Terraform across three AWS accounts.
Systems Administrator, Fabrikam, 2018 - 2020
- Maintained Linux servers and wrote Bash scripts for nightly backups.
Projects
Cost Dashboard - Grafana dashboards for cloud spend
- Collected billing data with Python and showed it in Grafana.
Skills
Cloud: AWS, Terraform, K8s
Tooling: GitHub Actions, Python, Bash, Grafana, Linux
Education
BSc Computer Science, University of Lagos, 2017
Certifications
AWS Certified Solutions Architect - Associate
"""


def extracted():
    return {
        'name': 'Ọlájídé Adéwálé', 'title': 'DevOps Engineer',
        'contact': 'olajide@example.com | +234 803 123 4567 | linkedin.com/in/olajide',
        'summary': 'DevOps engineer focused on reliable cloud platforms and automation.',
        'experience': [
            {'role': 'DevOps Engineer', 'company': 'Contoso Ltd', 'location': 'Lagos, Nigeria', 'dates': 'Jan 2021 - Present',
             'environment': '', 'bullets': ['Built CI/CD pipelines with GitHub Actions that cut release time by 40%.',
                                            'Ran production workloads on K8s and Terraform across three AWS accounts.']},
            {'role': 'Systems Administrator', 'company': 'Fabrikam', 'location': '', 'dates': '2018 - 2020',
             'environment': '', 'bullets': ['Maintained Linux servers and wrote Bash scripts for nightly backups.']},
        ],
        'projects': [{'title': 'Cost Dashboard', 'subtitle': 'Grafana dashboards for cloud spend', 'tech': '',
                      'bullets': ['Collected billing data with Python and showed it in Grafana.']}],
        'skills': {'Cloud': ['AWS', 'Terraform', 'K8s'], 'Tooling': ['GitHub Actions', 'Python', 'Bash', 'Grafana', 'Linux']},
        'education': [{'degree': 'BSc Computer Science', 'institution': 'University of Lagos', 'year': '2017'}],
        'certifications': ['AWS Certified Solutions Architect - Associate'],
        'additional_information': '',
    }


# ── Step 1: what the model read from the file ────────────────────────────────

def test_a_faithful_extraction_is_kept_untouched():
    data, report = verify_extraction(extracted(), SOURCE)
    assert report['total_removed'] == 0
    assert data == {**extracted(), 'contact': extracted()['contact']}


@pytest.mark.parametrize('field, invented, report_key', [
    ('certifications', 'Certified Kubernetes Administrator (CKA)', 'removed_certifications'),
    ('education', {'degree': 'MSc Artificial Intelligence', 'institution': 'Stanford University', 'year': '2022'},
     'removed_education'),
    ('projects', {'title': 'Fraud Detection Platform', 'subtitle': '', 'tech': '', 'bullets': ['Built it.']},
     'removed_projects'),
    ('experience', {'role': 'Senior SRE', 'company': 'Google', 'location': '', 'dates': '2022 - 2023',
                    'environment': '', 'bullets': ['Kept Search online.']}, 'removed_roles'),
])
def test_invented_entries_are_removed(field, invented, report_key):
    data = extracted()
    data[field].append(invented)
    cleaned, report = verify_extraction(data, SOURCE)
    assert invented not in cleaned[field] and report[report_key] == 1
    assert cleaned[field] == extracted()[field]


def test_invented_bullets_skills_and_contact_details_are_removed():
    data = extracted()
    data['experience'][0]['bullets'].append('Reduced cloud costs by 35% using spot instances.')   # not in the file
    data['experience'][0]['bullets'].append('Mentored a team of five junior engineers.')           # not in the file
    data['skills']['Cloud'].append('Azure')
    data['contact'] += ' | github.com/someone-else'
    cleaned, report = verify_extraction(data, SOURCE)
    assert cleaned['experience'][0]['bullets'] == extracted()['experience'][0]['bullets']
    assert 'Azure' not in cleaned['skills']['Cloud'] and 'github.com/someone-else' not in cleaned['contact']
    assert report['removed_bullets'] == 2 and report['removed_skills'] == 1


def test_wrong_dates_are_cleared_not_kept():
    data = extracted()
    data['experience'][1]['dates'] = '2015 - 2020'          # 2015 is not in the file
    cleaned, _ = verify_extraction(data, SOURCE)
    assert cleaned['experience'][1]['dates'] == '' and cleaned['experience'][1]['company'] == 'Fabrikam'


def test_names_with_accents_and_reformatted_phone_numbers_are_accepted():
    data = extracted()
    data['name'] = 'Olajide Adewale'                         # a PDF that dropped the accents
    data['contact'] = 'olajide@example.com | +2348031234567'
    cleaned, report = verify_extraction(data, SOURCE)
    assert cleaned['name'] == 'Olajide Adewale' and '+2348031234567' in cleaned['contact']
    assert report['total_removed'] == 0


def test_a_name_that_is_not_in_the_file_stops_the_run():
    data = extracted()
    data['name'] = 'Jane Smith'
    with pytest.raises(ValueError, match='name'):
        verify_extraction(data, SOURCE)


# ── Step 2: the tailored rewrite ─────────────────────────────────────────────

def rewrite(**changes):
    base = verify_extraction(extracted(), SOURCE)[0]
    out = {'optimized_summary': base['summary'],
           'optimized_experience': [{'role': e['role'], 'company': e['company'], 'dates': e['dates'],
                                     'bullets': list(e['bullets'])} for e in base['experience']],
           'optimized_skills': copy.deepcopy(base['skills']), 'confirmation_questions': [], 'suggestions_applied': []}
    for path, value in changes.items():
        if path == 'summary':
            out['optimized_summary'] = value
        else:
            out['optimized_experience'][int(path[-1])]['bullets'] = value
    return base, out


def test_honest_rewording_is_kept():
    base, out = rewrite(
        summary='DevOps engineer focused on reliable cloud platforms, automation and Kubernetes.',
        role0=['Ran production workloads on Kubernetes and Terraform across three AWS accounts.',     # K8s -> Kubernetes
               'Built GitHub Actions CI/CD pipelines that cut release time by 40%.'])
    result = merge_rewrite(base, out, SOURCE)
    assert result['experience'][0]['bullets'][0].startswith('Ran production workloads on Kubernetes')
    assert 'Kubernetes' in result['summary']
    assert out['rewrite_guard'] == {'summary_reverted': False, 'roles_reverted': 0}


@pytest.mark.parametrize('bullets, why', [
    (['Built CI/CD pipelines with GitHub Actions that cut release time by 60%.'], 'changed number'),
    (['Wrote Python tooling for CI/CD pipelines with GitHub Actions.'], 'tool from another part of the resume'),
    (['Built CI/CD pipelines with GitHub Actions and Datadog alerting.'], 'tool not in the resume'),
    (['Built CI/CD pipelines for Fortune 500 clients with GitHub Actions.'], 'invented client name'),
    (['Led a team that built CI/CD pipelines with GitHub Actions.'], 'invented leadership'),
    (['Built CI/CD pipelines with GitHub Actions on Zorbix Cloud.'], 'unknown product name'),
])
def test_invented_claims_in_a_role_are_reverted_to_the_original(bullets, why):
    base, out = rewrite(role0=bullets)
    result = merge_rewrite(base, out, SOURCE)
    assert result['experience'][0]['bullets'] == extracted()['experience'][0]['bullets'], why
    assert out['rewrite_guard']['roles_reverted'] == 1


def test_a_tool_is_not_moved_from_one_job_to_another():
    # Terraform is in the resume, but only at Contoso: it cannot appear at Fabrikam.
    base, out = rewrite(role1=['Maintained Linux servers with Terraform and wrote Bash scripts for nightly backups.'])
    result = merge_rewrite(base, out, SOURCE)
    assert result['experience'][1]['bullets'] == extracted()['experience'][1]['bullets']


@pytest.mark.parametrize('summary', [
    'Senior DevOps engineer focused on reliable cloud platforms and automation.',       # seniority
    'DevOps engineer with 10 years of experience in cloud platforms.',                 # number
    'DevOps engineer who led platform teams at Contoso Ltd.',                            # leadership
    'DevOps engineer experienced with Azure and Terraform.',                             # tool not in resume
])
def test_invented_claims_in_the_summary_are_reverted(summary):
    base, out = rewrite(summary=summary)
    result = merge_rewrite(base, out, SOURCE)
    assert result['summary'] == extracted()['summary'] and out['rewrite_guard']['summary_reverted'] is True


def test_changing_an_employer_title_or_dates_is_refused():
    base, out = rewrite()
    out['optimized_experience'][0]['company'] = 'Contoso Global'
    with pytest.raises(ValueError, match='company'):
        merge_rewrite(base, out, SOURCE)


def test_unsupported_skills_become_questions_not_claims():
    base, out = rewrite()
    out['optimized_skills']['Cloud'].append('Azure')
    result = merge_rewrite(base, out, SOURCE)
    assert 'Azure' not in [s for values in result['skills'].values() for s in values]
    assert any('Azure' in q for q in out['confirmation_questions'])


# ── The headline names the job being applied for ────────────────────────────

from backend.app.utils.resume_quality import target_headline  # noqa: E402


@pytest.mark.parametrize('job_title, expected', [
    ('Staff System Architect -SNSPD Systems', 'System Architect'),     # no staff-level evidence: level dropped
    ('Senior Platform Engineer (Remote)', 'Platform Engineer'),
    ('Lead SRE - Payments', 'SRE'),
    ('Cloud Engineer at Contoso', 'Cloud Engineer'),
    ('DevOps Engineer | Lagos', 'DevOps Engineer'),
    ('CI/CD Engineer', 'CI/CD Engineer'),
    ('platform engineer', 'Platform engineer'),
])
def test_headline_is_the_job_role_without_unearned_seniority(job_title, expected):
    assert target_headline(job_title, SOURCE, 'DevOps Engineer') == expected


def test_seniority_is_kept_when_the_resume_shows_it():
    senior = SOURCE.replace('DevOps Engineer, Contoso Ltd', 'Senior DevOps Engineer, Contoso Ltd')
    assert target_headline('Senior Platform Engineer', senior) == 'Senior Platform Engineer'


@pytest.mark.parametrize('job_title', ['', '  ', 'X', '— —'])
def test_unusable_job_titles_keep_the_resume_title(job_title):
    assert target_headline(job_title, SOURCE, 'DevOps Engineer') == 'DevOps Engineer'


def test_summary_may_name_the_target_role_but_not_claim_it():
    base, out = rewrite(summary='DevOps engineer focused on reliable cloud platforms, seeking a Platform Engineer role.')
    assert merge_rewrite(base, out, SOURCE, 'Platform Engineer')['summary'].endswith('Platform Engineer role.')
    base, out = rewrite(summary='Principal Platform Engineer focused on reliable cloud platforms.')
    assert merge_rewrite(base, out, SOURCE, 'Platform Engineer')['summary'] == extracted()['summary']
