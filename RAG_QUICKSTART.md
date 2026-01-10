# RAG System Quick Start Guide

## Installation

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

This will install:
- `chromadb` - Vector database
- `sentence-transformers` - Embeddings and reranking
- `torch` - PyTorch backend
- `scikit-learn` - Similarity calculations
- Other existing dependencies

2. **Verify installation**:
```python
from app.rag import VectorStoreManager
# Should import without errors
```

## Quick Setup

1. **Enable RAG in config.yaml** (already enabled by default):
```yaml
rag:
  enabled: true
```

2. **Index existing jobs**:
```bash
# Index all jobs
python -m app.rag.index_jobs

# Index first 100 jobs
python -m app.rag.index_jobs --limit 100

# Index specific jobs
python -m app.rag.index_jobs --job-ids 1 2 3 4 5
```

3. **Use RAG in content generation** (already integrated):
```python
from app.agents.content_agent import ContentGenerationAgent
from app.db import get_db

db = next(get_db())
agent = ContentGenerationAgent(db=db, use_rag=True)  # RAG enabled by default

# Generate content - RAG will automatically retrieve similar jobs for context
bullet_points = agent.generate_resume_points(job, run_id=1)
```

## Testing the RAG System

### Test Vector Store
```python
from app.rag import VectorStoreManager

vector_store = VectorStoreManager()
stats = vector_store.get_collection_stats()
print(f"Documents in vector store: {stats['document_count']}")
```

### Test Retrieval
```python
from app.rag.service import JobRAGService
from app.db import get_db

db = next(get_db())
rag_service = JobRAGService(db=db)

# Retrieve similar jobs
similar_jobs = rag_service.retrieve_similar_jobs(
    query="Product Manager role with Python and machine learning",
    k=5
)

for similar in similar_jobs:
    print(f"Job: {similar['job'].title} @ {similar['job'].company}")
    print(f"Similarity: {similar['similarity_score']:.3f}")
    print()
```

### Test Full RAG Query
```python
result = rag_service.answer_query(
    query="What are the key requirements for Senior Product Manager roles?",
)

print("Answer:", result["answer"])
print(f"Retrieved {len(result['documents'])} relevant documents")
print(f"Relevance ratio: {result.get('relevance_ratio', 0):.2f}")
```

## Configuration Options

### Use Different Embedding Models

**OpenAI embeddings** (requires API key):
```yaml
rag:
  embeddings:
    provider: "openai"
    model: "text-embedding-3-small"  # or text-embedding-3-large
```

**Ollama embeddings** (local):
```yaml
rag:
  embeddings:
    provider: "ollama"
    model: "llama3.2"  # or other Ollama embedding model
```

**HuggingFace embeddings** (default, local):
```yaml
rag:
  embeddings:
    provider: "huggingface"
    model: "sentence-transformers/all-MiniLM-L6-v2"  # Fast and efficient
    # Or use larger models:
    # model: "sentence-transformers/all-mpnet-base-v2"  # Better quality, slower
```

### Adjust Chunking Strategy
```yaml
rag:
  chunking:
    chunk_size: 500        # Characters per chunk
    chunk_overlap: 50      # Overlap between chunks
    similarity_threshold: 0.7  # Lower = more chunks (0.0-1.0)
    min_chunk_size: 100    # Minimum chunk size
```

### Tune Retrieval Performance
```yaml
rag:
  retrieval:
    stage1_k: 50          # Number of candidates to retrieve
    stage2_k: 5           # Final results after reranking
    rerank_threshold: 0.5  # Minimum rerank score (optional)
```

### Adjust RAG Agent Behavior
```yaml
rag:
  agent:
    max_iterations: 3           # Maximum retrieval cycles
    min_relevance_score: 0.7    # Minimum relevance to accept documents
```

### Enable/Disable HyDE
```yaml
rag:
  hyde:
    enabled: true  # Enable Hypothetical Document Embeddings
```

## Common Issues

### Issue: "ChromaDB not found" error
**Solution**: Install chromadb: `pip install chromadb==0.4.22`

### Issue: "sentence-transformers not available"
**Solution**: Install sentence-transformers: `pip install sentence-transformers==2.3.1`
Note: This will also install PyTorch, which may take time.

### Issue: Vector store directory permission errors
**Solution**: Ensure write permissions for `./vector_store` directory

### Issue: Embedding model download slow
**Solution**: 
- First run will download models (HuggingFace models ~80-400MB)
- Models are cached locally after first download
- Use smaller models like `all-MiniLM-L6-v2` for faster startup

### Issue: RAG not improving results
**Solution**:
1. Ensure jobs are indexed: `python -m app.rag.index_jobs`
2. Check vector store stats: `vector_store.get_collection_stats()`
3. Try adjusting `similarity_threshold` or `min_relevance_score`
4. Use larger embedding models for better quality

### Issue: Re-ranker model not available
**Solution**: 
- Install sentence-transformers (includes reranker support)
- Or the system will fall back to LLM-based reranking (slower but works)

## Performance Tips

1. **Index jobs incrementally**: Index new jobs as they're added
2. **Use local embeddings**: HuggingFace models are faster than API calls
3. **Adjust chunk sizes**: Smaller chunks = more precision, larger = more context
4. **Monitor relevance scores**: Tune thresholds based on your data
5. **Cache embeddings**: ChromaDB caches embeddings automatically

## Next Steps

1. **Index your jobs**: `python -m app.rag.index_jobs`
2. **Test retrieval**: Try querying for similar jobs
3. **Monitor performance**: Check logs for retrieval metrics
4. **Tune parameters**: Adjust thresholds based on results
5. **Evaluate quality**: Compare content with/without RAG

For more details, see [RAG_IMPLEMENTATION.md](RAG_IMPLEMENTATION.md)
