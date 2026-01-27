/**
 * Onboarding Wizard Page
 */

const onboardingPage = {
    state: {
        step: 1,
        totalSteps: 4,
        profile: {}
    },

    async render() {
        const content = document.getElementById('content');
        
        try {
            this.state.profile = await api.getProfile().catch(() => ({}));
        } catch (e) {
            console.error(e);
        }

        content.innerHTML = `
            <div class="onboarding-container" style="max-width: 800px; margin: 0 auto;">
                <div class="page-header text-center">
                    <h2>Welcome to Agentic Job Search</h2>
                    <p>Let's get your profile set up to find the perfect job for you.</p>
                </div>

                <div class="card">
                    <div class="progress-bar-container mb-4">
                        <div class="progress-bar" id="onboardingProgress" style="width: 25%"></div>
                        <div class="steps-indicator flex-between text-muted text-sm mt-1">
                            <span>Basics</span>
                            <span>Resume</span>
                            <span>Preferences</span>
                            <span>Review</span>
                        </div>
                    </div>

                    <div id="onboardingStepContent">
                        ${this.renderStep1()}
                    </div>
                </div>
            </div>
        `;
        
        this.attachStep1Handler();
    },

    renderStep1() {
        const p = this.state.profile;
        return `
            <h3 class="card-title mb-3">Step 1: The Basics</h3>
            <form id="step1Form">
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Full Name</label>
                        <input type="text" class="form-input" name="name" value="${components.escapeHtml(p.name || '')}" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Email</label>
                        <input type="email" class="form-input" name="email" value="${components.escapeHtml(p.email || '')}" required>
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">Current Job Title</label>
                    <input type="text" class="form-input" name="current_title" value="${components.escapeHtml(p.current_title || '')}" placeholder="e.g. Senior Software Engineer">
                </div>
                <div class="form-group">
                    <label class="form-label">LinkedIn URL</label>
                    <input type="url" class="form-input" name="linkedin_url" value="${components.escapeHtml(p.linkedin_url || '')}" placeholder="https://linkedin.com/in/...">
                </div>

                <div class="card mt-3" style="background-color: rgba(59, 130, 246, 0.05); border: 1px solid rgba(59, 130, 246, 0.2);">
                    <p class="text-sm" style="color: var(--accent);">
                        <strong>💡 Note:</strong> LinkedIn scraping credentials can be configured later in Settings > Search Parameters if needed.
                    </p>
                </div>
                
                <div class="flex-end mt-4">
                    <button type="submit" class="btn btn-primary">Next: Upload Resume</button>
                </div>
            </form>
        `;
    },

    renderStep2() {
        return `
            <h3 class="card-title mb-3">Step 2: Your Resume</h3>
            <p class="text-muted mb-3">Upload your resume (PDF/DOCX) so we can tailor applications to your experience.</p>
            
            <div class="form-group">
                <div class="upload-zone p-4 border-dashed text-center" style="border: 2px dashed var(--border-color); border-radius: 8px;">
                    <input type="file" id="resumeUpload" accept=".pdf,.doc,.docx" class="hidden" onchange="onboardingPage.handleFileUpload(this)">
                    <label for="resumeUpload" class="btn btn-secondary cursor-pointer">Choose File</label>
                    <p class="mt-2 text-muted" id="fileName">No file selected</p>
                </div>
            </div>

            <div class="flex-between mt-4">
                <button class="btn btn-secondary" onclick="onboardingPage.goToStep(1)">Back</button>
                <button class="btn btn-primary" onclick="onboardingPage.goToStep(3)" id="step2Next">Skip for now</button>
            </div>
        `;
    },

    renderStep3() {
        const p = this.state.profile;
        return `
            <h3 class="card-title mb-3">Step 3: Job Preferences</h3>
            <form id="step3Form">
                <div class="form-group">
                    <label class="form-label">Target Job Titles</label>
                    <div id="onboarding-titles-chip-input"></div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Minimum Salary</label>
                        <input type="number" class="form-input" name="salary_min" value="${p.salary_min || 100000}">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Remote Preference</label>
                        <select class="form-input" name="remote_preference">
                            <option value="remote" ${p.remote_preference === 'remote' ? 'selected' : ''}>Remote Only</option>
                            <option value="hybrid" ${p.remote_preference === 'hybrid' ? 'selected' : ''}>Hybrid</option>
                            <option value="on-site" ${p.remote_preference === 'on-site' ? 'selected' : ''}>On-Site</option>
                            <option value="any" ${!p.remote_preference || p.remote_preference === 'any' ? 'selected' : ''}>Any</option>
                        </select>
                    </div>
                </div>

                <div class="form-group">
                    <label class="form-label">Must-Have Skills/Keywords</label>
                    <div id="onboarding-keywords-chip-input"></div>
                </div>

                <div class="flex-between mt-4">
                    <button type="button" class="btn btn-secondary" onclick="onboardingPage.goToStep(2)">Back</button>
                    <button type="submit" class="btn btn-primary">Next: Review</button>
                </div>
            </form>
        `;
    },

    renderStep4() {
        return `
            <h3 class="card-title mb-3">Step 4: All Set!</h3>
            <div class="text-center py-4">
                <div style="font-size: 3rem; margin-bottom: 1rem;">🎉</div>
                <p>Your profile is configured. You're ready to start your first automated job search.</p>
                <p class="text-muted mt-2">You can change these settings anytime from the Settings page.</p>
            </div>

            <div class="flex-between mt-4">
                <button class="btn btn-secondary" onclick="onboardingPage.goToStep(3)">Back</button>
                <button class="btn btn-success" onclick="onboardingPage.finishOnboarding()">Go to Dashboard</button>
            </div>
        `;
    },

    async goToStep(step) {
        this.state.step = step;
        const container = document.getElementById('onboardingStepContent');
        const progressBar = document.getElementById('onboardingProgress');
        
        progressBar.style.width = `${(step / this.state.totalSteps) * 100}%`;

        if (step === 1) {
            container.innerHTML = this.renderStep1();
            this.attachStep1Handler();
        } else if (step === 2) {
            container.innerHTML = this.renderStep2();
        } else if (step === 3) {
            container.innerHTML = this.renderStep3();
            this.attachStep3Handler();
        } else if (step === 4) {
            container.innerHTML = this.renderStep4();
        }
    },

    attachStep1Handler() {
        const form = document.getElementById('step1Form');
        if (form) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(form);
                const data = Object.fromEntries(formData.entries());
                
                await api.updateProfile(data);
                this.state.profile = { ...this.state.profile, ...data };
                this.goToStep(2);
            });
        }
    },

    async handleFileUpload(input) {
        const file = input.files[0];
        if (file) {
            document.getElementById('fileName').textContent = file.name;
            const nextBtn = document.getElementById('step2Next');
            nextBtn.textContent = 'Uploading...';
            nextBtn.disabled = true;

            try {
                await api.uploadResume(file);
                components.notify('Resume uploaded successfully', 'success');
                this.goToStep(3);
            } catch (error) {
                components.notify('Upload failed: ' + error.message, 'error');
                nextBtn.textContent = 'Skip for now';
                nextBtn.disabled = false;
            }
        }
    },

    attachStep3Handler() {
        const form = document.getElementById('step3Form');
        if (!form) return;

        const p = this.state.profile;

        // Setup chip inputs
        const setupChipInput = (id, items, color, suggestions) => {
            const container = document.getElementById(id);
            if (!container) return;

            const chipInput = components.chipInput(id.replace('-chip-input', ''), items, color, suggestions);
            container.innerHTML = chipInput.html;
            chipInput.setup();
        };

        setupChipInput('onboarding-titles-chip-input', p.target_titles || [], 'blue', SUGGESTIONS.jobTitles);
        setupChipInput('onboarding-keywords-chip-input', p.must_have_keywords || [], 'red', SUGGESTIONS.keywords);

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(form);

            const data = {
                target_titles: window.chipInputs['onboarding-titles']?.getItems() || [],
                must_have_keywords: window.chipInputs['onboarding-keywords']?.getItems() || [],
                salary_min: parseInt(formData.get('salary_min')) || null,
                remote_preference: formData.get('remote_preference')
            };

            // Validate at least one title is provided
            if (data.target_titles.length === 0) {
                components.notify('Please add at least one job title', 'error');
                return;
            }

            await api.updateProfile(data);
            this.state.profile = { ...this.state.profile, ...data };
            this.goToStep(4);
        });
    },

    async finishOnboarding() {
        try {
            await api.updateProfile({ is_onboarded: true });
            router.navigate('/');
        } catch (error) {
            components.notify('Error completing setup', 'error');
        }
    }
};

window.onboardingPage = onboardingPage;
