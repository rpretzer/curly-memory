'use client';

import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { useRouter } from 'next/navigation';

interface SearchFormProps {
  onSuccess?: (runId: number) => void;
  compact?: boolean;
}

interface RunStatus {
  run_id: number;
  status: string;
  jobs_found: number;
  jobs_scored: number;
  jobs_above_threshold: number;
  started_at: string;
  completed_at?: string;
}

export default function SearchForm({ onSuccess, compact = false }: SearchFormProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState<RunStatus | null>(null);
  const [polling, setPolling] = useState(false);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  
  const [formData, setFormData] = useState({
    titles: ['Product Manager'],
    locations: ['Remote, US'],
    remote: true,
    keywords: [] as string[],
    max_results: 50,
    generate_content: true,
  });

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  const pollRunStatus = async (runId: number) => {
    try {
      const response = await axios.get(`/api/runs/${runId}`);
      const status: RunStatus = response.data;
      setRunStatus(status);

      // Check if run is complete or failed
      if (status.status === 'completed' || status.status === 'failed') {
        setPolling(false);
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }
        
        // Wait a moment then redirect or call onSuccess
        setTimeout(() => {
          if (onSuccess) {
            onSuccess(runId);
          } else {
            router.push(`/runs/${runId}`);
          }
        }, 1000);
      }
    } catch (err: any) {
      console.error('Error polling run status:', err);
      // If it's a 404, the run might have been deleted - stop polling
      if (err.response?.status === 404) {
        setError('Run not found. It may have been deleted.');
        setPolling(false);
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }
      }
      // For other errors, continue polling (might be temporary network issue)
      // But set error state
      if (err.response?.status >= 500) {
        setError(`Error checking run status: ${err.response?.data?.detail || err.message}`);
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setRunStatus(null);

    try {
      const response = await axios.post('/api/runs', {
        search: {
          titles: formData.titles.filter(t => t.trim()),
          locations: formData.locations.filter(l => l.trim()),
          remote: formData.remote,
          keywords: formData.keywords.filter(k => k.trim()),
          max_results: formData.max_results,
        },
        generate_content: formData.generate_content,
      });

      const runId = response.data.run_id;
      setRunStatus(response.data);
      setLoading(false);
      setPolling(true);

      // Start polling for status updates every 2 seconds
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
      pollingIntervalRef.current = setInterval(() => {
        pollRunStatus(runId);
      }, 2000);

      // Poll immediately
      pollRunStatus(runId);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.response?.data?.message || err.message || 'Failed to start search';
      setError(errorMessage);
      console.error('Error starting search:', err);
      console.error('Error details:', {
        status: err.response?.status,
        statusText: err.response?.statusText,
        data: err.response?.data,
        message: err.message,
      });
      setLoading(false);
    }
  };

  const addArrayItem = (field: 'titles' | 'locations' | 'keywords', value: string) => {
    if (value.trim() && !formData[field].includes(value.trim())) {
      setFormData({ ...formData, [field]: [...formData[field], value.trim()] });
    }
  };

  const removeArrayItem = (field: 'titles' | 'locations' | 'keywords', index: number) => {
    setFormData({
      ...formData,
      [field]: formData[field].filter((_, i) => i !== index),
    });
  };

  if (compact) {
    return (
      <div className="bg-white shadow rounded-lg p-4">
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Job Titles</label>
            <input
              type="text"
              value={formData.titles.join(', ')}
              onChange={(e) => setFormData({ ...formData, titles: e.target.value.split(',').map(t => t.trim()) })}
              placeholder="Product Manager, Senior PM"
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900"
              required
            />
          </div>
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
              <input
                type="text"
                value={formData.locations.join(', ')}
                onChange={(e) => setFormData({ ...formData, locations: e.target.value.split(',').map(l => l.trim()) })}
                placeholder="Remote, US"
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900"
              />
            </div>
            <div className="flex items-end">
              <label className="flex items-center space-x-2 text-sm">
                <input
                  type="checkbox"
                  checked={formData.remote}
                  onChange={(e) => setFormData({ ...formData, remote: e.target.checked })}
                  className="rounded"
                />
                <span>Remote</span>
              </label>
            </div>
          </div>
          {error && <div className="text-red-600 text-sm">{error}</div>}
          
          {/* Progress Indicator for compact view */}
          {(polling || runStatus) && runStatus && (
            <div className="p-3 bg-blue-50 border border-blue-200 rounded-md text-xs">
              <div className="flex items-center justify-between mb-1">
                <span className="font-medium">Run #{runStatus.run_id} - {runStatus.status}</span>
                {(runStatus.status === 'completed' || runStatus.status === 'failed') && (
                  <span className={runStatus.status === 'completed' ? 'text-green-600' : 'text-red-600'}>
                    {runStatus.status === 'completed' ? '✓' : '✗'}
                  </span>
                )}
              </div>
              <div className="text-gray-600">
                Jobs: {runStatus.jobs_found} found, {runStatus.jobs_scored} scored
              </div>
            </div>
          )}
          
          <button
            type="submit"
            disabled={loading || polling}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 text-sm"
          >
            {loading ? 'Starting...' : polling ? 'In Progress...' : 'Start Search'}
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <h3 className="text-lg font-semibold mb-4">Start New Search</h3>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Job Titles</label>
          <div className="flex flex-wrap gap-2 mb-2">
            {formData.titles.map((title, idx) => (
              <span
                key={idx}
                className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-800"
              >
                {title}
                <button
                  type="button"
                  onClick={() => removeArrayItem('titles', idx)}
                  className="ml-2 text-blue-600 hover:text-blue-800"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
          <input
            type="text"
            placeholder="Add job title"
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                addArrayItem('titles', e.currentTarget.value);
                e.currentTarget.value = '';
              }
            }}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Locations</label>
          <div className="flex flex-wrap gap-2 mb-2">
            {formData.locations.map((location, idx) => (
              <span
                key={idx}
                className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-green-100 text-green-800"
              >
                {location}
                <button
                  type="button"
                  onClick={() => removeArrayItem('locations', idx)}
                  className="ml-2 text-green-600 hover:text-green-800"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
          <input
            type="text"
            placeholder="Add location"
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                addArrayItem('locations', e.currentTarget.value);
                e.currentTarget.value = '';
              }
            }}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900"
          />
        </div>

        <div className="flex items-center space-x-4">
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={formData.remote}
              onChange={(e) => setFormData({ ...formData, remote: e.target.checked })}
              className="rounded"
            />
            <span className="text-sm">Remote only</span>
          </label>
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={formData.generate_content}
              onChange={(e) => setFormData({ ...formData, generate_content: e.target.checked })}
              className="rounded"
            />
            <span className="text-sm">Generate content</span>
          </label>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Max Results</label>
          <input
            type="number"
            value={formData.max_results}
            onChange={(e) => setFormData({ ...formData, max_results: parseInt(e.target.value) || 50 })}
            min={1}
            max={200}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900"
          />
        </div>

        {error && (
          <div className="p-3 bg-red-100 text-red-800 rounded-md text-sm">{error}</div>
        )}

        {/* Progress Indicator */}
        {(polling || runStatus) && runStatus && (
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-md">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                <div className={`animate-spin rounded-full h-4 w-4 border-b-2 ${
                  runStatus.status === 'completed' || runStatus.status === 'failed' 
                    ? 'border-green-500' 
                    : 'border-blue-500'
                }`}></div>
                <span className="text-sm font-medium text-gray-900">
                  Run #{runStatus.run_id} - {runStatus.status.charAt(0).toUpperCase() + runStatus.status.slice(1)}
                </span>
              </div>
              {runStatus.status === 'completed' && (
                <span className="text-xs text-green-600 font-medium">✓ Complete</span>
              )}
              {runStatus.status === 'failed' && (
                <span className="text-xs text-red-600 font-medium">✗ Failed</span>
              )}
            </div>
            
            <div className="space-y-2 text-sm text-gray-600">
              <div className="flex justify-between">
                <span>Jobs Found:</span>
                <span className="font-medium">{runStatus.jobs_found}</span>
              </div>
              {runStatus.jobs_scored > 0 && (
                <div className="flex justify-between">
                  <span>Jobs Scored:</span>
                  <span className="font-medium">{runStatus.jobs_scored}</span>
                </div>
              )}
              {runStatus.jobs_above_threshold > 0 && (
                <div className="flex justify-between">
                  <span>Above Threshold:</span>
                  <span className="font-medium text-green-600">{runStatus.jobs_above_threshold}</span>
                </div>
              )}
            </div>

            {/* Progress bar */}
            {runStatus.status !== 'completed' && runStatus.status !== 'failed' && (
              <div className="mt-3">
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{ 
                      width: `${Math.min(
                        ((runStatus.jobs_found > 0 ? 1 : 0) * 33 + 
                         (runStatus.jobs_scored > 0 ? 1 : 0) * 33 + 
                         (runStatus.status === 'completed' ? 1 : 0) * 34) * 100,
                        100
                      )}%` 
                    }}
                  ></div>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  {runStatus.status === 'pending' && 'Initializing...'}
                  {runStatus.status === 'searching' && 'Searching job boards...'}
                  {runStatus.status === 'scoring' && 'Scoring and filtering jobs...'}
                  {runStatus.status === 'content_generation' && 'Generating content...'}
                  {runStatus.status === 'completed' && 'Search complete!'}
                  {runStatus.status === 'failed' && 'Search failed. Check logs for details.'}
                </p>
              </div>
            )}
          </div>
        )}

        <button
          type="submit"
          disabled={loading || polling || formData.titles.length === 0}
          className="w-full px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 font-medium"
        >
          {loading ? 'Starting Search...' : polling ? 'Search in Progress...' : 'Start Search'}
        </button>
      </form>
    </div>
  );
}

