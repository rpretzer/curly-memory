'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import axios from 'axios';
import { format } from 'date-fns';
import DocumentViewer from '../../components/DocumentViewer';
import Notification from '../../components/Notification';

interface JobDetail {
  id: number;
  title: string;
  company: string;
  location?: string;
  source: string;
  source_url: string;
  description?: string;
  qualifications?: string;
  keywords?: string[];
  salary_min?: number;
  salary_max?: number;
  relevance_score?: number;
  scoring_breakdown?: Record<string, number>;
  status: string;
  approved: boolean;
  llm_summary?: string;
  tailored_resume_points?: string[];
  cover_letter_draft?: string;
  application_answers?: Record<string, string>;
  created_at: string;
  application_error?: string;
  application_started_at?: string;
  application_completed_at?: string;
}

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  useEffect(() => {
    if (params.id) {
      fetchJob(Number(params.id));
    }
  }, [params.id]);

  const fetchJob = async (id: number) => {
    try {
      const response = await axios.get(`/api/jobs/${id}`);
      setJob(response.data);
    } catch (error) {
      console.error('Error fetching job:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!job) return;
    try {
      await axios.post(`/api/jobs/${job.id}/approve`);
      setJob({ ...job, approved: true });
      setNotification({ message: 'Job approved successfully', type: 'success' });
    } catch (error) {
      console.error('Error approving job:', error);
      setNotification({ message: 'Failed to approve job', type: 'error' });
    }
  };

  const handleGenerateContent = async () => {
    if (!job) return;
    try {
      await axios.post(`/api/jobs/${job.id}/generate-content`);
      // Refresh job data after a delay
      setTimeout(() => fetchJob(job.id), 2000);
    } catch (error) {
      console.error('Error generating content:', error);
    }
  };

  const handleApply = async () => {
    if (!job) return;
    try {
      const response = await axios.post(`/api/jobs/${job.id}/apply`);
      if (response.data.status === 'started') {
        setNotification({ message: 'Application process started! Status will update shortly.', type: 'success' });
        // Refresh job data periodically to get updated status
        const refreshInterval = setInterval(() => {
          fetchJob(job.id);
        }, 3000);
        // Stop refreshing after 30 seconds
        setTimeout(() => clearInterval(refreshInterval), 30000);
      } else if (response.data.status === 'already_applied') {
        setNotification({ message: 'You have already applied to this job.', type: 'info' });
        fetchJob(job.id);
      }
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || 'Failed to start application';
      setNotification({ message: `Error: ${errorMsg}`, type: 'error' });
      console.error('Error applying:', error);
    }
  };

  if (loading) {
    return <div className="p-8">Loading job details...</div>;
  }

  if (!job) {
    return <div className="p-8">Job not found</div>;
  }

  return (
    <main className="min-h-screen bg-gray-50">
      {notification && (
        <Notification
          message={notification.message}
          type={notification.type}
          onClose={() => setNotification(null)}
        />
      )}
      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <button
            onClick={() => router.back()}
            className="mb-4 text-blue-600 hover:text-blue-800"
          >
            ← Back
          </button>

          <div className="bg-white shadow rounded-lg p-6 mb-6">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">{job.title}</h1>
                <p className="text-xl text-gray-600 mt-2">{job.company}</p>
                <p className="text-gray-500 mt-1">{job.location || 'Location not specified'}</p>
              </div>
              <div className="flex space-x-2">
                {!job.approved && (
                  <button
                    onClick={handleApprove}
                    className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
                  >
                    Approve
                  </button>
                )}
                {job.approved && job.status !== 'application_completed' && job.status !== 'application_started' && (
                  <button
                    onClick={handleApply}
                    disabled={job.status === 'application_started'}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {job.status === 'application_started' ? 'Applying...' : 'Apply'}
                  </button>
                )}
                {job.status === 'application_completed' && (
                  <span className="px-4 py-2 bg-green-600 text-white rounded">
                    ✓ Applied
                  </span>
                )}
                <a
                  href={job.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
                >
                  View Original
                </a>
              </div>
            </div>

            <div className="mb-4 flex flex-wrap gap-2 items-center">
              {job.relevance_score && (
                <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full font-semibold">
                  Relevance Score: {job.relevance_score.toFixed(2)}/10
                </span>
              )}
              {job.status === 'application_completed' && (
                <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full font-semibold">
                  ✓ Application Completed
                </span>
              )}
              {job.status === 'application_started' && (
                <span className="px-3 py-1 bg-yellow-100 text-yellow-800 rounded-full font-semibold">
                  ⏳ Application In Progress
                </span>
              )}
              {job.status === 'application_failed' && (
                <span className="px-3 py-1 bg-red-100 text-red-800 rounded-full font-semibold">
                  ✗ Application Failed
                </span>
              )}
            </div>
            
            {job.application_error && (
              <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                <h4 className="font-semibold text-red-800 mb-2">Application Error:</h4>
                <p className="text-red-700 text-sm">{job.application_error}</p>
                {job.application_error.includes('CAPTCHA') && (
                  <p className="text-red-600 text-xs mt-2">
                    💡 Tip: CAPTCHA detected. You may need to apply manually or solve the CAPTCHA.
                  </p>
                )}
              </div>
            )}
            
            {job.application_completed_at && (
              <div className="mb-4 text-sm text-gray-600">
                Applied on: {format(new Date(job.application_completed_at), 'PPp')}
              </div>
            )}

            {job.scoring_breakdown && (
              <div className="mb-4 p-4 bg-gray-50 rounded">
                <h3 className="font-semibold mb-2">Scoring Breakdown:</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                  {Object.entries(job.scoring_breakdown).map(([key, value]) => (
                    <div key={key}>
                      <span className="text-gray-600">{key.replace('_', ' ')}:</span>{' '}
                      <span className="font-semibold">{value.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Generated Content - Using Document Viewer */}
          {job.llm_summary && (
            <DocumentViewer
              title="AI Summary"
              content={job.llm_summary}
              type="summary"
            />
          )}

          {job.description && (
            <DocumentViewer
              title="Job Description"
              content={job.description}
              type="raw"
            />
          )}

          {job.tailored_resume_points && job.tailored_resume_points.length > 0 && (
            <DocumentViewer
              title="Tailored Resume Points"
              content={job.tailored_resume_points}
              type="resume-points"
            />
          )}

          {job.cover_letter_draft && (
            <DocumentViewer
              title="Cover Letter Draft"
              content={job.cover_letter_draft}
              type="cover-letter"
            />
          )}

          {!job.llm_summary && (
            <div className="bg-white shadow rounded-lg p-6">
              <button
                onClick={handleGenerateContent}
                className="px-6 py-3 bg-purple-600 text-white rounded hover:bg-purple-700"
              >
                Generate Content (Summary, Resume Points, Cover Letter)
              </button>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
