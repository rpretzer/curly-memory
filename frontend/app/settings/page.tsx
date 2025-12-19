'use client';

import { useEffect, useState } from 'react';
import axios from 'axios';
import Link from 'next/link';
import ScheduleForm from '../components/ScheduleForm';
import TypeaheadInput from '../components/TypeaheadInput';
import {
  LOCATION_SUGGESTIONS,
  JOB_TITLE_SUGGESTIONS,
  COMPANY_SUGGESTIONS,
  SKILL_SUGGESTIONS,
  KEYWORD_SUGGESTIONS,
} from '../data/suggestions';

// Wrapper component for array inputs
function TypeaheadInputWrapper({
  id,
  onAdd,
  suggestions,
  placeholder,
  buttonColor = 'blue',
}: {
  id: string;
  onAdd: (value: string) => void;
  suggestions: string[];
  placeholder: string;
  buttonColor?: 'blue' | 'green' | 'purple' | 'red' | 'yellow';
}) {
  const [inputValue, setInputValue] = useState('');

  const handleSelect = (value: string) => {
    onAdd(value);
    setInputValue('');
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (inputValue.trim()) {
        onAdd(inputValue.trim());
        setInputValue('');
      }
    }
  };

  const handleAddClick = () => {
    if (inputValue.trim()) {
      onAdd(inputValue.trim());
      setInputValue('');
    }
  };

  const colorClasses = {
    blue: 'bg-blue-600 hover:bg-blue-700',
    green: 'bg-green-600 hover:bg-green-700',
    purple: 'bg-purple-600 hover:bg-purple-700',
    red: 'bg-red-600 hover:bg-red-700',
    yellow: 'bg-yellow-600 hover:bg-yellow-700',
  };

  return (
    <div className="flex gap-2 flex-1">
      <div className="flex-1">
        <TypeaheadInput
          id={id}
          value={inputValue}
          onChange={setInputValue}
          onSelect={handleSelect}
          suggestions={suggestions}
          placeholder={placeholder}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900"
          onKeyPress={handleKeyPress}
        />
      </div>
      <button
        type="button"
        onClick={handleAddClick}
        className={`px-4 py-2 text-white rounded-md whitespace-nowrap ${colorClasses[buttonColor]}`}
      >
        Add
      </button>
    </div>
  );
}

// Wrapper for config array inputs
function ConfigTypeaheadWrapper({
  id,
  onAdd,
  suggestions,
  placeholder,
  existingValues,
  buttonColor = 'blue',
}: {
  id: string;
  onAdd: (value: string) => void;
  suggestions: string[];
  placeholder: string;
  existingValues: string[];
  buttonColor?: 'blue' | 'green' | 'purple' | 'red' | 'yellow';
}) {
  const [inputValue, setInputValue] = useState('');

  const handleSelect = (value: string) => {
    if (!existingValues.includes(value)) {
      onAdd(value);
      setInputValue('');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const value = inputValue.trim();
      if (value && !existingValues.includes(value)) {
        onAdd(value);
        setInputValue('');
      }
    }
  };

  const handleAddClick = () => {
    const value = inputValue.trim();
    if (value && !existingValues.includes(value)) {
      onAdd(value);
      setInputValue('');
    }
  };

  const colorClasses = {
    blue: 'bg-blue-600 hover:bg-blue-700',
    green: 'bg-green-600 hover:bg-green-700',
    purple: 'bg-purple-600 hover:bg-purple-700',
    red: 'bg-red-600 hover:bg-red-700',
    yellow: 'bg-yellow-600 hover:bg-yellow-700',
  };

  return (
    <div className="flex gap-2 flex-1">
      <div className="flex-1">
        <TypeaheadInput
          id={id}
          value={inputValue}
          onChange={setInputValue}
          onSelect={handleSelect}
          suggestions={suggestions}
          placeholder={placeholder}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900"
          onKeyPress={handleKeyPress}
        />
      </div>
      <button
        type="button"
        onClick={handleAddClick}
        className={`px-4 py-2 text-white rounded-md whitespace-nowrap ${colorClasses[buttonColor]}`}
      >
        Add
      </button>
    </div>
  );
}

