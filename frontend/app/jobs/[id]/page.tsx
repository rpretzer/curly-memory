'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import axios from 'axios';

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
}

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);

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
    } catch (error) {
      console.error('Error approving job:', error);
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
      await axios.post(`/api/jobs/${job.id}/apply`);
      alert('Application started!');
    } catch (error) {
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
                {job.approved && (
                  <button
                    onClick={handleApply}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                  >
                    Apply
                  </button>
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

            {job.relevance_score && (
              <div className="mb-4">
                <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full font-semibold">
                  Relevance Score: {job.relevance_score.toFixed(2)}/10
                </span>
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

          {job.llm_summary && (
            <div className="bg-white shadow rounded-lg p-6 mb-6">
              <h2 className="text-xl font-bold mb-4">AI Summary</h2>
              <p className="text-gray-700">{job.llm_summary}</p>
            </div>
          )}

          {job.description && (
            <div className="bg-white shadow rounded-lg p-6 mb-6">
              <h2 className="text-xl font-bold mb-4">Job Description</h2>
              <div className="prose max-w-none">
                <p className="text-gray-700 whitespace-pre-wrap">{job.description}</p>
              </div>
            </div>
          )}

          {job.tailored_resume_points && job.tailored_resume_points.length > 0 && (
            <div className="bg-white shadow rounded-lg p-6 mb-6">
              <h2 className="text-xl font-bold mb-4">Tailored Resume Points</h2>
              <ul className="list-disc list-inside space-y-2">
                {job.tailored_resume_points.map((point, idx) => (
                  <li key={idx} className="text-gray-700">{point}</li>
                ))}
              </ul>
            </div>
          )}

          {job.cover_letter_draft && (
            <div className="bg-white shadow rounded-lg p-6 mb-6">
              <h2 className="text-xl font-bold mb-4">Cover Letter Draft</h2>
              <div className="prose max-w-none">
                <p className="text-gray-700 whitespace-pre-wrap">{job.cover_letter_draft}</p>
              </div>
            </div>
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
