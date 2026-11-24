// Suggestions for the sign-up form. People can also type their own career
// track; countries must be one from this list. Both lists are sorted A to Z.

const byName = (a, b) => a.localeCompare(b, 'en', { sensitivity: 'base' });

export const TECH_TRACKS = [
  // Software engineering
  'Software Engineer', 'Frontend Developer', 'Backend Engineer', 'Full Stack Developer', 'Mobile Developer',
  'iOS Developer', 'Android Developer', 'Flutter Developer', 'React Native Developer', 'Web Developer',
  'JavaScript Developer', 'TypeScript Developer', 'Python Developer', 'Java Developer', 'Go Developer',
  'Rust Developer', 'C# / .NET Developer', 'PHP Developer', 'Ruby on Rails Developer', 'Node.js Developer',
  'Game Developer', 'Embedded Systems Engineer', 'Firmware Engineer', 'API Developer', 'Systems Engineer',
  // Cloud, infrastructure and operations
  'DevOps Engineer', 'Cloud Engineer', 'Cloud Architect', 'Platform Engineer', 'Site Reliability Engineer (SRE)',
  'Infrastructure Engineer', 'Kubernetes Engineer', 'Network Engineer', 'Systems Administrator',
  'Linux Administrator', 'Database Administrator (DBA)', 'Release Engineer', 'Build Engineer',
  'FinOps Engineer', 'IT Support Specialist', 'Solutions Architect', 'Enterprise Architect',
  // Data and AI
  'Data Engineer', 'Data Scientist', 'Data Analyst', 'Analytics Engineer', 'Business Intelligence Analyst',
  'Machine Learning Engineer', 'AI Engineer', 'MLOps Engineer', 'Deep Learning Engineer', 'NLP Engineer',
  'Computer Vision Engineer', 'LLM / Generative AI Engineer', 'Prompt Engineer', 'AI Research Scientist',
  'Data Architect', 'Big Data Engineer', 'Quantitative Developer',
  // Security
  'Cybersecurity Engineer', 'Security Analyst', 'Cloud Security Engineer', 'Application Security Engineer',
  'Penetration Tester', 'SOC Analyst', 'Security Architect', 'DevSecOps Engineer', 'GRC Analyst',
  'Identity and Access Management Engineer',
  // Quality
  'QA Engineer', 'QA Automation Engineer', 'Test Engineer', 'Performance Test Engineer',
  // Product, design and delivery
  'Product Manager', 'Technical Product Manager', 'Product Owner', 'Product Designer', 'UI/UX Designer',
  'UX Researcher', 'Technical Program Manager', 'Project Manager (IT)', 'Scrum Master', 'Agile Coach',
  'Business Analyst (IT)', 'Engineering Manager', 'CTO / Head of Engineering',
  // Specialised
  'Blockchain Developer', 'Smart Contract Developer', 'AR/VR Developer', 'Robotics Engineer', 'IoT Engineer',
  'Salesforce Developer', 'SAP Consultant', 'ERP Consultant', 'CRM Developer', 'Shopify Developer',
  'WordPress Developer', 'Technical Writer', 'Developer Advocate', 'Technical Support Engineer',
  'Sales Engineer', 'Customer Success Engineer', 'Growth Engineer', 'Technical Recruiter',
].sort(byName);

