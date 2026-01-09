"""
Indexer - Repository indexing pipeline.
Generates embeddings and stores in Qdrant vector database.
"""
import os
from pathlib import Path
from typing import Callable, Optional
from dotenv import load_dotenv

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

from chunker import chunk_file, get_files_to_index
from registry import add_repo, update_repo, repo_exists

# Configuration
COLLECTION_NAME = "codebase_chunks"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
BATCH_SIZE = 100  # Chunks per batch for embedding generation

# Initialize clients
load_dotenv()
qdrant = QdrantClient(host="localhost", port=6333)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def ensure_collection_exists() -> None:
    """Create the Qdrant collection if it doesn't exist."""
    collections = qdrant.get_collections().collections
    if not any(c.name == COLLECTION_NAME for c in collections):
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts using OpenAI API."""
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )
    return [item.embedding for item in response.data]


def index_repository(
    path: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    force_reindex: bool = False
) -> dict:
    """
    Index a repository into Qdrant.
    
    Args:
        path: Absolute path to the repository root
        progress_callback: Optional callback(current, total, message) for progress updates
        force_reindex: If True, delete existing index and re-index
    
    Returns:
        Dictionary with indexing statistics
    """
    root_path = Path(path).resolve()
    
    if not root_path.exists():
        raise ValueError(f"Path does not exist: {path}")
    
    if not root_path.is_dir():
        raise ValueError(f"Path is not a directory: {path}")
    
    # Check if already indexed
    existing = repo_exists(str(root_path))
    if existing and not force_reindex:
        raise ValueError(f"Repository already indexed. Use force_reindex=True to re-index.")
    
    # If re-indexing, delete existing data
    if existing:
        delete_repository_index(existing["repo_id"])
        repo_id = existing["repo_id"]
    else:
        repo_id = None
    
    ensure_collection_exists()
    
    # Collect all files to index
    files = list(get_files_to_index(root_path))
    total_files = len(files)
    
    if total_files == 0:
        raise ValueError("No indexable files found in the repository.")
    
    # Process files and collect chunks
    all_chunks = []
    processed_files = 0
    
    for file_path in files:
        if progress_callback:
            progress_callback(processed_files, total_files, f"Processing {file_path.name}")
        
        for chunk in chunk_file(file_path):
            chunk["repo_id"] = repo_id or "temp"  # Will be updated
            all_chunks.append(chunk)
        
        processed_files += 1
    
    if not all_chunks:
        raise ValueError("No code chunks could be extracted from the repository.")
    
    # Register/update repository
    repo_name = root_path.name
    if existing:
        repo = update_repo(repo_id, total_files)
    else:
        repo = add_repo(repo_name, str(root_path), total_files)
        repo_id = repo["repo_id"]
    
    # Update all chunks with the actual repo_id
    for chunk in all_chunks:
        chunk["repo_id"] = repo_id
    
    # Generate embeddings and upsert in batches
    total_chunks = len(all_chunks)
    points_created = 0
    
    for i in range(0, total_chunks, BATCH_SIZE):
        batch = all_chunks[i:i + BATCH_SIZE]
        
        if progress_callback:
            progress_callback(
                i, 
                total_chunks, 
                f"Generating embeddings ({i}/{total_chunks} chunks)"
            )
        
        # Generate embeddings for batch
        texts = [c["content"] for c in batch]
        embeddings = generate_embeddings(texts)
        
        # Create points for Qdrant
        points = []
        for j, (chunk, embedding) in enumerate(zip(batch, embeddings)):
            point_id = points_created + j
            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "repo_id": chunk["repo_id"],
                    "file_path": chunk["file_path"],
                    "start_line": chunk["start_line"],
                    "end_line": chunk["end_line"],
                    "language": chunk["language"],
                    "content": chunk["content"],
                }
            ))
        
        # Upsert to Qdrant
        qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
        points_created += len(points)
    
    if progress_callback:
        progress_callback(total_chunks, total_chunks, "Indexing complete!")
    
    return {
        "repo_id": repo_id,
        "repo_name": repo_name,
        "path": str(root_path),
        "files_indexed": total_files,
        "chunks_created": points_created,
    }


def delete_repository_index(repo_id: str) -> int:
    """
    Delete all indexed chunks for a repository.
    
    Returns:
        Number of points deleted
    """
    try:
        # Get count before deletion
        result = qdrant.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=Filter(
                must=[FieldCondition(key="repo_id", match=MatchValue(value=repo_id))]
            ),
            limit=1,
            with_payload=False,
            with_vectors=False,
        )
        
        # Delete points matching repo_id
        qdrant.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[FieldCondition(key="repo_id", match=MatchValue(value=repo_id))]
            ),
        )
        
        return len(result[0]) if result[0] else 0
    except Exception:
        return 0
