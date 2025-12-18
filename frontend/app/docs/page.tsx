'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

export default function DocsPage() {
  const [activeSection, setActiveSection] = useState<string>('overview');

  const sections = [
    { id: 'overview', title: 'Overview' },
    { id: 'quickstart', title: 'Quick Start' },
    { id: 'features', title: 'Features' },
    { id: 'workflow', title: 'Workflow' },
    { id: 'configuration', title: 'Configuration' },
    { id: 'api', title: 'API Reference' },
    { id: 'troubleshooting', title: 'Troubleshooting' },
  ];

  return (
    <main className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <Link href="/" className="flex-shrink-0 flex items-center">
                <h1 className="text-xl font-bold text-gray-900">Job Search Pipeline</h1>
              </Link>
              <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
                <Link
                  href="/"
                  className="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                >
                  Dashboard
                </Link>
                <Link
                  href="/runs"
                  className="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                >
                  Runs
                </Link>
                <Link
                  href="/jobs"
                  className="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                >
                  Jobs
                </Link>
                <Link
                  href="/settings"
                  className="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                >
                  Settings
                </Link>
                <Link
                  href="/docs"
                  className="border-blue-500 text-gray-900 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                >
                  Documentation
                </Link>
              </div>
            </div>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="flex">
            {/* Sidebar */}
            <div className="w-64 pr-8 border-r">
              <nav className="space-y-1">
                {sections.map((section) => (
                  <button
                    key={section.id}
                    onClick={() => setActiveSection(section.id)}
                    className={`w-full text-left px-4 py-2 rounded-lg ${
                      activeSection === section.id
                        ? 'bg-blue-50 text-blue-700 font-medium'
                        : 'text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    {section.title}
                  </button>
                ))}
              </nav>
            </div>

            {/* Content */}
            <div className="flex-1 pl-8">
              <div className="bg-white shadow rounded-lg p-8">
                {activeSection === 'overview' && (
                  <div className="prose max-w-none">
                    <h1 className="text-3xl font-bold mb-4">Job Search Pipeline Documentation</h1>
                    <p className="text-lg text-gray-600 mb-6">
                      A production-ready Python application with a Next.js frontend for automated job searching,
                      intelligent scoring, LLM-powered content generation, and semi-automated application management.
                    </p>

                    <h2 className="text-2xl font-bold mt-8 mb-4">What is this?</h2>
                    <p>
                      The Job Search Pipeline automates the process of finding, evaluating, and applying to jobs.
                      It searches multiple job boards (LinkedIn, Indeed, Wellfound), scores jobs based on relevance,
                      generates tailored content (resume points, cover letters), and can automatically apply to jobs
                      with your approval.
                    </p>

                    <h2 className="text-2xl font-bold mt-8 mb-4">Key Components</h2>
                    <ul className="list-disc pl-6 space-y-2">
                      <li><strong>Search Agent:</strong> Queries multiple job sources and normalizes results</li>
                      <li><strong>Filter & Score Agent:</strong> Scores and filters jobs based on configurable criteria</li>
                      <li><strong>Content Generation Agent:</strong> Uses LLM to generate tailored content</li>
                      <li><strong>Apply Agent:</strong> Handles job applications via browser automation</li>
                      <li><strong>Orchestrator:</strong> Coordinates agents through the pipeline lifecycle</li>
                    </ul>
                  </div>
                )}

                {activeSection === 'quickstart' && (
                  <div className="prose max-w-none">
                    <h1 className="text-3xl font-bold mb-4">Quick Start Guide</h1>

                    <h2 className="text-2xl font-bold mt-8 mb-4">1. Setup</h2>
                    <ol className="list-decimal pl-6 space-y-2">
                      <li>Ensure Python 3.10+ and Node.js 18+ are installed</li>
                      <li>Set your <code className="bg-gray-100 px-2 py-1 rounded">OPENAI_API_KEY</code> in <code className="bg-gray-100 px-2 py-1 rounded">.env</code></li>
                      <li>Run <code className="bg-gray-100 px-2 py-1 rounded">./setup.sh</code> or manually install dependencies</li>
                      <li>Start the API server: <code className="bg-gray-100 px-2 py-1 rounded">python -m app.api.main</code></li>
                      <li>Start the frontend: <code className="bg-gray-100 px-2 py-1 rounded">cd frontend && npm run dev</code></li>
                    </ol>

                    <h2 className="text-2xl font-bold mt-8 mb-4">2. Configure Your Profile</h2>
                    <ol className="list-decimal pl-6 space-y-2">
                      <li>Go to Settings → Profile & Resume</li>
                      <li>Fill in your contact information</li>
                      <li>Upload your resume (PDF, DOCX, or TXT)</li>
                      <li>Configure your job search preferences</li>
                    </ol>

                    <h2 className="text-2xl font-bold mt-8 mb-4">3. Run Your First Search</h2>
                    <ol className="list-decimal pl-6 space-y-2">
                      <li>From the Dashboard, enter job titles and locations</li>
                      <li>Click "Search Jobs"</li>
                      <li>View results in the Jobs page</li>
                      <li>Review and approve jobs you're interested in</li>
                      <li>Generate tailored content for approved jobs</li>
                      <li>Apply to jobs when ready</li>
                    </ol>
                  </div>
                )}

                {activeSection === 'features' && (
                  <div className="prose max-w-none">
                    <h1 className="text-3xl font-bold mb-4">Features</h1>

                    <h2 className="text-2xl font-bold mt-8 mb-4">Job Search</h2>
                    <ul className="list-disc pl-6 space-y-2">
                      <li>Multi-source job search (LinkedIn, Indeed, Wellfound)</li>
                      <li>Configurable search parameters (titles, locations, keywords)</li>
                      <li>Remote job filtering</li>
                      <li>Real-time job board scraping</li>
                    </ul>

                    <h2 className="text-2xl font-bold mt-8 mb-4">Intelligent Scoring</h2>
                    <ul className="list-disc pl-6 space-y-2">
                      <li>Relevance scoring based on multiple factors:
                        <ul className="list-disc pl-6 mt-2">
                          <li>Title match</li>
                          <li>Vertical/industry match</li>
                          <li>Keyword overlap</li>
                          <li>Company match</li>
                          <li>Compensation range</li>
                          <li>Remote preference</li>
                        </ul>
                      </li>
                      <li>Configurable scoring weights</li>
                      <li>Threshold filtering</li>
                      <li>Auto-approval based on score threshold</li>
                    </ul>

                    <h2 className="text-2xl font-bold mt-8 mb-4">Content Generation</h2>
                    <ul className="list-disc pl-6 space-y-2">
                      <li>AI-generated job summaries</li>
                      <li>Tailored resume bullet points</li>
                      <li>Personalized cover letters</li>
                      <li>Application question answers</li>
                      <li>Uses your profile and resume for personalization</li>
                    </ul>

                    <h2 className="text-2xl font-bold mt-8 mb-4">Application Automation</h2>
                    <ul className="list-disc pl-6 space-y-2">
                      <li>Browser automation for Easy Apply jobs (Indeed, LinkedIn)</li>
                      <li>Automatic form filling</li>
                      <li>Resume upload</li>
                      <li>Error handling and retry logic</li>
                      <li>CAPTCHA detection</li>
                      <li>Dry-run mode for testing</li>
                    </ul>

                    <h2 className="text-2xl font-bold mt-8 mb-4">Workflow Management</h2>
                    <ul className="list-disc pl-6 space-y-2">
                      <li>Human-in-the-loop approval</li>
                      <li>Bulk job approval</li>
                      <li>Application status tracking</li>
                      <li>Scheduled job searches</li>
                      <li>Comprehensive logging and analytics</li>
                    </ul>
                  </div>
                )}

                {activeSection === 'workflow' && (
                  <div className="prose max-w-none">
                    <h1 className="text-3xl font-bold mb-4">Workflow</h1>

                    <h2 className="text-2xl font-bold mt-8 mb-4">Pipeline Stages</h2>
                    <ol className="list-decimal pl-6 space-y-4">
                      <li>
                        <strong>Search:</strong> Queries job boards based on your criteria
                        <ul className="list-disc pl-6 mt-2">
                          <li>Search parameters are normalized across different job boards</li>
                          <li>Results are deduplicated</li>
                        </ul>
                      </li>
                      <li>
                        <strong>Score & Filter:</strong> Each job is scored and filtered
                        <ul className="list-disc pl-6 mt-2">
                          <li>Jobs below the minimum threshold are filtered out</li>
                          <li>Jobs above the auto-approval threshold are automatically approved</li>
                          <li>Detailed scoring breakdown is saved for review</li>
                        </ul>
                      </li>
                      <li>
                        <strong>Content Generation (Optional):</strong> Generate tailored content
                        <ul className="list-disc pl-6 mt-2">
                          <li>Job summary</li>
                          <li>Resume bullet points tailored to the job</li>
                          <li>Cover letter draft</li>
                          <li>Application answers</li>
                        </ul>
                      </li>
                      <li>
                        <strong>Approval:</strong> Review and approve jobs
                        <ul className="list-disc pl-6 mt-2">
                          <li>Manually approve individual jobs</li>
                          <li>Use bulk approval for multiple jobs</li>
                          <li>High-scoring jobs can be auto-approved</li>
                        </ul>
                      </li>
                      <li>
                        <strong>Application:</strong> Apply to approved jobs
                        <ul className="list-disc pl-6 mt-2">
                          <li>Automated form filling for Easy Apply jobs</li>
                          <li>Resume upload</li>
                          <li>Status tracking and error handling</li>
                        </ul>
                      </li>
                    </ol>

                    <h2 className="text-2xl font-bold mt-8 mb-4">Best Practices</h2>
                    <ul className="list-disc pl-6 space-y-2">
                      <li>Start with a dry-run to test the application flow</li>
                      <li>Review generated content before applying</li>
                      <li>Monitor application success rates in analytics</li>
                      <li>Adjust scoring weights based on your preferences</li>
                      <li>Keep your profile and resume up to date</li>
                    </ul>
                  </div>
                )}

                {activeSection === 'configuration' && (
                  <div className="prose max-w-none">
                    <h1 className="text-3xl font-bold mb-4">Configuration</h1>

                    <h2 className="text-2xl font-bold mt-8 mb-4">Configuration File (config.yaml)</h2>
                    <p>The main configuration file controls search parameters, scoring weights, and feature flags.</p>

                    <h3 className="text-xl font-bold mt-6 mb-3">Search Configuration</h3>
                    <pre className="bg-gray-100 p-4 rounded overflow-x-auto">
{`search:
  default_titles:
    - Senior Product Manager
  default_locations:
    - Remote, US
  default_remote_preference: remote
  default_salary_min: 120000`}
                    </pre>

                    <h3 className="text-xl font-bold mt-6 mb-3">Scoring Weights</h3>
                    <pre className="bg-gray-100 p-4 rounded overflow-x-auto">
{`scoring:
  title_match_weight: 8
  vertical_match_weight: 6
  remote_preference_weight: 5
  comp_match_weight: 7
  keyword_overlap_weight: 6
  company_match_weight: 5
  posting_recency_weight: 3`}
                    </pre>

                    <h3 className="text-xl font-bold mt-6 mb-3">Thresholds</h3>
                    <pre className="bg-gray-100 p-4 rounded overflow-x-auto">
{`thresholds:
  min_relevance_score: 5      # Jobs below this are filtered out
  high_relevance_score: 8     # High-quality jobs
  auto_approval_threshold: 8  # Jobs above this are auto-approved`}
                    </pre>

                    <h3 className="text-xl font-bold mt-6 mb-3">Features</h3>
                    <pre className="bg-gray-100 p-4 rounded overflow-x-auto">
{`features:
  enable_playwright: true           # Enable browser automation
  enable_auto_apply: false          # Never auto-apply (always requires approval)
  enable_content_generation: true   # Generate AI content
  enable_email_notifications: false # Email notifications (not yet implemented)`}
                    </pre>

                    <h3 className="text-xl font-bold mt-6 mb-3">Scheduler</h3>
                    <pre className="bg-gray-100 p-4 rounded overflow-x-auto">
{`scheduler:
  enabled: true
  run_frequency_hours: 24
  run_at_time: "09:00"`}
                    </pre>

                    <h2 className="text-2xl font-bold mt-8 mb-4">Environment Variables</h2>
                    <ul className="list-disc pl-6 space-y-2">
                      <li><code className="bg-gray-100 px-2 py-1 rounded">OPENAI_API_KEY</code> - Required for LLM features</li>
                      <li><code className="bg-gray-100 px-2 py-1 rounded">DATABASE_URL</code> - Database connection (defaults to SQLite)</li>
                      <li><code className="bg-gray-100 px-2 py-1 rounded">ENABLE_PLAYWRIGHT</code> - Enable browser automation</li>
                      <li><code className="bg-gray-100 px-2 py-1 rounded">PLAYWRIGHT_HEADLESS</code> - Run browser in headless mode</li>
                    </ul>
                  </div>
                )}

                {activeSection === 'api' && (
                  <div className="prose max-w-none">
                    <h1 className="text-3xl font-bold mb-4">API Reference</h1>

                    <h2 className="text-2xl font-bold mt-8 mb-4">Runs</h2>
                    <ul className="list-disc pl-6 space-y-2">
                      <li><code className="bg-gray-100 px-2 py-1 rounded">POST /runs</code> - Create and start a new pipeline run</li>
                      <li><code className="bg-gray-100 px-2 py-1 rounded">GET /runs</code> - Get all runs</li>
                      <li><code className="bg-gray-100 px-2 py-1 rounded">GET /runs/{`{run_id}`}</code> - Get run details</li>
                      <li><code className="bg-gray-100 px-2 py-1 rounded">GET /runs/{`{run_id}`}/jobs</code> - Get jobs from a run</li>
                    </ul>

                    <h2 className="text-2xl font-bold mt-8 mb-4">Jobs</h2>
                    <ul className="list-disc pl-6 space-y-2">
                      <li><code className="bg-gray-100 px-2 py-1 rounded">GET /jobs/{`{job_id}`}</code> - Get job details</li>
                      <li><code className="bg-gray-100 px-2 py-1 rounded">POST /jobs/{`{job_id}`}/approve</code> - Approve a job</li>
                      <li><code className="bg-gray-100 px-2 py-1 rounded">POST /jobs/{`{job_id}`}/generate-content</code> - Generate content for a job</li>
                      <li><code className="bg-gray-100 px-2 py-1 rounded">POST /jobs/{`{job_id}`}/apply</code> - Apply to a job (add <code className="bg-gray-100 px-2 py-1 rounded">?dry_run=true</code> for testing)</li>
                    </ul>

                    <h2 className="text-2xl font-bold mt-8 mb-4">Analytics</h2>
                    <ul className="list-disc pl-6 space-y-2">
                      <li><code className="bg-gray-100 px-2 py-1 rounded">GET /analytics/applications</code> - Get application analytics and success rates</li>
                      <li><code className="bg-gray-100 px-2 py-1 rounded">GET /metrics</code> - Get general system metrics</li>
                    </ul>

                    <h2 className="text-2xl font-bold mt-8 mb-4">Scheduler</h2>
                    <ul className="list-disc pl-6 space-y-2">
                      <li><code className="bg-gray-100 px-2 py-1 rounded">GET /scheduler/status</code> - Get scheduler status</li>
                      <li><code className="bg-gray-100 px-2 py-1 rounded">POST /scheduler/start</code> - Start the scheduler</li>
                      <li><code className="bg-gray-100 px-2 py-1 rounded">POST /scheduler/stop</code> - Stop the scheduler</li>
                      <li><code className="bg-gray-100 px-2 py-1 rounded">PUT /scheduler/config</code> - Update scheduler configuration</li>
                    </ul>

                    <h2 className="text-2xl font-bold mt-8 mb-4">Profile</h2>
                    <ul className="list-disc pl-6 space-y-2">
                      <li><code className="bg-gray-100 px-2 py-1 rounded">GET /profile</code> - Get user profile</li>
                      <li><code className="bg-gray-100 px-2 py-1 rounded">PUT /profile</code> - Update user profile</li>
                      <li><code className="bg-gray-100 px-2 py-1 rounded">POST /profile/upload-resume</code> - Upload resume file</li>
                    </ul>
                  </div>
                )}

                {activeSection === 'troubleshooting' && (
                  <div className="prose max-w-none">
                    <h1 className="text-3xl font-bold mb-4">Troubleshooting</h1>

                    <h2 className="text-2xl font-bold mt-8 mb-4">Common Issues</h2>

                    <h3 className="text-xl font-bold mt-6 mb-3">Application Fails Immediately</h3>
                    <ul className="list-disc pl-6 space-y-2">
                      <li>Check if Playwright is enabled: <code className="bg-gray-100 px-2 py-1 rounded">enable_playwright: true</code> in config.yaml</li>
                      <li>Verify browser is installed: <code className="bg-gray-100 px-2 py-1 rounded">playwright install chromium</code></li>
                      <li>Check job approval status</li>
                      <li>Review error message in job detail page</li>
                    </ul>

                    <h3 className="text-xl font-bold mt-6 mb-3">Resume Not Uploading</h3>
                    <ul className="list-disc pl-6 space-y-2">
                      <li>Verify resume file exists in <code className="bg-gray-100 px-2 py-1 rounded">resumes/</code> directory</li>
                      <li>Check file format (PDF, DOC, DOCX supported)</li>
                      <li>Ensure file is not corrupted</li>
                      <li>Try uploading again from Settings page</li>
                    </ul>

                    <h3 className="text-xl font-bold mt-6 mb-3">Form Fields Not Filling</h3>
                    <ul className="list-disc pl-6 space-y-2">
                      <li>Job board UI may have changed - selectors may need updating</li>
                      <li>Check browser console for errors (if headless=False)</li>
                      <li>Some job boards may use different form structures</li>
                      <li>Try applying manually to verify the form structure</li>
                    </ul>

                    <h3 className="text-xl font-bold mt-6 mb-3">CAPTCHA Detected</h3>
                    <ul className="list-disc pl-6 space-y-2">
                      <li>CAPTCHA protection requires manual intervention</li>
                      <li>Consider using headless=False mode to manually solve CAPTCHAs</li>
                      <li>Some job boards may require manual application</li>
                    </ul>

                    <h3 className="text-xl font-bold mt-6 mb-3">No Jobs Found</h3>
                    <ul className="list-disc pl-6 space-y-2">
                      <li>Check search parameters are correct</li>
                      <li>Verify job sources are enabled in config.yaml</li>
                      <li>Check network connectivity</li>
                      <li>Review API keys if using third-party services</li>
                    </ul>

                    <h3 className="text-xl font-bold mt-6 mb-3">Content Generation Fails</h3>
                    <ul className="list-disc pl-6 space-y-2">
                      <li>Verify <code className="bg-gray-100 px-2 py-1 rounded">OPENAI_API_KEY</code> is set correctly</li>
                      <li>Check API key has sufficient credits</li>
                      <li>Review error logs for specific error messages</li>
                    </ul>

                    <h2 className="text-2xl font-bold mt-8 mb-4">Getting Help</h2>
                    <p>For additional help:</p>
                    <ul className="list-disc pl-6 space-y-2">
                      <li>Check the logs in the console/output</li>
                      <li>Review job detail pages for specific error messages</li>
                      <li>Use dry-run mode to test applications without actually applying</li>
                      <li>Check the analytics page for success rates and patterns</li>
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

