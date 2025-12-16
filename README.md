# Agentic Job Search and Application Pipeline

A production-ready Python application with a Next.js frontend for automated job searching, intelligent scoring, LLM-powered content generation, and semi-automated application management with human-in-the-loop approval.

## Features

- **Multi-Source Job Search**: Searches LinkedIn, Indeed, and Wellfound (adapters can be extended)
- **Intelligent Scoring**: Configurable scoring system based on title match, verticals, compensation, keywords, and more
- **LLM-Powered Content Generation**: Generates tailored resume bullet points, cover letters, and application answers
- **Browser Automation**: Playwright-based automation for Easy Apply and external applications (with safety gates)
- **Human-in-the-Loop**: Approval workflows ensure quality control before applications
- **Comprehensive Logging**: Structured logging with agent reasoning, LLM usage tracking, and error handling
- **Web UI**: Next.js dashboard for configuration, job review, run management, and observability
- **Scheduling**: Automated pipeline runs on configurable schedules

## Architecture

### Backend (Python/FastAPI)

- **Agents**:
  - `SearchAgent`: Queries multiple job sources and normalizes results
  - `FilterAndScoreAgent`: Scores and filters jobs based on configurable criteria
  - `ContentGenerationAgent`: Uses LLM to generate tailored content
  - `ApplyAgent`: Handles job applications via API or browser automation
  - `LogAgent`: Structured logging for observability

- **Orchestrator**: Coordinates agents through the pipeline lifecycle
- **Database**: SQLAlchemy models with SQLite (PostgreSQL-ready)
- **API**: FastAPI with REST endpoints and background task support

### Frontend (Next.js/React/TypeScript)

- Dashboard for viewing runs and metrics
- Job review and approval interface
- Configuration forms for search parameters and scoring weights
- Real-time status updates

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- OpenAI API key (for LLM features)
- (Optional) Playwright for browser automation

### Backend Setup

1. **Clone and navigate to the project:**
   ```bash
   cd agentic-job-pipeline
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

5. **Create config file:**
   ```bash
   cp config.example.yaml config.yaml
   # Edit config.yaml with your preferences
   ```

6. **Initialize the database:**
   ```bash
   python cli.py init
   ```

7. **Run the API server:**
   ```bash
   python -m app.api.main
   # Or: uvicorn app.api.main:app --reload
   ```

   The API will be available at `http://localhost:8000`

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Run the development server:**
   ```bash
   npm run dev
   ```

   The frontend will be available at `http://localhost:3000`

### (Optional) Install Playwright for Browser Automation

```bash
playwright install chromium
```

## Usage

### CLI Usage

**Run a search only:**
```bash
python cli.py search --titles "Senior Product Manager" "Principal PM" --remote --locations "Remote, US"
```

**Run full pipeline (search, score, generate content):**
```bash
python cli.py run \
  --titles "Senior Product Manager" \
  --locations "Remote, US" \
  --remote \
  --keywords "insurance" "fintech" \
  --must-have "product management" "B2B" \
  --salary-min 120000
```

**Start the scheduler:**
```bash
python cli.py schedule
```

### API Usage

**Create a new pipeline run:**
```bash
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{
    "search": {
      "titles": ["Senior Product Manager"],
      "locations": ["Remote, US"],
      "remote": true,
      "max_results": 50
    },
    "target_companies": ["TechCorp"],
    "must_have_keywords": ["product management", "B2B"],
    "remote_preference": "remote",
    "salary_min": 120000,
    "generate_content": true
  }'
```

**Get run status:**
```bash
curl http://localhost:8000/runs/1
```

**List all jobs from a run:**
```bash
curl http://localhost:8000/runs/1/jobs
```

**Approve a job:**
```bash
curl -X POST http://localhost:8000/jobs/123/approve
```

**Generate content for a job:**
```bash
curl -X POST http://localhost:8000/jobs/123/generate-content
```

**Apply to a job:**
```bash
curl -X POST http://localhost:8000/jobs/123/apply
```

### Web UI Usage

1. Navigate to `http://localhost:3000`
2. Use the dashboard to:
   - View recent runs and their status
   - Browse and filter jobs
   - Approve/reject jobs for application
   - View generated content (summaries, resume points, cover letters)
   - Trigger applications

## Configuration

### Environment Variables (.env)

- `OPENAI_API_KEY`: Your OpenAI API key (required for content generation)
- `DATABASE_URL`: Database connection string (default: SQLite)
- `LLM_MODEL`: LLM model to use (default: gpt-4-turbo-preview)
- `LLM_TEMPERATURE`: Temperature for LLM (default: 0.7)
- `ENABLE_PLAYWRIGHT`: Enable browser automation (default: true)
- `HUMAN_IN_THE_LOOP`: Require approval before applications (default: true)

### Configuration File (config.yaml)

