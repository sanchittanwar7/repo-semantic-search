"""
Code Chunker - Intelligent code splitting that respects function/class boundaries.
Uses a recursive character splitter optimized for code.
"""
from pathlib import Path
from typing import Generator

# Supported file extensions and their languages
SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".cs": "csharp",
}

# Directories to ignore during indexing
IGNORE_DIRS = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "target",
    "vendor",
    ".idea",
    ".vscode",
    "coverage",
    ".tox",
    "eggs",
    "*.egg-info",
}

# Code-aware separators for chunking (order matters - most specific first)
CODE_SEPARATORS = [
    "\nclass ",       # Class definitions
    "\ndef ",         # Python functions
    "\nasync def ",   # Python async functions
    "\nfunction ",    # JS/TS functions
    "\nexport ",      # JS/TS exports
    "\nconst ",       # JS/TS constants
    "\nlet ",         # JS/TS variables
    "\nvar ",         # JS variables
    "\npublic ",      # Java/C# methods
    "\nprivate ",     # Java/C# methods
    "\nprotected ",   # Java/C# methods
    "\nfunc ",        # Go functions
    "\nfn ",          # Rust functions
    "\nimpl ",        # Rust implementations
    "\n\n",           # Paragraph breaks
    "\n",             # Line breaks
]

# Chunk size configuration
MAX_CHUNK_SIZE = 1500  # Characters
CHUNK_OVERLAP = 200    # Characters


def get_supported_extensions() -> set[str]:
    """Return the set of supported file extensions."""
    return set(SUPPORTED_EXTENSIONS.keys())


def should_ignore_path(path: Path) -> bool:
    """Check if a path should be ignored during indexing."""
    for part in path.parts:
        if part in IGNORE_DIRS or part.endswith(".egg-info"):
            return True
    return False


def detect_language(file_path: Path) -> str:
    """Detect the programming language based on file extension."""
    return SUPPORTED_EXTENSIONS.get(file_path.suffix.lower(), "text")


def split_text(text: str, separators: list[str], max_size: int) -> list[str]:
    """
    Recursively split text using separators, respecting max chunk size.
    Tries each separator in order until chunks are small enough.
    """
    if len(text) <= max_size:
        return [text] if text.strip() else []
    
    # Try each separator
    for sep in separators:
        if sep in text:
            parts = text.split(sep)
            chunks = []
            current = ""
            
            for i, part in enumerate(parts):
                # Add separator back (except for first part)
                piece = (sep + part) if i > 0 else part
                
                if len(current) + len(piece) <= max_size:
                    current += piece
                else:
                    if current.strip():
                        chunks.append(current)
                    current = piece
            
            if current.strip():
                chunks.append(current)
            
            # Recursively split any chunks that are still too large
            result = []
            remaining_seps = separators[separators.index(sep) + 1:]
            for chunk in chunks:
                if len(chunk) > max_size and remaining_seps:
                    result.extend(split_text(chunk, remaining_seps, max_size))
                else:
                    result.append(chunk)
            
            return result
    
    # Fallback: hard split by max_size
    return [text[i:i + max_size] for i in range(0, len(text), max_size)]


def chunk_file(file_path: Path) -> Generator[dict, None, None]:
    """
    Parse a file and extract meaningful chunks.
    
    Yields dictionaries with:
        - content: The chunk text
        - file_path: Absolute path to the file
        - start_line: Starting line number (1-indexed)
        - end_line: Ending line number (1-indexed)
        - language: Detected programming language
    """
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return
    
    if not content.strip():
        return
    
    language = detect_language(file_path)
    lines = content.split("\n")
    
    # Split into chunks
    chunks = split_text(content, CODE_SEPARATORS, MAX_CHUNK_SIZE)
    
    # Track line positions
    current_pos = 0
    
    for chunk in chunks:
        if not chunk.strip():
            continue
        
        # Find line numbers for this chunk
        chunk_start = content.find(chunk, current_pos)
        if chunk_start == -1:
            chunk_start = current_pos
        
        start_line = content[:chunk_start].count("\n") + 1
        end_line = start_line + chunk.count("\n")
        
        current_pos = chunk_start + len(chunk)
        
        yield {
            "content": chunk.strip(),
            "file_path": str(file_path.absolute()),
            "start_line": start_line,
            "end_line": end_line,
            "language": language,
        }


def get_files_to_index(root_path: Path) -> Generator[Path, None, None]:
    """
    Walk a directory and yield all indexable files.
    Ignores standard junk directories and unsupported file types.
    """
    supported = get_supported_extensions()
    
    for path in root_path.rglob("*"):
        if path.is_file() and path.suffix.lower() in supported:
            if not should_ignore_path(path):
                yield path
