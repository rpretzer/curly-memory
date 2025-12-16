#!/bin/bash
# Setup script for the job search pipeline

set -e

echo "Setting up Agentic Job Search Pipeline..."
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Set up environment file
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please edit .env and add your OPENAI_API_KEY"
else
    echo ".env file already exists"
fi

# Set up config file
if [ ! -f "config.yaml" ]; then
    echo "Creating config.yaml from template..."
    cp config.example.yaml config.yaml
    echo "Configuration file created. You can customize it as needed."
else
    echo "config.yaml already exists"
fi

# Initialize database
echo "Initializing database..."
python cli.py init

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your OPENAI_API_KEY"
echo "2. (Optional) Customize config.yaml"
echo "3. Start the API server: python -m app.api.main"
echo "4. In another terminal, start the frontend: cd frontend && npm install && npm run dev"
echo ""
echo "Or run the example: python example_run.py"
