import type { ResumeData } from '../types';

export function sampleResume(): ResumeData {
  return {
    fullName: 'Jordan Lee',
    headline: 'Cloud DevOps Engineer | AWS · Terraform · Kubernetes · CI/CD',
    location: 'Lagos, Nigeria', phone: '+234 801 555 0101', email: 'jordan.lee@example.org',
    linkedin: 'linkedin.com/in/jordanlee', github: 'github.com/jordanlee', portfolio: '',
    summary: 'Cloud DevOps engineer automating infrastructure on AWS and GCP with Terraform and Ansible. Cut deployment failures by 30% and reduced manual operational toil by 80% across 40 services.',
    coreCompetencies: ['Team communication', 'AWS (EC2, VPC, IAM, S3, Lambda)', 'Infrastructure as Code (Terraform, Ansible)',
      'CI/CD (GitHub Actions, Jenkins)', 'Docker and Kubernetes', 'Linux administration', 'Python and Bash scripting'],
    softSkills: ['Cross-functional collaboration', 'Root-cause problem solving', 'Clear written documentation'],
    projectsIntro: 'Selected projects built and run in production.',
    projects: [{ title: 'Job board scraper', tech: 'Python, FastAPI, PostgreSQL', description: 'Collects 700+ listings a day with 99% uptime.' },
      { title: 'Platform landing zone', tech: 'Terraform, AWS', description: 'Multi-account AWS setup with IAM guardrails for 6 teams.' }],
    technicalSkills: [{ label: 'Frontend', items: ['React', 'Tailwind'] },
      { label: 'Cloud', items: ['AWS', 'GCP', 'CloudWatch', 'CloudTrail'] },
      { label: 'Automation', items: ['Terraform', 'Ansible', 'GitHub Actions', 'Jenkins', 'Docker', 'Kubernetes'] }],
    experience: [{ role: 'DevOps Engineer', company: 'Litware', location: 'Lagos', dates: 'Jan 2022 – Present',
      bullets: ['Wrote onboarding guides for new engineers.', 'Migrated 40 services to Kubernetes on AWS EKS, cutting hosting cost by 28%.',
        'Built CI/CD pipelines with GitHub Actions that cut release time by 60%.'] },
    { role: 'Cloud Engineer', company: 'Adatum', location: 'Remote', dates: '2019 – 2021',
      bullets: ['Set up Prometheus and Grafana monitoring for 120 hosts.', 'Automated Linux patching with Ansible.'] }],
    education: [{ degree: 'B.Sc. Computer Science', institution: 'University of Lagos', date: '2018' }],
    certifications: [{ name: 'AWS Certified Cloud Practitioner (CLF-C02)', issuer: 'Amazon Web Services', date: '2024' }],
  };
}