interface UserProfile {
  id: number;
  name: string;
  email?: string;
  phone?: string;
  location?: string;
  linkedin_url?: string;
  portfolio_url?: string;
  github_url?: string;
  current_title?: string;
  target_titles: string[];
  skills: string[];
  experience_summary?: string;
  resume_text?: string;
  target_companies: string[];
  must_have_keywords: string[];
  nice_to_have_keywords: string[];
}

interface Config {
  search: {
    default_titles?: string[];
    default_locations?: string[];
    default_remote_preference?: string;
    default_salary_min?: number;
  };
  scoring: Record<string, number>;
  thresholds: {
    min_relevance_score?: number;
    high_relevance_score?: number;
    auto_approval_threshold?: number;
  };
  content_prompts: {
    resume_summary?: string;
    cover_letter_template?: string;
    application_answers?: string;
  };
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<'profile' | 'search' | 'schedule' | 'prompts' | 'debug'>('profile');
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [profileRes, configRes] = await Promise.all([
        axios.get('/api/profile'),
        axios.get('/api/config'),
      ]);
      setProfile(profileRes.data);
      setConfig(configRes.data);
    } catch (error) {
      console.error('Error fetching data:', error);
      setMessage({ type: 'error', text: 'Failed to load settings' });
    } finally {
      setLoading(false);
    }
  };

  const handleProfileUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile) return;

    setSaving(true);
    setMessage(null);
    try {
      await axios.put('/api/profile', profile);
      setMessage({ type: 'success', text: 'Profile updated successfully!' });
    } catch (error) {
      console.error('Error updating profile:', error);
      setMessage({ type: 'error', text: 'Failed to update profile' });
    } finally {
      setSaving(false);
    }
  };

  const handleConfigUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!config) return;

    setSaving(true);
    setMessage(null);
    try {
      await axios.put('/api/config', config);
      setMessage({ type: 'success', text: 'Configuration updated successfully!' });
    } catch (error) {
      console.error('Error updating config:', error);
      setMessage({ type: 'error', text: 'Failed to update configuration' });
    } finally {
      setSaving(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setMessage(null);
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await axios.post('/api/profile/upload-resume', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      // Reload profile to get updated resume text
      const profileRes = await axios.get('/api/profile');
      setProfile(profileRes.data);
      setMessage({ type: 'success', text: `Resume uploaded successfully! (${response.data.size} bytes)` });
    } catch (error) {
      console.error('Error uploading resume:', error);
      setMessage({ type: 'error', text: 'Failed to upload resume' });
    } finally {
      setUploading(false);
    }
  };

  const addArrayItem = (field: keyof UserProfile, value: string) => {
    if (!profile) return;
    const current = (profile[field] as string[]) || [];
    const trimmedValue = value.trim();
    if (trimmedValue && !current.includes(trimmedValue)) {
      setProfile({ ...profile, [field]: [...current, trimmedValue] });
    }
  };

  const removeArrayItem = (field: keyof UserProfile, index: number) => {
    if (!profile) return;
    const current = (profile[field] as string[]) || [];
    setProfile({ ...profile, [field]: current.filter((_, i) => i !== index) });
  };

  if (loading) {
    return <div className="p-8">Loading settings...</div>;
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
                  className="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                >
                  Jobs
                </Link>
                <Link
                  href="/settings"
                  className="border-blue-500 text-gray-900 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
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
          <div className="mb-6">
            <h2 className="text-3xl font-bold text-gray-900">Settings</h2>
            <p className="mt-2 text-gray-600">Configure your profile, search parameters, and prompts</p>
          </div>

          {message && (
            <div
              className={`mb-4 p-4 rounded-lg ${
                message.type === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
              }`}
            >
              {message.text}
            </div>
          )}

          {/* Tabs */}
          <div className="border-b border-gray-200 mb-6">
            <nav className="-mb-px flex space-x-8">
              <button
                onClick={() => setActiveTab('profile')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'profile'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Profile & Resume
              </button>
              <button
                onClick={() => setActiveTab('search')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'search'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Search Parameters
              </button>
              <button
                onClick={() => setActiveTab('schedule')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'schedule'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Schedule
              </button>
              <button
                onClick={() => setActiveTab('prompts')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'prompts'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Content Prompts
              </button>
              <button
                onClick={() => setActiveTab('debug')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'debug'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Debug & Stats
              </button>
            </nav>
          </div>

          {/* Profile Tab */}
          {activeTab === 'profile' && profile && (
            <form onSubmit={handleProfileUpdate} className="bg-white shadow rounded-lg p-6 space-y-6">
              <div>
                <h3 className="text-xl font-semibold mb-4">Personal Information</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                    <input
                      type="text"
                      value={profile.name}
                      onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                    <input
                      type="email"
                      value={profile.email || ''}
                      onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                    <input
                      type="tel"
                      value={profile.phone || ''}
                      onChange={(e) => setProfile({ ...profile, phone: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
                    <TypeaheadInput
                      value={profile.location || ''}
                      onChange={(value) => setProfile({ ...profile, location: value })}
                      suggestions={LOCATION_SUGGESTIONS}
                      placeholder="Enter location"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900"
                    />
                  </div>
                </div>
              </div>

              <div>
                <h3 className="text-xl font-semibold mb-4">Professional Information</h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Current Title</label>
                    <input
                      type="text"
                      value={profile.current_title || ''}
                      onChange={(e) => setProfile({ ...profile, current_title: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Target Job Titles</label>
                    <div className="flex flex-wrap gap-2 mb-2">
                      {profile.target_titles.map((title, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-800"
                        >
                          {title}
                          <button
                            type="button"
                            onClick={() => removeArrayItem('target_titles', idx)}
                            className="ml-2 text-blue-600 hover:text-blue-800"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <TypeaheadInputWrapper
                        id="target-titles-input"
                        onAdd={(value) => addArrayItem('target_titles', value)}
                        suggestions={JOB_TITLE_SUGGESTIONS}
                        placeholder="Add job title"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Skills</label>
                    <div className="flex flex-wrap gap-2 mb-2">
                      {profile.skills.map((skill, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-green-100 text-green-800"
                        >
                          {skill}
                          <button
                            type="button"
                            onClick={() => removeArrayItem('skills', idx)}
                            className="ml-2 text-green-600 hover:text-green-800"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <TypeaheadInputWrapper
                        id="skills-input"
                        onAdd={(value) => addArrayItem('skills', value)}
                        suggestions={SKILL_SUGGESTIONS}
                        placeholder="Add skill"
                        buttonColor="green"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Target Companies</label>
                    <div className="flex flex-wrap gap-2 mb-2">
                      {profile.target_companies.map((company, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-purple-100 text-purple-800"
                        >
                          {company}
                          <button
                            type="button"
                            onClick={() => removeArrayItem('target_companies', idx)}
                            className="ml-2 text-purple-600 hover:text-purple-800"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <TypeaheadInputWrapper
                        id="target-companies-input"
                        onAdd={(value) => addArrayItem('target_companies', value)}
                        suggestions={COMPANY_SUGGESTIONS}
                        placeholder="Add target company"
                        buttonColor="purple"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Must Have Keywords</label>
                    <div className="flex flex-wrap gap-2 mb-2">
                      {profile.must_have_keywords.map((keyword, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-red-100 text-red-800"
                        >
                          {keyword}
                          <button
                            type="button"
                            onClick={() => removeArrayItem('must_have_keywords', idx)}
                            className="ml-2 text-red-600 hover:text-red-800"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <TypeaheadInputWrapper
                        id="must-have-keywords-input"
                        onAdd={(value) => addArrayItem('must_have_keywords', value)}
                        suggestions={KEYWORD_SUGGESTIONS}
                        placeholder="Add must-have keyword"
                        buttonColor="red"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Nice to Have Keywords</label>
                    <div className="flex flex-wrap gap-2 mb-2">
                      {profile.nice_to_have_keywords.map((keyword, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-yellow-100 text-yellow-800"
                        >
                          {keyword}
                          <button
                            type="button"
                            onClick={() => removeArrayItem('nice_to_have_keywords', idx)}
                            className="ml-2 text-yellow-600 hover:text-yellow-800"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <TypeaheadInputWrapper
                        id="nice-to-have-keywords-input"
                        onAdd={(value) => addArrayItem('nice_to_have_keywords', value)}
                        suggestions={KEYWORD_SUGGESTIONS}
                        placeholder="Add nice-to-have keyword"
                        buttonColor="yellow"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Experience Summary</label>
                    <textarea
                      value={profile.experience_summary || ''}
                      onChange={(e) => setProfile({ ...profile, experience_summary: e.target.value })}
                      rows={4}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900"
                      placeholder="Brief summary of your professional experience..."
                    />
                  </div>
                </div>
              </div>

              <div>
                <h3 className="text-xl font-semibold mb-4">Resume Upload</h3>
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-6">
                  <input
                    type="file"
                    accept=".txt,.pdf,.doc,.docx"
                    onChange={handleFileUpload}
                    disabled={uploading}
                    className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                  />
                  {uploading && <p className="mt-2 text-sm text-gray-500">Uploading...</p>}
                  {profile.resume_text && (
                    <p className="mt-2 text-sm text-gray-600">
                      Resume loaded ({profile.resume_text.length} characters)
                    </p>
                  )}
                </div>
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={saving}
                  className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {saving ? 'Saving...' : 'Save Profile'}
                </button>
              </div>
            </form>
          )}

          {/* Search Parameters Tab */}
          {activeTab === 'search' && config && (
            <form onSubmit={handleConfigUpdate} className="bg-white shadow rounded-lg p-6 space-y-6">
              <div>
                <h3 className="text-xl font-semibold mb-4">Default Search Parameters</h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Default Job Titles</label>
                    <div className="flex flex-wrap gap-2 mb-2">
                      {(config.search?.default_titles || []).map((title, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-800"
                        >
                          {title}
                          <button
                            type="button"
                            onClick={() => {
                              const titles = (config.search?.default_titles || []).filter((_, i) => i !== idx);
                              setConfig({
                                ...config,
                                search: { ...config.search, default_titles: titles },
                              });
                            }}
                            className="ml-2 text-blue-600 hover:text-blue-800"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <ConfigTypeaheadWrapper
                        id="default-titles-input"
                        onAdd={(value) => {
                          if (!(config.search?.default_titles || []).includes(value)) {
                            const titles = [...(config.search?.default_titles || []), value];
                            setConfig({
                              ...config,
                              search: { ...config.search, default_titles: titles },
                            });
                          }
                        }}
                        suggestions={JOB_TITLE_SUGGESTIONS}
                        placeholder="Add default job title"
                        existingValues={config.search?.default_titles || []}
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Default Locations</label>
                    <div className="flex flex-wrap gap-2 mb-2">
                      {(config.search?.default_locations || []).map((location, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-green-100 text-green-800"
                        >
                          {location}
                          <button
                            type="button"
                            onClick={() => {
                              const locations = (config.search?.default_locations || []).filter((_, i) => i !== idx);
                              setConfig({
                                ...config,
                                search: { ...config.search, default_locations: locations },
                              });
                            }}
                            className="ml-2 text-green-600 hover:text-green-800"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <ConfigTypeaheadWrapper
                        id="default-locations-input"
                        onAdd={(value) => {
                          if (!(config.search?.default_locations || []).includes(value)) {
                            const locations = [...(config.search?.default_locations || []), value];
                            setConfig({
                              ...config,
                              search: { ...config.search, default_locations: locations },
                            });
                          }
                        }}
                        suggestions={LOCATION_SUGGESTIONS}
                        placeholder="Add default location"
                        existingValues={config.search?.default_locations || []}
                        buttonColor="green"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Remote Preference</label>
                      <select
                        value={config.search?.default_remote_preference || 'any'}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            search: { ...config.search, default_remote_preference: e.target.value },
                          })
                        }
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900"
                      >
                        <option value="any">Any</option>
                        <option value="remote">Remote</option>
                        <option value="hybrid">Hybrid</option>
                        <option value="on-site">On-Site</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Minimum Salary</label>
                      <input
                        type="number"
                        value={config.search?.default_salary_min || ''}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            search: { ...config.search, default_salary_min: parseInt(e.target.value) || undefined },
                          })
                        }
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900"
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <h3 className="text-xl font-semibold mb-4">Scoring Thresholds</h3>
                <div className="space-y-4">
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4">
                    <p className="text-sm text-blue-800">
                      <strong>Minimum Relevance Score:</strong> Jobs below this score are filtered out completely.
                      Lower this value to see more jobs (useful for debugging).
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Minimum Relevance Score (0-10)
                      </label>
                      <input
                        type="number"
                        min="0"
                        max="10"
                        step="0.1"
                        value={config.thresholds?.min_relevance_score || 5.0}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            thresholds: {
                              ...config.thresholds,
                              min_relevance_score: parseFloat(e.target.value),
                            },
                          })
                        }
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900"
                      />
                      <p className="text-xs text-gray-500 mt-1">Jobs below this score are filtered out</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        High Relevance Score (0-10)
                      </label>
                      <input
                        type="number"
                        min="0"
                        max="10"
                        step="0.1"
                        value={config.thresholds?.high_relevance_score || 8.0}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            thresholds: {
                              ...config.thresholds,
                              high_relevance_score: parseFloat(e.target.value),
                            },
                          })
                        }
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900"
                      />
                      <p className="text-xs text-gray-500 mt-1">Used for categorization</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Auto-Approval Threshold (0-10)
                      </label>
                      <input
                        type="number"
                        min="0"
                        max="10"
                        step="0.1"
                        value={config.thresholds?.auto_approval_threshold || 8.0}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            thresholds: {
                              ...config.thresholds,
                              auto_approval_threshold: parseFloat(e.target.value),
                            },
                          })
                        }
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900"
                      />
                      <p className="text-xs text-gray-500 mt-1">Jobs at/above this score are auto-approved</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={saving}
                  className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {saving ? 'Saving...' : 'Save Configuration'}
                </button>
              </div>
            </form>
          )}

          {/* Schedule Tab */}
          {activeTab === 'schedule' && (
            <ScheduleForm />
          )}

          {/* Debug Tab */}
          {activeTab === 'debug' && (
            <DebugStatsTab />
          )}

          {/* Prompts Tab */}
          {activeTab === 'prompts' && config && (
            <form onSubmit={handleConfigUpdate} className="bg-white shadow rounded-lg p-6 space-y-6">
              <div>
                <h3 className="text-xl font-semibold mb-4">Content Generation Prompts</h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Resume Summary Prompt</label>
                    <textarea
                      value={config.content_prompts?.resume_summary || ''}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          content_prompts: {
                            ...config.content_prompts,
                            resume_summary: e.target.value,
                          },
                        })
                      }
                      rows={4}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm text-gray-900"
                      placeholder="Generate 3-5 tailored bullet points for a resume..."
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Cover Letter Template</label>
                    <textarea
                      value={config.content_prompts?.cover_letter_template || ''}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          content_prompts: {
                            ...config.content_prompts,
                            cover_letter_template: e.target.value,
                          },
                        })
                      }
                      rows={6}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm text-gray-900"
                      placeholder="Write a professional cover letter..."
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Application Answers Prompt</label>
                    <textarea
                      value={config.content_prompts?.application_answers || ''}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          content_prompts: {
                            ...config.content_prompts,
                            application_answers: e.target.value,
                          },
                        })
                      }
                      rows={4}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm text-gray-900"
                      placeholder="Generate concise answers to application questions..."
                    />
                  </div>
                </div>
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={saving}
                  className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {saving ? 'Saving...' : 'Save Prompts'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </main>
  );
}

