/**
 * Autocomplete suggestions for various fields
 * Enhanced with comprehensive lists and fuzzy matching
 */

const SUGGESTIONS = {
    locations: [
        // Remote Options
        'Remote, US',
        'Remote, Worldwide',
        'Remote, North America',
        'Remote, Europe',
        'Hybrid - US',

        // Major US Cities (Top 100)
        'New York, NY',
        'Los Angeles, CA',
        'Chicago, IL',
        'Houston, TX',
        'Phoenix, AZ',
        'Philadelphia, PA',
        'San Antonio, TX',
        'San Diego, CA',
        'Dallas, TX',
        'San Jose, CA',
        'Austin, TX',
        'Jacksonville, FL',
        'Fort Worth, TX',
        'Columbus, OH',
        'Charlotte, NC',
        'San Francisco, CA',
        'Indianapolis, IN',
        'Seattle, WA',
        'Denver, CO',
        'Washington, DC',
        'Boston, MA',
        'El Paso, TX',
        'Nashville, TN',
        'Detroit, MI',
        'Oklahoma City, OK',
        'Portland, OR',
        'Las Vegas, NV',
        'Memphis, TN',
        'Louisville, KY',
        'Baltimore, MD',
        'Milwaukee, WI',
        'Albuquerque, NM',
        'Tucson, AZ',
        'Fresno, CA',
        'Mesa, AZ',
        'Sacramento, CA',
        'Atlanta, GA',
        'Kansas City, MO',
        'Colorado Springs, CO',
        'Raleigh, NC',
        'Miami, FL',
        'Long Beach, CA',
        'Virginia Beach, VA',
        'Omaha, NE',
        'Oakland, CA',
        'Minneapolis, MN',
        'Tulsa, OK',
        'Tampa, FL',
        'Arlington, TX',
        'New Orleans, LA',
        'Wichita, KS',
        'Cleveland, OH',
        'Bakersfield, CA',
        'Aurora, CO',
        'Anaheim, CA',
        'Honolulu, HI',
        'Santa Ana, CA',
        'Riverside, CA',
        'Corpus Christi, TX',
        'Lexington, KY',
        'Stockton, CA',
        'Henderson, NV',
        'Saint Paul, MN',
        'St. Louis, MO',
        'Cincinnati, OH',
        'Pittsburgh, PA',
        'Greensboro, NC',
        'Anchorage, AK',
        'Plano, TX',
        'Lincoln, NE',
        'Orlando, FL',
        'Irvine, CA',
        'Newark, NJ',
        'Durham, NC',
        'Chula Vista, CA',
        'Toledo, OH',
        'Fort Wayne, IN',
        'St. Petersburg, FL',
        'Laredo, TX',
        'Jersey City, NJ',
        'Chandler, AZ',
        'Madison, WI',
        'Lubbock, TX',
        'Scottsdale, AZ',
        'Reno, NV',
        'Buffalo, NY',
        'Gilbert, AZ',
        'Glendale, AZ',
        'North Las Vegas, NV',
        'Winston-Salem, NC',
        'Chesapeake, VA',
        'Norfolk, VA',
        'Fremont, CA',
        'Garland, TX',
        'Irving, TX',
        'Hialeah, FL',
        'Richmond, VA',
        'Boise, ID',
        'Spokane, WA',

        // International Tech Hubs
        'London, UK',
        'Berlin, Germany',
        'Amsterdam, Netherlands',
        'Paris, France',
        'Dublin, Ireland',
        'Toronto, Canada',
        'Vancouver, Canada',
        'Montreal, Canada',
        'Sydney, Australia',
        'Melbourne, Australia',
        'Singapore',
        'Tokyo, Japan',
        'Hong Kong',
        'Bangalore, India',
        'Tel Aviv, Israel',
        'Zurich, Switzerland',
        'Stockholm, Sweden',
        'Copenhagen, Denmark',
    ],

    jobTitles: [
        // Product Management
        'Product Manager',
        'Senior Product Manager',
        'Principal Product Manager',
        'Staff Product Manager',
        'Lead Product Manager',
        'Director of Product',
        'VP of Product',
        'Chief Product Officer',
        'Group Product Manager',
        'Product Owner',
        'Technical Product Manager',
        'Senior Technical Product Manager',
        'Product Management Lead',
        'Associate Product Manager',
        'Junior Product Manager',
        'Product Marketing Manager',
        'Senior Product Marketing Manager',
        'Growth Product Manager',
        'Data Product Manager',
        'AI Product Manager',
        'Platform Product Manager',
        'Consumer Product Manager',
        'B2B Product Manager',
        'Enterprise Product Manager',
        'Mobile Product Manager',
        'Hardware Product Manager',

        // Software Engineering
        'Software Engineer',
        'Senior Software Engineer',
        'Staff Software Engineer',
        'Principal Software Engineer',
        'Distinguished Engineer',
        'Engineering Manager',
        'Senior Engineering Manager',
        'Director of Engineering',
        'VP of Engineering',
        'CTO',
        'Chief Technology Officer',
        'Lead Engineer',
        'Technical Lead',
        'Full Stack Engineer',
        'Senior Full Stack Engineer',
        'Frontend Engineer',
        'Senior Frontend Engineer',
        'Backend Engineer',
        'Senior Backend Engineer',
        'Systems Engineer',
        'Infrastructure Engineer',
        'Platform Engineer',
        'Site Reliability Engineer',
        'Senior Site Reliability Engineer',
        'SRE',
        'DevOps Engineer',
        'Senior DevOps Engineer',
        'Cloud Engineer',
        'Solutions Architect',
        'Technical Architect',
        'Enterprise Architect',

        // Data & Analytics
        'Data Scientist',
        'Senior Data Scientist',
        'Staff Data Scientist',
        'Lead Data Scientist',
        'Principal Data Scientist',
        'Data Engineer',
        'Senior Data Engineer',
        'Staff Data Engineer',
        'Analytics Engineer',
        'Data Analyst',
        'Senior Data Analyst',
        'Business Intelligence Analyst',
        'BI Developer',
        'Data Architect',
        'Machine Learning Engineer',
        'Senior Machine Learning Engineer',
        'ML Engineer',
        'AI Engineer',
        'Research Scientist',
        'Applied Scientist',
        'Quantitative Analyst',
        'Director of Data Science',
        'VP of Data',
        'Chief Data Officer',

        // Design
        'Product Designer',
        'Senior Product Designer',
        'Lead Product Designer',
        'UX Designer',
        'Senior UX Designer',
        'UI Designer',
        'UI/UX Designer',
        'Visual Designer',
        'Interaction Designer',
        'User Researcher',
        'UX Researcher',
        'Design Director',
        'Head of Design',
        'VP of Design',
        'Creative Director',
        'Brand Designer',
        'Graphic Designer',

        // Program/Project Management
        'Program Manager',
        'Senior Program Manager',
        'Principal Program Manager',
        'Technical Program Manager',
        'Senior Technical Program Manager',
        'TPM',
        'Project Manager',
        'Senior Project Manager',
        'Scrum Master',
        'Agile Coach',
        'Delivery Manager',
        'Portfolio Manager',

        // Marketing
        'Marketing Manager',
        'Senior Marketing Manager',
        'Director of Marketing',
        'VP of Marketing',
        'CMO',
        'Chief Marketing Officer',
        'Growth Marketing Manager',
        'Performance Marketing Manager',
        'Content Marketing Manager',
        'Social Media Manager',
        'SEO Manager',
        'Demand Generation Manager',
        'Digital Marketing Manager',
        'Brand Manager',
        'Communications Manager',

        // Sales & Business Development
        'Account Executive',
        'Senior Account Executive',
        'Sales Manager',
        'Senior Sales Manager',
        'Sales Director',
        'VP of Sales',
        'Chief Revenue Officer',
        'CRO',
        'Business Development Manager',
        'BD Manager',
        'Partnerships Manager',
        'Enterprise Account Executive',
        'Solutions Engineer',
        'Sales Engineer',
        'Customer Success Manager',
        'Senior Customer Success Manager',
        'Director of Customer Success',

        // Security
        'Security Engineer',
        'Senior Security Engineer',
        'Security Analyst',
        'Information Security Analyst',
        'Cybersecurity Engineer',
        'Application Security Engineer',
        'Security Architect',
        'CISO',
        'Chief Information Security Officer',
        'Penetration Tester',
        'SOC Analyst',
        'Threat Intelligence Analyst',

        // Mobile Development
        'Mobile Engineer',
        'Senior Mobile Engineer',
        'iOS Developer',
        'Senior iOS Developer',
        'iOS Engineer',
        'Android Developer',
        'Senior Android Developer',
        'Android Engineer',
        'React Native Developer',
        'Flutter Developer',

        // Specialized Engineering
        'Embedded Software Engineer',
        'Firmware Engineer',
        'Blockchain Engineer',
        'Robotics Engineer',
        'Computer Vision Engineer',
        'NLP Engineer',
        'Distributed Systems Engineer',
        'Performance Engineer',
        'QA Engineer',
        'Quality Assurance Engineer',
        'Test Engineer',
        'SDET',
        'Automation Engineer',

        // Operations & Support
        'Operations Manager',
        'IT Manager',
        'Systems Administrator',
        'Network Engineer',
        'Database Administrator',
        'DBA',
        'Technical Support Engineer',
        'Support Engineer',
        'Customer Support Manager',
        'Help Desk Manager',

        // Executive & Leadership
        'CEO',
        'Chief Executive Officer',
        'COO',
        'Chief Operating Officer',
        'CFO',
        'Chief Financial Officer',
        'General Manager',
        'Head of Product',
        'Head of Engineering',
        'Head of Data',
        'Head of Growth',
        'Head of Operations',

        // Other Technical Roles
        'Technical Writer',
        'Documentation Engineer',
        'Developer Advocate',
        'Developer Relations Engineer',
        'Implementation Engineer',
        'Professional Services Engineer',
        'Integration Engineer',
        'API Engineer',
    ],

    companies: [
        // FAANG+
        'Google',
        'Meta',
        'Facebook',
        'Amazon',
        'Apple',
        'Microsoft',
        'Netflix',

        // Major Tech
        'Salesforce',
        'Adobe',
        'Oracle',
        'SAP',
        'IBM',
        'Cisco',
        'Intel',
        'NVIDIA',
        'AMD',
        'Qualcomm',

        // Social & Communication
        'Twitter',
        'X',
        'LinkedIn',
        'Snap',
        'Snapchat',
        'Reddit',
        'Discord',
        'Slack',
        'Zoom',

        // E-commerce & Marketplace
        'Shopify',
        'eBay',
        'Etsy',
        'Wayfair',
        'DoorDash',
        'Uber',
        'Lyft',
        'Airbnb',
        'Instacart',

        // Fintech
        'Stripe',
        'Square',
        'Block',
        'PayPal',
        'Coinbase',
        'Robinhood',
        'Plaid',
        'Chime',
        'Affirm',
        'Brex',
        'Ramp',

        // Enterprise SaaS
        'Atlassian',
        'ServiceNow',
        'Workday',
        'Splunk',
        'Datadog',
        'Snowflake',
        'Databricks',
        'MongoDB',
        'Elastic',
        'Confluent',
        'HashiCorp',

        // Cloud & Infrastructure
        'Cloudflare',
        'DigitalOcean',
        'Akamai',
        'Fastly',

        // Productivity
        'Notion',
        'Figma',
        'Asana',
        'Monday.com',
        'Airtable',
        'Miro',

        // Security
        'CrowdStrike',
        'Okta',
        'Auth0',
        'Palo Alto Networks',
        'Fortinet',

        // Other Notable
        'Tesla',
        'SpaceX',
        'GitHub',
        'GitLab',
        'Dropbox',
        'Box',
        'Twilio',
        'SendGrid',
        'HubSpot',
        'Zendesk',
        'DocuSign',
        'Unity',
        'Epic Games',
        'Roblox',
    ],

    skills: [
        // Programming Languages
        'Python',
        'JavaScript',
        'TypeScript',
        'Java',
        'C++',
        'C#',
        'Go',
        'Golang',
        'Rust',
        'Ruby',
        'PHP',
        'Swift',
        'Kotlin',
        'Scala',
        'R',
        'MATLAB',

        // Frontend
        'React',
        'Vue.js',
        'Angular',
        'Svelte',
        'Next.js',
        'HTML',
        'CSS',
        'SASS',
        'Tailwind CSS',
        'Redux',
        'GraphQL',
        'REST API',

        // Backend
        'Node.js',
        'Express',
        'Django',
        'Flask',
        'FastAPI',
        'Spring Boot',
        'Ruby on Rails',
        '.NET',
        'ASP.NET',

        // Mobile
        'React Native',
        'Flutter',
        'iOS Development',
        'Android Development',

        // Data & ML
        'SQL',
        'PostgreSQL',
        'MySQL',
        'MongoDB',
        'Redis',
        'Cassandra',
        'Machine Learning',
        'Deep Learning',
        'TensorFlow',
        'PyTorch',
        'scikit-learn',
        'Pandas',
        'NumPy',
        'Data Analysis',
        'Data Visualization',
        'Tableau',
        'Power BI',
        'Looker',

        // Cloud & DevOps
        'AWS',
        'Azure',
        'Google Cloud',
        'GCP',
        'Docker',
        'Kubernetes',
        'Terraform',
        'CI/CD',
        'Jenkins',
        'GitHub Actions',
        'GitLab CI',
        'Ansible',
        'Chef',
        'Puppet',

        // Product Management
        'Product Strategy',
        'Roadmapping',
        'User Research',
        'A/B Testing',
        'Product Analytics',
        'Agile',
        'Scrum',
        'JIRA',
        'Confluence',
        'Figma',
        'Miro',
        'Stakeholder Management',
        'Go-to-Market',
        'Competitive Analysis',

        // Soft Skills
        'Leadership',
        'Communication',
        'Team Management',
        'Cross-functional Collaboration',
        'Problem Solving',
        'Critical Thinking',
        'Technical Writing',
        'Presentation Skills',
    ],

    keywords: [
        'remote',
        'hybrid',
        'flexible hours',
        'work-life balance',
        'stock options',
        'equity',
        'RSUs',
        '401k',
        'healthcare',
        'health insurance',
        'dental',
        'vision',
        'unlimited PTO',
        'paid time off',
        'parental leave',
        'startup',
        'enterprise',
        'B2B',
        'B2C',
        'SaaS',
        'PaaS',
        'IaaS',
        'AI/ML',
        'artificial intelligence',
        'machine learning',
        'blockchain',
        'crypto',
        'web3',
        'cloud',
        'mobile',
        'web',
        'fintech',
        'insurtech',
        'healthtech',
        'edtech',
        'climate tech',
        'greentech',
        'clean energy',
        'social impact',
        'mission-driven',
        'diversity',
        'inclusion',
        'DEI',
        'growth stage',
        'series A',
        'series B',
        'series C',
        'pre-IPO',
        'public company',
        'Fortune 500',
        'fast-paced',
        'collaborative',
        'innovative',
        'cutting edge',
    ],

    industries: [
        'fintech',
        'insurtech',
        'financial services',
        'payments',
        'banking',
        'cryptocurrency',
        'blockchain',
        'healthcare',
        'healthtech',
        'biotech',
        'pharma',
        'medical devices',
        'ai',
        'artificial intelligence',
        'machine learning',
        'data analytics',
        'data science',
        'big data',
        'developer tools',
        'infrastructure',
        'cloud',
        'cybersecurity',
        'infosec',
        'security',
        'saas',
        'b2b',
        'b2c',
        'enterprise software',
        'marketplace',
        'e-commerce',
        'retail',
        'consumer',
        'social media',
        'media',
        'content',
        'adtech',
        'martech',
        'edtech',
        'education',
        'hr tech',
        'recruiting',
        'productivity',
        'collaboration',
        'communication',
        'travel',
        'hospitality',
        'food delivery',
        'logistics',
        'supply chain',
        'transportation',
        'automotive',
        'real estate',
        'proptech',
        'legal tech',
        'regtech',
        'gaming',
        'entertainment',
        'creative tools',
        'design tools',
        'no-code',
        'low-code',
        'api',
        'platform',
        'semiconductors',
        'hardware',
        'iot',
        'robotics',
        'clean energy',
        'climate tech',
        'agtech',
        'agriculture',
    ],

    companySizes: [
        'startup (1-50)',
        'small (51-200)',
        'mid-size (201-1000)',
        'large (1001-5000)',
        'enterprise (5000+)',
    ],

    companyStages: [
        'pre-seed',
        'seed',
        'series-a',
        'series-b',
        'series-c',
        'series-d+',
        'growth',
        'unicorn',
        'pre-ipo',
        'public',
        'acquired',
    ],

    techStack: [
        // Languages
        'Python',
        'JavaScript',
        'TypeScript',
        'Java',
        'Go',
        'Golang',
        'Rust',
        'C++',
        'C#',
        'Ruby',
        'PHP',
        'Swift',
        'Kotlin',
        'Scala',
        'Elixir',
        'R',
        'SQL',

        // Frontend
        'React',
        'Vue',
        'Angular',
        'Svelte',
        'Next.js',
        'Nuxt',
        'HTML',
        'CSS',
        'Tailwind',
        'WebAssembly',
        'WebGL',

        // Backend
        'Node.js',
        'Express',
        'Django',
        'Flask',
        'FastAPI',
        'Spring Boot',
        'Rails',
        'Laravel',
        '.NET',
        'GraphQL',
        'REST API',

        // Databases
        'PostgreSQL',
        'MySQL',
        'MongoDB',
        'Redis',
        'Cassandra',
        'DynamoDB',
        'Elasticsearch',
        'Neo4j',
        'Oracle',

        // Cloud & Infrastructure
        'AWS',
        'Azure',
        'GCP',
        'Google Cloud',
        'Kubernetes',
        'Docker',
        'Terraform',
        'CloudFormation',
        'Serverless',
        'Lambda',

        // Data & ML
        'Spark',
        'Hadoop',
        'Airflow',
        'Kafka',
        'TensorFlow',
        'PyTorch',
        'scikit-learn',
        'Pandas',
        'NumPy',
        'Jupyter',

        // DevOps & Tools
        'Git',
        'GitHub',
        'GitLab',
        'Jenkins',
        'CircleCI',
        'GitHub Actions',
        'Ansible',
        'Chef',
        'Puppet',
        'Datadog',
        'New Relic',
        'Prometheus',
        'Grafana',

        // Other
        'Linux',
        'Unix',
        'Nginx',
        'Apache',
        'Microservices',
        'CI/CD',
        'Agile',
        'Scrum',
    ],
};

