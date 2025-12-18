'use client';

import { useState } from 'react';

interface ScheduleFormProps {
  onSave?: (schedule: ScheduleConfig) => void;
}

interface ScheduleConfig {
  enabled: boolean;
  frequency: 'daily' | 'weekly' | 'custom';
  time: string;
  days?: number[];
  search_params: {
    titles: string[];
    locations: string[];
    remote: boolean;
    max_results: number;
  };
}

export default function ScheduleForm({ onSave }: ScheduleFormProps) {
  const [schedule, setSchedule] = useState<ScheduleConfig>({
    enabled: false,
    frequency: 'daily',
    time: '09:00',
    search_params: {
      titles: ['Product Manager'],
      locations: ['Remote, US'],
      remote: true,
      max_results: 50,
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (onSave) {
      onSave(schedule);
    }
    // In a real implementation, this would save to backend
    alert('Schedule saved! (Note: Backend scheduling not yet implemented)');
  };

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <h3 className="text-lg font-semibold mb-4">Schedule Automatic Searches</h3>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex items-center space-x-2">
          <input
            type="checkbox"
            id="schedule-enabled"
            checked={schedule.enabled}
            onChange={(e) => setSchedule({ ...schedule, enabled: e.target.checked })}
            className="rounded"
          />
          <label htmlFor="schedule-enabled" className="text-sm font-medium">
            Enable scheduled searches
          </label>
        </div>

        {schedule.enabled && (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Frequency
              </label>
              <select
                value={schedule.frequency}
                onChange={(e) =>
                  setSchedule({
                    ...schedule,
                    frequency: e.target.value as 'daily' | 'weekly' | 'custom',
                  })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900"
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="custom">Custom (Cron)</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Time
              </label>
              <input
                type="time"
                value={schedule.time}
                onChange={(e) => setSchedule({ ...schedule, time: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900"
              />
            </div>

            {schedule.frequency === 'weekly' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Days of Week
                </label>
                <div className="flex space-x-2">
                  {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day, idx) => (
                    <label key={idx} className="flex items-center">
                      <input
                        type="checkbox"
                        checked={schedule.days?.includes(idx) || false}
                        onChange={(e) => {
                          const days = schedule.days || [];
                          if (e.target.checked) {
                            setSchedule({ ...schedule, days: [...days, idx] });
                          } else {
                            setSchedule({
                              ...schedule,
                              days: days.filter((d) => d !== idx),
                            });
                          }
                        }}
                        className="rounded"
                      />
                      <span className="ml-1 text-sm">{day}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            <div className="pt-4 border-t border-gray-200">
              <h4 className="text-sm font-medium text-gray-700 mb-2">Search Parameters</h4>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs text-gray-600 mb-1">Job Titles</label>
                  <input
                    type="text"
                    value={schedule.search_params.titles.join(', ')}
                    onChange={(e) =>
                      setSchedule({
                        ...schedule,
                        search_params: {
                          ...schedule.search_params,
                          titles: e.target.value.split(',').map((t) => t.trim()),
                        },
                      })
                    }
                    placeholder="Product Manager, Senior PM"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">Locations</label>
                  <input
                    type="text"
                    value={schedule.search_params.locations.join(', ')}
                    onChange={(e) =>
                      setSchedule({
                        ...schedule,
                        search_params: {
                          ...schedule.search_params,
                          locations: e.target.value.split(',').map((l) => l.trim()),
                        },
                      })
                    }
                    placeholder="Remote, US"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900"
                  />
                </div>
                <div className="flex items-center space-x-4">
                  <label className="flex items-center space-x-2 text-sm">
                    <input
                      type="checkbox"
                      checked={schedule.search_params.remote}
                      onChange={(e) =>
                        setSchedule({
                          ...schedule,
                          search_params: {
                            ...schedule.search_params,
                            remote: e.target.checked,
                          },
                        })
                      }
                      className="rounded"
                    />
                    <span>Remote only</span>
                  </label>
                  <div>
                    <label className="text-sm text-gray-600 mr-2">Max Results:</label>
                    <input
                      type="number"
                      value={schedule.search_params.max_results}
                      onChange={(e) =>
                        setSchedule({
                          ...schedule,
                          search_params: {
                            ...schedule.search_params,
                            max_results: parseInt(e.target.value) || 50,
                          },
                        })
                      }
                      min={1}
                      max={200}
                      className="w-20 px-2 py-1 border border-gray-300 rounded text-sm text-gray-900"
                    />
                  </div>
                </div>
              </div>
            </div>
          </>
        )}

        <div className="pt-4">
          <button
            type="submit"
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Save Schedule
          </button>
        </div>

        {schedule.enabled && (
          <div className="text-xs text-gray-500 bg-yellow-50 p-3 rounded">
            <strong>Note:</strong> Backend scheduling (cron jobs) is not yet implemented. This UI
            is ready for when scheduling is added to the API.
          </div>
        )}
      </form>
    </div>
  );
}

