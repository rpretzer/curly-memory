# Ollama Setup Guide

## Installation

Ollama installation requires sudo privileges. Install it manually with:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Or on macOS:
```bash
brew install ollama
```

## Starting Ollama

After installation, start the Ollama service:

```bash
# Linux (systemd)
sudo systemctl start ollama

# Or run manually in the background
ollama serve
```

## Downloading a Model

Pull a model (choose based on your hardware):

```bash
# Small, fast model (good for most tasks)
ollama pull llama3.2

# Or larger, more capable models
ollama pull llama3
ollama pull mistral
ollama pull codellama  # Good for code-related content
```

## Configuration

Update `config.yaml` to use Ollama:

```yaml
llm:
  provider: ollama  # Change from "openai" to "ollama"
  model: llama3.2   # Use the model you pulled
  ollama_base_url: http://localhost:11434
  temperature: 0.7
  max_tokens: 2000
```

Or set environment variables:

```bash
export LLM_PROVIDER=ollama
export LLM_MODEL=llama3.2
export OLLAMA_BASE_URL=http://localhost:11434
```

## Testing

Test that Ollama is working:

```bash
curl http://localhost:11434/api/tags
```

Or test from Python:

```python
from langchain_community.chat_models import ChatOllama

llm = ChatOllama(model="llama3.2")
response = llm.invoke("Say hello!")
print(response.content)
```

## Switching Back to OpenAI

To switch back to OpenAI:

```yaml
llm:
  provider: openai
  model: gpt-4o-mini
```

Make sure `OPENAI_API_KEY` is set in your `.env` file.