/**
 * Fuzzy matching utility for better typeahead suggestions
 * Supports:
 * - Exact matches (highest priority)
 * - Starts with (high priority)
 * - Contains (medium priority)
 * - Abbreviation matching (e.g., "pm" -> "Product Manager")
 * - Word boundary matching (e.g., "sr eng" -> "Senior Engineer")
 */
const fuzzyMatch = (search, candidate, searchTerm) => {
    const searchLower = search.toLowerCase();
    const candidateLower = candidate.toLowerCase();
    const searchWords = searchLower.split(/\s+/).filter(Boolean);

    // Exact match (highest score)
    if (candidateLower === searchLower) {
        return { score: 1000, match: true };
    }

    // Starts with (very high score)
    if (candidateLower.startsWith(searchLower)) {
        return { score: 900, match: true };
    }

    // Contains (high score)
    if (candidateLower.includes(searchLower)) {
        return { score: 700, match: true };
    }

    // Abbreviation matching (e.g., "pm" -> "Product Manager", "swe" -> "Software Engineer")
    const candidateWords = candidate.split(/\s+/).filter(Boolean);
    const abbreviation = candidateWords.map(w => w[0].toLowerCase()).join('');
    if (abbreviation === searchLower || abbreviation.startsWith(searchLower)) {
        return { score: 600, match: true };
    }

    // Word boundary matching (all search words match word boundaries)
    const allWordsMatch = searchWords.every(word =>
        candidateWords.some(cw => cw.toLowerCase().startsWith(word))
    );
    if (allWordsMatch && searchWords.length > 0) {
        return { score: 500, match: true };
    }

    // Partial word matches (each character in search appears in order)
    let candidateIndex = 0;
    for (let i = 0; i < searchLower.length; i++) {
        const charIndex = candidateLower.indexOf(searchLower[i], candidateIndex);
        if (charIndex === -1) {
            return { score: 0, match: false };
        }
        candidateIndex = charIndex + 1;
    }

    // Sequential character match (lower score)
    return { score: 300, match: true };
};

/**
 * Enhanced filter function for suggestions
 * Returns sorted results with best matches first
 */
const filterSuggestions = (searchTerm, suggestions, maxResults = 10) => {
    if (!searchTerm || searchTerm.trim() === '') {
        return [];
    }

    const results = suggestions
        .map(suggestion => ({
            value: suggestion,
            ...fuzzyMatch(searchTerm, suggestion, searchTerm)
        }))
        .filter(r => r.match)
        .sort((a, b) => b.score - a.score)
        .slice(0, maxResults)
        .map(r => r.value);

    return results;
};

// Make SUGGESTIONS and utilities available globally
window.SUGGESTIONS = SUGGESTIONS;
window.fuzzyMatch = fuzzyMatch;
window.filterSuggestions = filterSuggestions;
