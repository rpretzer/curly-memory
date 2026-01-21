/**
 * Jobs Page - List and Detail Views
 */

const jobsPage = {
    currentFilter: 'all',
    selectedJobs: new Set(),

    async renderList() {
        const content = document.getElementById('content');

        try {
            const jobs = await api.getJobs();

            // Group jobs by status
            const pending = jobs.filter(j => !j.approved && j.status !== 'rejected');
            const approved = jobs.filter(j => j.approved);
            const rejected = jobs.filter(j => j.status === 'rejected');
            const applied = jobs.filter(j => j.status === 'application_completed');

            // Filter based on current tab
            let displayJobs = jobs;
            if (this.currentFilter === 'pending') displayJobs = pending;
            else if (this.currentFilter === 'approved') displayJobs = approved;
            else if (this.currentFilter === 'rejected') displayJobs = rejected;
            else if (this.currentFilter === 'applied') displayJobs = applied;

            content.innerHTML = `
                <div class="page-header flex-between">
                    <div>
                        <h2>Jobs</h2>
                        <p>${jobs.length} total jobs found</p>
                    </div>
                    <div class="flex gap-1">
                        <button class="btn btn-sm btn-secondary" onclick="jobsPage.refreshList()">
                            Refresh
                        </button>
                        <button class="btn btn-sm btn-success" onclick="jobsPage.bulkApprove()"
                            id="bulkApproveBtn" ${this.selectedJobs.size === 0 ? 'disabled' : ''}>
                            Approve Selected (${this.selectedJobs.size})
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="jobsPage.bulkReject()"
                            id="bulkRejectBtn" ${this.selectedJobs.size === 0 ? 'disabled' : ''}>
                            Reject Selected (${this.selectedJobs.size})
                        </button>
                    </div>
                </div>

                <div class="tabs">
                    <button class="tab ${this.currentFilter === 'all' ? 'active' : ''}"
                        onclick="jobsPage.setFilter('all')">
                        All (${jobs.length})
                    </button>
                    <button class="tab ${this.currentFilter === 'pending' ? 'active' : ''}"
                        onclick="jobsPage.setFilter('pending')">
                        Pending (${pending.length})
                    </button>
                    <button class="tab ${this.currentFilter === 'approved' ? 'active' : ''}"
                        onclick="jobsPage.setFilter('approved')">
                        Approved (${approved.length})
                    </button>
                    <button class="tab ${this.currentFilter === 'applied' ? 'active' : ''}"
                        onclick="jobsPage.setFilter('applied')">
                        Applied (${applied.length})
                    </button>
                    <button class="tab ${this.currentFilter === 'rejected' ? 'active' : ''}"
                        onclick="jobsPage.setFilter('rejected')">
                        Rejected (${rejected.length})
                    </button>
                </div>

                <div id="jobsList">
                    ${displayJobs.length > 0 ?
                        displayJobs.map(job => this.renderJobCardWithCheckbox(job)).join('') :
                        components.emptyState('No jobs', 'No jobs match the current filter')
                    }
                </div>
            `;
        } catch (error) {
            content.innerHTML = components.emptyState('Error loading jobs', error.message);
        }
    },

    renderJobCardWithCheckbox(job) {
        const scoreClass = components.getScoreClass(job.relevance_score || 0);
        const isSelected = this.selectedJobs.has(job.id);
        const canSelect = !job.approved && job.status !== 'rejected';

        return `
            <div class="job-card" style="display: flex; gap: 1rem; align-items: flex-start;">
                ${canSelect ? `
                    <label class="checkbox-wrapper" onclick="event.stopPropagation()">
                        <input type="checkbox" ${isSelected ? 'checked' : ''}
                            onchange="jobsPage.toggleJobSelection(${job.id}, this.checked)">
                    </label>
                ` : '<div style="width: 1.25rem;"></div>'}
                <div style="flex: 1;" onclick="router.navigate('/jobs/${job.id}')">
                    <div class="job-card-header">
                        <div>
                            <div class="job-title">${components.escapeHtml(job.title)}</div>
                            <div class="job-company">${components.escapeHtml(job.company)}</div>
                        </div>
                        <div class="flex gap-1">
                            ${job.relevance_score ?
                                `<span class="score ${scoreClass}">${job.relevance_score.toFixed(1)}</span>` : ''}
                            ${components.statusBadge(job.status)}
                            ${job.approved ? '<span class="badge badge-success">Approved</span>' : ''}
                        </div>
                    </div>
                    <div class="job-meta">
                        <span>${components.escapeHtml(job.location || 'N/A')}</span>
                        <span>${components.escapeHtml(job.source)}</span>
                        <span>${components.formatRelativeTime(job.posting_date)}</span>
                    </div>
                </div>
            </div>
        `;
    },

    setFilter(filter) {
        this.currentFilter = filter;
        this.selectedJobs.clear();
        this.renderList();
    },

    toggleJobSelection(jobId, selected) {
        if (selected) {
            this.selectedJobs.add(jobId);
        } else {
            this.selectedJobs.delete(jobId);
        }

        // Update bulk approve button
        const btn = document.getElementById('bulkApproveBtn');
        if (btn) {
            btn.disabled = this.selectedJobs.size === 0;
            btn.textContent = `Approve Selected (${this.selectedJobs.size})`;
        }

        // Update bulk reject button
        const rejectBtn = document.getElementById('bulkRejectBtn');
        if (rejectBtn) {
            rejectBtn.disabled = this.selectedJobs.size === 0;
            rejectBtn.textContent = `Reject Selected (${this.selectedJobs.size})`;
        }
    },

    async bulkApprove() {
        if (this.selectedJobs.size === 0) return;

        try {
            const jobIds = Array.from(this.selectedJobs);
            await api.bulkApprove(jobIds);
            components.notify(`Approved ${jobIds.length} jobs`, 'success');
            this.selectedJobs.clear();
            this.renderList();
        } catch (error) {
            components.notify(`Error: ${error.message}`, 'error');
        }
    },

    async bulkReject() {
        if (this.selectedJobs.size === 0) return;

        const reason = prompt('Rejection reason (optional):');
        
        try {
            const jobIds = Array.from(this.selectedJobs);
            await api.bulkReject(jobIds, reason);
            components.notify(`Rejected ${jobIds.length} jobs`, 'success');
            this.selectedJobs.clear();
            this.renderList();
        } catch (error) {
            components.notify(`Error: ${error.message}`, 'error');
        }
    },

    refreshList() {
        this.renderList();
    },

    async renderDetail(params) {
        const content = document.getElementById('content');
        const jobId = params.id;

        try {
            const job = await api.getJob(jobId);

            content.innerHTML = `
                <div class="page-header">
                    <a href="#/jobs" class="text-muted">&larr; Back to Jobs</a>
                    <h2>${components.escapeHtml(job.title)}</h2>
                    <p>${components.escapeHtml(job.company)} &bull; ${components.escapeHtml(job.location || 'Location N/A')}</p>
                </div>

                <div class="stats-grid">
                    ${job.relevance_score ?
                        components.statCard(job.relevance_score.toFixed(1), 'Relevance Score') : ''}
                    ${components.statCard(job.source, 'Source')}
                    ${components.statCard(components.formatRelativeTime(job.posting_date), 'Posted')}
                </div>

                <div class="flex gap-1 mb-2">
                    ${!job.approved && job.status !== 'rejected' ? `
                        <button class="btn btn-success" onclick="jobsPage.approveJob(${job.id})">
                            Approve
                        </button>
                        <button class="btn btn-danger" onclick="jobsPage.rejectJob(${job.id})">
                            Reject
                        </button>
                    ` : ''}
                    ${job.approved && job.status !== 'application_completed' ? `
                        <button class="btn btn-primary" onclick="jobsPage.applyToJob(${job.id})">
                            Apply Now
                        </button>
                    ` : ''}
                    <button class="btn btn-secondary" onclick="jobsPage.generateContent(${job.id})">
                        Generate Content
                    </button>
                    <a href="${job.source_url}" target="_blank" class="btn btn-secondary">
                        View Original
                    </a>
                </div>

                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">Status</h3>
                    </div>
                    <div class="flex gap-2">
                        ${components.statusBadge(job.status)}
                        ${job.approved ? '<span class="badge badge-success">Approved</span>' : ''}
                    </div>
                    ${job.application_error ? `
                        <p class="text-error mt-1">${components.escapeHtml(job.application_error)}</p>
                    ` : ''}
                </div>

                ${job.description ? `
                    <div class="card">
                        <div class="card-header">
                            <h3 class="card-title">Description</h3>
                        </div>
                        <div style="white-space: pre-wrap; color: var(--text-secondary);">
                            ${components.renderDescription(job.description)}
                        </div>
                    </div>
                ` : ''}

                ${job.scoring_breakdown ? `
                    <div class="card">
                        <div class="card-header">
                            <h3 class="card-title">Scoring Breakdown</h3>
                        </div>
                        <table>
                            <tbody>
                                ${Object.entries(job.scoring_breakdown).map(([key, value]) => `
                                    <tr>
                                        <td>${key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</td>
                                        <td class="text-right">${typeof value === 'number' ? value.toFixed(2) : value}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                ` : ''}

                ${job.cover_letter_draft ? `
                    <div class="card">
                        <div class="card-header">
                            <h3 class="card-title">Generated Cover Letter</h3>
                        </div>
                        <div style="white-space: pre-wrap; color: var(--text-secondary);">
                            ${components.escapeHtml(job.cover_letter_draft)}
                        </div>
                    </div>
                ` : ''}

                ${job.tailored_resume_points?.length > 0 ? `
                    <div class="card">
                        <div class="card-header">
                            <h3 class="card-title">Resume Points</h3>
                        </div>
                        <ul style="margin-left: 1.5rem; color: var(--text-secondary);">
                            ${job.tailored_resume_points.map(point =>
                                `<li style="margin-bottom: 0.5rem;">${components.escapeHtml(point)}</li>`
                            ).join('')}
                        </ul>
                    </div>
                ` : ''}
            `;
        } catch (error) {
            content.innerHTML = components.emptyState('Error loading job', error.message);
        }
    },

    async approveJob(id) {
        try {
            await api.approveJob(id);
            components.notify('Job approved!', 'success');
            this.renderDetail({ id });
        } catch (error) {
            components.notify(`Error: ${error.message}`, 'error');
        }
    },

    async rejectJob(id) {
        const reason = prompt('Rejection reason (optional):');
        try {
            await api.rejectJob(id, reason);
            components.notify('Job rejected', 'success');
            this.renderDetail({ id });
        } catch (error) {
            components.notify(`Error: ${error.message}`, 'error');
        }
    },

    async applyToJob(id) {
        try {
            components.notify('Starting application...', 'info');
            const result = await api.applyToJob(id);
            components.notify('Application process started', 'success');
            this.renderDetail({ id });
        } catch (error) {
            components.notify(`Error: ${error.message}`, 'error');
        }
    },

    async generateContent(id) {
        try {
            components.notify('Generating content...', 'info');
            await api.generateContent(id);
            components.notify('Content generated!', 'success');
            this.renderDetail({ id });
        } catch (error) {
            components.notify(`Error: ${error.message}`, 'error');
        }
    }
};

window.jobsPage = jobsPage;
