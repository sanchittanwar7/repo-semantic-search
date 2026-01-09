"""
Searcher - Semantic search functionality.
Queries Qdrant with repository filtering.
"""
import os
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from dotenv import load_dotenv

# Configuration
COLLECTION_NAME = "codebase_chunks"
EMBEDDING_MODEL = "text-embedding-3-small"

# Initialize clients
load_dotenv()
qdrant = QdrantClient(host="localhost", port=6333)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_query_embedding(query: str) -> list[float]:
    """Generate embedding for a search query."""
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[query]
    )
    return response.data[0].embedding


def search(query: str, repo_id: str, top_k: int = 10) -> list[dict]:
    """
    Search for code chunks matching a natural language query.
    
    Args:
        query: Natural language search query
        repo_id: Repository ID to scope the search
        top_k: Number of results to return (default: 10)
    
    Returns:
        List of search results with:
            - file_path: Path to the source file
            - start_line: Starting line number
            - end_line: Ending line number
            - code_snippet: The matching code chunk
            - language: Programming language
            - score: Similarity score (0-1)
    """
    # Generate query embedding
    query_embedding = generate_query_embedding(query)
    
    # Search with repository filter
    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding,
        query_filter=Filter(
            must=[FieldCondition(key="repo_id", match=MatchValue(value=repo_id))]
        ),
        limit=top_k,
        with_payload=True,
    )
    
    # Format results
    formatted = []
    for hit in results.points:
        formatted.append({
            "file_path": hit.payload.get("file_path", ""),
            "start_line": hit.payload.get("start_line", 0),
            "end_line": hit.payload.get("end_line", 0),
            "code_snippet": hit.payload.get("content", ""),
            "language": hit.payload.get("language", "text"),
            "score": hit.score,
        })
    
    return formatted


def get_stats(repo_id: str) -> dict:
    """Get statistics for a repository's index."""
    try:
        result = qdrant.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=Filter(
                must=[FieldCondition(key="repo_id", match=MatchValue(value=repo_id))]
            ),
            limit=10000,
            with_payload=False,
            with_vectors=False,
        )
        return {"chunk_count": len(result[0])}
    except Exception:
        return {"chunk_count": 0}
