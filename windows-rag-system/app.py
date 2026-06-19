"""Windows Local RAG System - Streamlit Entry Point (Minimal UI)."""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import streamlit as st

from ui.theme import apply_theme, render_card, render_compact_metric, render_status_bar
from ui.report_generator import render_report_generator

from core.document_manager import DocumentManager
from core.api_persistence import APIPersistence
from core.embedder import APIEmbedder
from core.retriever import DocumentRetriever
from core.rag_pipeline import RAGPipeline
from core.reranker import Reranker
from llm.gateway import LLMGateway

from vectorstore.faiss_store import FAISSStore
from utils.file_io import read_json
from utils.logger import setup_logger

logger = setup_logger("app")


def _get_provider_config(api_persistence, provider_name):
    """Get provider base_url and api_key by name from api_persistence."""
    providers = api_persistence.get_providers()
    pconf = providers.get(provider_name, {})
    return pconf.get("base_url", ""), pconf.get("api_key", "")


def _find_provider_by_model(api_persistence, model_name):
    """Find which provider has the given model in its model list."""
    providers = api_persistence.get_providers()
    for name, pconf in providers.items():
        if model_name in pconf.get("models", []):
            return name, pconf
    return None, {}


# ============================================================
# Page Configuration
# ============================================================
st.set_page_config(
    page_title="RAG System",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Apply minimal theme
if "is_dark" not in st.session_state:
    st.session_state.is_dark = True
apply_theme(st.session_state.is_dark)

# ============================================================
# Initialize Session State
# ============================================================
if "initialized" not in st.session_state:
    st.session_state.initialized = False
    st.session_state.doc_manager = None
    st.session_state.rag_pipeline = None
    st.session_state.llm = None
    st.session_state.api_persistence = None
    st.session_state.settings = {}
    st.session_state.indexing_status = ""
    st.session_state.page = "reports"
    st.session_state.save_message = ""
    st.session_state.save_message_type = ""  # 'success', 'error', 'warning'
    st.session_state.reranker = None
    st.session_state.needs_reinit = False
    st.session_state.sync_task = None
    st.session_state.reindex_task = None

# ============================================================
# Load Configuration
# ============================================================
@st.cache_resource
def load_settings():
    """Load application settings."""
    return read_json("config/settings.json")

settings = load_settings()
st.session_state.settings = settings

# ============================================================
# Initialize System Components
# ============================================================
def initialize_system():
    """Initialize all system components."""
    if st.session_state.initialized:
        return

    # Always initialize API persistence first
    api_persistence = APIPersistence()
    st.session_state.api_persistence = api_persistence

    # Always initialize document manager (no LLM/embedder needed for folder ops)
    if st.session_state.doc_manager is None:
        doc_manager = DocumentManager(
            index_path="data/metadata/doc_index.json",
            vector_dir="data/vectors",
            settings=st.session_state.settings,
        )
        st.session_state.doc_manager = doc_manager

    # Check if API is configured
    if not api_persistence.is_configured():
        logger.info("API not configured. Skipping LLM initialization.")
        st.session_state.initialized = False
        return

    # Check if embedding model is set
    embedding_model = st.session_state.settings.get("embedding_model", "")
    if not embedding_model:
        logger.info("Embedding model not configured. Skipping system initialization.")
        st.session_state.initialized = False
        return

    try:
        # Initialize LLM for chat (uses default provider from api_keys.local.json)
        llm = LLMGateway(
            config_path="config/api_keys.local.json",
            fallback_path="config/api_keys.json",
        )
        st.session_state.llm = llm

        # Initialize embedder with embedding provider's OWN config
        embed_provider_name = st.session_state.settings.get("embedding_provider", "")
        embed_base_url, embed_api_key = _get_provider_config(api_persistence, embed_provider_name)

        embedder = APIEmbedder(
            model_name=embedding_model,
            base_url=embed_base_url,
            api_key=embed_api_key,
        )

        # Initialize vector store
        vector_store = FAISSStore(
            dimension=embedder.dimension,
            index_path="data/vectors/faiss.index",
            metadata_path="data/vectors/metadata.pkl",
        )
        vector_store.load()

        # Bind stores to document manager
        st.session_state.doc_manager.initialize_stores(embedder, vector_store)

        # Initialize retriever and pipeline
        retriever = DocumentRetriever(
            vector_store=vector_store,
            embedder=embedder,
            top_k=st.session_state.settings.get("top_k", 5),
        )
        rag_pipeline = RAGPipeline(retriever=retriever, llm_gateway=llm)
        st.session_state.rag_pipeline = rag_pipeline

        # Initialize reranker with reranker provider's OWN config
        if st.session_state.settings.get("rerank_enabled", False):
            rerank_model = st.session_state.settings.get("rerank_model", "")
            _, rerank_pconf = _find_provider_by_model(api_persistence, rerank_model)
            if rerank_pconf:
                reranker = Reranker(
                    model=rerank_model,
                    base_url=rerank_pconf.get("base_url", ""),
                    api_key=rerank_pconf.get("api_key", ""),
                )
                st.session_state.reranker = reranker
                retriever.update_reranker(reranker)

        st.session_state.initialized = True
        logger.info("System initialized successfully")

    except Exception as e:
        logger.error(f"Initialization error: {e}")
        st.session_state.initialized = False
        st.error(f"System initialization failed: {e}")


def reinitialize_llm_components():
    """Reinitialize LLM, embedder, retriever, and pipeline after API config change.

    Each component uses its own provider config:
    - LLM (chat) → default provider (deepseek-v4)
    - Embedder → embedding provider (讯飞)
    - Reranker → reranker provider (魔力)
    """
    api_persistence = st.session_state.api_persistence
    if not api_persistence or not api_persistence.is_configured():
        st.session_state.save_message = "⚠️ API not configured. Please configure API first."
        st.session_state.save_message_type = "warning"
        return False

    embedding_model = st.session_state.settings.get("embedding_model", "")
    if not embedding_model:
        st.session_state.save_message = "⚠️ Embedding model not configured. Please set it in Settings > System Settings."
        st.session_state.save_message_type = "warning"
        return False

    try:
        # Create new LLM gateway (reads fresh config from api_keys.local.json)
        llm = LLMGateway(
            config_path="config/api_keys.local.json",
            fallback_path="config/api_keys.json",
        )
        st.session_state.llm = llm

        # Create new embedder with embedding provider's OWN config
        embed_provider_name = st.session_state.settings.get("embedding_provider", "")
        embed_base_url, embed_api_key = _get_provider_config(api_persistence, embed_provider_name)

        embedder = APIEmbedder(
            model_name=embedding_model,
            base_url=embed_base_url,
            api_key=embed_api_key,
        )

        # Ensure vector store has the correct dimension
        vector_store = FAISSStore(
            dimension=embedder.dimension,
            index_path="data/vectors/faiss.index",
            metadata_path="data/vectors/metadata.pkl",
        )
        vector_store.load()

        # Update document manager embedder
        if st.session_state.doc_manager:
            st.session_state.doc_manager.embedder = embedder
            st.session_state.doc_manager.vector_store = vector_store

        # Create or update retriever
        if st.session_state.rag_pipeline and st.session_state.rag_pipeline.retriever:
            st.session_state.rag_pipeline.retriever.update_embedder(embedder)
            st.session_state.rag_pipeline.retriever.vector_store = vector_store
        else:
            from core.retriever import DocumentRetriever
            retriever = DocumentRetriever(
                vector_store=vector_store,
                embedder=embedder,
                top_k=st.session_state.settings.get("top_k", 5),
            )
            rag_pipeline = RAGPipeline(retriever=retriever, llm_gateway=llm)
            st.session_state.rag_pipeline = rag_pipeline

        # Update reranker with reranker provider's OWN config
        if st.session_state.settings.get("rerank_enabled", False):
            rerank_model = st.session_state.settings.get("rerank_model", "")
            _, rerank_pconf = _find_provider_by_model(api_persistence, rerank_model)
            if rerank_pconf:
                reranker = Reranker(
                    model=rerank_model,
                    base_url=rerank_pconf.get("base_url", ""),
                    api_key=rerank_pconf.get("api_key", ""),
                )
                st.session_state.reranker = reranker
                if st.session_state.rag_pipeline and st.session_state.rag_pipeline.retriever:
                    st.session_state.rag_pipeline.retriever.update_reranker(reranker)
        else:
            st.session_state.reranker = None
            if st.session_state.rag_pipeline and st.session_state.rag_pipeline.retriever:
                st.session_state.rag_pipeline.retriever.update_reranker(None)

        # Update pipeline LLM
        if st.session_state.rag_pipeline:
            st.session_state.rag_pipeline.llm = llm

        st.session_state.initialized = True
        logger.info("LLM components reinitialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to reinitialize LLM components: {e}")
        st.session_state.save_message = f"❌ Failed to reinitialize: {e}"
        st.session_state.save_message_type = "error"
        st.session_state.initialized = False
        return False

# Initialize on first run
if not st.session_state.initialized:
    initialize_system()

# Check and apply API/model re-initialization if requested from floating settings dialog
if getattr(st.session_state, "needs_reinit", False):
    reinitialize_llm_components()
    st.session_state.needs_reinit = False

# (Sidebar removed - controls moved to main Reports header)

# ============================================================
# Main Content Area (Reports & Copilot is the single main view)
# ============================================================
render_report_generator(st.session_state.rag_pipeline, st.session_state.llm)
