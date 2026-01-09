"""
Codebase Semantic Search - Streamlit Application
"""
import streamlit as st
from pathlib import Path

from registry import get_all_repos, repo_exists, get_repo_by_id
from indexer import index_repository
from searcher import search, get_stats

# Page config
st.set_page_config(
    page_title="Codebase Semantic Search",
    page_icon="🔍",
    layout="wide",
)

# Custom CSS for better code display
st.markdown("""
<style>
    .stCodeBlock {
        max-height: 400px;
        overflow-y: auto;
    }
    .result-header {
        background-color: #1e1e1e;
        padding: 8px 12px;
        border-radius: 4px 4px 0 0;
        margin-bottom: 0;
    }
    .file-path {
        color: #569cd6;
        font-family: monospace;
    }
    .line-numbers {
        color: #808080;
        font-size: 0.9em;
    }
    .score-badge {
        background-color: #2d5a27;
        color: white;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.8em;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar navigation
st.sidebar.title("🔍 Codebase Search")
page = st.sidebar.radio("Navigation", ["Search Existing", "Index New Repo"], index=0)

# Get indexed repos
repos = get_all_repos()

if page == "Search Existing":
    st.title("🔎 Search Your Codebase")
    
    if not repos:
        st.warning("No repositories indexed yet. Go to 'Index New Repo' to add one.")
    else:
        # Repository selector
        repo_options = {f"{r['name']} ({r['path']})": r['repo_id'] for r in repos}
        selected_display = st.selectbox(
            "Select Repository",
            options=list(repo_options.keys()),
            help="Choose which repository to search in"
        )
        selected_repo_id = repo_options[selected_display]
        
        # Show repo stats
        selected_repo = get_repo_by_id(selected_repo_id)
        if selected_repo:
            stats = get_stats(selected_repo_id)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Files Indexed", selected_repo.get('file_count', 0))
            with col2:
                st.metric("Code Chunks", stats.get('chunk_count', 0))
            with col3:
                st.metric("Last Indexed", selected_repo.get('indexed_at', 'N/A')[:10])
        
        st.divider()
        
        # Search input
        query = st.text_input(
            "🔍 Enter your search query",
            placeholder="e.g., function that handles user authentication",
            help="Use natural language to describe the code you're looking for"
        )
        
        col1, col2 = st.columns([3, 1])
        with col2:
            top_k = st.slider("Results", min_value=1, max_value=20, value=5)
        
        if query:
            with st.spinner("Searching..."):
                try:
                    results = search(query, selected_repo_id, top_k=top_k)
                    
                    if not results:
                        st.info("No results found. Try a different query.")
                    else:
                        st.success(f"Found {len(results)} results")
                        
                        for i, result in enumerate(results, 1):
                            file_path = result['file_path']
                            filename = Path(file_path).name
                            rel_path = file_path
                            
                            # Result header
                            score_pct = int(result['score'] * 100)
                            st.markdown(f"""
                            **{i}. {filename}** `Lines {result['start_line']}-{result['end_line']}`
                            <span style='float: right; background-color: #2d5a27; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.8em;'>{score_pct}% match</span>
                            
                            <small style='color: #808080;'>{rel_path}</small>
                            """, unsafe_allow_html=True)
                            
                            # Code block with syntax highlighting
                            st.code(result['code_snippet'], language=result['language'])
                            st.divider()
                            
                except Exception as e:
                    st.error(f"Search failed: {str(e)}")
                    st.info("Make sure Qdrant is running: `docker run -p 6333:6333 qdrant/qdrant`")

elif page == "Index New Repo":
    st.title("📁 Index a New Repository")
    
    # Show existing repos
    if repos:
        st.subheader("Previously Indexed Repositories")
        for repo in repos:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{repo['name']}**")
                st.caption(repo['path'])
            with col2:
                st.write(f"{repo['file_count']} files")
            with col3:
                st.caption(repo['indexed_at'][:10])
        st.divider()
    
    # New repo form
    st.subheader("Add New Repository")
    
    repo_path = st.text_input(
        "Repository Path",
        placeholder="/path/to/your/repository",
        help="Enter the absolute path to the repository you want to index"
    )
    
    force_reindex = False
    existing_repo = None
    
    if repo_path:
        path = Path(repo_path).resolve()
        existing_repo = repo_exists(str(path))
        
        if existing_repo:
            st.warning(f"⚠️ This repository was already indexed on {existing_repo['indexed_at'][:10]}")
            force_reindex = st.checkbox("Re-index repository (overwrites existing data)")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        start_button = st.button(
            "🚀 Start Indexing",
            type="primary",
            disabled=not repo_path
        )
    
    if start_button and repo_path:
        path = Path(repo_path).resolve()
        
        if not path.exists():
            st.error(f"❌ Path does not exist: {repo_path}")
        elif not path.is_dir():
            st.error(f"❌ Path is not a directory: {repo_path}")
        elif existing_repo and not force_reindex:
            st.error("❌ Repository already indexed. Check 'Re-index' to overwrite.")
        else:
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(current: int, total: int, message: str):
                if total > 0:
                    progress_bar.progress(current / total)
                status_text.text(message)
            
            try:
                with st.spinner("Indexing repository..."):
                    result = index_repository(
                        str(path),
                        progress_callback=update_progress,
                        force_reindex=force_reindex
                    )
                
                progress_bar.progress(1.0)
                st.success(f"""
                ✅ **Indexing Complete!**
                
                - **Repository:** {result['repo_name']}
                - **Files Indexed:** {result['files_indexed']}
                - **Code Chunks Created:** {result['chunks_created']}
                
                Switch to the **Search Existing** tab to start searching!
                """)
                
                # Force refresh of repos list
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Indexing failed: {str(e)}")
                st.info("""
                **Troubleshooting:**
                1. Make sure Qdrant is running: `docker run -p 6333:6333 qdrant/qdrant`
                2. Ensure OPENAI_API_KEY environment variable is set
                3. Check that the path contains supported code files (.py, .js, .ts, etc.)
                """)

# Footer
st.sidebar.divider()
st.sidebar.caption("Built with Streamlit + Qdrant + OpenAI")
