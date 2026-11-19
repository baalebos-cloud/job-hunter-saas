"""Regenerate the sample resume exports in this folder.

Run from the repository root:  python docs/resume-samples/generate.py
Needs pdftoppm (poppler-utils) for the PNG previews. All candidates are fictional.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.utils.pdf_generator import download_filename, export_resume  # noqa: E402

NG = {
    'name': 'Ọlájídé Ẹ̀bùn Adéwálé', 'title': 'DevOps Engineer',
    'contact': 'olajide.adewale@example.com | +234 803 000 0000 | Lagos, Nigeria | linkedin.com/in/olajide-adewale',
    'summary': ('DevOps engineer with five years of experience automating cloud infrastructure on AWS, building CI/CD '
                'pipelines and supporting Python services for fintech teams in Lagos.'),
    'experience': [
        {'role': 'DevOps Engineer', 'company': 'Ìtàn Payments Ltd', 'location': 'Lagos, Nigeria',
         'dates': 'March 2021 – Present', 'environment': '', 'bullets': [
             'CI/CD pipelines: Built and maintained CI/CD pipelines in GitHub Actions for 14 Python microservices.',
             'Cloud migration: Migrated legacy virtual machines to AWS ECS, reducing monthly infrastructure cost by 30%.',
             'Wrote runbooks and led on-call R&D reviews for incidents with <5s alert latency.',
             'Mentored two junior engineers in Linux administration and Bash scripting.']},
        {'role': 'Systems Administrator', 'company': 'Ọ̀yọ́ Data Services', 'location': 'Ìbàdàn, Nigeria',
         'dates': 'Jan 2018 to Feb 2021', 'environment': 'Linux, Bash, cron', 'bullets': [
             'Administered 60 Linux servers across two data centres in Ìbàdàn and Lagos.',
             'Automated backups with Bash and cron, cutting restore time from hours to minutes.',
             'Supported Python reporting scripts used by the finance team.']},
    ],
    'projects': [{'title': 'Infrastructure monitoring dashboard', 'subtitle': 'Internal uptime visibility',
                  'tech': 'Python, Grafana, Prometheus',
                  'bullets': ['Built dashboards that track uptime for internal services.']}],
    'skills': {'Cloud': ['AWS', 'ECS', 'S3'], 'Automation': ['GitHub Actions', 'Bash', 'Python'],
               'Systems': ['Linux', 'Prometheus', 'Grafana']},
    'education': [{'degree': 'BSc Computer Science', 'institution': 'Obafemi Awolowo University, Ilé-Ifẹ̀', 'year': '2017'}],
    'certifications': ['AWS Certified Solutions Architect - Associate', 'Linux Professional Institute LPIC-1'],
    'additional_information': 'Languages: English, Yorùbá',
}

US = {
    'name': 'Jane Doe', 'title': 'Backend Software Engineer',
    'contact': 'jane.doe@example.com | (512) 555-0147 | Austin, TX, USA | github.com/janedoe',
    'summary': 'Backend engineer with six years of experience building Python APIs and data pipelines on AWS for B2B SaaS products.',
    'experience': [
        {'role': 'Senior Software Engineer', 'company': 'Northwind Analytics', 'location': 'Austin, TX',
         'dates': 'Jun 2020 - Present', 'environment': '', 'bullets': [
             'Designed FastAPI services handling 2 million requests per day.',
             'Led migration of batch jobs to AWS Lambda and Step Functions.',
             'Introduced contract tests that cut production regressions by half.']},
        {'role': 'Software Engineer', 'company': 'Contoso Health', 'location': 'Remote',
         'dates': 'Aug 2017 - May 2020', 'environment': '', 'bullets': [
             'Built HL7 integration services in Python and PostgreSQL.',
             'Improved query performance on reporting endpoints by adding indexes.']},
    ],
    'projects': [], 'certifications': [],
    'skills': {'Languages': ['Python', 'SQL', 'TypeScript'], 'Cloud': ['AWS', 'Lambda', 'PostgreSQL']},
    'education': [{'degree': 'BS Computer Science', 'institution': 'University of Texas at Austin', 'year': '2017'}],
    # Removed from the US export by convention; kept in the source to show that.
    'additional_information': 'Date of Birth: 14 May 1993',
}


def main():
    out = Path(__file__).resolve().parent
    for data, region, size in ((NG, 'NG', 'A4'), (US, 'US', 'Letter')):
        result = export_resume(data, region=region)
        stem = download_filename(data['name'])[0].removesuffix('.pdf') + f'_{region}_{size}'
        (out / f'{stem}.pdf').write_bytes(result.pdf)
        subprocess.run(['pdftoppm', '-r', '110', '-png', '-singlefile', str(out / f'{stem}.pdf'), str(out / stem)], check=True)
        print(stem, result.info())


if __name__ == '__main__':
    main()
