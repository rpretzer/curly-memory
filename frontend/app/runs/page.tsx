'use client';

import { useEffect, useState } from 'react';
import axios from 'axios';
import Link from 'next/link';
import { format } from 'date-fns';

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

  useEffect(() => {
    fetchRuns();
  }, []);

  const fetchRuns = async () => {
    try {
      const response = await axios.get('/api/runs');
      setRuns(response.data);
    } catch (error) {
      console.error('Error fetching runs:', error);
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

  if (loading) {
    return <div className="p-8">Loading runs...</div>;
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
          <h2 className="text-2xl font-bold mb-6">Pipeline Runs</h2>
          
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
                      <div className="mt-2 grid grid-cols-2 md:grid-cols-6 gap-4 text-sm">
                        <div>
                          <span className="text-gray-500">Found:</span>
                          <span className="ml-2 font-semibold">{run.jobs_found}</span>
                        </div>
                        <div>
                          <span className="text-gray-500">Scored:</span>
                          <span className="ml-2 font-semibold">{run.jobs_scored}</span>
                        </div>
                        <div>
                          <span className="text-gray-500">Above Threshold:</span>
                          <span className="ml-2 font-semibold">{run.jobs_above_threshold}</span>
                        </div>
                        <div>
                          <span className="text-gray-500">Applied:</span>
                          <span className="ml-2 font-semibold">{run.jobs_applied}</span>
                        </div>
                        <div>
                          <span className="text-gray-500">Failed:</span>
                          <span className="ml-2 font-semibold">{run.jobs_failed}</span>
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
