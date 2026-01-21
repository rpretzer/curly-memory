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

        // Calculate stats
        const recentRuns = runs.slice(0, 5);
        const pendingJobs = jobs.filter(j => !j.approved && j.status !== 'rejected');
        const approvedJobs = jobs.filter(j => j.approved);
        const appliedJobs = jobs.filter(j => j.status === 'application_completed');
        const totalJobsFound = runs.reduce((sum, r) => sum + (r.jobs_found || 0), 0);

        content.innerHTML = `
            <div class="page-header">
                <h2>Dashboard</h2>
                <p>Job search pipeline overview</p>
            </div>

            <div class="stats-grid">
                ${components.statCard(runs.length, 'Total Runs', null, "router.navigate('/runs')")}
                ${components.statCard(totalJobsFound, 'Jobs Found', null, "dashboardPage.goToJobs('all')")}
                ${components.statCard(pendingJobs.length, 'Pending Review', '#f59e0b', "dashboardPage.goToJobs('pending')")}
                ${components.statCard(approvedJobs.length, 'Approved', '#22c55e', "dashboardPage.goToJobs('approved')")}
                ${components.statCard(appliedJobs.length, 'Applied', '#3b82f6', "dashboardPage.goToJobs('applied')")}
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

        // Setup chip inputs
        api.getProfile().then(profile => {
            const setupChipInput = (id, items, color, suggestions) => {
                const container = document.getElementById(id);
                if (!container) return;

                const chipInput = components.chipInput(id.replace('-chip-input', ''), items, color, suggestions, 'primary');
                container.innerHTML = chipInput.html;
                chipInput.setup();
            };

            setupChipInput('search-titles-chip-input', profile.target_titles || ['Product Manager'], 'blue', SUGGESTIONS.jobTitles);
            setupChipInput('search-locations-chip-input', ['Remote, US'], 'green', SUGGESTIONS.locations);
            setupChipInput('search-keywords-chip-input', profile.must_have_keywords || [], 'purple', SUGGESTIONS.keywords);
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

            const runConfig = {
                search: searchConfig,
                salary_min: formData.get('salary_min') ? parseInt(formData.get('salary_min')) : null,
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