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

        content.innerHTML = `
            <div class="page-header">
                <h2>Dashboard</h2>
                <p>Job search pipeline overview</p>
            </div>

            <div class="stats-grid">
                ${components.statCard(runs.length, 'Total Runs', null, "router.navigate('/runs')")}
                ${components.statCard(totalJobsFound, 'Jobs Found', null, "dashboardPage.goToJobs('all')")}
                ${components.statCard(pendingCount, 'Pending Review', '#f59e0b', "dashboardPage.goToJobs('pending')")}
                ${components.statCard(totalJobsApproved, 'Approved', '#22c55e', "dashboardPage.goToJobs('approved')")}
                ${components.statCard(totalJobsApplied, 'Applied', '#3b82f6', "dashboardPage.goToJobs('applied')")}
            </div>

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
        setupChipInput('search-keywords-chip-input', [], 'purple', SUGGESTIONS.keywords);

        // Setup salary input formatting
        const salaryInput = document.getElementById('salary_min');
        if (salaryInput) {
            salaryInput.addEventListener('input', (e) => {
                // Remove non-digits
                let value = e.target.value.replace(/[^\d]/g, '');
                // Format with commas
                if (value) {
                    value = parseInt(value).toLocaleString('en-US');
                }
                e.target.value = value;
            });
        }

        // Update with profile data when available
        api.getProfile().then(profile => {
            if (profile.target_titles && profile.target_titles.length > 0) {
                setupChipInput('search-titles-chip-input', profile.target_titles, 'blue', SUGGESTIONS.jobTitles);
            }
            if (profile.must_have_keywords && profile.must_have_keywords.length > 0) {
                setupChipInput('search-keywords-chip-input', profile.must_have_keywords, 'purple', SUGGESTIONS.keywords);
            }
        }).catch(error => {
            console.warn('Could not load profile for search form:', error);
            // Already setup with defaults above
        });

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const formData = new FormData(form);
            const submitBtn = form.querySelector('button[type="submit"]');

            // Get selected sources
            const sources = [];
            form.querySelectorAll('input[name="sources"]:checked').forEach(cb => {
                sources.push(cb.value);
            });

            // Get chip input values
            const titles = window.chipInputs['search-titles']?.getItems() || [];
            const locations = window.chipInputs['search-locations']?.getItems() || [];
            const keywords = window.chipInputs['search-keywords']?.getItems() || [];

            // Construct the payload matching RunRequest model
            const searchConfig = {
                titles: titles.length > 0 ? titles : null,
                locations: locations.length > 0 ? locations : null,
                keywords: keywords.length > 0 ? keywords : null,
                remote: formData.get('remote') === 'on',
                sources: sources.length > 0 ? sources : null,
                max_results: parseInt(formData.get('max_results')) || 50
            };

            // Parse salary_min (remove commas)
            const salaryMinStr = formData.get('salary_min');
            const salaryMin = salaryMinStr ? parseInt(salaryMinStr.replace(/[^\d]/g, '')) : null;

            const runConfig = {
                search: searchConfig,
                salary_min: salaryMin,
                // Default values for other fields
                remote_preference: 'any',
                generate_content: true,
                auto_apply: false
            };

            try {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Starting search...';

                const run = await api.createRun(runConfig);
                components.notify('Search started successfully!', 'success');

                // Navigate to run details
                router.navigate(`/runs/${run.run_id}`);
            } catch (error) {
                components.notify(`Error: ${error.message}`, 'error');
                submitBtn.disabled = false;
                submitBtn.textContent = 'Start Search';
            }
        });
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