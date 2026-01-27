/**
 * Dashboard Page
 */

const dashboardPage = {
    async render() {
        const content = document.getElementById('content');

        // Fetch data in parallel
        const [runs, jobs, profile] = await Promise.all([
            api.getRuns().catch(() => []),
            api.getJobs({ limit: 10 }).catch(() => []),
            api.getProfile().catch(() => ({}))
        ]);

        // Calculate stats from runs data (not limited jobs)
        const recentRuns = runs.slice(0, 5);
        const totalJobsFound = runs.reduce((sum, r) => sum + (r.jobs_found || 0), 0);
        const totalJobsApproved = runs.reduce((sum, r) => sum + (r.jobs_approved || 0), 0);
        const totalJobsApplied = runs.reduce((sum, r) => sum + (r.jobs_applied || 0), 0);
        const totalJobsScored = runs.reduce((sum, r) => sum + (r.jobs_scored || 0), 0);
        // Pending = scored but not approved and not applied
        const pendingCount = Math.max(0, totalJobsScored - totalJobsApproved - totalJobsApplied);

        // Check if stats should be shown
        const showStats = localStorage.getItem('showStats') !== 'false'; // default true

        content.innerHTML = `
            <div class="page-header">
                <h2>Dashboard</h2>
                <p>Job search pipeline overview</p>
            </div>

            ${showStats ? `
                <div class="stats-grid">
                    ${components.statCard(runs.length, 'Total Runs', null, "router.navigate('/runs')")}
                    ${components.statCard(totalJobsFound, 'Jobs Found', null, "dashboardPage.goToJobs('all')")}
                    ${components.statCard(pendingCount, 'Pending Review', '#f59e0b', "dashboardPage.goToJobs('pending')")}
                    ${components.statCard(totalJobsApproved, 'Approved', '#10b981', "dashboardPage.goToJobs('approved')")}
                    ${components.statCard(totalJobsApplied, 'Applied', '#3b82f6', "dashboardPage.goToJobs('applied')")}
                </div>
            ` : ''}

            ${components.searchForm(profile)}

            <div class="card mt-2">
                <div class="card-header">
                    <h3 class="card-title">Recent Runs</h3>
                    <div class="flex gap-1">
                        ${recentRuns.length > 0 ? 
                            '<button class="btn btn-sm btn-danger" onclick="dashboardPage.clearRuns()">Clear All</button>' : ''}
                        <a href="#/runs" class="btn btn-sm btn-secondary">View All</a>
                    </div>
                </div>
                ${recentRuns.length > 0 ?
                    recentRuns.map(run => components.runCard(run)).join('') :
                    components.emptyState('No runs yet', 'Start your first job search above')
                }
            </div>

            <div class="card mt-2">
                <div class="card-header">
                    <h3 class="card-title">Recent Jobs</h3>
                    <a href="#/jobs" class="btn btn-sm btn-secondary">View All</a>
                </div>
                ${jobs.length > 0 ?
                    jobs.slice(0, 5).map(job => components.jobCard(job)).join('') :
                    components.emptyState('No jobs found', 'Run a search to find jobs')
                }
            </div>
        `;

        // Attach search form handler
        this.attachSearchHandler();
    },

    goToJobs(filter) {
        if (window.jobsPage) {
            window.jobsPage.currentFilter = filter;
        }
        router.navigate('/jobs');
    },

    resetSearchForm() {
        const form = document.getElementById('searchForm');
        if (!form) return;

        const defaults = window.searchFormDefaults || {
            titles: [],
            locations: [],
            remote_preference: 'any',
            max_results: 50
        };

        // Reset chip inputs
        if (window.chipInputs['search-titles']) {
            window.chipInputs['search-titles'].items = [...defaults.titles];
            window.chipInputs['search-titles'].render();
        }
        if (window.chipInputs['search-locations']) {
            window.chipInputs['search-locations'].items = [...defaults.locations];
            window.chipInputs['search-locations'].render();
        }

        // Reset form fields
        const remoteSelect = form.querySelector('select[name="remote_preference"]');
        if (remoteSelect) {
            remoteSelect.value = defaults.remote_preference;
        }

        const maxResultsInput = form.querySelector('input[name="max_results"]');
        if (maxResultsInput) {
            maxResultsInput.value = defaults.max_results;
        }

        const generateContentCheckbox = form.querySelector('input[name="generate_content"]');
        if (generateContentCheckbox) {
            generateContentCheckbox.checked = true;
        }

        components.notify('Form reset to defaults', 'info');
    },

    attachSearchHandler() {
        const form = document.getElementById('searchForm');
        if (!form) return;

        // Setup chip inputs helper
        const setupChipInput = (id, items, color, suggestions) => {
            const container = document.getElementById(id);
            if (!container) {
                console.warn(`Container not found for chip input: ${id}`);
                return;
            }

            const chipInput = components.chipInput(id.replace('-chip-input', ''), items, color, suggestions, 'primary');
            container.innerHTML = chipInput.html;
            chipInput.setup();
        };

        // Setup chip inputs - empty by default, will be populated from profile if available
        setupChipInput('search-titles-chip-input', [], 'blue', SUGGESTIONS.jobTitles);
        setupChipInput('search-locations-chip-input', [], 'green', SUGGESTIONS.locations);

        // Store default values for reset functionality
        const formDefaults = {
            titles: [],
            locations: [],
            remote_preference: 'any',
            max_results: 50
        };

        // Update with profile data when available
        api.getProfile().then(profile => {
            if (profile.target_titles && profile.target_titles.length > 0) {
                setupChipInput('search-titles-chip-input', profile.target_titles, 'blue', SUGGESTIONS.jobTitles);
                formDefaults.titles = profile.target_titles;
            }
            // Pre-populate locations from profile's location if available
            if (profile.location) {
                setupChipInput('search-locations-chip-input', [profile.location], 'green', SUGGESTIONS.locations);
                formDefaults.locations = [profile.location];
            }
            // Pre-populate remote preference
            if (profile.remote_preference) {
                const remoteSelect = form.querySelector('select[name="remote_preference"]');
                if (remoteSelect) {
                    remoteSelect.value = profile.remote_preference;
                    formDefaults.remote_preference = profile.remote_preference;
                }
            }
        }).catch(error => {
            console.warn('Could not load profile for search form:', error);
        });

        // Store defaults globally for reset button
        window.searchFormDefaults = formDefaults;

        // Polling state
        let pollingInterval = null;

        const stopPolling = () => {
            if (pollingInterval) {
                clearInterval(pollingInterval);
                pollingInterval = null;
            }
        };

        const resetFormState = () => {
            stopPolling();
            this.currentRunId = null;
            const submitBtn = document.getElementById('searchSubmitBtn');
            const cancelBtn = document.getElementById('searchCancelBtn');
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Start Search';
            }
            if (cancelBtn) {
                cancelBtn.style.display = 'none';
            }
        };

        // Expose resetFormState for cancel button
        this.resetFormState = resetFormState;

        const pollRunStatus = async (runId) => {
            try {
                const runStatus = await api.getRun(runId);

                // Update progress box
                const progressBox = document.getElementById('search-progress-box');
                if (progressBox) {
                    progressBox.innerHTML = components.progressBox(runStatus);
                }

                // Check if complete or cancelled
                if (runStatus.status === 'completed' || runStatus.status === 'failed' || runStatus.status === 'cancelled') {
                    resetFormState();

                    // Only redirect if completed successfully
                    if (runStatus.status === 'completed') {
                        setTimeout(() => {
                            router.navigate(`/runs/${runId}`);
                        }, 1500);
                    } else if (runStatus.status === 'cancelled') {
                        components.notify('Search cancelled', 'info');
                        // Clear progress box
                        const progressBox = document.getElementById('search-progress-box');
                        if (progressBox) {
                            progressBox.innerHTML = '';
                        }
                    }
                }
            } catch (error) {
                console.error('Error polling run status:', error);
                stopPolling();
            }
        };

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const formData = new FormData(form);
            const submitBtn = document.getElementById('searchSubmitBtn');

            // Get chip input values
            const titles = window.chipInputs['search-titles']?.getItems() || [];
            const locations = window.chipInputs['search-locations']?.getItems() || [];

            // Validation
            if (titles.length === 0) {
                components.notify('At least one job title is required', 'error');
                return;
            }
            if (locations.length === 0) {
                components.notify('At least one location is required', 'error');
                return;
            }

            // Construct the payload
            const remotePreference = formData.get('remote_preference');
            const searchConfig = {
                titles: titles,
                locations: locations,
                remote: remotePreference === 'remote',  // For backward compatibility with backend
                remote_preference: remotePreference,
                max_results: parseInt(formData.get('max_results')) || 50
            };

            const runConfig = {
                search: searchConfig,
                generate_content: formData.get('generate_content') === 'on',
                auto_apply: false
            };

            try {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Starting Search...';

                const run = await api.createRun(runConfig);
                this.currentRunId = run.run_id;

                // Show cancel button
                const cancelBtn = document.getElementById('searchCancelBtn');
                if (cancelBtn) {
                    cancelBtn.style.display = 'inline-flex';
                }

                // Show initial progress
                const progressBox = document.getElementById('search-progress-box');
                if (progressBox) {
                    progressBox.innerHTML = components.progressBox(run);
                }

                submitBtn.textContent = 'Search in Progress...';

                // Start polling every 2 seconds
                stopPolling(); // Clear any existing interval
                pollingInterval = setInterval(() => {
                    pollRunStatus(run.run_id);
                }, 2000);

                // Poll immediately
                pollRunStatus(run.run_id);

            } catch (error) {
                components.notify(`Error: ${error.message}`, 'error');
                resetFormState();
            }
        });
    },

    async cancelSearch() {
        if (!window.dashboardPage || !window.dashboardPage.currentRunId) {
            components.notify('No search in progress', 'error');
            return;
        }

        const runId = window.dashboardPage.currentRunId;

        try {
            await api.cancelRun(runId);
            components.notify('Cancelling search...', 'info');
        } catch (error) {
            components.notify(`Error cancelling search: ${error.message}`, 'error');
            // Reset form anyway
            if (window.dashboardPage && window.dashboardPage.resetFormState) {
                window.dashboardPage.resetFormState();
            }
        }
    },

    async clearRuns() {
        if (!confirm('Are you sure you want to delete ALL runs and job data? This action cannot be undone.')) {
            return;
        }

        try {
            await api.deleteRuns();
            components.notify('All runs cleared', 'success');
            // Reload dashboard
            this.render();
        } catch (error) {
            components.notify(`Error clearing runs: ${error.message}`, 'error');
        }
    }
};

window.dashboardPage = dashboardPage;