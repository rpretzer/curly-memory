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
  const [filter, setFilter] = useState<'all' | 'approved' | 'pending'>('all');
  const [selectedJobs, setSelectedJobs] = useState<Set<number>>(new Set());
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  useEffect(() => {
    fetchJobs();
  }, []);

  const fetchJobs = async () => {
    try {
      // Fetch from latest run or all jobs
      const response = await axios.get('/api/runs');
      const runs = response.data;
      if (runs.length > 0) {
        const latestRunId = runs[0].run_id;
        const jobsResponse = await axios.get(`/api/runs/${latestRunId}/jobs`);
        setJobs(jobsResponse.data);
      }
    } catch (error) {
      console.error('Error fetching jobs:', error);
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

  if (loading) {
    return <div className="p-8">Loading jobs...</div>;
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
                  className="border-blue-500 text-gray-900 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
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
            <div className="flex space-x-2">
              <button
                onClick={() => setFilter('all')}
                className={`px-4 py-2 rounded ${filter === 'all' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
              >
                All
              </button>
              <button
                onClick={() => setFilter('approved')}
                className={`px-4 py-2 rounded ${filter === 'approved' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
              >
                Approved
              </button>
              <button
                onClick={() => setFilter('pending')}
                className={`px-4 py-2 rounded ${filter === 'pending' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
              >
                Pending
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

          <div className="bg-white shadow overflow-hidden sm:rounded-md">
            <ul className="divide-y divide-gray-200">
              {filteredJobs.map((job) => (
                <li key={job.id} className={`px-6 py-4 hover:bg-gray-50 ${selectedJobs.has(job.id) ? 'bg-blue-50' : ''}`}>
                  <div className="flex items-center justify-between">
                    {!job.approved && (
                      <input
                        type="checkbox"
                        checked={selectedJobs.has(job.id)}
                        onChange={() => toggleJobSelection(job.id)}
                        className="mr-4 h-4 w-4 text-blue-600 rounded"
                      />
                    )}
                    {job.approved && <div className="mr-4 w-4"></div>}
                    <div className="flex-1">
                      <div className="flex items-center">
                        <h3 className="text-lg font-medium text-gray-900">{job.title}</h3>
                        {job.relevance_score && (
                          <span className="ml-4 px-2 py-1 text-xs font-semibold bg-blue-100 text-blue-800 rounded">
                            Score: {job.relevance_score.toFixed(2)}
                          </span>
                        )}
                        {job.approved && (
                          <span className="ml-2 px-2 py-1 text-xs font-semibold bg-green-100 text-green-800 rounded">
                            Approved
                          </span>
                        )}
                        {job.status === 'application_completed' && (
                          <span className="ml-2 px-2 py-1 text-xs font-semibold bg-blue-100 text-blue-800 rounded">
                            Applied
                          </span>
                        )}
                        {job.status === 'application_failed' && (
                          <span className="ml-2 px-2 py-1 text-xs font-semibold bg-red-100 text-red-800 rounded">
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
                    <div className="flex space-x-2">
                      {!job.approved && (
                        <button
                          onClick={() => handleApprove(job.id)}
                          className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
                        >
                          Approve
                        </button>
                      )}
                      <Link
                        href={`/jobs/${job.id}`}
                        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                      >
                        View
                      </Link>
                      <a
                        href={job.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
                      >
                        Open
                      </a>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </main>
  );
}
