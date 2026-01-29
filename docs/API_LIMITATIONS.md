# Job Application API Limitations

## Overview

This document explains the reality of job board APIs and why browser automation (Playwright) is the primary method for job applications in this system.

## The Reality: No Public APIs for Job Applications

**TL;DR: Major job boards do NOT provide public APIs for submitting job applications.**

### Why Job Boards Don't Offer Application APIs

1. **Spam Prevention**: APIs would enable mass spam applications
2. **User Experience Control**: Job boards want to control the application flow
3. **Revenue**: Job boards monetize traffic from job seekers
4. **Legal/Compliance**: Automated applications raise legal concerns
5. **Quality Control**: Human interaction ensures application quality

## Job Board API Support Matrix

| Job Board | Search API | Application API | Notes |
|-----------|-----------|-----------------|-------|
| **LinkedIn** | ✅ Yes | ❌ No | Jobs API only supports search and job posting, not applications |
| **Indeed** | ✅ Yes | ❌ No | Publisher API only supports search and job details |
| **Greenhouse** | ✅ Partial | ❌ No | Can fetch application form structure, but not submit |
| **Workday** | ❌ No | ❌ No | No public candidate-facing APIs |
| **Monster** | ✅ Limited | ❌ No | Deprecated XML API, no application submission |
| **Wellfound** | ✅ Limited | ❌ No | Limited public API access |

## What IS Possible

### 1. Job Search APIs
Most boards offer APIs to search and retrieve job listings:
- **LinkedIn Jobs API**: Search jobs, get job details
- **Indeed Publisher API**: Search jobs across Indeed
- **Greenhouse Board API**: Public job board listings

### 2. Application Form Structure (Limited)
Some ATS platforms allow retrieving application form metadata:
- **Greenhouse**: Can fetch application questions via Board API
- **Workday**: No public API for form structure

### 3. Browser Automation (Our Primary Method)
Using Playwright to fill out application forms programmatically:
- ✅ **Indeed**: Easy Apply automation
- ✅ **LinkedIn**: Easy Apply automation
- ✅ **Greenhouse/Workday**: Form filling with field detection
- ✅ **External Sites**: Assisted mode with pre-filling

## Implementation in This Codebase

### API Adapter Pattern
We've implemented an API adapter pattern (`app/jobsources/api_adapters.py`) that:
- Documents what each job board supports
- Provides a framework for future API integrations
- Returns clear error messages explaining limitations
- Can fetch application questions where supported (e.g., Greenhouse)

### Usage Flow
```python
# 1. Try API first (will fail for most sources)
if job.application_type == ApplicationType.API:
    success = apply_via_api(job, data)
    if not success:
        # Fall back to browser automation
        success = apply_via_playwright(job, data)

# 2. Use browser automation directly for Easy Apply
elif job.application_type == ApplicationType.EASY_APPLY:
    success = apply_via_playwright(job, data)

# 3. Use assisted mode for external applications
elif job.application_type == ApplicationType.EXTERNAL:
    success = apply_external_assisted(job, data)
```

### Code Organization
```
app/
├── jobsources/
│   └── api_adapters.py          # API adapter classes
├── agents/
│   └── apply_agent.py            # Application submission logic
└── models.py                     # ApplicationType enum
```

## Future Possibilities

### If APIs Become Available
The adapter pattern is extensible. To add a new API:

1. Create adapter class in `api_adapters.py`:
```python
class NewBoardAPIAdapter(JobApplicationAPIAdapter):
    def submit_application(self, job_id, data):
        # Implementation
        response = requests.post(f"{API_URL}/apply", json=data)
        return response.status_code == 200, None
```

2. Register in `get_api_adapter()`:
```python
adapters = {
    "newboard": NewBoardAPIAdapter,
    # ...
}
```

3. Update `ApplicationType` enum if needed

### OAuth Integration
If job boards offer OAuth for user authorization:
- LinkedIn OAuth could enable API access to user profile
- Could store access tokens in database (encrypted)
- Still wouldn't enable application submission (LinkedIn doesn't support it)

## Recommendations

### For Maximum Success Rate
1. **Use Browser Automation (Playwright)** as primary method
2. **Enable Easy Apply Filtering** to focus on automatable applications
3. **Human-in-the-Loop for Complex Forms** - use assisted mode
4. **Resume Parsing** - extract data to fill forms accurately

### For Reliability
1. **Implement retries** with exponential backoff
2. **CAPTCHA detection** - pause and alert user
3. **Form field detection** - multiple selector strategies
4. **Error logging** - track why applications fail

### For Compliance
1. **Rate limiting** - don't spam job boards
2. **Respect robots.txt** - check allowed automation
3. **User consent** - ensure users approve automated applications
4. **Transparency** - clearly communicate automation use

## References

### Official API Documentation
- [LinkedIn Jobs API](https://docs.microsoft.com/en-us/linkedin/talent/job-postings) - Search only
- [Indeed Publisher API](https://opensource.indeedeng.io/api-documentation/) - Search only
- [Greenhouse Board API](https://developers.greenhouse.io/job-board.html) - Job listings

### Alternative Approaches
- Browser automation (Playwright, Selenium)
- Chrome extensions for assisted applications
- Email-based application tracking
- Application Management Systems (AMS) integration

---

**Last Updated**: 2026-01-29
**Status**: Current as of 2026 - major job boards still do not offer application APIs
