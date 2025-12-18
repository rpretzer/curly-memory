# Web Scraping Enhancement Guide

This document describes the enhanced web scraping features implemented for the job search pipeline.

## Features Implemented

### 1. Retry Logic with Exponential Backoff

All scraping operations now include automatic retry logic with exponential backoff to handle transient failures.

**Configuration:**
```yaml
job_sources:
  indeed:
    max_retries: 3      # Number of retry attempts
    retry_delay: 2.0    # Initial delay in seconds
```

**How it works:**
- Retries failed requests up to `max_retries` times
- Delay increases exponentially: 2s → 4s → 8s (with jitter)
- Maximum delay capped at 60 seconds
- Random jitter added to prevent thundering herd

### 2. Proxy Rotation

Support for proxy rotation to avoid IP-based rate limiting and blocking.

**Configuration:**
```yaml
job_sources:
  indeed:
    proxies:
      - "http://user:pass@proxy1.example.com:8080"
      - "http://user:pass@proxy2.example.com:8080"
      - "socks5://user:pass@proxy3.example.com:1080"
```

**Features:**
- Round-robin proxy rotation
- Automatic failed proxy detection and exclusion
- Automatic reset of failed proxies after all are marked failed
- Supports HTTP, HTTPS, and SOCKS5 proxies

### 3. Third-Party API Integration

Integration with professional scraping APIs that handle CAPTCHAs, proxies, and anti-bot measures.

#### ScrapeOps API

**Setup:**
1. Sign up at https://scrapeops.io
2. Get your API key
3. Add to `.env`: `SCRAPEOPS_API_KEY=your-key-here`
4. Enable in `config.yaml`:
```yaml
job_sources:
  indeed:
    use_scrapeops: true
```

**Benefits:**
- Handles CAPTCHAs automatically
- Uses rotating proxies
- Higher success rates
- Clean JSON responses

#### HasData API

**Setup:**
1. Sign up at https://hasdata.com
2. Get your API key
3. Add to `.env`: `HASDATA_API_KEY=your-key-here`
4. Enable in `config.yaml`:
```yaml
job_sources:
  indeed:
    use_hasdata: true
```

**Benefits:**
- 1,000 free API calls/month
- No credit card required for free tier
- Handles proxies and CAPTCHAs
- Normalized data format

**Priority:**
If both APIs are configured, ScrapeOps is tried first, then HasData, then falls back to direct scraping.

### 4. Improved HTML Selector Handling

Enhanced selector fallback system to handle website structure changes.

**Multiple Selector Attempts:**
- Each field (title, company, location, etc.) tries multiple CSS selectors
- Falls back gracefully if primary selector fails
- Logs warnings when selectors fail for debugging

**Example:**
```python
# Title extraction tries multiple selectors:
title_elem = (
    card.find('h2', class_='jobTitle') or
    card.find('h2', {'data-testid': 'job-title'}) or
    card.find('h2') or
    card.find('a', class_='jcs-JobTitle')
)
```

### 5. User-Agent Rotation

Automatic rotation of realistic user agents to reduce detection.

**Features:**
- 6 different user agents (Chrome, Safari, Firefox on different OS)
- Random selection on each request
- 30% chance of rotation per request
- Realistic browser headers

## Configuration

### Environment Variables

Add to `.env`:
```bash
# Third-party API keys (optional)
SCRAPEOPS_API_KEY=your-scrapeops-key
HASDATA_API_KEY=your-hasdata-key

# Proxy configuration (optional, can also use config.yaml)
PROXY_LIST=http://proxy1:8080,http://proxy2:8080
```

### Config.yaml

```yaml
job_sources:
  indeed:
    enabled: true
    max_results: 50
    rate_limit_delay: 3.0
    use_scrapeops: false  # Enable if you have API key
    use_hasdata: false    # Enable if you have API key
    max_retries: 3
    retry_delay: 2.0
    proxies: []  # Optional proxy list
```

## Usage Examples

### Using Third-Party APIs

1. **Get API keys:**
   - ScrapeOps: https://scrapeops.io (free tier available)
   - HasData: https://hasdata.com (1,000 free calls/month)

2. **Configure:**
   ```bash
   # Add to .env
   SCRAPEOPS_API_KEY=your-key
   ```

   ```yaml
   # config.yaml
   job_sources:
     indeed:
       use_scrapeops: true
   ```

3. **Run search:**
   ```bash
   python cli.py run --titles "Product Manager" --max-results 20
   ```

### Using Proxy Rotation

1. **Get proxies:**
   - Free: https://free-proxy-list.net
   - Paid: Bright Data, Smartproxy, etc.

2. **Configure:**
   ```yaml
   job_sources:
     indeed:
       proxies:
         - "http://user:pass@proxy1.com:8080"
         - "http://user:pass@proxy2.com:8080"
   ```

3. **Run search:**
   The system will automatically rotate through proxies.

## Monitoring and Debugging

### Logging

All scraping operations log:
- Retry attempts
- Proxy failures
- API fallbacks
- Selector failures

**Log levels:**
- `INFO`: Normal operations
- `WARNING`: Retries, fallbacks, selector issues
- `ERROR`: Complete failures

### Error Handling

The system gracefully handles:
- Network timeouts
- Rate limiting (403 errors)
- CAPTCHA detection
- HTML structure changes
- API failures

All errors fall back to mock data for testing continuity.

## Best Practices

1. **Start with Third-Party APIs:**
   - Highest success rates
   - Handle CAPTCHAs automatically
   - Free tiers available

2. **Use Proxies for Direct Scraping:**
   - Reduces IP-based blocking
   - Distributes load
   - Better for high-volume scraping

3. **Configure Appropriate Rate Limits:**
   - 3-5 seconds for direct scraping
   - 1-2 seconds for API-based scraping
   - Adjust based on success rates

4. **Monitor Logs:**
   - Watch for repeated failures
   - Update selectors if needed
   - Rotate proxies if blocked

## Troubleshooting

### High Failure Rates

1. **Enable third-party APIs** (recommended)
2. **Add more proxies** to rotation
3. **Increase rate limits** (slower but more reliable)
4. **Check logs** for specific error patterns

### Selector Failures

1. **Check website structure** - sites change frequently
2. **Update selectors** in adapter code
3. **Use browser dev tools** to find new selectors
4. **Report issues** - selector fallbacks should handle most cases

### API Failures

1. **Verify API keys** are correct
2. **Check API quotas** - free tiers have limits
3. **Review API status** - services may be down
4. **System falls back** to direct scraping automatically

## Performance

### Expected Success Rates

- **Direct Scraping:** 30-50% (varies by site)
- **With Proxies:** 60-80%
- **Third-Party APIs:** 90-99%

### Speed

- **Direct Scraping:** ~3-5 seconds per page
- **With Retries:** +2-8 seconds on failures
- **Third-Party APIs:** ~1-2 seconds per request

## Cost Considerations

### Free Options

- **HasData:** 1,000 free API calls/month
- **ScrapeOps:** Free tier with limited calls
- **Free Proxies:** Available but unreliable

### Paid Options

- **ScrapeOps:** ~$29/month for 100k requests
- **HasData:** Pay-as-you-go pricing
- **Proxy Services:** $50-200/month for reliable proxies

## Future Enhancements

Potential improvements:
- [ ] Selenium/Playwright for JavaScript-heavy sites
- [ ] Machine learning for selector detection
- [ ] Automatic selector updates
- [ ] Distributed scraping with multiple workers
- [ ] Caching to reduce API calls

