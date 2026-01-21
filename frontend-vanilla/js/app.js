/**
 * Main Application Entry Point
 */

(function() {
    'use strict';

    // Register routes
    router.register('/', () => dashboardPage.render());
    router.register('/jobs', () => jobsPage.renderList());
    router.register('/jobs/:id', (params) => jobsPage.renderDetail(params));
    router.register('/runs', () => runsPage.renderList());
    router.register('/runs/:id', (params) => runsPage.renderDetail(params));
    router.register('/settings', () => settingsPage.render());
    router.register('/onboarding', () => onboardingPage.render());

    // Initialize router when DOM is ready
    document.addEventListener('DOMContentLoaded', async () => {
        router.init();
        
        try {
            const profile = await api.getProfile();
            if (!profile.is_onboarded && window.location.hash !== '#/onboarding') {
                console.log('User not onboarded, redirecting...');
                router.navigate('/onboarding');
            }
        } catch (e) {
            console.error('Failed to check onboarding status:', e);
        }
        
        console.log('Job Search Pipeline initialized');
    });

    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        if (runsPage.pollInterval) {
            clearInterval(runsPage.pollInterval);
        }
    });

    // Global error handler
    window.addEventListener('error', (event) => {
        console.error('Global error:', event.error);
        components.notify('An unexpected error occurred', 'error');
    });

    // Handle unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
        console.error('Unhandled promise rejection:', event.reason);
        components.notify('An unexpected error occurred', 'error');
    });
})();
