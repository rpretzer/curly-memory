'use client';

import { useState } from 'react';

interface DocumentViewerProps {
  title: string;
  content: string | string[];
  type?: 'summary' | 'cover-letter' | 'resume-points' | 'raw';
  onClose?: () => void;
}

export default function DocumentViewer({ title, content, type = 'raw', onClose }: DocumentViewerProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!content || (Array.isArray(content) && content.length === 0)) {
    return null;
  }

  const formatContent = () => {
    if (type === 'resume-points') {
      const points = Array.isArray(content) ? content : (typeof content === 'string' ? content.split('\n').filter(p => p.trim()) : []);
      return (
        <ul className="list-disc list-inside space-y-2">
          {points.map((point: string, idx: number) => (
            <li key={idx} className="text-gray-700">{point}</li>
          ))}
        </ul>
      );
    }
    const textContent = typeof content === 'string' ? content : JSON.stringify(content, null, 2);
    return <div className="prose max-w-none text-gray-700 whitespace-pre-wrap">{textContent}</div>;
  };

  return (
    <div className="bg-white shadow rounded-lg p-4 mb-4">
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        <div className="flex gap-2">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            {isExpanded ? 'Collapse' : 'Expand'}
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Close
            </button>
          )}
        </div>
      </div>
      <div
        className={`overflow-hidden transition-all duration-300 ${
          isExpanded ? 'max-h-none' : 'max-h-96'
        }`}
      >
        <div className="border border-gray-200 rounded p-4 bg-gray-50 overflow-y-auto">
          {formatContent()}
        </div>
      </div>
      {!isExpanded && (
        <button
          onClick={() => setIsExpanded(true)}
          className="mt-2 text-sm text-blue-600 hover:text-blue-800"
        >
          Show full content...
        </button>
      )}
    </div>
  );
}

