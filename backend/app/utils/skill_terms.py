"""Technology and practice terms, alias aware.

Used by the rewrite guard to reject tailored text that names a tool or
practice the source resume never mentions. Format of each taxonomy line:
"Category | Canonical | alias, alias, ...". An alias prefixed with "!" is
matched case-sensitively (for short words that are also common English).
"""
from __future__ import annotations

import re

_TAXONOMY_SRC = """
Cloud | AWS | amazon web services
Cloud | Azure | microsoft azure
Cloud | GCP | google cloud, google cloud platform
Cloud | Cloudflare |
Cloud | AWS Lambda | lambda, serverless
Cloud | EC2 |
Cloud | S3 | amazon s3
Cloud | RDS |
Cloud | VPC |
Cloud | Azure DevOps | ado pipelines
Infrastructure as Code | Terraform | terragrunt
Infrastructure as Code | Infrastructure as Code | iac, infrastructure-as-code
Infrastructure as Code | CloudFormation | aws cloudformation
Infrastructure as Code | Ansible |
Infrastructure as Code | Pulumi |
Infrastructure as Code | Bicep | arm templates
CI/CD | CI/CD | ci cd, cicd, ci/cd pipelines, continuous integration, continuous delivery, continuous deployment
CI/CD | GitHub Actions | github action
CI/CD | Jenkins |
CI/CD | GitLab CI | gitlab ci/cd, gitlab-ci
CI/CD | ArgoCD | argo cd
CI/CD | GitOps |
Containers & Orchestration | Docker | dockerfile, dockerfiles, docker compose, docker-compose
Containers & Orchestration | Kubernetes | k8s, eks, aks, gke
Containers & Orchestration | Helm | helm charts
Containers & Orchestration | Containers | containerisation, containerization, containerised, containerized
Containers & Orchestration | Microservices | micro-services
Scripting & Languages | Python | python3
Scripting & Languages | Bash | shell scripting, bash scripting
Scripting & Languages | PowerShell | pwsh
Scripting & Languages | JavaScript | js, ecmascript
Scripting & Languages | TypeScript |
Scripting & Languages | Java |
Scripting & Languages | C# | csharp
Scripting & Languages | C++ | cpp
Scripting & Languages | Golang | go lang
Scripting & Languages | SQL |
Scripting & Languages | .NET | dotnet
Monitoring & Observability | Prometheus |
Monitoring & Observability | Grafana |
Monitoring & Observability | Datadog |
Monitoring & Observability | CloudWatch | amazon cloudwatch
Monitoring & Observability | ELK Stack | elk, elasticsearch, kibana, logstash
Monitoring & Observability | Observability | opentelemetry
Monitoring & Observability | Monitoring | alerting, monitored, monitor, monitors
Systems & Networking | Linux | ubuntu, debian, rhel, centos
Systems & Networking | Networking | tcp/ip
Systems & Networking | DNS |
Systems & Networking | TLS | ssl
Systems & Networking | Load Balancing | load balancer, load balancers
Systems & Networking | Nginx |
Systems & Networking | Windows Server |
Security | Security | secure coding, secured
Security | DevSecOps |
Security | IAM | identity and access management
Security | Secrets Management | hashicorp vault
Security | OWASP |
Databases | PostgreSQL | postgres
Databases | MySQL |
Databases | MongoDB |
Databases | Redis |
Databases | NoSQL |
Data & ML | Machine Learning | ml
Data & ML | MLOps |
Data & ML | LLM | llms, large language model, large language models
Data & ML | Pandas |
Data & ML | NumPy |
Data & ML | scikit-learn | sklearn
Data & ML | TensorFlow |
Data & ML | PyTorch |
Data & ML | Spark | pyspark, apache spark
Data & ML | Airflow | apache airflow
Data & ML | ETL | data pipelines, data pipeline
Data & ML | Power BI | powerbi
Data & ML | Tableau |
Frameworks & Web | FastAPI |
Frameworks & Web | Flask |
Frameworks & Web | Django |
Frameworks & Web | React | reactjs, react.js
Frameworks & Web | Node.js | nodejs
Frameworks & Web | REST APIs | rest api, restful, restful apis, rest
Frameworks & Web | GraphQL |
Tools & Practices | Git | version control
Tools & Practices | pytest | unit testing
Tools & Practices | Agile | scrum
Tools & Practices | Jira |
Tools & Practices | SRE | site reliability, site reliability engineering
Tools & Practices | Incident Response | incident management, on-call
Tools & Practices | Automation | automated, automate, automating, automations
Data & ML | Snowflake |
Data & ML | BigQuery | google bigquery
Data & ML | dbt |
Data & ML | Looker |
Data & ML | Microsoft Excel | !Excel, advanced excel, ms excel
Data & ML | SPSS |
Data & ML | Stata |
Project & Product Management | Confluence |
Project & Product Management | Asana |
Project & Product Management | Trello |
Project & Product Management | Figma |
Project & Product Management | PMP | project management professional
Project & Product Management | PRINCE2 | prince 2
Project & Product Management | Certified ScrumMaster | certified scrum master
Project & Product Management | Kanban |
Project & Product Management | OKRs | okr, objectives and key results
Finance & Accounting | IFRS | international financial reporting standards
Finance & Accounting | GAAP | us gaap, generally accepted accounting principles
Finance & Accounting | SAP | !SAP S/4HANA, sap erp
Finance & Accounting | QuickBooks |
Finance & Accounting | Xero |
Finance & Accounting | ACCA |
Finance & Accounting | ICAN |
Finance & Accounting | CPA | certified public accountant
Finance & Accounting | CFA | chartered financial analyst
Finance & Accounting | Financial Modeling | financial modelling
Finance & Accounting | Bloomberg Terminal |
Healthcare | EHR | emr, electronic health records, electronic medical records, electronic health record
Healthcare | Epic EHR | !Epic Systems
Healthcare | Cerner |
Healthcare | HIPAA |
Healthcare | BLS | basic life support
Healthcare | ACLS | advanced cardiovascular life support
Healthcare | ICD-10 | icd10
Sales & Marketing | Salesforce | sfdc
Sales & Marketing | HubSpot |
Sales & Marketing | Google Analytics | ga4
Sales & Marketing | SEO | search engine optimisation, search engine optimization
Sales & Marketing | SEM | search engine marketing
Sales & Marketing | Google Ads | adwords
Sales & Marketing | Meta Ads | facebook ads
Sales & Marketing | Mailchimp |
Sales & Marketing | CRM | customer relationship management
Operations & HR | Workday HCM | !Workday
Operations & HR | SAP SuccessFactors | successfactors
Operations & HR | BambooHR |
Operations & HR | Six Sigma | lean six sigma
Operations & HR | ISO 9001 | iso9001
Operations & HR | CIPD |
Operations & HR | SHRM |
Operations & HR | ITIL |
Compliance | GDPR |
"""

SKILL_CATEGORIES: dict[str, str] = {}
_PATTERNS: dict[str, re.Pattern] = {}


def _alias_regex(alias: str) -> str:
    case_sensitive = alias.startswith('!')
    text = alias[1:] if case_sensitive else alias
    pattern = re.escape(text).replace(r'\ ', r'[\s\-]+')
    return pattern if case_sensitive else f'(?i:{pattern})'


def _build() -> None:
    for line in _TAXONOMY_SRC.strip().splitlines():
        category, canonical, aliases = [p.strip() for p in line.split('|')]
        SKILL_CATEGORIES[canonical] = category
        alternatives = [canonical] + [a.strip() for a in aliases.split(',') if a.strip()]
        body = '|'.join(_alias_regex(a) for a in sorted(set(alternatives), key=len, reverse=True))
        # Not glued to letters, digits, "+" or "#" on either side (C, C++, C#).
        _PATTERNS[canonical] = re.compile(rf'(?<![A-Za-z0-9+#])(?:{body})(?![A-Za-z0-9+#])')


_build()


def find_terms(text: str) -> list[str]:
    """Canonical taxonomy terms present in ``text``."""
    return [canonical for canonical, pattern in _PATTERNS.items() if pattern.search(text or '')]
