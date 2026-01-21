/**
 * Runs Page - List and Detail Views
 */

const runsPage = {
    pollInterval: null,

    async renderList() {
        const content = document.getElementById('content');

        try {
            const runs = await api.getRuns();

            content.innerHTML = `
                <div class="page-header flex-between">
                    <div>
                        <h2>Search Runs</h2>
                        <p>${runs.length} total runs</p>
                    </div>
                    <button class="btn btn-primary" onclick="router.navigate('/')">
                        New Search
                    </button>
                </div>

                <div id="runsList">
                    ${runs.length > 0 ?
                        runs.map(run => components.runCard(run)).join('') :
                        components.emptyState('No runs yet', 'Start your first job search from the dashboard')
                    }
                </div>
            `;
        } catch (error) {
            content.innerHTML = components.emptyState('Error loading runs', error.message);
        }
    },

    async renderDetail(params) {
        const content = document.getElementById('content');
        const runId = params.id;

        try {
            const [run, jobs] = await Promise.all([
                api.getRun(runId),
                api.getRunJobs(runId)
            ]);

            const isRunning = ['pending', 'searching', 'scoring', 'content_generating', 'applying']
                .includes(run.status?.toLowerCase());

            content.innerHTML = `
                <div class="page-header">
                    <a href="#/runs" class="text-muted">&larr; Back to Runs</a>
                    <h2>Run #${run.run_id}</h2>
                    <p>Started ${components.formatDate(run.started_at)}</p>
                </div>

                <div class="stats-grid">
                    ${components.statCard(run.jobs_found || 0, 'Jobs Found')}
                    ${components.statCard(run.jobs_scored || 0, 'Jobs Scored')}
                    ${components.statCard(run.jobs_approved || 0, 'Approved')}
                    ${components.statCard(run.jobs_applied || 0, 'Applied')}
                </div>

                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">Status</h3>
                        ${isRunning ? '<div class="spinner" style="width: 1rem; height: 1rem;"></div>' : ''}
                    </div>
                    <div class="flex gap-2">
                        ${components.statusBadge(run.status)}
                        ${run.completed_at ? `
                            <span class="text-muted">
                                Completed ${components.formatDate(run.completed_at)}
                            </span>
                        ` : ''}
                    </div>
                    ${run.error_message ? `
                        <p class="text-error mt-1">${components.escapeHtml(run.error_message)}</p>
                    ` : ''}

                    ${isRunning ? `
                        <div class="mt-2">
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${this.getProgressPercent(run)}%"></div>
                            </div>
                            <p class="text-muted mt-1">${this.getProgressText(run)}</p>
                        </div>
                    ` : ''}
                </div>

                ${run.search_config ? `
                    <div class="card">
                        <div class="card-header">
                            <h3 class="card-title">Search Configuration</h3>
                        </div>
                        <table>
                            <tbody>
                                ${run.search_config.titles ? `
                                    <tr>
                                        <td>Titles</td>
                                        <td>${run.search_config.titles.join(', ')}</td>
                                    </tr>
                                ` : ''}
                                ${run.search_config.locations ? `
                                    <tr>
                                        <td>Locations</td>
                                        <td>${run.search_config.locations.join(', ')}</td>
                                    </tr>
                                ` : ''}
                                ${run.search_config.keywords ? `
                                    <tr>
                                        <td>Keywords</td>
                                        <td>${run.search_config.keywords.join(', ')}</td>
                                    </tr>
                                ` : ''}
                                <tr>
                                    <td>Remote</td>
                                    <td>${run.search_config.remote ? 'Yes' : 'No'}</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                ` : ''}

                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">Jobs from this Run</h3>
                    </div>
                    ${jobs.length > 0 ?
                        jobs.map(job => components.jobCard(job)).join('') :
                        components.emptyState('No jobs', isRunning ? 'Jobs will appear as they are found...' : 'No jobs were found in this run')
                    }
                </div>
            `;

            // Start polling if run is still active
            if (isRunning) {
                this.startPolling(runId);
            } else {
                this.stopPolling();
            }
        } catch (error) {
            content.innerHTML = components.emptyState('Error loading run', error.message);
        }
    },

    getProgressPercent(run) {
        const status = run.status?.toLowerCase();
        const statusProgress = {
            'pending': 5,
            'searching': 25,
            'scoring': 50,
            'content_generating': 75,
            'applying': 90,
            'completed': 100,
            'failed': 100
        };
        return statusProgress[status] || 0;
    },

    getProgressText(run) {
        const status = run.status?.toLowerCase();
        const statusText = {
            'pending': 'Initializing search...',
            'searching': `Searching job boards... (${run.jobs_found || 0} found)`,
            'scoring': `Scoring ${run.jobs_found || 0} jobs...`,
            'content_generating': 'Generating tailored content...',
            'applying': 'Processing applications...'
        };
        return statusText[status] || 'Processing...';
    },

    startPolling(runId) {
        this.stopPolling(); // Clear any existing polling

        this.pollInterval = setInterval(async () => {
            try {
                const run = await api.getRun(runId);
                const isRunning = ['pending', 'searching', 'scoring', 'content_generating', 'applying']
                    .includes(run.status?.toLowerCase());

                if (!isRunning) {
                    this.stopPolling();
                    this.renderDetail({ id: runId }); // Final refresh
                    components.notify('Search completed!', 'success');
                } else {
                    // Update stats without full re-render
                    this.updateRunStats(run);
                }
            } catch (error) {
                console.error('Polling error:', error);
            }
        }, 3000); // Poll every 3 seconds
    },

    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    },

    updateRunStats(run) {
        // Update stat cards if they exist
        const statCards = document.querySelectorAll('.stat-card');
        if (statCards.length >= 4) {
            statCards[0].querySelector('.stat-value').textContent = run.jobs_found || 0;
            statCards[1].querySelector('.stat-value').textContent = run.jobs_scored || 0;
            statCards[2].querySelector('.stat-value').textContent = run.jobs_approved || 0;
            statCards[3].querySelector('.stat-value').textContent = run.jobs_applied || 0;
        }

        // Update progress bar
        const progressFill = document.querySelector('.progress-fill');
        if (progressFill) {
            progressFill.style.width = `${this.getProgressPercent(run)}%`;
        }

        // Update progress text
        const progressText = document.querySelector('.progress-bar + p');
        if (progressText) {
            progressText.textContent = this.getProgressText(run);
        }
    }
};

window.runsPage = runsPage;
