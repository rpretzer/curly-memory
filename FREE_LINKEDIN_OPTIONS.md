# Free LinkedIn Job Search Options

## Free Alternatives to Mantiks

### Option 1: Apify Free Tier (Recommended)

**Apify** offers a free tier with $5/month in platform credits:
- **Service**: https://apify.com
- **Free Tier**: $5/month credits (enough for ~100-500 job searches depending on actor)
- **LinkedIn Actor**: "LinkedIn Jobs Scraper" available
- **Setup**:
  1. Sign up at https://apify.com (free account)
  2. Get your API key from dashboard
  3. Add to `.env`: `APIFY_API_KEY=your-key`
  4. Enable in `config.yaml`: `use_apify: true`

**Pros**:
- Free tier available
- Handles CAPTCHAs
- Reliable scraping

**Cons**:
- Limited to $5/month (may need to upgrade for heavy use)
- Requires API key setup

### Option 2: Improved Direct Scraping (100% Free)

We've improved the direct scraping implementation to work without any API keys:

**Features**:
- ✅ No API keys required
- ✅ Free forever
- ✅ Better session management
- ✅ Multiple selector fallbacks
- ✅ Automatic retry logic

**Limitations**:
- ⚠️ May get blocked by LinkedIn (rate limiting)
- ⚠️ Requires LinkedIn to allow public access (they may redirect to login)
- ⚠️ Less reliable than paid APIs

**How it works**:
- Uses requests library with proper headers
- Rotates user agents
- Tries multiple HTML selectors
- Falls back to mock data if blocked

### Option 3: Use Only Indeed + Wellfound (Free)

Since LinkedIn is challenging, you can:
- **Disable LinkedIn** in `config.yaml`:
  ```yaml
  job_sources:
    linkedin:
      enabled: false
  ```
- **Focus on Indeed** (with ScrapeOps - already configured)
- **Use Wellfound** (free direct scraping)

This gives you 2 out of 3 sources working well for free!

## Current Configuration

The system will try in this order:
1. **Mantiks API** (if configured) - Paid
2. **Apify API** (if configured) - Free tier available
3. **Direct scraping** (always available) - Free but may be blocked
4. **Mock data** (fallback) - For testing

## Recommendation

**Best free option**: Use **Apify free tier** ($5/month credits):
- Most reliable free option
- Handles LinkedIn's anti-scraping measures
- Enough credits for moderate use
- Easy to upgrade if needed

**Alternative**: Use improved direct scraping:
- Already implemented
- No setup required
- Works until LinkedIn blocks it
- Free forever

## Setup Instructions

### For Apify (Free Tier):

1. **Sign up**: https://apify.com
2. **Get API key**: Dashboard → Settings → Integrations
3. **Add to `.env`**:
   ```bash
   APIFY_API_KEY=your-apify-key-here
   ```
4. **Enable in `config.yaml`**:
   ```yaml
   job_sources:
     linkedin:
       use_apify: true
   ```

### For Direct Scraping (No Setup):

Already enabled! The system will automatically try direct scraping if no APIs are configured.

## Testing

Run a search to test:
```bash
python cli.py run --titles "Product Manager" --max-results 10
```

Check logs to see which method was used:
- "Using Apify API" = Apify working
- "Attempting direct LinkedIn scraping" = Direct scraping
- "Using mock data" = All methods failed

