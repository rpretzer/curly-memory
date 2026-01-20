/**
 * Simple hash-based router for SPA navigation
 */

const router = {
    routes: {},
    currentPage: null,

    /**
     * Register a route handler
     */
    register(path, handler) {
        this.routes[path] = handler;
    },

    /**
     * Navigate to a path
     */
    navigate(path) {
        window.location.hash = path;
    },

    /**
     * Get current route from hash
     */
    getCurrentRoute() {
        const hash = window.location.hash.slice(1) || '/';
        return this.parseRoute(hash);
    },

    /**
     * Parse route and extract params
     */
    parseRoute(hash) {
        const parts = hash.split('/').filter(Boolean);

        // Match routes with params
        for (const [pattern, handler] of Object.entries(this.routes)) {
            const patternParts = pattern.split('/').filter(Boolean);

            if (this.matchRoute(parts, patternParts)) {
                const params = this.extractParams(parts, patternParts);
                return { pattern, handler, params, path: hash };
            }
        }

        // Default to dashboard
        return {
            pattern: '/',
            handler: this.routes['/'] || (() => {}),
            params: {},
            path: '/'
        };
    },

    /**
     * Check if URL parts match pattern parts
     */
    matchRoute(urlParts, patternParts) {
        if (urlParts.length !== patternParts.length) {
            return false;
        }

        return patternParts.every((part, i) => {
            return part.startsWith(':') || part === urlParts[i];
        });
    },

    /**
     * Extract params from URL based on pattern
     */
    extractParams(urlParts, patternParts) {
        const params = {};

        patternParts.forEach((part, i) => {
            if (part.startsWith(':')) {
                const paramName = part.slice(1);
                params[paramName] = urlParts[i];
            }
        });

        return params;
    },

    /**
     * Handle route change
     */
    async handleRouteChange() {
        const route = this.getCurrentRoute();
        const content = document.getElementById('content');

        // Update nav active state
        document.querySelectorAll('.nav-link').forEach(link => {
            const linkPage = link.dataset.page;
            const isActive = route.path === '/' ? linkPage === 'dashboard' :
                route.path.startsWith(`/${linkPage}`);
            link.classList.toggle('active', isActive);
        });

        // Show loading
        content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        try {
            if (route.handler) {
                await route.handler(route.params);
            }
        } catch (error) {
            console.error('Route handler error:', error);
            content.innerHTML = `
                <div class="empty-state">
                    <h3>Error loading page</h3>
                    <p>${error.message}</p>
                </div>
            `;
        }
    },

    /**
     * Initialize router
     */
    init() {
        // Listen for hash changes
        window.addEventListener('hashchange', () => this.handleRouteChange());

        // Handle initial route
        this.handleRouteChange();
    }
};

window.router = router;
