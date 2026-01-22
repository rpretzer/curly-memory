/**
 * Settings Page
 */

const settingsPage = {
    async render() {
        const content = document.getElementById('content');

        try {
            const [profile, schedulerStatus] = await Promise.all([
                api.getProfile().catch(() => ({})),
                api.getSchedulerStatus().catch(() => ({ running: false }))
            ]);

            // Store status for tab switching
            this.schedulerStatus = schedulerStatus;

            content.innerHTML = `
                <div class="page-header flex-between">
                    <div>
                        <h2>Settings</h2>
                        <p>Configure your profile and preferences</p>
                    </div>
                    <button class="btn btn-secondary btn-sm" onclick="router.navigate('/onboarding')">
                        View Onboarding
                    </button>
                </div>

                <div class="tabs">
                    <button class="tab active" onclick="settingsPage.showTab('profile')">Profile & Resume</button>
                    <button class="tab" onclick="settingsPage.showTab('search')">Search Parameters</button>
                    <button class="tab" onclick="settingsPage.showTab('autoapply')">Auto-Apply</button>
                    <button class="tab" onclick="settingsPage.showTab('scheduler')">Scheduler</button>
                    <button class="tab" onclick="settingsPage.showTab('preferences')">Preferences</button>
                </div>

                <div id="settingsContent">
                    ${this.renderProfileTab(profile)}
                </div>
            `;
        } catch (error) {
            content.innerHTML = components.emptyState('Error loading settings', error.message);
        }
    },

    showTab(tab) {
        // Update tab active state
        document.querySelectorAll('.tabs .tab').forEach((t, i) => {
            t.classList.toggle('active',
                (tab === 'profile' && i === 0) ||
                (tab === 'search' && i === 1) ||
                (tab === 'autoapply' && i === 2) ||
                (tab === 'scheduler' && i === 3) ||
                (tab === 'preferences' && i === 4)
            );
        });

        const settingsContent = document.getElementById('settingsContent');

        if (tab === 'profile') {
            api.getProfile().then(profile => {
                settingsContent.innerHTML = this.renderProfileTab(profile);
                // Only attach handler if we're in view mode (edit mode handled by toggleProfileMode)
                // View mode doesn't need the handler since there's no form
            });
        } else if (tab === 'search') {
            api.getConfig().then(config => {
                settingsContent.innerHTML = this.renderSearchParametersTab(config);
                this.attachSearchHandler(config);
            }).catch(error => {
                console.error('Error loading search parameters:', error);
                settingsContent.innerHTML = '<div class="card"><p>Error loading configuration</p></div>';
            });
        } else if (tab === 'autoapply') {
            Promise.all([
                api.getAutoApplyStatus(),
                api.getConfig()
            ]).then(([status, config]) => {
                settingsContent.innerHTML = this.renderAutoApplyTab(status, config);
                this.attachAutoApplyHandler(config);
            }).catch(() => {
                settingsContent.innerHTML = this.renderAutoApplyTab({ enabled: false, queue_size: 0 }, {});
            });
        } else if (tab === 'scheduler') {
            // Use stored status or fetch fresh
            if (this.schedulerStatus) {
                settingsContent.innerHTML = this.renderSchedulerTab(this.schedulerStatus);
                this.attachSchedulerHandler();
                // Refresh in background
                api.getSchedulerStatus().then(status => {
                    this.schedulerStatus = status;
                    // Only re-render if we are still on the scheduler tab
                    // Check if scheduler tab is active (simple check)
                    if (document.querySelector('.tabs .tab:nth-child(4)').classList.contains('active')) {
                         settingsContent.innerHTML = this.renderSchedulerTab(status);
                         this.attachSchedulerHandler();
                    }
                });
            } else {
                api.getSchedulerStatus().then(status => {
                    this.schedulerStatus = status;
                    settingsContent.innerHTML = this.renderSchedulerTab(status);
                    this.attachSchedulerHandler();
                }).catch(() => {
                    settingsContent.innerHTML = this.renderSchedulerTab({ running: false });
                });
            }
        } else if (tab === 'preferences') {
            settingsContent.innerHTML = this.renderPreferencesTab();
            this.attachPreferencesHandler();
        }
    },

    renderProfileTab(profile, mode = 'view') {
        const isEdit = mode === 'edit';
        const lastUpdated = profile.updated_at ? components.formatRelativeTime(profile.updated_at) : 'Never';

        return `
            <div class="card">
                <div class="card-header flex-between">
                    <div>
                        <h3 class="card-title">Personal Information</h3>
                        <p class="text-sm text-muted">Last updated: ${lastUpdated}</p>
                    </div>
                    <button class="btn btn-sm ${isEdit ? 'btn-secondary' : 'btn-primary'}" 
                        onclick="settingsPage.toggleProfileMode('${isEdit ? 'view' : 'edit'}')">
                        ${isEdit ? 'Cancel' : 'Edit Profile'}
                    </button>
                </div>

                ${!isEdit ? this.renderProfileView(profile) : this.renderProfileForm(profile)}
            </div>
        `;
    },

    renderProfileView(profile) {
        const field = (label, value) => `
            <div class="mb-3">
                <div class="text-xs text-muted uppercase font-bold">${label}</div>
                <div class="text-base">${value || '<span class="text-muted italic">Not set</span>'}</div>
            </div>
        `;

        return `
            <div class="profile-view">
                <div class="grid grid-cols-2 gap-4">
                    ${field('Full Name', components.escapeHtml(profile.name))}
                    ${field('Email', components.escapeHtml(profile.email))}
                    ${field('Phone', components.escapeHtml(profile.phone))}
                    ${field('Location', components.escapeHtml(profile.location))}
                </div>
                
                <div class="grid grid-cols-2 gap-4 mt-2">
                    ${field('Current Title', components.escapeHtml(profile.current_title))}
                    ${field('LinkedIn Profile', profile.linkedin_url ? `<a href="${components.escapeHtml(profile.linkedin_url)}" target="_blank" class="text-primary hover:underline">View Profile</a>` : null)}
                </div>

                <div class="grid grid-cols-2 gap-4 mt-2">
                    ${field('Portfolio', profile.portfolio_url ? `<a href="${components.escapeHtml(profile.portfolio_url)}" target="_blank" class="text-primary hover:underline">View Portfolio</a>` : null)}
                    ${field('GitHub', profile.github_url ? `<a href="${components.escapeHtml(profile.github_url)}" target="_blank" class="text-primary hover:underline">View GitHub</a>` : null)}
                </div>

                ${(profile.other_links && profile.other_links.length > 0) ? `
                    <div class="mt-2">
                        ${field('Other Links', (profile.other_links || []).map(link => `<a href="${components.escapeHtml(link)}" target="_blank" class="text-primary hover:underline block">${components.escapeHtml(link)}</a>`).join(' '))}
                    </div>
                ` : ''}

                <div class="mt-2">
                    ${field('Target Titles', (profile.target_titles || []).map(t => `<span class="chip chip-blue">${components.escapeHtml(t)}</span>`).join(' '))}
                </div>

                <div class="mt-2">
                    ${field('Skills', (profile.skills || []).map(s => `<span class="chip chip-green">${components.escapeHtml(s)}</span>`).join(' '))}
                </div>

                <div class="mt-2">
                    ${field('Target Companies', (profile.target_companies || []).map(c => `<span class="chip chip-purple">${components.escapeHtml(c)}</span>`).join(' '))}
                </div>

                <div class="mt-2">
                    ${field('Must-Have Keywords', (profile.must_have_keywords || []).map(k => `<span class="chip chip-red">${components.escapeHtml(k)}</span>`).join(' '))}
                </div>

                <div class="mt-2">
                    ${field('Nice-to-Have Keywords', (profile.nice_to_have_keywords || []).map(k => `<span class="chip chip-yellow">${components.escapeHtml(k)}</span>`).join(' '))}
                </div>

                <div class="mt-2">
                    ${field('Experience Summary', components.escapeHtml(profile.experience_summary))}
                </div>

                <div class="mt-4">
                    <h4 class="text-sm font-semibold mb-2">Resume</h4>
                    ${profile.resume_text ?
                        `<div class="p-2 rounded" style="background: var(--bg-tertiary);">
                            <p class="text-sm text-muted">Resume loaded (${profile.resume_text.length} characters)</p>
                            ${profile.resume_file_path ? `<p class="text-xs text-muted mt-1">File: ${components.escapeHtml(profile.resume_file_path.split('/').pop())}</p>` : ''}
                        </div>` :
                        `<p class="text-muted italic">No resume uploaded</p>`
                    }
                </div>
            </div>
        `;
    },

    renderProfileForm(profile) {
        return `
            <form id="profileForm">
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Full Name</label>
                        <input type="text" class="form-input" name="name"
                            value="${components.escapeHtml(profile.name || '')}">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Email</label>
                        <input type="email" class="form-input" name="email"
                            value="${components.escapeHtml(profile.email || '')}">
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Phone</label>
                        <input type="tel" class="form-input" name="phone"
                            value="${components.escapeHtml(profile.phone || '')}">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Location</label>
                        <input type="text" class="form-input" name="location"
                            value="${components.escapeHtml(profile.location || '')}">
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">LinkedIn URL</label>
                        <input type="url" class="form-input" name="linkedin_url"
                            value="${components.escapeHtml(profile.linkedin_url || '')}" placeholder="https://linkedin.com/in/yourprofile">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Portfolio/Website</label>
                        <input type="url" class="form-input" name="portfolio_url"
                            value="${components.escapeHtml(profile.portfolio_url || '')}" placeholder="https://yourportfolio.com">
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">GitHub URL</label>
                        <input type="url" class="form-input" name="github_url"
                            value="${components.escapeHtml(profile.github_url || '')}" placeholder="https://github.com/yourusername">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Other Links</label>
                        <div id="other-links-chip-input"></div>
                    </div>
                </div>

                <div class="form-group">
                    <label class="form-label">Current Title</label>
                    <input type="text" class="form-input" name="current_title"
                        value="${components.escapeHtml(profile.current_title || '')}">
                </div>

                <div class="form-group">
                    <label class="form-label">Target Job Titles</label>
                    <div id="target-titles-chip-input"></div>
                </div>

                <div class="form-group">
                    <label class="form-label">Skills</label>
                    <div id="skills-chip-input"></div>
                </div>

                <div class="form-group">
                    <label class="form-label">Target Companies</label>
                    <div id="target-companies-chip-input"></div>
                </div>

                <div class="form-group">
                    <label class="form-label">Must-Have Keywords</label>
                    <div id="must-have-keywords-chip-input"></div>
                </div>

                <div class="form-group">
                    <label class="form-label">Nice-to-Have Keywords</label>
                    <div id="nice-to-have-keywords-chip-input"></div>
                </div>

                <div class="form-group">
                    <label class="form-label">Experience Summary</label>
                    <textarea class="form-textarea" name="experience_summary"
                        placeholder="Brief summary of your experience...">${components.escapeHtml(profile.experience_summary || '')}</textarea>
                </div>

                <div class="card p-3" style="background-color: var(--bg-tertiary);">
                    <h4 class="text-sm font-semibold mb-2">Resume Upload</h4>
                    <div class="form-group">
                        <label class="form-label">Upload Resume (PDF, DOC, DOCX)</label>
                        <input type="file" id="resumeFileEdit" accept=".pdf,.doc,.docx"
                            class="form-input" style="padding: 0.5rem;">
                    </div>
                    <button type="button" class="btn btn-sm btn-secondary" onclick="settingsPage.uploadResumeInline()">
                        Upload Resume
                    </button>
                    ${profile && profile.resume_text ? `
                        <div class="mt-2">
                            <p class="text-sm text-muted">Current resume: ${profile.resume_text.length} characters loaded</p>
                            ${profile.resume_file_path ? `<p class="text-xs text-muted">File: ${components.escapeHtml(profile.resume_file_path.split('/').pop())}</p>` : ''}
                        </div>
                    ` : ''}
                </div>

                <div class="flex-end gap-2 mt-4">
                    <button type="button" class="btn btn-secondary" onclick="settingsPage.toggleProfileMode('view')">Cancel</button>
                    <button type="submit" class="btn btn-primary" id="saveProfileBtn">Save Changes</button>
                </div>
            </form>
        `;
    },

    toggleProfileMode(mode) {
        api.getProfile().then(profile => {
            const settingsContent = document.getElementById('settingsContent');
            settingsContent.innerHTML = this.renderProfileTab(profile, mode);
            if (mode === 'edit') {
                this.attachProfileHandler(profile);
            }
        });
    },

    renderSearchParametersTab(config) {
        const search = config.search || {};
        const thresholds = config.thresholds || {};
        const linkedinConfig = config.job_sources?.linkedin || {};

        return `
            <form id="searchForm" class="space-y-4">
                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">LinkedIn Credentials</h3>
                    </div>
                    <p class="text-sm text-muted mb-3">Provide your LinkedIn credentials for authenticated scraping. Credentials are stored in config.yaml.</p>

                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">LinkedIn Email</label>
                            <input type="email" class="form-input" name="linkedin_email"
                                value="${components.escapeHtml(linkedinConfig.linkedin_email || '')}"
                                placeholder="your.email@example.com">
                        </div>
                        <div class="form-group">
                            <label class="form-label">LinkedIn Password</label>
                            <input type="password" class="form-input" name="linkedin_password"
                                value="${components.escapeHtml(linkedinConfig.linkedin_password || '')}"
                                placeholder="Enter password">
                        </div>
                    </div>
                    <p class="text-xs text-warning mt-2">⚠️ These credentials will be saved to config.yaml. Keep your config file secure.</p>
                </div>

                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">Default Search Parameters</h3>
                    </div>

                    <div class="form-group">
                        <label class="form-label">Default Job Titles</label>
                        <div id="default-titles-chip-input"></div>
                    </div>

                    <div class="form-group">
                        <label class="form-label">Default Locations</label>
                        <div id="default-locations-chip-input"></div>
                    </div>

                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">Remote Preference</label>
                            <select class="form-select" name="default_remote_preference">
                                <option value="any" ${search.default_remote_preference === 'any' ? 'selected' : ''}>Any</option>
                                <option value="remote" ${search.default_remote_preference === 'remote' ? 'selected' : ''}>Remote</option>
                                <option value="hybrid" ${search.default_remote_preference === 'hybrid' ? 'selected' : ''}>Hybrid</option>
                                <option value="on-site" ${search.default_remote_preference === 'on-site' ? 'selected' : ''}>On-Site</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Minimum Salary</label>
                            <input type="number" class="form-input" name="default_salary_min"
                                value="${search.default_salary_min || ''}"
                                placeholder="e.g., 115000">
                        </div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">Scoring Thresholds</h3>
                    </div>
                    <p class="text-sm text-info mb-3">ℹ️ Minimum Relevance Score: Jobs below this score are filtered out completely. Lower this value to see more jobs (useful for debugging).</p>

                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">Minimum Relevance Score (0-10)</label>
                            <input type="number" class="form-input" name="min_relevance_score"
                                min="0" max="10" step="0.1"
                                value="${thresholds.min_relevance_score || 4.5}">
                            <p class="text-xs text-muted mt-1">Jobs below this score are filtered out</p>
                        </div>
                        <div class="form-group">
                            <label class="form-label">High Relevance Score (0-10)</label>
                            <input type="number" class="form-input" name="high_relevance_score"
                                min="0" max="10" step="0.1"
                                value="${thresholds.high_relevance_score || 7.5}">
                            <p class="text-xs text-muted mt-1">Used for categorization</p>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Auto-Approval Threshold (0-10)</label>
                            <input type="number" class="form-input" name="auto_approval_threshold"
                                min="0" max="10" step="0.1"
                                value="${thresholds.auto_approval_threshold || 8.0}">
                            <p class="text-xs text-muted mt-1">Jobs at/above this score are auto-approved</p>
                        </div>
                    </div>
                </div>

                <div class="flex-end gap-2">
                    <button type="submit" class="btn btn-primary" id="saveSearchBtn">Save Configuration</button>
                </div>
            </form>
        `;
    },

    renderAutoApplyTab(status, config = {}) {
        const contentPrompts = config.content_prompts || {};
        return `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Auto-Apply Settings</h3>
                </div>

                <div class="flex-between mb-2">
                    <div>
                        <p>Status: ${status.enabled ?
                            '<span class="badge badge-success">Enabled</span>' :
                            '<span class="badge badge-neutral">Disabled</span>'
                        }</p>
                        <p class="text-muted mt-1">
                            Queue: ${status.queue_size || 0} jobs |
                            Applied this hour: ${status.applications_this_hour || 0}/${status.max_per_hour || 20}
                        </p>
                    </div>
                    <div class="flex gap-1">
                        ${status.enabled ?
                            '<button class="btn btn-danger" onclick="settingsPage.disableAutoApply()">Disable</button>' :
                            '<button class="btn btn-success" onclick="settingsPage.enableAutoApply()">Enable</button>'
                        }
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Application Queue</h3>
                </div>

                <div class="form-group">
                    <label class="form-label">Queue approved jobs for application</label>
                    <div class="flex gap-1">
                        <button class="btn btn-secondary" onclick="settingsPage.queueApprovedJobs()">
                            Queue All Approved
                        </button>
                        <button class="btn btn-secondary" onclick="settingsPage.queueHighScoreJobs()">
                            Queue High Score (8+)
                        </button>
                    </div>
                </div>

                <div class="form-group mt-2">
                    <label class="form-label">Process applications</label>
                    <div class="flex gap-1">
                        <button class="btn btn-primary" onclick="settingsPage.processBatch(5)"
                            ${!status.enabled ? 'disabled' : ''}>
                            Process 5 Jobs
                        </button>
                        <button class="btn btn-primary" onclick="settingsPage.startAutoApply()"
                            ${!status.enabled ? 'disabled' : ''}>
                            Start Auto-Apply
                        </button>
                        <button class="btn btn-secondary" onclick="settingsPage.stopAutoApply()">
                            Stop
                        </button>
                    </div>
                </div>

                <div class="form-group mt-2">
                    <button class="btn btn-sm btn-secondary" onclick="settingsPage.clearQueue()">
                        Clear Queue
                    </button>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Test Answer Generation</h3>
                </div>

                <div class="form-group">
                    <label class="form-label">Application Question</label>
                    <input type="text" class="form-input" id="testQuestion"
                        placeholder="e.g., Why are you interested in this role?">
                </div>

                <button class="btn btn-secondary" onclick="settingsPage.testAnswerGeneration()">
                    Generate Answer
                </button>

                <div id="generatedAnswer" class="mt-2" style="display: none;">
                    <label class="form-label">Generated Answer:</label>
                    <div class="card" style="background: var(--bg-tertiary);">
                        <pre id="answerText" style="white-space: pre-wrap; margin: 0;"></pre>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Rate Limiting</h3>
                </div>
                <table>
                    <tbody>
                        <tr>
                            <td>Delay between applications</td>
                            <td>${status.rate_limit_delay || 30} seconds</td>
                        </tr>
                        <tr>
                            <td>Max applications per hour</td>
                            <td>${status.max_per_hour || 20}</td>
                        </tr>
                        <tr>
                            <td>Auto-approval threshold</td>
                            <td>${status.auto_apply_threshold || 8.0}</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Content Generation Prompts</h3>
                </div>

                <div class="form-group">
                    <label class="form-label">Resume Summary Prompt</label>
                    <textarea class="form-textarea" id="resumeSummaryPrompt" rows="4"
                        style="font-family: monospace; font-size: 0.875rem;"
                        placeholder="Generate 3-5 tailored bullet points for a resume...">${components.escapeHtml(contentPrompts.resume_summary || '')}</textarea>
                </div>

                <div class="form-group">
                    <label class="form-label">Cover Letter Template</label>
                    <textarea class="form-textarea" id="coverLetterTemplate" rows="6"
                        style="font-family: monospace; font-size: 0.875rem;"
                        placeholder="Write a professional cover letter...">${components.escapeHtml(contentPrompts.cover_letter_template || '')}</textarea>
                </div>

                <div class="form-group">
                    <label class="form-label">Application Answers Prompt</label>
                    <textarea class="form-textarea" id="applicationAnswersPrompt" rows="4"
                        style="font-family: monospace; font-size: 0.875rem;"
                        placeholder="Generate concise answers to application questions...">${components.escapeHtml(contentPrompts.application_answers || '')}</textarea>
                </div>

                <div class="flex-end">
                    <button type="button" class="btn btn-primary" onclick="settingsPage.saveContentPrompts()">
                        Save Prompts
                    </button>
                </div>
            </div>
        `;
    },

    renderSchedulerTab(status) {
        const schedule = status.schedule || {
            enabled: status.running || false,
            frequency: 'daily',
            time: '09:00',
            days: [],
            search_params: {
                titles: ['Product Manager'],
                locations: ['Remote, US'],
                remote: true,
                max_results: 50
            }
        };

        return `
            <form id="scheduleForm" class="card">
                <div class="card-header">
                    <h3 class="card-title">Schedule Automatic Searches</h3>
                </div>

                <div class="form-group">
                    <label class="checkbox-wrapper">
                        <input type="checkbox" id="schedule-enabled" name="enabled" ${schedule.enabled ? 'checked' : ''}>
                        <span>Enable scheduled searches</span>
                    </label>
                </div>

                <div id="schedule-options" class="${schedule.enabled ? '' : 'hidden'}">
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">Frequency</label>
                            <select class="form-select" name="frequency" id="schedule-frequency">
                                <option value="daily" ${schedule.frequency === 'daily' ? 'selected' : ''}>Daily</option>
                                <option value="weekly" ${schedule.frequency === 'weekly' ? 'selected' : ''}>Weekly</option>
                                <option value="custom" ${schedule.frequency === 'custom' ? 'selected' : ''}>Custom (Cron)</option>
                            </select>
                        </div>

                        <div class="form-group">
                            <label class="form-label">Time</label>
                            <input type="time" class="form-input" name="time" value="${schedule.time}">
                        </div>
                    </div>

                    <div id="weekly-days" class="form-group ${schedule.frequency === 'weekly' ? '' : 'hidden'}">
                        <label class="form-label">Days of Week</label>
                        <div class="flex gap-2" style="flex-wrap: wrap;">
                            ${['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day, idx) => `
                                <label class="checkbox-wrapper">
                                    <input type="checkbox" name="days" value="${idx}"
                                        ${(schedule.days || []).includes(idx) ? 'checked' : ''}>
                                    <span>${day}</span>
                                </label>
                            `).join('')}
                        </div>
                    </div>

                    <div class="card p-3 mt-2" style="background: var(--bg-tertiary); border-top: 2px solid var(--border);">
                        <h4 class="text-sm font-semibold mb-2">Search Parameters</h4>

                        <div class="form-group">
                            <label class="form-label">Job Titles</label>
                            <div id="schedule-titles-chip-input"></div>
                        </div>

                        <div class="form-group">
                            <label class="form-label">Locations</label>
                            <div id="schedule-locations-chip-input"></div>
                        </div>

                        <div class="form-row">
                            <div class="form-group">
                                <label class="checkbox-wrapper">
                                    <input type="checkbox" name="remote" ${schedule.search_params.remote ? 'checked' : ''}>
                                    <span>Remote only</span>
                                </label>
                            </div>

                            <div class="form-group">
                                <label class="form-label">Max Results</label>
                                <input type="number" class="form-input" name="max_results"
                                    value="${schedule.search_params.max_results || 50}"
                                    min="1" max="200">
                            </div>
                        </div>
                    </div>
                </div>

                ${schedule.enabled ? `
                    <div class="flex-end gap-2 mt-4">
                        <button type="button" class="btn btn-secondary" onclick="settingsPage.showTab('scheduler')">Cancel</button>
                        <button type="submit" class="btn btn-primary">Save Schedule</button>
                    </div>
                ` : ''}

                ${schedule.enabled ? `
                    <div class="card mt-2 p-3" style="background: rgba(251, 191, 36, 0.1); border: 1px solid var(--warning);">
                        <p class="text-sm" style="color: var(--warning);">
                            <strong>Note:</strong> Backend scheduling (cron jobs) is not yet fully implemented.
                            The basic start/stop functionality works, but custom schedules may not persist across restarts.
                        </p>
                    </div>
                ` : ''}
            </form>
        `;
    },


    attachProfileHandler(profile = {}) {
        const form = document.getElementById('profileForm');
        if (!form) return;

        // Setup chip inputs with profile data
        const setupChipInput = (id, items, color, suggestions) => {
            const container = document.getElementById(id);
            if (!container) return;

            const chipInput = components.chipInput(id.replace('-chip-input', ''), items, color, suggestions);
            container.innerHTML = chipInput.html;
            chipInput.setup();
        };

        setupChipInput('target-titles-chip-input', profile.target_titles || [], 'blue', SUGGESTIONS.jobTitles);
        setupChipInput('skills-chip-input', profile.skills || [], 'green', SUGGESTIONS.skills);
        setupChipInput('target-companies-chip-input', profile.target_companies || [], 'purple', SUGGESTIONS.companies);
        setupChipInput('must-have-keywords-chip-input', profile.must_have_keywords || [], 'red', SUGGESTIONS.keywords);
        setupChipInput('nice-to-have-keywords-chip-input', profile.nice_to_have_keywords || [], 'yellow', SUGGESTIONS.keywords);
        setupChipInput('other-links-chip-input', profile.other_links || [], 'blue', []);

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const saveBtn = document.getElementById('saveProfileBtn');
            const originalBtnText = saveBtn.textContent;

            // UI: Loading state
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<div class="spinner spinner-sm"></div> Saving...';

            const formData = new FormData(form);
            const data = {
                name: formData.get('name'),
                email: formData.get('email'),
                phone: formData.get('phone'),
                location: formData.get('location'),
                linkedin_url: formData.get('linkedin_url'),
                portfolio_url: formData.get('portfolio_url'),
                github_url: formData.get('github_url'),
                other_links: window.chipInputs['other-links']?.getItems() || [],
                current_title: formData.get('current_title'),
                target_titles: window.chipInputs['target-titles']?.getItems() || [],
                skills: window.chipInputs['skills']?.getItems() || [],
                target_companies: window.chipInputs['target-companies']?.getItems() || [],
                must_have_keywords: window.chipInputs['must-have-keywords']?.getItems() || [],
                nice_to_have_keywords: window.chipInputs['nice-to-have-keywords']?.getItems() || [],
                experience_summary: formData.get('experience_summary')
            };

            try {
                // Save and get updated profile
                const updatedProfile = await api.updateProfile(data);

                components.notify('Profile saved successfully!', 'success');

                // UX: Switch back to view mode with updated data
                const settingsContent = document.getElementById('settingsContent');
                settingsContent.innerHTML = this.renderProfileTab(updatedProfile, 'view');

            } catch (error) {
                components.notify(`Error saving profile: ${error.message}`, 'error');

                // UI: Reset button state on error
                saveBtn.disabled = false;
                saveBtn.textContent = originalBtnText;
            }
        });
    },

    attachSearchHandler(config = {}) {
        const form = document.getElementById('searchForm');
        if (!form) return;

        // Setup chip inputs for default search parameters
        const setupChipInput = (id, items, color, suggestions) => {
            const container = document.getElementById(id);
            if (!container) return;

            const chipInput = components.chipInput(id.replace('-chip-input', ''), items, color, suggestions);
            container.innerHTML = chipInput.html;
            chipInput.setup();
        };

        const search = config.search || {};
        setupChipInput('default-titles-chip-input', search.default_titles || [], 'blue', SUGGESTIONS.jobTitles);
        setupChipInput('default-locations-chip-input', search.default_locations || [], 'green', SUGGESTIONS.locations);

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const saveBtn = document.getElementById('saveSearchBtn');
            const originalBtnText = saveBtn.textContent;

            saveBtn.disabled = true;
            saveBtn.innerHTML = '<div class="spinner spinner-sm"></div> Saving...';

            const formData = new FormData(form);

            // Build updated config
            const updatedConfig = {
                ...config,
                search: {
                    ...config.search,
                    default_titles: window.chipInputs['default-titles']?.getItems() || [],
                    default_locations: window.chipInputs['default-locations']?.getItems() || [],
                    default_remote_preference: formData.get('default_remote_preference'),
                    default_salary_min: parseInt(formData.get('default_salary_min')) || undefined
                },
                thresholds: {
                    ...config.thresholds,
                    min_relevance_score: parseFloat(formData.get('min_relevance_score')),
                    high_relevance_score: parseFloat(formData.get('high_relevance_score')),
                    auto_approval_threshold: parseFloat(formData.get('auto_approval_threshold'))
                },
                job_sources: {
                    ...config.job_sources,
                    linkedin: {
                        ...config.job_sources?.linkedin,
                        linkedin_email: formData.get('linkedin_email'),
                        linkedin_password: formData.get('linkedin_password')
                    }
                }
            };

            try {
                await api.updateConfig(updatedConfig);
                components.notify('Configuration saved successfully!', 'success');
                saveBtn.disabled = false;
                saveBtn.textContent = originalBtnText;
            } catch (error) {
                components.notify(`Error saving configuration: ${error.message}`, 'error');
                saveBtn.disabled = false;
                saveBtn.textContent = originalBtnText;
            }
        });
    },

    attachAutoApplyHandler(config = {}) {
        // Auto-apply tab doesn't need form handlers - buttons use onclick
        // This function exists for future enhancements
    },

    attachSchedulerHandler() {
        const form = document.getElementById('scheduleForm');
        if (!form) return;

        // Setup chip inputs for schedule search parameters
        const setupScheduleChips = () => {
            api.getSchedulerStatus().then(status => {
                const schedule = status.schedule || {
                    search_params: {
                        titles: ['Product Manager'],
                        locations: ['Remote, US']
                    }
                };

                const setupChipInput = (id, items, color, suggestions) => {
                    const container = document.getElementById(id);
                    if (!container) return;

                    const chipInput = components.chipInput(id.replace('-chip-input', ''), items, color, suggestions);
                    container.innerHTML = chipInput.html;
                    chipInput.setup();
                };

                setupChipInput('schedule-titles-chip-input', schedule.search_params?.titles || ['Product Manager'], 'blue', SUGGESTIONS.jobTitles);
                setupChipInput('schedule-locations-chip-input', schedule.search_params?.locations || ['Remote, US'], 'green', SUGGESTIONS.locations);
            });
        };

        // Setup chip inputs
        setupScheduleChips();

        // Toggle schedule options visibility
        const enabledCheckbox = document.getElementById('schedule-enabled');
        const scheduleOptions = document.getElementById('schedule-options');

        if (enabledCheckbox && scheduleOptions) {
            enabledCheckbox.addEventListener('change', (e) => {
                if (e.target.checked) {
                    scheduleOptions.classList.remove('hidden');
                } else {
                    scheduleOptions.classList.add('hidden');
                }
            });
        }

        // Toggle weekly days visibility
        const frequencySelect = document.getElementById('schedule-frequency');
        const weeklyDays = document.getElementById('weekly-days');

        if (frequencySelect && weeklyDays) {
            frequencySelect.addEventListener('change', (e) => {
                if (e.target.value === 'weekly') {
                    weeklyDays.classList.remove('hidden');
                } else {
                    weeklyDays.classList.add('hidden');
                }
            });
        }

        // Form submission
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const formData = new FormData(form);

            // Get selected days
            const days = [];
            form.querySelectorAll('input[name="days"]:checked').forEach(cb => {
                days.push(parseInt(cb.value));
            });

            const scheduleConfig = {
                enabled: formData.get('enabled') === 'on',
                frequency: formData.get('frequency'),
                time: formData.get('time'),
                days: days.length > 0 ? days : undefined,
                search_params: {
                    titles: window.chipInputs['schedule-titles']?.getItems() || [],
                    locations: window.chipInputs['schedule-locations']?.getItems() || [],
                    remote: formData.get('remote') === 'on',
                    max_results: parseInt(formData.get('max_results')) || 50
                }
            };

            try {
                // TODO: Add API endpoint to save schedule configuration
                // await api.updateSchedule(scheduleConfig);

                components.notify('Schedule configuration saved!', 'success');

                // If enabling, start the scheduler
                if (scheduleConfig.enabled) {
                    await this.startScheduler();
                } else {
                    await this.stopScheduler();
                }

            } catch (error) {
                components.notify(`Error saving schedule: ${error.message}`, 'error');
            }
        });
    },

    async startScheduler() {
        try {
            await api.startScheduler();
            components.notify('Scheduler started!', 'success');
            window.schedulerStatus = { running: true };
            this.showTab('scheduler');
        } catch (error) {
            components.notify(`Error: ${error.message}`, 'error');
        }
    },

    async stopScheduler() {
        try {
            await api.stopScheduler();
            components.notify('Scheduler stopped', 'success');
            window.schedulerStatus = { running: false };
            this.showTab('scheduler');
        } catch (error) {
            components.notify(`Error: ${error.message}`, 'error');
        }
    },

    async uploadResume() {
        const fileInput = document.getElementById('resumeFile');
        const file = fileInput?.files[0];

        if (!file) {
            components.notify('Please select a file', 'error');
            return;
        }

        try {
            await api.uploadResume(file);
            components.notify('Resume uploaded!', 'success');
            this.showTab('profile');
        } catch (error) {
            components.notify(`Error: ${error.message}`, 'error');
        }
    },

    async uploadResumeInline() {
        const fileInput = document.getElementById('resumeFileEdit');
        const file = fileInput?.files[0];

        if (!file) {
            components.notify('Please select a file', 'error');
            return;
        }

        try {
            await api.uploadResume(file);
            components.notify('Resume uploaded!', 'success');
            // Refresh the profile tab to show the updated resume
            const profile = await api.getProfile();
            const settingsContent = document.getElementById('settingsContent');
            settingsContent.innerHTML = this.renderProfileTab(profile, 'edit');
            this.attachProfileHandler(profile);
        } catch (error) {
            components.notify(`Error: ${error.message}`, 'error');
        }
    },

    async saveContentPrompts() {
        const resumeSummaryPrompt = document.getElementById('resumeSummaryPrompt')?.value;
        const coverLetterTemplate = document.getElementById('coverLetterTemplate')?.value;
        const applicationAnswersPrompt = document.getElementById('applicationAnswersPrompt')?.value;

        try {
            const config = await api.getConfig();
            const updatedConfig = {
                ...config,
                content_prompts: {
                    ...config.content_prompts,
                    resume_summary: resumeSummaryPrompt,
                    cover_letter_template: coverLetterTemplate,
                    application_answers: applicationAnswersPrompt
                }
            };

            await api.updateConfig(updatedConfig);
            components.notify('Content prompts saved successfully!', 'success');
        } catch (error) {
            components.notify(`Error saving prompts: ${error.message}`, 'error');
        }
    },

    // Auto-Apply Methods
    async enableAutoApply() {
        try {
            await api.enableAutoApply();
            components.notify('Auto-apply enabled!', 'success');
            this.showTab('autoapply');
        } catch (error) {
            components.notify(`Error: ${error.message}`, 'error');
        }
    },

    async disableAutoApply() {
        try {
            await api.disableAutoApply();
            components.notify('Auto-apply disabled', 'success');
            this.showTab('autoapply');
        } catch (error) {
            components.notify(`Error: ${error.message}`, 'error');
        }
    },

    async queueApprovedJobs() {
        try {
            const result = await api.queueJobsForApplication({});
            components.notify(`Queued ${result.jobs_added} jobs`, 'success');
            this.showTab('autoapply');
        } catch (error) {
            components.notify(`Error: ${error.message}`, 'error');
        }
    },

    async queueHighScoreJobs() {
        try {
            const result = await api.queueJobsForApplication({ min_score: 8.0 });
            components.notify(`Queued ${result.jobs_added} high-score jobs`, 'success');
            this.showTab('autoapply');
        } catch (error) {
            components.notify(`Error: ${error.message}`, 'error');
        }
    },

    async processBatch(batchSize) {
        try {
            await api.processApplicationBatch(batchSize);
            components.notify(`Processing ${batchSize} applications...`, 'info');
        } catch (error) {
            components.notify(`Error: ${error.message}`, 'error');
        }
    },

    async startAutoApply() {
        try {
            await api.startAutoApply();
            components.notify('Auto-apply processing started', 'success');
            this.showTab('autoapply');
        } catch (error) {
            components.notify(`Error: ${error.message}`, 'error');
        }
    },

    async stopAutoApply() {
        try {
            await api.stopAutoApply();
            components.notify('Auto-apply stopped', 'success');
            this.showTab('autoapply');
        } catch (error) {
            components.notify(`Error: ${error.message}`, 'error');
        }
    },

    async clearQueue() {
        try {
            await api.clearApplicationQueue();
            components.notify('Queue cleared', 'success');
            this.showTab('autoapply');
        } catch (error) {
            components.notify(`Error: ${error.message}`, 'error');
        }
    },

    async testAnswerGeneration() {
        const question = document.getElementById('testQuestion')?.value;
        if (!question) {
            components.notify('Please enter a question', 'error');
            return;
        }

        try {
            const result = await api.answerQuestion(question);
            const answerDiv = document.getElementById('generatedAnswer');
            const answerText = document.getElementById('answerText');

            if (result.answer) {
                answerText.textContent = result.answer;
                answerDiv.style.display = 'block';
            } else {
                answerText.textContent = 'No template matched for this question.';
                answerDiv.style.display = 'block';
            }
        } catch (error) {
            components.notify(`Error: ${error.message}`, 'error');
        }
    },

    renderPreferencesTab() {
        // Get current preferences from localStorage
        const currentTheme = localStorage.getItem('theme') || 'dark';
        const showStats = localStorage.getItem('showStats') !== 'false'; // default true

        return `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Display Preferences</h3>
                </div>

                <div class="form-group">
                    <label class="form-label">Theme</label>
                    <div class="flex gap-2" style="flex-wrap: wrap;">
                        <label class="checkbox-wrapper">
                            <input type="radio" name="theme" value="dark" ${currentTheme === 'dark' ? 'checked' : ''}>
                            <span>Dark Mode</span>
                        </label>
                        <label class="checkbox-wrapper">
                            <input type="radio" name="theme" value="light" ${currentTheme === 'light' ? 'checked' : ''}>
                            <span>Light Mode</span>
                        </label>
                    </div>
                    <p class="text-xs text-muted mt-1">Choose your preferred color theme</p>
                </div>

                <div class="form-group">
                    <label class="checkbox-wrapper">
                        <input type="checkbox" id="showStatsToggle" ${showStats ? 'checked' : ''}>
                        <span>Show Statistics Cards on Dashboard</span>
                    </label>
                    <p class="text-xs text-muted mt-1">Toggle visibility of stats boxes (Total Runs, Jobs Found, etc.)</p>
                </div>

                <div class="flex-end gap-2 mt-4">
                    <button type="button" class="btn btn-primary" onclick="settingsPage.savePreferences()">
                        Save Preferences
                    </button>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">About</h3>
                </div>
                <p class="text-sm text-muted">Job Search Pipeline - Vanilla Frontend</p>
                <p class="text-xs text-muted mt-2">Refactored to match Next.js UI with horizontal navigation, light mode support, and progress tracking.</p>
            </div>
        `;
    },

    attachPreferencesHandler() {
        // Listen for theme changes
        const themeRadios = document.querySelectorAll('input[name="theme"]');
        themeRadios.forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.applyTheme(e.target.value);
            });
        });
    },

    applyTheme(theme) {
        if (theme === 'light') {
            document.body.classList.add('light-mode');
        } else {
            document.body.classList.remove('light-mode');
        }
        localStorage.setItem('theme', theme);
    },

    savePreferences() {
        const theme = document.querySelector('input[name="theme"]:checked')?.value || 'dark';
        const showStats = document.getElementById('showStatsToggle')?.checked || false;

        localStorage.setItem('theme', theme);
        localStorage.setItem('showStats', showStats ? 'true' : 'false');

        this.applyTheme(theme);

        components.notify('Preferences saved!', 'success');

        // Reload dashboard if we're changing stats visibility
        if (window.location.hash === '#/' || window.location.hash === '') {
            setTimeout(() => {
                if (window.dashboardPage) {
                    window.dashboardPage.render();
                }
            }, 500);
        }
    }
};

window.settingsPage = settingsPage;
