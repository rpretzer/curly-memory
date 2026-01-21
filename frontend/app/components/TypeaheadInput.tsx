'use client';

import { useState, useRef, useEffect, useId } from 'react';

interface TypeaheadInputProps {
  value: string;
  onChange: (value: string) => void;
  onSelect?: (value: string) => void;
  suggestions: string[];
  placeholder?: string;
  className?: string;
  id?: string;
  onKeyPress?: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  'aria-label'?: string;
}

export default function TypeaheadInput({
  value,
  onChange,
  onSelect,
  suggestions,
  placeholder,
  className = '',
  id,
  onKeyPress,
  'aria-label': ariaLabel,
}: TypeaheadInputProps) {
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [filteredSuggestions, setFilteredSuggestions] = useState<string[]>([]);
  const [activeIndex, setActiveIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const listboxId = useId();
  const inputId = id || useId();

  useEffect(() => {
    if (value && suggestions.length > 0) {
      const filtered = suggestions
        .filter((s) => s.toLowerCase().includes(value.toLowerCase()))
        .filter((s) => s.toLowerCase() !== value.toLowerCase())
        .slice(0, 8);
      setFilteredSuggestions(filtered);
      setShowSuggestions(filtered.length > 0);
    } else {
      setFilteredSuggestions([]);
      setShowSuggestions(false);
    }
  }, [value, suggestions]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.value);
    setActiveIndex(-1);
  };

  const handleSelect = (suggestion: string) => {
    onChange(suggestion);
    if (onSelect) {
      onSelect(suggestion);
    }
    setShowSuggestions(false);
    setActiveIndex(-1);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showSuggestions || filteredSuggestions.length === 0) {
      if (onKeyPress) {
        onKeyPress(e);
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setActiveIndex((prev) =>
          prev < filteredSuggestions.length - 1 ? prev + 1 : prev
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setActiveIndex((prev) => (prev > 0 ? prev - 1 : -1));
        break;
      case 'Enter':
        e.preventDefault();
        if (activeIndex >= 0 && activeIndex < filteredSuggestions.length) {
          handleSelect(filteredSuggestions[activeIndex]);
        } else if (onKeyPress) {
          onKeyPress(e);
        }
        break;
      case 'Escape':
        setShowSuggestions(false);
        setActiveIndex(-1);
        break;
      default:
        if (onKeyPress) {
          onKeyPress(e);
        }
    }
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        suggestionsRef.current &&
        !suggestionsRef.current.contains(event.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(event.target as Node)
      ) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  return (
    <div className="relative">
      <input
        ref={inputRef}
        id={inputId}
        type="text"
        role="combobox"
        aria-expanded={showSuggestions && filteredSuggestions.length > 0}
        aria-haspopup="listbox"
        aria-controls={listboxId}
        aria-autocomplete="list"
        aria-activedescendant={activeIndex >= 0 ? `${listboxId}-option-${activeIndex}` : undefined}
        aria-label={ariaLabel || placeholder}
        value={value}
        onChange={handleInputChange}
        onKeyDown={handleKeyDown}
        onFocus={() => {
          if (filteredSuggestions.length > 0) {
            setShowSuggestions(true);
          }
        }}
        placeholder={placeholder}
        className={className}
        autoComplete="off"
      />
      {showSuggestions && filteredSuggestions.length > 0 && (
        <div
          ref={suggestionsRef}
          id={listboxId}
          role="listbox"
          aria-label={`${ariaLabel || placeholder} suggestions`}
          className="absolute z-50 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto"
        >
          {filteredSuggestions.map((suggestion, index) => (
            <div
              key={index}
              id={`${listboxId}-option-${index}`}
              role="option"
              aria-selected={index === activeIndex}
              onClick={() => handleSelect(suggestion)}
              className={`px-4 py-2 cursor-pointer hover:bg-blue-50 ${
                index === activeIndex ? 'bg-blue-100' : ''
              }`}
            >
              <span className="text-sm text-gray-900">{suggestion}</span>
            </div>
          ))}
        </div>
      )}
      {/* Screen reader announcement for suggestions count */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {showSuggestions && filteredSuggestions.length > 0
          ? `${filteredSuggestions.length} suggestions available. Use arrow keys to navigate.`
          : ''}
      </div>
    </div>
  );
}


