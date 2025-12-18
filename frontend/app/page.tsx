'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import axios from 'axios';
import SearchForm from './components/SearchForm';

interface Run {
  run_id: number;
  status: string;
  jobs_found: number;
  jobs_above_threshold: number;
  started_at: string;
}

export default function Home() {
  const [recentRuns, setRecentRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRecentRuns();
  }, []);

  const fetchRecentRuns = async () => {
    try {
      const response = await axios.get('/api/runs');
      setRecentRuns(response.data.slice(0, 5));
    } catch (error) {
      console.error('Error fetching runs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchSuccess = (runId: number) => {
    // Refresh recent runs
    fetchRecentRuns();
    // Optionally redirect to run details
    window.location.href = `/runs/${runId}`;
  };

  return (
    <main className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <div className="flex-shrink-0 flex items-center">
                <h1 className="text-xl font-bold text-gray-900">Job Search Pipeline</h1>
              </div>
              <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
                <Link
                  href="/"
                  className="border-blue-500 text-gray-900 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
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
              </div>
            </div>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Search Form */}
            <div className="lg:col-span-2">
              <SearchForm onSuccess={handleSearchSuccess} />
            </div>

            {/* Recent Runs */}
            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-lg font-semibold mb-4">Recent Runs</h3>
              {loading ? (
                <div className="text-gray-500 text-sm">Loading...</div>
              ) : recentRuns.length === 0 ? (
                <div className="text-gray-500 text-sm">No runs yet. Start a search!</div>
              ) : (
                <div className="space-y-3">
                  {recentRuns.map((run) => (
                    <Link
                      key={run.run_id}
                      href={`/runs/${run.run_id}`}
                      className="block p-3 border border-gray-200 rounded-md hover:bg-gray-50 transition"
                    >
                      <div className="flex justify-between items-start">
                        <div>
                          <div className="font-medium text-sm">Run #{run.run_id}</div>
                          <div className="text-xs text-gray-500 mt-1">
                            {run.jobs_found} jobs found • {run.jobs_above_threshold} above threshold
                          </div>
                        </div>
                        <span
                          className={`px-2 py-1 text-xs rounded-full ${
                            run.status === 'completed'
                              ? 'bg-green-100 text-green-800'
                              : run.status === 'failed'
                              ? 'bg-red-100 text-red-800'
                              : 'bg-yellow-100 text-yellow-800'
                          }`}
                        >
                          {run.status}
                        </span>
                      </div>
                    </Link>
                  ))}
                  <Link
                    href="/runs"
                    className="block text-center text-sm text-blue-600 hover:text-blue-800 mt-4"
                  >
                    View All Runs →
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
