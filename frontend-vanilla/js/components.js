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
            <div class="job-card" onclick="router.navigate('/runs/${run.id}')">
                <div class="job-card-header">
                    <div>
                        <div class="job-title">Run #${run.id}</div>
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
    statCard(value, label, color = null) {
        const style = color ? `color: ${color}` : '';
        return `
            <div class="stat-card">
                <div class="stat-value" style="${style}">${value}</div>
                <div class="stat-label">${label}</div>
            </div>
        `;
    },

    /**
     * Render search form
     */
    searchForm() {
        return `
            <form id="searchForm" class="card">
                <div class="card-header">
                    <h3 class="card-title">New Job Search</h3>
                </div>

                <div class="form-group">
                    <label class="form-label">Job Titles</label>
                    <input type="text" class="form-input" name="titles"
                        placeholder="e.g., Product Manager, Senior PM" required>
                    <small class="text-muted">Separate multiple titles with commas</small>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Locations</label>
                        <input type="text" class="form-input" name="locations"
                            placeholder="e.g., Remote, New York, San Francisco">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Min Salary</label>
                        <input type="number" class="form-input" name="salary_min"
                            placeholder="e.g., 150000">
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Keywords</label>
                        <input type="text" class="form-input" name="keywords"
                            placeholder="e.g., AI, Machine Learning, Analytics">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Max Results</label>
                        <input type="number" class="form-input" name="max_results"
                            value="50" min="1" max="500">
                    </div>
                </div>

                <div class="form-group">
                    <label class="checkbox-wrapper">
                        <input type="checkbox" name="remote" checked>
                        <span>Remote positions only</span>
                    </label>
                </div>

                <div class="form-group">
                    <label class="form-label">Job Sources</label>
                    <div class="flex gap-2" style="flex-wrap: wrap;">
                        <label class="checkbox-wrapper">
                            <input type="checkbox" name="sources" value="greenhouse" checked>
                            <span>Greenhouse</span>
                        </label>
                        <label class="checkbox-wrapper">
                            <input type="checkbox" name="sources" value="workday" checked>
                            <span>Workday</span>
                        </label>
                        <label class="checkbox-wrapper">
                            <input type="checkbox" name="sources" value="linkedin" checked>
                            <span>LinkedIn</span>
                        </label>
                        <label class="checkbox-wrapper">
                            <input type="checkbox" name="sources" value="indeed">
                            <span>Indeed</span>
                        </label>
                    </div>
                </div>

                <button type="submit" class="btn btn-primary">Start Search</button>
            </form>
        `;
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
    }
};

window.components = components;
