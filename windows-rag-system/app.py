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
    initial_sidebar_state="expanded",
)

# Apply minimal theme
apply_theme()

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
    st.session_state.page = "documents"
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

# ============================================================
# Sidebar - Minimal Navigation
# ============================================================
with st.sidebar:
    # Logo
    st.markdown("""
    <div style="padding: 8px 0 16px 0;">
        <h2 style="color: #ffffff; margin: 0; font-size: 1.4em;">🧠 RAG System</h2>
        <p style="color: rgba(255,255,255,0.4); margin: 4px 0 0 0; font-size: 0.8em;">Local AI Document Intelligence</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<hr class='minimal-divider'>", unsafe_allow_html=True)
    
    # Navigation - Large buttons (only Documents and Reports)
    current_page = st.session_state.page
    if current_page not in ["documents", "reports"]:
        current_page = "documents"
        st.session_state.page = "documents"
        
    nav_items = [
        ("📄", "Documents", "documents"),
        ("📊", "Reports", "reports"),
    ]
    
    for icon, label, page_id in nav_items:
        active = current_page == page_id
        active_class = " active" if active else ""
        
        # Use st.button for actual navigation
        if st.button(
            f"{icon} {label}",
            key=f"nav_{page_id}",
            use_container_width=True,
            type="primary" if active else "secondary",
        ):
            st.session_state.page = page_id
            st.rerun()
    
    st.markdown("<hr class='minimal-divider'>", unsafe_allow_html=True)
    
    # Gear button for floating API settings
    from ui.api_settings import api_settings_dialog
    if st.button("⚙️ API Settings", key="nav_api_settings_btn", use_container_width=True):
        api_settings_dialog()
        
    st.markdown("<hr class='minimal-divider'>", unsafe_allow_html=True)
    
    # Minimal footer
    st.markdown("""
    <div style="color: rgba(255,255,255,0.3); font-size: 0.75em; padding: 8px 0;">
        v1.0.0 | Windows Local RAG
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# Main Content Area
# ============================================================
page = st.session_state.page

# --- DOCUMENTS PAGE ---
if page == "documents":
    st.markdown("<h1 style='color: #ffffff;'>📄 Documents</h1>", unsafe_allow_html=True)
    
    # Check if API is configured
    api_persistence = st.session_state.api_persistence
    if api_persistence and not api_persistence.is_configured():
        st.markdown("""
        <div style="padding: 16px; background: rgba(255,184,0,0.1); border: 1px solid rgba(255,184,0,0.3); border-radius: 12px; margin-bottom: 16px;">
            <h4 style="color: #ffb800; margin: 0;">⚠️ API Not Configured</h4>
            <p style="color: rgba(255,255,255,0.7); margin: 8px 0;">
                Please configure your API settings in <strong>Settings > API Configuration</strong> before using the system.
            </p>
        </div>
        """, unsafe_allow_html=True)
        st.stop()
    
    # Check if embedding model is set
    if not st.session_state.settings.get("embedding_model"):
        st.markdown("""
        <div style="padding: 16px; background: rgba(255,184,0,0.1); border: 1px solid rgba(255,184,0,0.3); border-radius: 12px; margin-bottom: 16px;">
            <h4 style="color: #ffb800; margin: 0;">⚠️ Embedding Model Not Set</h4>
            <p style="color: rgba(255,255,255,0.7); margin: 8px 0;">
                Please set an embedding model in <strong>Settings > System Settings > Embedding</strong>.
            </p>
        </div>
        """, unsafe_allow_html=True)
        st.stop()
    
    # System Status - Moved to documents page (compact)
    if st.session_state.initialized:
        doc_manager = st.session_state.doc_manager
        if doc_manager:
            status = doc_manager.get_status()
            
            st.markdown("<h3 style='color: #e4e6eb; margin-top: 0;'>System Status</h3>", unsafe_allow_html=True)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                render_compact_metric("Documents", status["document_count"])
            with col2:
                render_compact_metric("Vectors", status["vector_count"])
            with col3:
                llm_status = "Ready" if st.session_state.llm else "Not Ready"
                render_compact_metric("LLM", llm_status)
            with col4:
                folder_status = "Set" if status["selected_folder"] else "Not Set"
                render_compact_metric("Folder", folder_status)
            
            st.markdown("<br>", unsafe_allow_html=True)
    
    # Folder paths management
    st.markdown("<h3 style='color: #e4e6eb;'>📁 Folder Paths</h3>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([4, 1])
    with col1:
        new_folder_path = st.text_input(
            "Folder Path",
            placeholder="C:/Users/Documents/PDFs",
            key="folder_input",
            label_visibility="collapsed",
        )
    with col2:
        if st.button("Add Path", use_container_width=True, key="add_folder_path_btn"):
            if new_folder_path and os.path.isdir(new_folder_path):
                try:
                    if st.session_state.doc_manager is None:
                        doc_manager = DocumentManager(
                            index_path="data/metadata/doc_index.json",
                            vector_dir="data/vectors",
                            settings=st.session_state.settings,
                        )
                        st.session_state.doc_manager = doc_manager
                    st.session_state.doc_manager.add_folder(new_folder_path)
                    st.success(f"Folder added: {new_folder_path}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.error("Invalid folder path")

    # Folder list & actions
    if st.session_state.doc_manager:
        status = st.session_state.doc_manager.get_status()
        folders = status.get("selected_folders", [])
        indexed_docs = status.get("documents", [])
        
        # Actions row
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            sync_disabled = bool(not folders or (st.session_state.get("sync_task") is not None and st.session_state.sync_task.is_running))
            if st.button("🔄 Sync Folders", use_container_width=True, key="sync_folder", disabled=sync_disabled):
                from utils.background_task import BackgroundTask
                task = BackgroundTask(target=st.session_state.doc_manager.sync)
                st.session_state.sync_task = task
                task.start()
                st.toast("🔄 Sync started in background!", icon="⚡")
                st.rerun()
        
        with col2:
            reindex_disabled = bool(not folders or (st.session_state.get("reindex_task") is not None and st.session_state.reindex_task.is_running))
            if st.button("🔄 Re-index All", use_container_width=True, key="reindex_all", disabled=reindex_disabled):
                from utils.background_task import BackgroundTask
                task = BackgroundTask(target=st.session_state.doc_manager.index_all, kwargs={"force_reindex": True})
                st.session_state.reindex_task = task
                task.start()
                st.toast("🔄 Re-indexing started in background!", icon="⚡")
                st.rerun()
        
        with col3:
            if st.button("🗑️ Clear Index", use_container_width=True, key="clear_index"):
                st.session_state.doc_manager.vector_store.clear()
                st.session_state.doc_manager.documents = {}
                st.session_state.doc_manager._save_index()
                st.success("Index cleared")
                st.rerun()

        # Background Task Status Displays
        sync_task = st.session_state.sync_task
        if sync_task:
            if sync_task.is_running:
                st.info("🔄 Synchronizing folders in the background...")
                st.button("🔄 Check Sync Status", key="chk_sync_btn")
            elif sync_task.is_done:
                if sync_task.error:
                    st.error(f"❌ Synchronization failed: {sync_task.error}")
                else:
                    res = sync_task.result
                    if isinstance(res, dict) and res.get("status") == "success":
                        st.success(f"✅ Indexed {res['indexed']} chunks from {res['files']} files successfully!")
                    else:
                        st.success("✅ Synchronization complete!")
                st.session_state.sync_task = None
                st.button("Dismiss", key="dismiss_sync_btn")

        reindex_task = st.session_state.reindex_task
        if reindex_task:
            if reindex_task.is_running:
                st.info("🔄 Re-indexing files in the background...")
                st.button("🔄 Check Re-index Status", key="chk_reindex_btn")
            elif reindex_task.is_done:
                if reindex_task.error:
                    st.error(f"❌ Re-indexing failed: {reindex_task.error}")
                else:
                    st.success("✅ Re-indexing complete!")
                st.session_state.reindex_task = None
                st.button("Dismiss", key="dismiss_reindex_btn")
        
        # Display folder expander structure (Collapse files under folder path)
        if folders:
            st.markdown("<h3 style='color: #e4e6eb; margin-top: 16px;'>Folder Paths & Indexed Files</h3>", unsafe_allow_html=True)
            for f_path in folders:
                folder_docs = [d for d in indexed_docs if d["file"].startswith(f_path) and d["status"] == "indexed"]
                
                col_exp, col_del = st.columns([5, 1])
                with col_exp:
                    expander_label = f"📁 {f_path} ({len(folder_docs)} files)"
                    with st.expander(expander_label, expanded=False):
                        if folder_docs:
                            for doc in folder_docs:
                                filename = os.path.basename(doc["file"])
                                st.markdown(f"""
                                <div class="source-item" style="margin: 4px 0;">
                                    <strong>{filename}</strong>
                                    <span style="float: right; color: rgba(255,255,255,0.5);">
                                        {doc['chunks']} chunks
                                    </span>
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.caption("No files indexed in this folder yet.")
                with col_del:
                    if st.button("🗑️ Remove", key=f"del_folder_{hash(f_path)}", use_container_width=True):
                        try:
                            st.session_state.doc_manager.remove_folder(f_path)
                            st.success(f"Removed folder path: {f_path}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error removing folder: {e}")
                            
            # Other Uploaded Files (not in folders)
            other_docs = [d for d in indexed_docs if d["status"] == "indexed" and not any(d["file"].startswith(fp) for fp in folders)]
            if other_docs:
                with st.expander(f"📤 Uploaded Files ({len(other_docs)} files)", expanded=False):
                    for doc in other_docs:
                        filename = os.path.basename(doc["file"])
                        st.markdown(f"""
                        <div class="source-item" style="margin: 4px 0;">
                            <strong>{filename}</strong>
                            <span style="float: right; color: rgba(255,255,255,0.5);">
                                {doc['chunks']} chunks (uploaded)
                            </span>
                        </div>
                        """, unsafe_allow_html=True)
    
    # File upload
    st.markdown("<h3 style='color: #e4e6eb; margin-top: 24px;'>📤 Upload</h3>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "Drop PDF here",
        type=["pdf"],
        key="pdf_uploader",
        label_visibility="collapsed",
    )
    
    if uploaded_file:
        upload_dir = Path("data/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / uploaded_file.name
        
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        if st.button("Index", key="index_upload"):
            with st.spinner("Indexing..."):
                count = st.session_state.doc_manager.handle_upload(str(file_path))
                st.success(f"Indexed {count} chunks from {uploaded_file.name}")
                st.rerun()

# --- REPORT GENERATOR PAGE ---
elif page == "reports":
    if not st.session_state.initialized:
        st.markdown("""
        <div style="padding: 24px; background: rgba(255,184,0,0.1); border: 1px solid rgba(255,184,0,0.3); border-radius: 12px;">
            <h3 style="color: #ffb800; margin: 0;">⚠️ System Not Ready</h3>
            <p style="color: rgba(255,255,255,0.7); margin: 12px 0;">
                Please configure your API and embedding model in <strong>Settings</strong> before using Reports.
            </p>
        </div>
        """, unsafe_allow_html=True)
        st.stop()
    render_report_generator(st.session_state.rag_pipeline, st.session_state.llm)

# --- SETTINGS PAGE ---
elif page == "settings":
    st.markdown("<h1 style='color: #ffffff;'>⚙️ Settings</h1>", unsafe_allow_html=True)
    
    # API Configuration
    st.markdown("<h3 style='color: #e4e6eb;'>API Configuration</h3>", unsafe_allow_html=True)
    
    api_persistence = st.session_state.api_persistence
    if api_persistence:
        # --- Existing Providers ---
        all_providers = api_persistence.get_providers()
        current_provider, current_model = api_persistence.get_default()
        
        if all_providers:
            selected_provider = st.selectbox(
                "Existing Provider",
                options=list(all_providers.keys()),
                index=list(all_providers.keys()).index(current_provider) if current_provider in all_providers else 0,
                key="provider_select",
            )
            provider_config = api_persistence.get_provider_config(selected_provider)
            is_new = False
        else:
            st.markdown("<p style='color: rgba(255,255,255,0.5);'>No providers configured yet.</p>", unsafe_allow_html=True)
            selected_provider = ""
            provider_config = {}
            is_new = True
        
        st.markdown("<hr class='minimal-divider'>", unsafe_allow_html=True)
        
        # --- Provider Form (Edit existing or Add new) ---
        st.markdown("<h4 style='color: #e4e6eb;'>Provider Details</h4>", unsafe_allow_html=True)
        
        provider_name = st.text_input(
            "Provider Name",
            value=selected_provider if not is_new else "",
            placeholder="e.g., openai, my-api",
            key="provider_name_input",
        )
        
        base_url = st.text_input(
            "Base URL",
            value=provider_config.get("base_url", ""),
            placeholder="https://api.example.com/v1",
            key="base_url_input",
        )
        
        api_key = st.text_input(
            "API Key",
            value=provider_config.get("api_key", ""),
            type="password",
            placeholder="sk-...",
            key="api_key_input",
        )
        
        models_text = st.text_area(
            "Models (one per line)",
            value="\n".join(provider_config.get("models", [])) if provider_config.get("models") else "",
            placeholder="gpt-4o\ngpt-4o-mini",
            key="models_input",
            height=80,
        )
        models_list = [m.strip() for m in models_text.split("\n") if m.strip()]
        
        if models_list:
            selected_model = st.selectbox(
                "Default Model",
                options=models_list,
                index=models_list.index(current_model) if current_model in models_list else 0,
                key="model_select",
            )
        else:
            selected_model = st.text_input(
                "Default Model",
                value=current_model,
                key="model_select_text",
            )
        
        # Actions
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            if st.button("💾 Save", use_container_width=True, key="save_api_config"):
                if not provider_name:
                    st.error("Provider name required")
                elif not base_url:
                    st.error("Base URL required")
                elif not models_list:
                    st.error("At least one model required")
                else:
                    try:
                        api_persistence.update_provider_config(
                            provider=provider_name,
                            api_key=api_key,
                            base_url=base_url,
                            models=models_list,
                            description="",
                        )
                        api_persistence.update_provider(provider_name, selected_model)
                        
                        # CRITICAL: Reinitialize all LLM components to use new API key
                        if reinitialize_llm_components():
                            st.session_state.save_message = f"✅ API configuration saved for {provider_name}"
                            st.session_state.save_message_type = "success"
                            st.toast(f"✅ Saved {provider_name}!", icon="🎉")
                        st.rerun()
                    except Exception as e:
                        st.session_state.save_message = f"❌ Failed to save: {e}"
                        st.session_state.save_message_type = "error"
                        st.rerun()
        
        with col2:
            if st.button("🔄 Reload", use_container_width=True, key="reinit_llm"):
                if reinitialize_llm_components():
                    st.session_state.save_message = "✅ LLM reloaded successfully"
                    st.session_state.save_message_type = "success"
                    st.toast("✅ LLM reloaded!", icon="🔄")
                st.rerun()
        
        with col3:
            confirm_key = "confirm_reset_api"
            if confirm_key not in st.session_state:
                st.session_state[confirm_key] = False

            if st.button("🗑️ Reset" if not st.session_state[confirm_key] else "⚠️ Confirm Reset",
                        use_container_width=True, key="reset_api_config"):
                if not st.session_state[confirm_key]:
                    st.session_state[confirm_key] = True
                    st.warning("Click again to confirm: this will delete ALL API configurations.")
                    st.rerun()
                else:
                    api_persistence.reset_to_defaults()
                    st.session_state[confirm_key] = False
                    if reinitialize_llm_components():
                        st.session_state.save_message = "✅ Configuration reset"
                        st.session_state.save_message_type = "success"
                        st.toast("✅ Reset!", icon="🗑️")
                    st.rerun()
        
        # Persistent save message
        if st.session_state.save_message:
            msg_color = {
                "success": "#00cc6a",
                "error": "#ff4343",
                "warning": "#ffb800",
            }.get(st.session_state.save_message_type, "#00cc6a")
            st.markdown(f"""
            <div style="padding: 10px 14px; background: rgba(255,255,255,0.03); border-left: 3px solid {msg_color}; border-radius: 0 8px 8px 0; margin: 8px 0;">
                <span style="color: {msg_color}; font-weight: 500;">{st.session_state.save_message}</span>
            </div>
            """, unsafe_allow_html=True)
            if st.button("✕ Dismiss", key="dismiss_save_msg", type="secondary"):
                st.session_state.save_message = ""
                st.session_state.save_message_type = ""
                st.rerun()
        
        # Validation
        st.markdown("<h4 style='color: #e4e6eb; margin-top: 16px;'>Status</h4>", unsafe_allow_html=True)
        validation = api_persistence.validate()
        
        for provider_name, pconf in all_providers.items():
            valid = validation.get(provider_name, False)
            status = "ready" if valid else "error"
            label = "✅" if valid else "❌"
            render_status_bar(provider_name, f"{label} {provider_name}", status)
    
    # System Settings
    st.markdown("---")
    st.markdown("<h3 style='color: #e4e6eb;'>System Settings</h3>", unsafe_allow_html=True)
    
    with st.expander("Retrieval & Embedding"):
        # --- Embedding Settings ---
        st.markdown("<h4 style='color: #ffffff; margin-top: 0;'>🔤 Embedding</h4>", unsafe_allow_html=True)
        
        emb_provider = st.text_input(
            "Embedding Provider",
            value=settings.get("embedding_provider", ""),
            placeholder="openai",
            key="emb_provider_select",
        )
        
        emb_model = st.text_input(
            "Embedding Model",
            value=settings.get("embedding_model", ""),
            placeholder="text-embedding-3-small",
            key="emb_model_select",
            help="Changing embedding model requires clearing index and re-syncing",
        )
        
        st.markdown("<hr class='minimal-divider'>", unsafe_allow_html=True)
        
        # --- Retrieval Settings ---
        st.markdown("<h4 style='color: #ffffff; margin-top: 0;'>🔍 Retrieval</h4>", unsafe_allow_html=True)
        
        chunk_size = st.slider("Chunk Size", 100, 2000, settings.get("chunk_size", 800), 50)
        chunk_overlap = st.slider("Chunk Overlap", 0, 500, settings.get("chunk_overlap", 100), 10)
        top_k = st.slider("Top K", 1, 20, settings.get("top_k", 5), 1)
        
        st.markdown("<hr class='minimal-divider'>", unsafe_allow_html=True)
        
        # --- Rerank Settings ---
        st.markdown("<h4 style='color: #ffffff; margin-top: 0;'>📊 Rerank</h4>", unsafe_allow_html=True)
        
        rerank_enabled = st.toggle(
            "Enable Reranking",
            value=settings.get("rerank_enabled", False),
            key="rerank_enabled",
            help="Use LLM to rerank retrieved documents for better relevance",
        )
        
        if rerank_enabled:
            rerank_model = st.text_input(
                "Rerank Model",
                value=settings.get("rerank_model", ""),
                placeholder="gpt-4o-mini",
                key="rerank_model_select",
            )
            
            rerank_top_k = st.slider(
                "Rerank Top K",
                1,
                50,
                settings.get("rerank_top_k", 10),
                1,
                key="rerank_top_k",
                help="Number of documents to retrieve before reranking",
            )
        
        # Warning if embedding model changed
        model_changed = emb_model != settings.get("embedding_model")
        if model_changed:
            st.warning("⚠️ Embedding model changed! You MUST clear index and re-sync documents.")
        
        if st.button("💾 Save Settings", use_container_width=True, key="save_settings_btn"):
            settings["chunk_size"] = chunk_size
            settings["chunk_overlap"] = chunk_overlap
            settings["top_k"] = top_k
            settings["embedding_provider"] = emb_provider
            settings["embedding_model"] = emb_model
            settings["rerank_enabled"] = rerank_enabled
            if rerank_enabled:
                settings["rerank_model"] = rerank_model
                settings["rerank_top_k"] = rerank_top_k
            else:
                settings["rerank_enabled"] = False
            
            from utils.file_io import write_json
            write_json("config/settings.json", settings)
            
            # Reinitialize with new settings
            if reinitialize_llm_components():
                st.session_state.save_message = "✅ Settings saved successfully"
                st.session_state.save_message_type = "success"
                st.toast("✅ Settings saved!", icon="🎉")
            st.rerun()
    
    # About
    st.markdown("---")
    st.markdown("""
    <div style="color: rgba(255,255,255,0.4); font-size: 0.85em;">
        <strong>Windows Local RAG System</strong> v1.0.0<br>
        Streamlit + FAISS + API Embeddings
    </div>
    """, unsafe_allow_html=True)
