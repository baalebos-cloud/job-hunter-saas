"""Requirement scoring with equivalences, skill/question split, categorised confirmed skills,
and the wider job-family taxonomy."""
import pytest

from backend.app.utils.pdf_generator import merge_confirmed_keywords
from backend.app.utils.resume_quality import is_skill_phrase, score_requirements, split_missing
from backend.app.utils.skill_terms import SKILL_CATEGORIES, find_terms

JD = ('We need 5+ years of DevOps experience, a Bachelor\'s degree in Computer Science or related field, '
      'Terraform, and a Master\'s degree in Data Science. 3 years of nursing experience. A PhD in Physics.')


def req(*phrases):
    return [{'phrase': p, 'priority': 'required'} for p in phrases]


def detail(result, phrase):
    return next(d for d in result['requirements'] if d['requirement'] == phrase)


def test_more_years_meet_a_years_requirement_in_the_same_field():
    resume = 'Summary\nDevOps engineer with 7 years of DevOps experience on AWS.\nSkills: Terraform'
    result = score_requirements(resume, JD, req('5+ years of DevOps experience', 'Terraform'))
    years = detail(result, '5+ years of DevOps experience')
    assert years['matched'] and years['match'] == 'equivalent' and '7 years' in years['evidence']
    assert detail(result, 'Terraform')['match'] == 'exact'
    assert result['breakdown'] == {'exact': 1, 'equivalent': 1, 'missing': 0}
    assert result['overall_score'] == 100.0


def test_fewer_years_or_another_field_do_not_count():
    assert not detail(score_requirements('DevOps engineer, 3 years of DevOps.', JD, req('5+ years of DevOps experience')),
                      '5+ years of DevOps experience')['matched']
    # Seven years, but of nursing: does not meet a DevOps requirement.
    assert not detail(score_requirements('Registered nurse with 7 years of nursing experience.', JD,
                                         req('5+ years of DevOps experience')), '5+ years of DevOps experience')['matched']


@pytest.mark.parametrize('line', ['MSc Computer Science, University of Lagos', 'B.Eng Computer Engineering, UNILAG',
                                  'HND Computer Science, Yaba College of Technology', 'B.Sc. Information Technology',
                                  'PhD Computer Science'])
def test_degree_levels_and_equivalents_meet_a_bachelors(line):
    phrase = "Bachelor's degree in Computer Science or related field"
    d = detail(score_requirements(f'Education\n{line}', JD, req(phrase)), phrase)
    assert d['matched'] and d['match'] == 'equivalent' and d['evidence'] == line


def test_a_lower_degree_does_not_meet_a_higher_one():
    phrase = "Master's degree in Data Science"
    assert not detail(score_requirements('BSc Data Science, University of Ibadan', JD, req(phrase)), phrase)['matched']
    assert detail(score_requirements('MSc Data Science, University of Ibadan', JD, req(phrase)), phrase)['matched']
    assert not detail(score_requirements('MSc Physics', JD, req('A PhD in Physics')), 'A PhD in Physics')['matched']


def test_degree_in_an_unrelated_named_field_does_not_count():
    phrase = "Master's degree in Data Science"
    assert not detail(score_requirements('MSc History of Art', JD, req(phrase)), phrase)['matched']


@pytest.mark.parametrize('phrase, skill', [
    ('Terraform', True), ('AWS Certified Solutions Architect', True), ('Power BI', True), ('IFRS', True),
    ('5+ years of experience with Kubernetes', False), ("Bachelor's degree in Computer Science", False),
    ('Must be authorized to work in the US', False), ('Excellent communication skills', False),
    ('Willing to travel up to 25%', False), ('Experience with distributed systems and event-driven design.', False),
])
def test_only_short_skills_are_offered_as_tick_boxes(phrase, skill):
    assert is_skill_phrase(phrase) is skill


def test_non_skill_requirements_become_questions():
    skills, questions = split_missing(['Terraform', 'Must be authorized to work in the US', 'Helm'])
    assert skills == ['Terraform', 'Helm']
    assert len(questions) == 1 and 'Must be authorized to work in the US' in questions[0]
    assert 'not added for you' in questions[0]


def test_confirmed_keywords_go_into_the_matching_skill_group():
    data = {'name': 'Ada', 'contact': 'ada@example.org',
            'skills': {'Cloud Platforms': ['AWS'], 'Pipelines': ['GitHub Actions'], 'Languages': ['Python']}}
    out = merge_confirmed_keywords(data, ['GCP', 'Jenkins', 'Snowflake', 'Communication'])
    assert out['skills']['Cloud Platforms'] == ['AWS', 'GCP']          # same category as AWS
    assert out['skills']['Pipelines'] == ['GitHub Actions', 'Jenkins']  # same category as GitHub Actions
    assert out['skills']['Data & ML'] == ['Snowflake']                  # new group named after its category
    assert out['skills']['Additional Skills'] == ['Communication']      # not in the taxonomy
    assert 'Additional Skills' not in merge_confirmed_keywords(data, ['GCP'])['skills']


def test_a_resume_with_one_skills_list_keeps_one_list():
    data = {'name': 'Ada', 'contact': 'ada@example.org', 'skills': {'Skills': ['AWS']}}
    assert merge_confirmed_keywords(data, ['GCP'])['skills'] == {'Skills': ['AWS', 'GCP']}


@pytest.mark.parametrize('text, term', [
    ('Built dashboards in Tableau and Power BI', 'Power BI'), ('Prepared statements under IFRS', 'IFRS'),
    ('Managed Salesforce pipeline', 'Salesforce'), ('Charted in Epic Systems EHR', 'EHR'),
    ('Ran HR on Workday', 'Workday HCM'), ('Lean Six Sigma Green Belt', 'Six Sigma'), ('PRINCE2 Practitioner', 'PRINCE2'),
])
def test_job_families_beyond_engineering_are_recognised(text, term):
    assert term in find_terms(text)
    assert SKILL_CATEGORIES[term]


@pytest.mark.parametrize('text', ['I excel at stakeholder work', 'a lean team', 'an epic project', 'a long workday'])
def test_ordinary_words_are_not_mistaken_for_tools(text):
    assert find_terms(text) == []


def test_invented_tool_from_a_new_job_family_is_reverted():
    from backend.test.test_no_hallucination import SOURCE, extracted, rewrite
    from backend.app.utils.resume_quality import merge_rewrite
    base, out = rewrite(role0=['Built CI/CD pipelines with GitHub Actions and reported results in Power BI.'])
    result = merge_rewrite(base, out, SOURCE)
    assert result['experience'][0]['bullets'] == [extracted()['experience'][0]['bullets'][0]]
    assert 'Power BI' in out['rewrite_guard']['reverted'][0]['reason']
