'use client';

import { useEffect, useState } from 'react';
import axios from 'axios';
import Link from 'next/link';
import { format } from 'date-fns';
import Notification from '../components/Notification';

interface Job {
  id: number;
  title: string;
  company: string;
  location?: string;
  source: string;
  source_url: string;
  relevance_score?: number;
  status: string;
  approved: boolean;
  created_at: string;
  application_error?: string;
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'approved' | 'pending'>('all');
  const [selectedJobs, setSelectedJobs] = useState<Set<number>>(new Set());
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  useEffect(() => {
    fetchJobs();
  }, []);

  const fetchJobs = async () => {
    setError(null);
    try {
      // Fetch from latest run or all jobs
      const response = await axios.get('/api/runs');
      const runs = response.data;
      if (runs.length > 0) {
        const latestRunId = runs[0].run_id;
        const jobsResponse = await axios.get(`/api/runs/${latestRunId}/jobs`);
        setJobs(jobsResponse.data.jobs || jobsResponse.data);
      }
    } catch (error) {
      console.error('Error fetching jobs:', error);
      setError('Failed to load jobs. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (jobId: number) => {
    try {
      await axios.post(`/api/jobs/${jobId}/approve`);
      const newSelected = new Set(selectedJobs);
      newSelected.delete(jobId);
      setSelectedJobs(newSelected);
      fetchJobs();
      setNotification({ message: 'Job approved successfully', type: 'success' });
    } catch (error) {
      console.error('Error approving job:', error);
      setNotification({ message: 'Failed to approve job', type: 'error' });
    }
  };

  const handleBulkApprove = async () => {
    if (selectedJobs.size === 0) {
      setNotification({ message: 'Please select jobs to approve', type: 'info' });
      return;
    }

    try {
      const approvePromises = Array.from(selectedJobs).map(jobId =>
        axios.post(`/api/jobs/${jobId}/approve`)
      );
      await Promise.all(approvePromises);
      const count = selectedJobs.size;
      setSelectedJobs(new Set());
      fetchJobs();
      setNotification({ message: `Successfully approved ${count} job(s)`, type: 'success' });
    } catch (error) {
      console.error('Error bulk approving jobs:', error);
      setNotification({ message: 'Failed to approve some jobs', type: 'error' });
    }
  };

  const toggleJobSelection = (jobId: number) => {
    const newSelected = new Set(selectedJobs);
    if (newSelected.has(jobId)) {
      newSelected.delete(jobId);
    } else {
      newSelected.add(jobId);
    }
    setSelectedJobs(newSelected);
  };

  const selectAll = () => {
    const pendingJobs = filteredJobs.filter(j => !j.approved).map(j => j.id);
    setSelectedJobs(new Set(pendingJobs));
  };

  const deselectAll = () => {
    setSelectedJobs(new Set());
  };

  const filteredJobs = jobs.filter((job) => {
    if (filter === 'approved') return job.approved;
    if (filter === 'pending') return !job.approved;
    return true;
  });

  // Skeleton loader component for jobs
  const JobSkeleton = () => (
    <div className="px-6 py-4 animate-pulse">
      <div className="flex items-center justify-between">
        <div className="w-4 h-4 bg-gray-200 rounded mr-4"></div>
        <div className="flex-1">
          <div className="h-5 bg-gray-200 rounded w-1/3 mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2 mb-1"></div>
          <div className="h-3 bg-gray-200 rounded w-1/4"></div>
        </div>
        <div className="flex space-x-2">
          <div className="h-10 w-20 bg-gray-200 rounded"></div>
          <div className="h-10 w-16 bg-gray-200 rounded"></div>
        </div>
      </div>
    </div>
  );

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-50" role="main" aria-label="Jobs page">
        <nav className="bg-white shadow-sm border-b" role="navigation" aria-label="Main navigation">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16">
              <div className="flex items-center">
                <h1 className="text-xl font-bold text-gray-900">Job Search Pipeline</h1>
              </div>
            </div>
          </div>
        </nav>
        <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
          <div className="px-4 py-6 sm:px-0">
            <h2 className="text-2xl font-bold mb-6">Jobs</h2>
            <div className="bg-white shadow overflow-hidden sm:rounded-md" aria-busy="true" aria-label="Loading jobs">
              <ul className="divide-y divide-gray-200">
                {[1, 2, 3, 4, 5].map((i) => (
                  <li key={i}><JobSkeleton /></li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-gray-50" role="main" aria-label="Jobs page">
        <nav className="bg-white shadow-sm border-b" role="navigation" aria-label="Main navigation">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16">
              <div className="flex items-center">
                <h1 className="text-xl font-bold text-gray-900">Job Search Pipeline</h1>
              </div>
            </div>
          </div>
        </nav>
        <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
          <div className="px-4 py-6 sm:px-0">
            <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center" role="alert">
              <h2 className="text-lg font-semibold text-red-800 mb-2">Error Loading Jobs</h2>
              <p className="text-red-600 mb-4">{error}</p>
              <button
                onClick={() => { setLoading(true); fetchJobs(); }}
                className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
              >
                Try Again
              </button>
            </div>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50" role="main" aria-label="Jobs page">
      {notification && (
        <Notification
          message={notification.message}
          type={notification.type}
          onClose={() => setNotification(null)}
        />
      )}
      <nav className="bg-white shadow-sm border-b" role="navigation" aria-label="Main navigation">
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
                  className="border-blue-500 text-gray-900 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                  aria-current="page"
                >
                  Jobs
                </Link>
              </div>
            </div>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold">Jobs</h2>
            <div className="flex space-x-2" role="tablist" aria-label="Filter jobs">
              <button
                onClick={() => setFilter('all')}
                role="tab"
                aria-selected={filter === 'all'}
                aria-controls="jobs-list"
                className={`px-4 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${filter === 'all' ? 'bg-blue-600 text-white' : 'bg-gray-200 hover:bg-gray-300'}`}
              >
                All ({jobs.length})
              </button>
              <button
                onClick={() => setFilter('approved')}
                role="tab"
                aria-selected={filter === 'approved'}
                aria-controls="jobs-list"
                className={`px-4 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${filter === 'approved' ? 'bg-blue-600 text-white' : 'bg-gray-200 hover:bg-gray-300'}`}
              >
                Approved ({jobs.filter(j => j.approved).length})
              </button>
              <button
                onClick={() => setFilter('pending')}
                role="tab"
                aria-selected={filter === 'pending'}
                aria-controls="jobs-list"
                className={`px-4 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${filter === 'pending' ? 'bg-blue-600 text-white' : 'bg-gray-200 hover:bg-gray-300'}`}
              >
                Pending ({jobs.filter(j => !j.approved).length})
              </button>
            </div>
          </div>

          {selectedJobs.size > 0 && (
            <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg flex items-center justify-between">
              <span className="text-blue-800 font-medium">
                {selectedJobs.size} job(s) selected
              </span>
              <div className="flex space-x-2">
                <button
                  onClick={handleBulkApprove}
                  className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
                >
                  Approve Selected
                </button>
                <button
                  onClick={deselectAll}
                  className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
                >
                  Clear Selection
                </button>
              </div>
            </div>
          )}

          {filter === 'pending' && filteredJobs.filter(j => !j.approved).length > 0 && selectedJobs.size === 0 && (
            <div className="mb-4">
              <button
                onClick={selectAll}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 text-sm"
              >
                Select All Pending
              </button>
            </div>
          )}

          <div
            id="jobs-list"
            role="tabpanel"
            aria-label={`${filter} jobs`}
            className="bg-white shadow overflow-hidden sm:rounded-md"
          >
            {filteredJobs.length === 0 ? (
              <div className="px-6 py-12 text-center">
                <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <h3 className="mt-2 text-sm font-medium text-gray-900">No {filter} jobs</h3>
                <p className="mt-1 text-sm text-gray-500">
                  {filter === 'approved' && 'No jobs have been approved yet. Review pending jobs to approve them.'}
                  {filter === 'pending' && 'All jobs have been reviewed. Great work!'}
                  {filter === 'all' && 'No jobs found. Start a new search to find jobs.'}
                </p>
                {filter !== 'all' && (
                  <button
                    onClick={() => setFilter('all')}
                    className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                  >
                    View All Jobs
                  </button>
                )}
              </div>
            ) : (
              <ul className="divide-y divide-gray-200" role="list" aria-label="Job listings">
                {filteredJobs.map((job) => (
                  <li key={job.id} className={`px-6 py-4 hover:bg-gray-50 ${selectedJobs.has(job.id) ? 'bg-blue-50' : ''}`}>
                    <article className="flex items-center justify-between">
                      {!job.approved && (
                        <input
                          type="checkbox"
                          id={`job-select-${job.id}`}
                          checked={selectedJobs.has(job.id)}
                          onChange={() => toggleJobSelection(job.id)}
                          aria-label={`Select ${job.title} at ${job.company}`}
                          className="mr-4 h-4 w-4 text-blue-600 rounded focus:ring-2 focus:ring-blue-500"
                        />
                      )}
                      {job.approved && <div className="mr-4 w-4" aria-hidden="true"></div>}
                      <div className="flex-1">
                        <div className="flex items-center flex-wrap gap-2">
                          <h3 className="text-lg font-medium text-gray-900">{job.title}</h3>
                          {job.relevance_score && (
                            <span className="px-2 py-1 text-xs font-semibold bg-blue-100 text-blue-800 rounded" aria-label={`Relevance score: ${job.relevance_score.toFixed(2)}`}>
                              Score: {job.relevance_score.toFixed(2)}
                            </span>
                          )}
                          {job.approved && (
                            <span className="px-2 py-1 text-xs font-semibold bg-green-100 text-green-800 rounded">
                              Approved
                            </span>
                          )}
                          {job.status === 'application_completed' && (
                            <span className="px-2 py-1 text-xs font-semibold bg-blue-100 text-blue-800 rounded">
                              Applied
                            </span>
                          )}
                          {job.status === 'application_failed' && (
                            <span className="px-2 py-1 text-xs font-semibold bg-red-100 text-red-800 rounded">
                              Failed
                            </span>
                          )}
                        </div>
                        <div className="mt-1 text-sm text-gray-600">
                          {job.company} • {job.location || 'Location not specified'}
                        </div>
                        <div className="mt-1 text-xs text-gray-400">
                          Source: {job.source} • {format(new Date(job.created_at), 'PPp')}
                        </div>
                      </div>
                      <div className="flex space-x-2 ml-4">
                        {!job.approved && (
                          <button
                            onClick={() => handleApprove(job.id)}
                            aria-label={`Approve ${job.title}`}
                            className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
                          >
                            Approve
                          </button>
                        )}
                        <Link
                          href={`/jobs/${job.id}`}
                          aria-label={`View details for ${job.title}`}
                          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                        >
                          View
                        </Link>
                        <a
                          href={job.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label={`Open ${job.title} on ${job.source} (opens in new tab)`}
                          className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
                        >
                          Open
                        </a>
                      </div>
                    </article>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
