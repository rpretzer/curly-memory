# Quick Start Guide

Get the job search pipeline up and running in 5 minutes!

## 1. Setup Backend (Python)

```bash
# Run the setup script
./setup.sh

# Or manually:
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
cp config.example.yaml config.yaml
python cli.py init
```

**Important**: Edit `.env` and add your `OPENAI_API_KEY`:

```bash
OPENAI_API_KEY=sk-your-key-here
```

## 2. Start the API Server

```bash
source venv/bin/activate
python -m app.api.main
```

The API will be available at `http://localhost:8000`

## 3. Setup Frontend (Next.js)

In a new terminal:

```bash
cd frontend
npm install
npm run dev
```

The UI will be available at `http://localhost:3000`

## 4. Run Your First Search

### Option A: Using the CLI

```bash
python cli.py run \
  --titles "Senior Product Manager" \
  --remote \
  --locations "Remote, US" \
  --keywords "insurance" "fintech"
```

### Option B: Using the Example Script

```bash
python example_run.py
```

### Option C: Using the API

```bash
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{
    "search": {
      "titles": ["Senior Product Manager"],
      "locations": ["Remote, US"],
      "remote": true,
      "max_results": 20
    },
    "generate_content": true
  }'
```

Then visit `http://localhost:3000/jobs` to view the results!

## 5. Review and Approve Jobs

1. Go to `http://localhost:3000/jobs`
2. Browse the found jobs
3. Click "Approve" on jobs you want to apply to
4. Click "View" to see generated content (cover letter, resume points)
5. Click "Apply" when ready (requires approval)

## What's Next?

- Customize `config.yaml` with your preferences
- Set up the scheduler: `python cli.py schedule`
- Read the full [README.md](README.md) for advanced features

## Troubleshooting

**"No module named 'app'"**: Make sure you're in the project root and the virtual environment is activated.

**"OPENAI_API_KEY not found"**: Check your `.env` file and ensure the API key is set correctly.

**Frontend can't connect to API**: Make sure the backend API is running on port 8000.

**Database errors**: Run `python cli.py init` to initialize the database.
