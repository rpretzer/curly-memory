/**
 * Reusable UI Components
 */

const components = {
    /**
     * Show notification toast
     */
    notify(message, type = 'info') {
        const notification = document.getElementById('notification');
        notification.textContent = message;
        notification.className = `notification ${type}`;

        setTimeout(() => {
            notification.classList.add('hidden');
        }, 3000);
    },

    /**
     * Format date for display
     */
    formatDate(dateStr) {
        if (!dateStr) return 'N/A';
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    /**
     * Format relative time
     */
    formatRelativeTime(dateStr) {
        if (!dateStr) return 'N/A';
        const date = new Date(dateStr);
        const now = new Date();
        const diff = now - date;

        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(diff / 3600000);
        const days = Math.floor(diff / 86400000);

        if (minutes < 1) return 'Just now';
        if (minutes < 60) return `${minutes}m ago`;
        if (hours < 24) return `${hours}h ago`;
        if (days < 7) return `${days}d ago`;
        return this.formatDate(dateStr);
    },

    /**
     * Get score class based on value
     */
    getScoreClass(score) {
        if (score >= 7) return 'score-high';
        if (score >= 5) return 'score-medium';
        return 'score-low';
    },

    /**
     * Get status badge HTML
     */
    statusBadge(status) {
        const statusMap = {
            'found': { class: 'badge-info', text: 'Found' },
            'scored': { class: 'badge-info', text: 'Scored' },
            'approved': { class: 'badge-success', text: 'Approved' },
            'rejected': { class: 'badge-error', text: 'Rejected' },
            'applied': { class: 'badge-success', text: 'Applied' },
            'application_started': { class: 'badge-warning', text: 'In Progress' },
            'application_completed': { class: 'badge-success', text: 'Completed' },
            'application_failed': { class: 'badge-error', text: 'Failed' },
            'pending': { class: 'badge-neutral', text: 'Pending' },
            'searching': { class: 'badge-warning', text: 'Searching' },
            'scoring': { class: 'badge-warning', text: 'Scoring' },
            'completed': { class: 'badge-success', text: 'Completed' },
            'failed': { class: 'badge-error', text: 'Failed' }
        };

        const config = statusMap[status?.toLowerCase()] || { class: 'badge-neutral', text: status || 'Unknown' };
        return `<span class="badge ${config.class}">${config.text}</span>`;
    },

    /**
     * Render job card
     */
    jobCard(job) {
        const scoreClass = this.getScoreClass(job.relevance_score || 0);
        return `
            <div class="job-card" onclick="router.navigate('/jobs/${job.id}')">
                <div class="job-card-header">
                    <div>
                        <div class="job-title">${this.escapeHtml(job.title)}</div>
                        <div class="job-company">${this.escapeHtml(job.company)}</div>
                    </div>
                    <div class="flex gap-1">
                        ${job.relevance_score ? `<span class="score ${scoreClass}">${job.relevance_score.toFixed(1)}</span>` : ''}
                        ${this.statusBadge(job.status)}
                    </div>
                </div>
                <div class="job-meta">
                    <span>${this.escapeHtml(job.location || 'Location N/A')}</span>
                    <span>${this.escapeHtml(job.source)}</span>
                    <span>${this.formatRelativeTime(job.posting_date)}</span>
                </div>
            </div>
        `;
    },

    /**
     * Render run card
     */
    runCard(run) {
        return `
            <div class="job-card" onclick="router.navigate('/runs/${run.run_id}')">
                <div class="job-card-header">
                    <div>
                        <div class="job-title">Run #${run.run_id}</div>
                        <div class="job-company">${this.formatDate(run.started_at)}</div>
                    </div>
                    ${this.statusBadge(run.status)}
                </div>
                <div class="job-meta">
                    <span>${run.jobs_found || 0} found</span>
                    <span>${run.jobs_scored || 0} scored</span>
                    <span>${run.jobs_approved || 0} approved</span>
                    <span>${run.jobs_applied || 0} applied</span>
                </div>
            </div>
        `;
    },

    /**
     * Render stat card
     */
    statCard(value, label, color = null, onClick = null) {
        const style = color ? `color: ${color}` : '';
        const cursor = onClick ? 'cursor: pointer;' : '';
        const clickAttr = onClick ? `onclick="${onClick}"` : '';
        return `
            <div class="stat-card" style="${cursor}" ${clickAttr}>
                <div class="stat-value" style="${style}">${value}</div>
                <div class="stat-label">${label}</div>
            </div>
        `;
    },

    /**
     * Render search form (single column layout like Next.js)
     */
    searchForm(profile = {}) {
        const salaryMin = profile.salary_min || '';
        const isRemote = profile.remote_preference === 'remote';

        return `
            <form id="searchForm" class="card">
                <div class="card-header flex-between">
                    <div>
                        <h3 class="card-title">Start New Search</h3>
                        <p class="text-xs text-muted">Defaults loaded from your profile. Edit for this search only.</p>
                    </div>
                    <button type="button" class="btn btn-sm btn-secondary" onclick="dashboardPage.resetSearchForm()">
                        Reset to Defaults
                    </button>
                </div>

                <div class="form-group">
                    <label class="form-label">Job Titles (this search only) <span style="color: var(--error);">*</span></label>
                    <div id="search-titles-chip-input"></div>
                </div>

                <div class="form-group">
                    <label class="form-label">Locations (this search only) <span style="color: var(--error);">*</span></label>
                    <div id="search-locations-chip-input"></div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Remote Preference</label>
                        <select class="form-select" name="remote_preference">
                            <option value="any" ${!profile.remote_preference || profile.remote_preference === 'any' ? 'selected' : ''}>Any</option>
                            <option value="remote" ${profile.remote_preference === 'remote' ? 'selected' : ''}>Remote Only</option>
                            <option value="hybrid" ${profile.remote_preference === 'hybrid' ? 'selected' : ''}>Hybrid</option>
                            <option value="on-site" ${profile.remote_preference === 'on-site' ? 'selected' : ''}>On-Site</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="checkbox-wrapper" style="margin-top: 1.75rem;">
                            <input type="checkbox" name="generate_content" checked>
                            <span>Generate content</span>
                        </label>
                    </div>
                </div>

                <div class="form-group">
                    <label class="form-label">Max Results</label>
                    <input type="number" class="form-input" name="max_results"
                        value="50" min="1" max="200">
                </div>

                <!-- Progress indicator will be inserted here -->
                <div id="search-progress-box"></div>

                <button type="submit" class="btn btn-primary" id="searchSubmitBtn" style="width: 100%;">
                    Start Search
                </button>
            </form>
        `;
    },

    /**
     * Render job description, handling both HTML and plain text
     */
    renderDescription(text) {
        if (!text) return '';
        
        // Simple heuristic: if it looks like HTML, render it as is
        // Otherwise escape it
        const hasHtml = /<[a-z][\s\S]*>/i.test(text);
        if (hasHtml) {
            return text;
        }
        
        return this.escapeHtml(text);
    },

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * Render empty state
     */
    emptyState(title, message) {
        return `
            <div class="empty-state">
                <h3>${title}</h3>
                <p>${message}</p>
            </div>
        `;
    },

    /**
     * Render loading spinner
     */
    loading() {
        return '<div class="loading"><div class="spinner"></div></div>';
    },

    /**
     * Render progress box for search status (like Next.js)
     */
    progressBox(runStatus) {
        if (!runStatus) return '';

        const isComplete = runStatus.status === 'completed' || runStatus.status === 'failed';
        const isSpinning = !isComplete;

        // Calculate progress percentage
        let progressPercent = 0;
        if (runStatus.jobs_found > 0) progressPercent = 33;
        if (runStatus.jobs_scored > 0) progressPercent = 66;
        if (runStatus.status === 'completed') progressPercent = 100;

        // Status messages
        const statusMessages = {
            'pending': 'Initializing...',
            'searching': 'Searching job boards...',
            'scoring': 'Scoring and filtering jobs...',
            'content_generation': 'Generating content...',
            'completed': 'Search complete!',
            'failed': 'Search failed. Check logs for details.'
        };

        const statusMessage = statusMessages[runStatus.status] || 'Processing...';

        return `
            <div class="progress-box">
                <div class="progress-box-header">
                    <div class="progress-box-title">
                        ${isSpinning ? '<div class="spinner-sm"></div>' : ''}
                        <span>Run #${runStatus.run_id} - ${runStatus.status.charAt(0).toUpperCase() + runStatus.status.slice(1)}</span>
                    </div>
                    ${runStatus.status === 'completed' ? '<span style="color: var(--success); font-size: 0.75rem; font-weight: 600;">✓ Complete</span>' : ''}
                    ${runStatus.status === 'failed' ? '<span style="color: var(--error); font-size: 0.75rem; font-weight: 600;">✗ Failed</span>' : ''}
                </div>

                <div class="progress-box-stats">
                    <div class="progress-box-stat">
                        <span class="progress-box-stat-label">Jobs Found:</span>
                        <span class="progress-box-stat-value">${runStatus.jobs_found || 0}</span>
                    </div>
                    ${runStatus.jobs_scored > 0 ? `
                        <div class="progress-box-stat">
                            <span class="progress-box-stat-label">Jobs Scored:</span>
                            <span class="progress-box-stat-value">${runStatus.jobs_scored}</span>
                        </div>
                    ` : ''}
                    ${runStatus.jobs_above_threshold > 0 ? `
                        <div class="progress-box-stat">
                            <span class="progress-box-stat-label">Above Threshold:</span>
                            <span class="progress-box-stat-value" style="color: var(--success);">${runStatus.jobs_above_threshold}</span>
                        </div>
                    ` : ''}
                </div>

                ${!isComplete ? `
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${progressPercent}%;"></div>
                    </div>
                    <div class="progress-box-message">${statusMessage}</div>
                ` : ''}
            </div>
        `;
    },

    /**
     * Render a chip (removable pill)
     */
    chip(text, color = 'blue', onRemove = null) {
        const removeBtn = onRemove
            ? `<button class="chip-remove" onclick="${onRemove}" aria-label="Remove ${this.escapeHtml(text)}">×</button>`
            : '';
        return `
            <span class="chip chip-${color}">
                ${this.escapeHtml(text)}
                ${removeBtn}
            </span>
        `;
    },

    /**
     * Render chip container with multiple chips
     */
    chipContainer(items, color = 'blue', removeCallback = null) {
        if (!items || items.length === 0) {
            return '<div class="chip-container"></div>';
        }

        const chips = items.map((item, idx) => {
            const onRemove = removeCallback ? `${removeCallback}(${idx})` : null;
            return this.chip(item, color, onRemove);
        }).join('');

        return `<div class="chip-container">${chips}</div>`;
    },

    /**
     * Create a typeahead input with suggestions
     * This returns an object with setup method to be called after DOM render
     */
    createTypeahead(inputId, suggestions = [], onSelect = null) {
        return {
            inputId,
            suggestions,
            onSelect,
            filteredSuggestions: [],
            activeIndex: -1,
            suggestionsId: `${inputId}-suggestions`,

            setup() {
                const input = document.getElementById(this.inputId);
                if (!input) return;

                // Wrap input in typeahead wrapper if not already wrapped
                if (!input.parentElement.classList.contains('typeahead-wrapper')) {
                    const wrapper = document.createElement('div');
                    wrapper.className = 'typeahead-wrapper';
                    input.parentNode.insertBefore(wrapper, input);
                    wrapper.appendChild(input);
                }

                const wrapper = input.parentElement;

                // Create suggestions dropdown
                const suggestionsEl = document.createElement('div');
                suggestionsEl.id = this.suggestionsId;
                suggestionsEl.className = 'typeahead-suggestions';
                suggestionsEl.style.display = 'none';
                wrapper.appendChild(suggestionsEl);

                // Input event handler
                input.addEventListener('input', (e) => {
                    const value = e.target.value.toLowerCase();
                    if (value.length === 0) {
                        this.hideSuggestions();
                        return;
                    }

                    this.filteredSuggestions = this.suggestions.filter(s =>
                        s.toLowerCase().includes(value)
                    ).slice(0, 10);

                    if (this.filteredSuggestions.length > 0) {
                        this.showSuggestions();
                    } else {
                        this.hideSuggestions();
                    }
                });

                // Keyboard navigation
                input.addEventListener('keydown', (e) => {
                    if (!suggestionsEl.style.display || suggestionsEl.style.display === 'none') return;

                    if (e.key === 'ArrowDown') {
                        e.preventDefault();
                        this.activeIndex = Math.min(this.activeIndex + 1, this.filteredSuggestions.length - 1);
                        this.updateActiveSuggestion();
                    } else if (e.key === 'ArrowUp') {
                        e.preventDefault();
                        this.activeIndex = Math.max(this.activeIndex - 1, -1);
                        this.updateActiveSuggestion();
                    } else if (e.key === 'Enter' && this.activeIndex >= 0) {
                        e.preventDefault();
                        this.selectSuggestion(this.filteredSuggestions[this.activeIndex]);
                    } else if (e.key === 'Escape') {
                        this.hideSuggestions();
                    }
                });

                // Click outside to close
                document.addEventListener('click', (e) => {
                    if (!wrapper.contains(e.target)) {
                        this.hideSuggestions();
                    }
                });
            },

            showSuggestions() {
                const suggestionsEl = document.getElementById(this.suggestionsId);
                if (!suggestionsEl) return;

                suggestionsEl.innerHTML = this.filteredSuggestions.map((suggestion, idx) =>
                    `<div class="typeahead-suggestion" data-index="${idx}">${components.escapeHtml(suggestion)}</div>`
                ).join('');

                suggestionsEl.style.display = 'block';
                this.activeIndex = -1;

                // Add click handlers
                suggestionsEl.querySelectorAll('.typeahead-suggestion').forEach((el, idx) => {
                    el.addEventListener('click', () => {
                        this.selectSuggestion(this.filteredSuggestions[idx]);
                    });
                });
            },

            hideSuggestions() {
                const suggestionsEl = document.getElementById(this.suggestionsId);
                if (suggestionsEl) {
                    suggestionsEl.style.display = 'none';
                }
                this.activeIndex = -1;
            },

            updateActiveSuggestion() {
                const suggestionsEl = document.getElementById(this.suggestionsId);
                if (!suggestionsEl) return;

                suggestionsEl.querySelectorAll('.typeahead-suggestion').forEach((el, idx) => {
                    el.classList.toggle('active', idx === this.activeIndex);
                });
            },

            selectSuggestion(value) {
                const input = document.getElementById(this.inputId);
                if (input) {
                    input.value = value;
                }
                this.hideSuggestions();
                if (this.onSelect) {
                    this.onSelect(value);
                }
            }
        };
    },

    /**
     * Render chip input field with typeahead
     * Returns HTML + setup function
     */
    chipInput(id, items = [], color = 'blue', suggestions = [], addButtonColor = 'primary') {
        const inputId = `${id}-input`;
        const containerId = `${id}-container`;
        const buttonId = `${id}-add-btn`;

        return {
            html: `
                <div class="chip-input-wrapper">
                    <div class="chip-container" id="${containerId}">
                        ${items.map((item, idx) => this.chip(item, color, `window.chipInputs['${id}'].remove(${idx})`)).join('')}
                    </div>
                    <div class="input-group">
                        <input
                            type="text"
                            id="${inputId}"
                            class="form-input"
                            placeholder="Type to add..."
                        />
                        <button type="button" id="${buttonId}" class="btn btn-${addButtonColor}">Add</button>
                    </div>
                </div>
            `,

            setup() {
                const inputEl = document.getElementById(inputId);
                const buttonEl = document.getElementById(buttonId);
                const containerEl = document.getElementById(containerId);

                if (!window.chipInputs) window.chipInputs = {};

                const chipInput = {
                    items: [...items],

                    add(value) {
                        if (!value || value.trim() === '') return;
                        const trimmed = value.trim();
                        if (this.items.includes(trimmed)) return;

                        this.items.push(trimmed);
                        this.render();
                        if (inputEl) inputEl.value = '';
                    },

                    remove(index) {
                        this.items.splice(index, 1);
                        this.render();
                    },

                    render() {
                        if (!containerEl) return;
                        containerEl.innerHTML = this.items.map((item, idx) =>
                            components.chip(item, color, `window.chipInputs['${id}'].remove(${idx})`)
                        ).join('');
                    },

                    getItems() {
                        return this.items;
                    }
                };

                window.chipInputs[id] = chipInput;

                // Add button handler
                if (buttonEl && inputEl) {
                    buttonEl.addEventListener('click', () => {
                        chipInput.add(inputEl.value);
                    });
                }

                // Enter key handler
                if (inputEl) {
                    inputEl.addEventListener('keypress', (e) => {
                        if (e.key === 'Enter') {
                            e.preventDefault();
                            chipInput.add(inputEl.value);
                        }
                    });
                }

                // Setup typeahead if suggestions provided
                if (suggestions.length > 0) {
                    const typeahead = components.createTypeahead(inputId, suggestions, (value) => {
                        chipInput.add(value);
                    });
                    typeahead.setup();
                }
            }
        };
    }
};

window.components = components;
