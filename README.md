# Codebase Semantic Search

Local semantic code search powered by OpenAI embeddings and Qdrant. Index multiple repositories and search with natural language.

## Features

- 🔍 **Natural Language Search** - Find code using plain English queries
- 📁 **Multi-Repo Support** - Index and switch between multiple repositories
- 🧠 **Smart Chunking** - Code-aware splitting respects function/class boundaries
- 🔒 **Repo Isolation** - Searches scoped to selected repository only
- ⚡ **Re-indexing** - Detect changes and re-index existing repos

## Prerequisites

- Python 3.10+
- Docker (for Qdrant)
- OpenAI API key

## Quick Start

```bash
# 1. Start Qdrant
docker run -p 6333:6333 qdrant/qdrant

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env file
echo "OPENAI_API_KEY=your-key-here" > .env

# 4. Run the app
streamlit run app.py
```

Open http://localhost:8501, index a repo, and start searching!
