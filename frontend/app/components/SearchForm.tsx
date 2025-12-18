'use client';

import { useState } from 'react';
import axios from 'axios';
import { useRouter } from 'next/navigation';

interface SearchFormProps {
  onSuccess?: (runId: number) => void;
  compact?: boolean;
}

export default function SearchForm({ onSuccess, compact = false }: SearchFormProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [formData, setFormData] = useState({
    titles: ['Product Manager'],
    locations: ['Remote, US'],
    remote: true,
    keywords: [] as string[],
    max_results: 50,
    generate_content: true,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

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

      if (onSuccess) {
        onSuccess(response.data.run_id);
      } else {
        router.push(`/runs/${response.data.run_id}`);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start search');
      console.error('Error starting search:', err);
    } finally {
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
          <button
            type="submit"
            disabled={loading}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 text-sm"
          >
            {loading ? 'Starting Search...' : 'Start Search'}
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

        <button
          type="submit"
          disabled={loading || formData.titles.length === 0}
          className="w-full px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 font-medium"
        >
          {loading ? 'Starting Search...' : 'Start Search'}
        </button>
      </form>
    </div>
  );
}

