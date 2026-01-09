"""
Repository Registry - Manages indexed repository metadata.
Stores data in a local JSON file.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

REGISTRY_FILE = Path(__file__).parent / "registry.json"


def load_registry() -> list[dict]:
    """Load the registry from JSON file."""
    if not REGISTRY_FILE.exists():
        return []
    with open(REGISTRY_FILE, "r") as f:
        return json.load(f)


def save_registry(repos: list[dict]) -> None:
    """Save the registry to JSON file."""
    with open(REGISTRY_FILE, "w") as f:
        json.dump(repos, f, indent=2)


def add_repo(name: str, path: str, file_count: int) -> dict:
    """Add a new repository to the registry."""
    repos = load_registry()
    repo = {
        "repo_id": str(uuid.uuid4()),
        "name": name,
        "path": path,
        "indexed_at": datetime.now().isoformat(),
        "file_count": file_count
    }
    repos.append(repo)
    save_registry(repos)
    return repo


def get_all_repos() -> list[dict]:
    """Get all indexed repositories."""
    return load_registry()


def repo_exists(path: str) -> Optional[dict]:
    """Check if a repository path is already indexed."""
    repos = load_registry()
    for repo in repos:
        if repo["path"] == path:
            return repo
    return None


def get_repo_by_id(repo_id: str) -> Optional[dict]:
    """Get a repository by its ID."""
    repos = load_registry()
    for repo in repos:
        if repo["repo_id"] == repo_id:
            return repo
    return None


def update_repo(repo_id: str, file_count: int) -> Optional[dict]:
    """Update an existing repository entry (for re-indexing)."""
    repos = load_registry()
    for repo in repos:
        if repo["repo_id"] == repo_id:
            repo["indexed_at"] = datetime.now().isoformat()
            repo["file_count"] = file_count
            save_registry(repos)
            return repo
    return None


def remove_repo(repo_id: str) -> bool:
    """Remove a repository from the registry."""
    repos = load_registry()
    updated = [r for r in repos if r["repo_id"] != repo_id]
    if len(updated) < len(repos):
        save_registry(updated)
        return True
    return False