Key sections:
- **search**: Default search parameters (titles, locations, remote preference)
- **scoring**: Scoring weights for different criteria (0-10 scale)
- **verticals**: Target industry keywords for vertical matching
- **thresholds**: Minimum and high relevance scores
- **llm**: LLM configuration defaults
- **job_sources**: Configuration for each job board adapter
- **scheduler**: Schedule configuration (frequency, time)

Example configuration:
```yaml
scoring:
  title_match_weight: 8.0
  vertical_match_weight: 6.0
  comp_match_weight: 7.0
  keyword_overlap_weight: 6.0

thresholds:
  min_relevance_score: 5.0
  high_relevance_score: 8.0
```

## Example Run

Here's an example of running a search for "Senior Product Manager" roles in InsurTech:

```python
from app.db import get_db_context
from app.orchestrator import PipelineOrchestrator

with get_db_context() as db:
    orchestrator = PipelineOrchestrator(db)
    
    run = orchestrator.create_run(
        search_config={"titles": ["Senior Product Manager"]},
        scoring_config={},
        llm_config={},
    )
    
    result = orchestrator.run_full_pipeline(
        run_id=run.id,
        titles=["Senior Product Manager", "Principal Product Manager"],
        locations=["Remote, US"],
        remote=True,
        keywords=["insurance", "insurtech", "fintech"],
        target_companies=["TechCorp Insurance"],
        must_have_keywords=["product management", "B2B"],
        nice_to_have_keywords=["data analytics", "API"],
        remote_preference="remote",
        salary_min=120000,
        generate_content=True,
        auto_apply=False,  # Always requires manual approval
    )
    
    print(f"Run complete: {result}")
```

## Project Structure

```
agentic-job-pipeline/
├── app/
│   ├── agents/           # Agent implementations
│   │   ├── search_agent.py
│   │   ├── filter_score_agent.py
│   │   ├── content_agent.py
│   │   ├── apply_agent.py
│   │   └── log_agent.py
│   ├── jobsources/       # Job board adapters
│   │   ├── base.py
│   │   ├── linkedin_adapter.py
│   │   ├── indeed_adapter.py
│   │   └── wellfound_adapter.py
│   ├── api/              # FastAPI application
│   │   └── main.py
│   ├── models.py         # SQLAlchemy models
│   ├── db.py             # Database setup
│   ├── config.py         # Configuration management
│   ├── orchestrator.py   # Pipeline orchestration
│   ├── scheduling.py     # Scheduler
│   └── user_profile.py   # User profile management
├── frontend/             # Next.js frontend
│   ├── app/
│   │   ├── page.tsx      # Dashboard
│   │   ├── runs/         # Runs page
│   │   └── jobs/         # Jobs pages
│   └── package.json
├── cli.py                # Command-line interface
├── requirements.txt      # Python dependencies
├── config.example.yaml   # Configuration template
├── .env.example          # Environment variables template
└── README.md
```

## Extending the System

### Adding a New Job Source

1. Create a new adapter in `app/jobsources/`:
   ```python
   from app.jobsources.base import BaseJobSource, JobListing
   
   class NewSourceAdapter(BaseJobSource):
       def search(self, query, location=None, remote=False, max_results=50, **kwargs):
           # Implement search logic
           return job_listings
   ```

2. Register it in `app/agents/search_agent.py`

### Adding a New Agent

1. Create agent class in `app/agents/`
2. Implement a `run()` method or similar interface
3. Integrate with `PipelineOrchestrator`

### Using a Different LLM Provider

The `ContentGenerationAgent` uses LangChain, which supports multiple providers. Modify the LLM initialization in `app/agents/content_agent.py`:

```python
from langchain_anthropic import ChatAnthropic

self.llm = ChatAnthropic(
    model="claude-3-opus",
    anthropic_api_key=api_key,
)
```

## Observability

- **Structured Logging**: All agent activities are logged with context (run_id, job_id, reasoning)
- **Database Tracking**: Complete audit trail of jobs, runs, and applications
- **Metrics Endpoint**: `/api/metrics` provides aggregate statistics
- **Error Tracking**: Failed operations are logged with stack traces

## Safety and Ethics

- **Human-in-the-Loop**: Applications always require explicit approval
- **Rate Limiting**: Built-in delays between API calls to job sources
- **Error Handling**: Graceful degradation when APIs fail
- **Privacy**: Job data is stored locally; no sharing without consent

## Limitations and TODOs

- **Job Source APIs**: Current adapters use mock data. Real integrations require:
  - LinkedIn Jobs API access (limited availability)
  - Indeed Publisher API key
  - Wellfound API documentation
  
- **Browser Automation**: Playwright flows are stubbed. Real implementation requires:
  - Site-specific selectors and form handling
  - CAPTCHA handling (may require manual intervention)
  - Multi-step application flows
  
- **Content Generation**: Currently uses OpenAI. Can be extended to support:
  - Anthropic Claude
  - Local models (via Ollama)
  - Multiple models with fallback

## License

[Your License Here]

## Contributing

[Contributing Guidelines]

## Support

For issues, questions, or contributions, please open an issue on GitHub.
