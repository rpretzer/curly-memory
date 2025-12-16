'use client';

import { useEffect, useState } from 'react';
import axios from 'axios';
import Link from 'next/link';
import { format } from 'date-fns';

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
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'approved' | 'pending'>('all');

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
      fetchJobs();
    } catch (error) {
      console.error('Error approving job:', error);
    }
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
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <Link href="/" className="flex-shrink-0 flex items-center">
                <h1 className="text-xl font-bold text-gray-900">Job Search Pipeline</h1>
              </Link>
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

          <div className="bg-white shadow overflow-hidden sm:rounded-md">
            <ul className="divide-y divide-gray-200">
              {filteredJobs.map((job) => (
                <li key={job.id} className="px-6 py-4 hover:bg-gray-50">
                  <div className="flex items-center justify-between">
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
