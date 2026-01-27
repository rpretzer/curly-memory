/**
 * API Client for Job Search Pipeline
 */

const API_BASE = 'http://localhost:8000';

const api = {
    /**
     * Make API request
     */
    async request(endpoint, options = {}) {
        const url = `${API_BASE}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);

            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: response.statusText }));
                let errorMessage = error.detail || `HTTP ${response.status}`;
                
                // Handle Pydantic validation errors (array of objects)
                if (Array.isArray(errorMessage)) {
                    errorMessage = errorMessage.map(e => `${e.loc.join('.')}: ${e.msg}`).join(', ');
                } else if (typeof errorMessage === 'object') {
                    errorMessage = JSON.stringify(errorMessage);
                }
                
                throw new Error(errorMessage);
            }

            return await response.json();
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    },

    // Runs
    async getRuns() {
        return this.request('/runs');
    },

    async getRun(id) {
        return this.request(`/runs/${id}`);
    },

    async getRunJobs(id) {
        return this.request(`/runs/${id}/jobs`);
    },

    async createRun(config) {
        return this.request('/runs', {
            method: 'POST',
            body: JSON.stringify(config)
        });
    },

    async deleteRuns() {
        return this.request('/runs', { method: 'DELETE' });
    },

    async cancelRun(id) {
        return this.request(`/runs/${id}/cancel`, { method: 'POST' });
    },

    // Jobs
    async getJobs(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/jobs${query ? '?' + query : ''}`);
    },

    async getJob(id) {
        return this.request(`/jobs/${id}`);
    },

    async approveJob(id) {
        return this.request(`/jobs/${id}/approve`, { method: 'POST' });
    },

    async rejectJob(id, reason) {
        return this.request(`/jobs/${id}/reject`, {
            method: 'POST',
            body: JSON.stringify({ reason })
        });
    },

    async applyToJob(id) {
        return this.request(`/jobs/${id}/apply`, { method: 'POST' });
    },

    async generateContent(id) {
        return this.request(`/jobs/${id}/generate-content`, { method: 'POST' });
    },

    async bulkApprove(jobIds) {
        return this.request('/jobs/bulk-approve', {
            method: 'POST',
            body: JSON.stringify({ job_ids: jobIds })
        });
    },

    async bulkReject(jobIds, reason) {
        return this.request('/jobs/bulk-reject', {
            method: 'POST',
            body: JSON.stringify({ job_ids: jobIds, reason })
        });
    },

    // Profile
    async getProfile() {
        return this.request('/profile');
    },

    async updateProfile(data) {
        return this.request('/profile', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    async uploadResume(file) {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE}/profile/upload-resume`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Failed to upload resume');
        }

        return response.json();
    },

    // Config
    async getConfig() {
        return this.request('/config');
    },

    async updateConfig(data) {
        return this.request('/config', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    // Scheduler
    async getSchedulerStatus() {
        return this.request('/scheduler/status');
    },

    async startScheduler() {
        return this.request('/scheduler/start', { method: 'POST' });
    },

    async stopScheduler() {
        return this.request('/scheduler/stop', { method: 'POST' });
    },

    // Analytics
    async getAnalytics() {
        return this.request('/analytics/applications');
    },

    // Auto-Apply
    async getAutoApplyStatus() {
        return this.request('/auto-apply/status');
    },

    async enableAutoApply() {
        return this.request('/auto-apply/enable', { method: 'POST' });
    },

    async disableAutoApply() {
        return this.request('/auto-apply/disable', { method: 'POST' });
    },

    async queueJobsForApplication(options = {}) {
        return this.request('/auto-apply/queue', {
            method: 'POST',
            body: JSON.stringify(options)
        });
    },

    async processApplicationBatch(batchSize = 5) {
        return this.request('/auto-apply/process-batch', {
            method: 'POST',
            body: JSON.stringify({ batch_size: batchSize })
        });
    },

    async startAutoApply() {
        return this.request('/auto-apply/start', { method: 'POST' });
    },

    async stopAutoApply() {
        return this.request('/auto-apply/stop', { method: 'POST' });
    },

    async autoApplyToJob(jobId) {
        return this.request(`/auto-apply/apply/${jobId}`, { method: 'POST' });
    },

    async answerQuestion(question, jobId = null) {
        return this.request('/auto-apply/answer-question', {
            method: 'POST',
            body: JSON.stringify({ question, job_id: jobId })
        });
    },

    async clearApplicationQueue() {
        return this.request('/auto-apply/clear-queue', { method: 'POST' });
    }
};

window.api = api;
