'use client';

import { useEffect, useState } from 'react';
import axios from 'axios';
import Link from 'next/link';
import { format } from 'date-fns';
import SearchForm from '../components/SearchForm';

interface Run {
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

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRuns();
  }, []);

  const fetchRuns = async () => {
    setError(null);
    try {
      const response = await axios.get('/api/runs');
      setRuns(response.data);
    } catch (error) {
      console.error('Error fetching runs:', error);
      setError('Failed to load runs. Please try again.');
    } finally {
      setLoading(false);
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

  // Skeleton loader for runs
  const RunSkeleton = () => (
    <div className="bg-white rounded-lg shadow p-6 animate-pulse">
      <div className="flex justify-between items-start mb-4">
        <div className="h-6 bg-gray-200 rounded w-24"></div>
        <div className="h-5 bg-gray-200 rounded w-20"></div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="text-center">
            <div className="h-8 bg-gray-200 rounded w-12 mx-auto mb-1"></div>
            <div className="h-3 bg-gray-200 rounded w-16 mx-auto"></div>
          </div>
        ))}
      </div>
    </div>
  );

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-50" role="main" aria-label="Runs page">
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
            <h2 className="text-2xl font-bold mb-6">Pipeline Runs</h2>
            <div className="space-y-4" aria-busy="true" aria-label="Loading runs">
              {[1, 2, 3].map((i) => (
                <RunSkeleton key={i} />
              ))}
            </div>
          </div>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-gray-50" role="main" aria-label="Runs page">
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
              <h2 className="text-lg font-semibold text-red-800 mb-2">Error Loading Runs</h2>
              <p className="text-red-600 mb-4">{error}</p>
              <button
                onClick={() => { setLoading(true); fetchRuns(); }}
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
    <main className="min-h-screen bg-gray-50" role="main" aria-label="Runs page">
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
                  className="border-blue-500 text-gray-900 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                  aria-current="page"
                >
                  Runs
                </Link>
                <Link
                  href="/jobs"
                  className="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
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
            <h2 className="text-2xl font-bold">Pipeline Runs</h2>
            <Link
              href="/settings"
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              Configure Schedule →
            </Link>
          </div>

          {/* Quick Search Form */}
          <div className="mb-6">
            <SearchForm compact={true} onSuccess={(runId) => {
              fetchRuns();
              window.location.href = `/runs/${runId}`;
            }} />
          </div>
          
          <div className="bg-white shadow overflow-hidden sm:rounded-md">
            <ul className="divide-y divide-gray-200">
              {runs.map((run) => (
                <li key={run.run_id} className="px-6 py-4 hover:bg-gray-50">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center">
                        <span className={`px-2 py-1 text-xs font-semibold rounded-full ${statusColors[run.status] || 'bg-gray-100 text-gray-800'}`}>
                          {run.status}
                        </span>
                        <span className="ml-4 text-sm text-gray-500">
                          Run #{run.run_id}
                        </span>
                      </div>
                      <div className="mt-2 grid grid-cols-2 md:grid-cols-5 gap-4">
                        <div className="bg-blue-50 p-3 rounded">
                          <div className="text-xs text-gray-600">Jobs Found</div>
                          <div className="text-2xl font-bold text-blue-700">{run.jobs_found}</div>
                        </div>
                        <div className="bg-purple-50 p-3 rounded">
                          <div className="text-xs text-gray-600">Scored</div>
                          <div className="text-2xl font-bold text-purple-700">{run.jobs_scored}</div>
                        </div>
                        <div className="bg-green-50 p-3 rounded">
                          <div className="text-xs text-gray-600">Above Threshold</div>
                          <div className="text-2xl font-bold text-green-700">{run.jobs_above_threshold}</div>
                        </div>
                        <div className="bg-indigo-50 p-3 rounded">
                          <div className="text-xs text-gray-600">Applied</div>
                          <div className="text-2xl font-bold text-indigo-700">{run.jobs_applied}</div>
                        </div>
                        <div className="bg-red-50 p-3 rounded">
                          <div className="text-xs text-gray-600">Failed</div>
                          <div className="text-2xl font-bold text-red-700">{run.jobs_failed}</div>
                        </div>
                      </div>
                      <div className="mt-2 text-xs text-gray-400">
                        Started: {format(new Date(run.started_at), 'PPp')}
                        {run.completed_at && (
                          <> • Completed: {format(new Date(run.completed_at), 'PPp')}</>
                        )}
                      </div>
                    </div>
                    <Link
                      href={`/runs/${run.run_id}`}
                      className="ml-4 text-blue-600 hover:text-blue-800 text-sm font-medium"
                    >
                      View Details →
                    </Link>
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
