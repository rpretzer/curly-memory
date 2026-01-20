/**
 * Dashboard Page
 */

const dashboardPage = {
    async render() {
        const content = document.getElementById('content');

        // Fetch data in parallel
        const [runs, jobs] = await Promise.all([
            api.getRuns().catch(() => []),
            api.getJobs({ limit: 10 }).catch(() => [])
        ]);

        // Calculate stats
        const recentRuns = runs.slice(0, 5);
        const pendingJobs = jobs.filter(j => !j.approved && j.status !== 'rejected');
        const approvedJobs = jobs.filter(j => j.approved);
        const totalJobsFound = runs.reduce((sum, r) => sum + (r.jobs_found || 0), 0);

        content.innerHTML = `
            <div class="page-header">
                <h2>Dashboard</h2>
                <p>Job search pipeline overview</p>
            </div>

            <div class="stats-grid">
                ${components.statCard(runs.length, 'Total Runs')}
                ${components.statCard(totalJobsFound, 'Jobs Found')}
                ${components.statCard(pendingJobs.length, 'Pending Review', '#f59e0b')}
                ${components.statCard(approvedJobs.length, 'Approved', '#22c55e')}
            </div>

            ${components.searchForm()}

            <div class="card mt-2">
                <div class="card-header">
                    <h3 class="card-title">Recent Runs</h3>
                    <a href="#/runs" class="btn btn-sm btn-secondary">View All</a>
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

    attachSearchHandler() {
        const form = document.getElementById('searchForm');
        if (!form) return;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const formData = new FormData(form);
            const submitBtn = form.querySelector('button[type="submit"]');

            // Get selected sources
            const sources = [];
            form.querySelectorAll('input[name="sources"]:checked').forEach(cb => {
                sources.push(cb.value);
            });

            const config = {
                titles: formData.get('titles').split(',').map(t => t.trim()).filter(Boolean),
                locations: formData.get('locations') ?
                    formData.get('locations').split(',').map(l => l.trim()).filter(Boolean) : null,
                keywords: formData.get('keywords') ?
                    formData.get('keywords').split(',').map(k => k.trim()).filter(Boolean) : null,
                remote: formData.get('remote') === 'on',
                salary_min: formData.get('salary_min') ? parseInt(formData.get('salary_min')) : null,
                max_results: parseInt(formData.get('max_results')) || 50,
                sources: sources.length > 0 ? sources : null
            };

            try {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Starting search...';

                const run = await api.createRun(config);
                components.notify('Search started successfully!', 'success');

                // Navigate to run details
                router.navigate(`/runs/${run.id}`);
            } catch (error) {
                components.notify(`Error: ${error.message}`, 'error');
                submitBtn.disabled = false;
                submitBtn.textContent = 'Start Search';
            }
        });
    }
};

window.dashboardPage = dashboardPage;
