# LinkedIn API Setup Guide

## Important: LinkedIn Doesn't Have a Job Search API

LinkedIn does **not** provide a public API for searching jobs. The available LinkedIn APIs are:
- **Job Posting API** - For posting jobs (not searching)
- **Talent Solutions APIs** - For recruiters/employers
- **Marketing APIs** - For advertising
- **Learning APIs** - For educational content

## Options for LinkedIn Job Search

### Option 1: Third-Party APIs (Recommended)

We've already integrated support for:

#### Mantiks API
- **Service**: https://mantiks.io
- **Best for**: Real-time LinkedIn job data
- **Setup**:
  1. Sign up at https://mantiks.io
  2. Get your API key
  3. Add to `.env`: `MANTIKS_API_KEY=your-key`
  4. Enable in `config.yaml`: `use_mantiks: true`

#### Apify API
- **Service**: https://apify.com
- **Best for**: LinkedIn Jobs Scraper actor
- **Setup**:
  1. Sign up at https://apify.com
  2. Get your API key
  3. Add to `.env`: `APIFY_API_KEY=your-key`
  4. Enable in `config.yaml`: `use_apify: true`

### Option 2: OAuth-Authenticated Scraping

If you have a LinkedIn developer account, you can:

1. **Set up OAuth 2.0**:
   - Go to https://www.linkedin.com/developers/
   - Create an app
   - Get Client ID and Client Secret
   - Set redirect URLs

2. **Request Permissions**:
   - Request `r_liteprofile` or `r_basicprofile`
   - Note: LinkedIn may not allow scraping even with OAuth

3. **Implementation**:
   - Users authenticate with LinkedIn
   - Use their session to scrape jobs
   - More complex, requires user interaction

### Option 3: Official LinkedIn Partnership

For enterprise use cases:
- Apply for **Talent Solutions Partnership**
- Requires business case, user base, compliance
- Approval process: several months
- Low acceptance rate
- Still may not provide job search endpoints

## Current Implementation

The system currently:
- ✅ Supports Mantiks API (ready to use)
- ✅ Supports Apify API (ready to use)
- ✅ Falls back to mock data if no APIs configured
- ⚠️ Direct scraping disabled (requires authentication)

## Recommendation

**Use Mantiks API** for LinkedIn job search:
- Designed specifically for LinkedIn job data
- Handles authentication automatically
- Real-time data access
- No user interaction required

## Next Steps

1. **Get Mantiks API key** (recommended)
2. **Or get Apify API key** (alternative)
3. Add to `.env` file
4. Enable in `config.yaml`
5. System will automatically use the API

## If You Have LinkedIn Developer Credentials

If you want to use OAuth-based scraping:
1. Share your Client ID and Client Secret
2. I can implement OAuth flow
3. Users will need to authenticate
4. We'll use their session for scraping

Note: This is more complex and may still violate LinkedIn's ToS for automated scraping.