export const COUNTRIES = [
  'Afghanistan', 'Albania', 'Algeria', 'Andorra', 'Angola', 'Antigua and Barbuda', 'Argentina', 'Armenia',
  'Australia', 'Austria', 'Azerbaijan', 'Bahamas', 'Bahrain', 'Bangladesh', 'Barbados', 'Belarus', 'Belgium',
  'Belize', 'Benin', 'Bhutan', 'Bolivia', 'Bosnia and Herzegovina', 'Botswana', 'Brazil', 'Brunei', 'Bulgaria',
  'Burkina Faso', 'Burundi', 'Cabo Verde', 'Cambodia', 'Cameroon', 'Canada', 'Central African Republic', 'Chad',
  'Chile', 'China', 'Colombia', 'Comoros', 'Congo', 'Costa Rica', "Côte d'Ivoire", 'Croatia', 'Cuba', 'Cyprus',
  'Czech Republic', 'Democratic Republic of the Congo', 'Denmark', 'Djibouti', 'Dominica', 'Dominican Republic',
  'Ecuador', 'Egypt', 'El Salvador', 'Equatorial Guinea', 'Eritrea', 'Estonia', 'Eswatini', 'Ethiopia', 'Fiji',
  'Finland', 'France', 'Gabon', 'Gambia', 'Georgia', 'Germany', 'Ghana', 'Greece', 'Grenada', 'Guatemala',
  'Guinea', 'Guinea-Bissau', 'Guyana', 'Haiti', 'Honduras', 'Hong Kong', 'Hungary', 'Iceland', 'India',
  'Indonesia', 'Iran', 'Iraq', 'Ireland', 'Israel', 'Italy', 'Jamaica', 'Japan', 'Jordan', 'Kazakhstan', 'Kenya',
  'Kiribati', 'Kosovo', 'Kuwait', 'Kyrgyzstan', 'Laos', 'Latvia', 'Lebanon', 'Lesotho', 'Liberia', 'Libya',
  'Liechtenstein', 'Lithuania', 'Luxembourg', 'Madagascar', 'Malawi', 'Malaysia', 'Maldives', 'Mali', 'Malta',
  'Marshall Islands', 'Mauritania', 'Mauritius', 'Mexico', 'Micronesia', 'Moldova', 'Monaco', 'Mongolia',
  'Montenegro', 'Morocco', 'Mozambique', 'Myanmar', 'Namibia', 'Nauru', 'Nepal', 'Netherlands', 'New Zealand',
  'Nicaragua', 'Niger', 'Nigeria', 'North Korea', 'North Macedonia', 'Norway', 'Oman', 'Pakistan', 'Palau',
  'Palestine', 'Panama', 'Papua New Guinea', 'Paraguay', 'Peru', 'Philippines', 'Poland', 'Portugal',
  'Puerto Rico', 'Qatar', 'Romania', 'Russia', 'Rwanda', 'Saint Kitts and Nevis', 'Saint Lucia',
  'Saint Vincent and the Grenadines', 'Samoa', 'San Marino', 'São Tomé and Príncipe', 'Saudi Arabia', 'Senegal',
  'Serbia', 'Seychelles', 'Sierra Leone', 'Singapore', 'Slovakia', 'Slovenia', 'Solomon Islands', 'Somalia',
  'South Africa', 'South Korea', 'South Sudan', 'Spain', 'Sri Lanka', 'Sudan', 'Suriname', 'Sweden',
  'Switzerland', 'Syria', 'Taiwan', 'Tajikistan', 'Tanzania', 'Thailand', 'Timor-Leste', 'Togo', 'Tonga',
  'Trinidad and Tobago', 'Tunisia', 'Turkey', 'Turkmenistan', 'Tuvalu', 'Uganda', 'Ukraine',
  'United Arab Emirates', 'United Kingdom', 'United States', 'Uruguay', 'Uzbekistan', 'Vanuatu', 'Vatican City',
  'Venezuela', 'Vietnam', 'Yemen', 'Zambia', 'Zimbabwe',
].sort(byName);

const fold = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').trim().toLowerCase();
const ALIASES = { usa: 'United States', us: 'United States', 'united states of america': 'United States',
  uk: 'United Kingdom', 'great britain': 'United Kingdom', england: 'United Kingdom', uae: 'United Arab Emirates',
  'ivory coast': "Côte d'Ivoire", 'cape verde': 'Cabo Verde', swaziland: 'Eswatini', 'east timor': 'Timor-Leste',
  burma: 'Myanmar', 'czechia': 'Czech Republic', 'drc': 'Democratic Republic of the Congo', turkiye: 'Turkey' };

/** The country from the list that the typed text means, or null. "nigeria", "UK", "Cote d'Ivoire" all work. */
export function matchCountry(text) {
  const key = fold(text);
  if (!key) return null;
  return COUNTRIES.find(c => fold(c) === key) || ALIASES[key] || null;
}

/** A typed career track, tidied: suggestions keep their exact spelling; anything else is trimmed. */
export function cleanTrack(text) {
  const value = String(text || '').replace(/\s+/g, ' ').trim().slice(0, 80);
  return TECH_TRACKS.find(t => fold(t) === fold(value)) || value;
}
