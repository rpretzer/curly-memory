'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import axios from 'axios';
import Link from 'next/link';
import { format } from 'date-fns';

interface RunDetail {
  run_id: number;
  status: string;
  started_at: string;
  completed_at?: string;
  jobs_found: number;
  jobs_scored: number;
  jobs_above_threshold: number;
  jobs_applied: number;
  jobs_failed: number;
}

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

export default function RunDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'above_threshold' | 'approved'>('all');

  useEffect(() => {
    if (params.id) {
      fetchRun(Number(params.id));
      fetchJobs(Number(params.id));
    }
  }, [params.id]);

  const fetchRun = async (id: number) => {
    try {
      const response = await axios.get(`/api/runs/${id}`);
      setRun(response.data);
    } catch (error) {
      console.error('Error fetching run:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchJobs = async (runId: number) => {
    try {
      const response = await axios.get(`/api/runs/${runId}/jobs`);
      setJobs(response.data);
    } catch (error) {
      console.error('Error fetching jobs:', error);
    }
  };

  const statusColors: Record<string, string> = {
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    pending: 'bg-yellow-100 text-yellow-800',
    searching: 'bg-blue-100 text-blue-800',
    scoring: 'bg-purple-100 text-purple-800',
    content_generating: 'bg-indigo-100 text-indigo-800',
    applying: 'bg-pink-100 text-pink-800',
  };

  const filteredJobs = jobs.filter((job) => {
    if (filter === 'above_threshold') {
      return job.relevance_score && job.relevance_score >= 5.0;
    }
    if (filter === 'approved') {
      return job.approved;
    }
    return true;
  });

  if (loading) {
    return <div className="p-8">Loading run details...</div>;
  }

  if (!run) {
    return (
      <div className="p-8">
        <div className="text-red-600">Run not found</div>
        <Link href="/runs" className="text-blue-600 hover:text-blue-800 mt-4 inline-block">
          ← Back to Runs
        </Link>
      </div>
    );
  }

  const duration = run.completed_at
    ? Math.round((new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000)
    : null;

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
                  className="border-blue-500 text-gray-900 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
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
              </div>
            </div>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <Link
            href="/runs"
            className="text-blue-600 hover:text-blue-800 mb-4 inline-block"
          >
            ← Back to Runs
          </Link>

          {/* Run Summary */}
          <div className="bg-white shadow rounded-lg p-6 mb-6">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">Run #{run.run_id}</h1>
                <div className="mt-2 flex items-center space-x-4">
                  <span className={`px-3 py-1 text-sm font-semibold rounded-full ${statusColors[run.status] || 'bg-gray-100 text-gray-800'}`}>
                    {run.status}
                  </span>
                  {duration && (
                    <span className="text-sm text-gray-500">
                      Duration: {duration}s
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-6">
              <div className="bg-blue-50 p-4 rounded-lg">
                <div className="text-sm text-gray-600 mb-1">Jobs Found</div>
                <div className="text-3xl font-bold text-blue-700">{run.jobs_found}</div>
              </div>
              <div className="bg-purple-50 p-4 rounded-lg">
                <div className="text-sm text-gray-600 mb-1">Jobs Scored</div>
                <div className="text-3xl font-bold text-purple-700">{run.jobs_scored}</div>
              </div>
              <div className="bg-green-50 p-4 rounded-lg">
                <div className="text-sm text-gray-600 mb-1">Above Threshold</div>
                <div className="text-3xl font-bold text-green-700">{run.jobs_above_threshold}</div>
                {run.jobs_found > 0 && (
                  <div className="text-xs text-gray-500 mt-1">
                    {Math.round((run.jobs_above_threshold / run.jobs_found) * 100)}% match rate
                  </div>
                )}
              </div>
              <div className="bg-indigo-50 p-4 rounded-lg">
                <div className="text-sm text-gray-600 mb-1">Applied</div>
                <div className="text-3xl font-bold text-indigo-700">{run.jobs_applied}</div>
              </div>
              <div className="bg-red-50 p-4 rounded-lg">
                <div className="text-sm text-gray-600 mb-1">Failed</div>
                <div className="text-3xl font-bold text-red-700">{run.jobs_failed}</div>
              </div>
            </div>

            {/* Timestamps */}
            <div className="mt-6 pt-6 border-t border-gray-200">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">Started:</span>
                  <span className="ml-2 font-medium">{format(new Date(run.started_at), 'PPp')}</span>
                </div>
                {run.completed_at && (
                  <div>
                    <span className="text-gray-500">Completed:</span>
                    <span className="ml-2 font-medium">{format(new Date(run.completed_at), 'PPp')}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Jobs List */}
          <div className="bg-white shadow rounded-lg p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">Jobs ({filteredJobs.length})</h2>
              <div className="flex space-x-2">
                <button
                  onClick={() => setFilter('all')}
                  className={`px-3 py-1 rounded text-sm ${
                    filter === 'all' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'
                  }`}
                >
                  All
                </button>
                <button
                  onClick={() => setFilter('above_threshold')}
                  className={`px-3 py-1 rounded text-sm ${
                    filter === 'above_threshold' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'
                  }`}
                >
                  Above Threshold
                </button>
                <button
                  onClick={() => setFilter('approved')}
                  className={`px-3 py-1 rounded text-sm ${
                    filter === 'approved' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'
                  }`}
                >
                  Approved
                </button>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Job
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Company
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Location
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Score
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredJobs.map((job) => (
                    <tr key={job.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">{job.title}</div>
                        <div className="text-xs text-gray-500">{job.source}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {job.company}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {job.location || 'N/A'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {job.relevance_score ? (
                          <span
                            className={`px-2 py-1 text-xs font-semibold rounded ${
                              job.relevance_score >= 8
                                ? 'bg-green-100 text-green-800'
                                : job.relevance_score >= 5
                                ? 'bg-yellow-100 text-yellow-800'
                                : 'bg-red-100 text-red-800'
                            }`}
                          >
                            {job.relevance_score.toFixed(2)}
                          </span>
                        ) : (
                          <span className="text-gray-400">N/A</span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`px-2 py-1 text-xs font-semibold rounded ${
                            job.approved
                              ? 'bg-green-100 text-green-800'
                              : job.status === 'scored'
                              ? 'bg-blue-100 text-blue-800'
                              : 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {job.approved ? 'Approved' : job.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <Link
                          href={`/jobs/${job.id}`}
                          className="text-blue-600 hover:text-blue-900 mr-4"
                        >
                          View
                        </Link>
                        <a
                          href={job.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-gray-600 hover:text-gray-900"
                        >
                          Open
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filteredJobs.length === 0 && (
                <div className="text-center py-8 text-gray-500">No jobs found</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

