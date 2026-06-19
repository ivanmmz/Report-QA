"""Floating API & Document Settings dialog UI for Windows RAG System."""
import os
import streamlit as st
from pathlib import Path
from utils.file_io import write_json
from utils.background_task import BackgroundTask
from utils.paths import (
    DOC_INDEX_PATH,
    VECTOR_DIR,
    UPLOADS_DIR,
    SETTINGS_PATH,
)
from core.document_manager import DocumentManager


# ---------------------------------------------------------------------------
# CSS: compact settings dialog — targets Streamlit buttons by data-testid key
# ---------------------------------------------------------------------------
def _inject_css() -> None:
    is_dark = st.session_state.get("is_dark", True)
    if is_dark:
        modal_bg = "rgba(255,255,255,0.05)"
        modal_border = "rgba(255,255,255,0.08)"
        text0 = "#e0e0e0"
        text2 = "#888"
        hover_bg = "rgba(255,255,255,0.05)"
        prov_card_bg = "rgba(128,128,128,0.06)"
    else:
        modal_bg = "#f0f0f0"
        modal_border = "rgba(0,0,0,0.1)"
        text0 = "#1a1a2e"
        text2 = "rgba(0,0,0,0.4)"
        hover_bg = "rgba(0,0,0,0.04)"
        prov_card_bg = "rgba(0,0,0,0.04)"

    accent = "#0066cc" if not is_dark else "#4f8bea"

    css = f"""
    <style>
    /* ── Every button inside the settings dialog: compact ghost style ── */
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) button[kind="secondary"],
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) button[kind="primary"] {{
        padding: 4px 14px !important;
        font-size: 0.80rem !important;
        min-height: 30px !important;
        height: 30px !important;
        border-radius: 7px !important;
        font-weight: 500 !important;
        letter-spacing: 0.01em !important;
    }}

    /* Default: ghost / outlined */
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) button[kind="secondary"] {{
        background: transparent !important;
        border: 1px solid rgba(128,128,128,0.30) !important;
        color: {text0} !important;
        width: auto !important;
        max-width: fit-content !important;
    }}
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) button[kind="secondary"]:hover {{
        background: {hover_bg} !important;
        border-color: rgba(128,128,128,0.50) !important;
    }}

    /* Destructive buttons: Red-tinted ghost */
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-dlg_clear_index"] button,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-dlg_del_folder"] button,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-delete_prov_btn"] button {{
        color: #e05555 !important;
        border-color: rgba(224,85,85,0.35) !important;
        background: transparent !important;
    }}
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-dlg_clear_index"] button:hover,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-dlg_del_folder"] button:hover,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-delete_prov_btn"] button:hover {{
        background: rgba(224,85,85,0.08) !important;
    }}

    /* Save / primary action buttons: small accent pill */
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-save_chat_settings_btn"] button,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-save_emb_settings_btn"] button,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-save_rerank_settings_btn"] button,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-save_edit_prov_btn"] button,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-add_prov_btn"] button,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-dlg_add_folder_path_btn"] button {{
        background: {accent} !important;
        border: none !important;
        color: #fff !important;
        width: auto !important;
        max-width: fit-content !important;
    }}
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-save_chat_settings_btn"] button:hover,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-save_emb_settings_btn"] button:hover,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-save_rerank_settings_btn"] button:hover,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-save_edit_prov_btn"] button:hover,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-add_prov_btn"] button:hover,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-dlg_add_folder_path_btn"] button:hover {{
        opacity: 0.85 !important;
    }}

    /* Override use_container_width on action buttons — keep them auto-width */
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-dlg_sync_folder"] button,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-dlg_reindex_all"] button,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-dlg_clear_index"] button,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) div[class*="st-key-dlg_del_folder"] button {{
        width: 100% !important;
    }}

    /* ── Status row ── */
    .dlg-status-row {{
        display: flex;
        gap: 0;
        align-items: stretch;
        padding: 10px 0 14px;
    }}
    .dlg-stat {{
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
        padding: 0 18px;
        border-right: 1px solid rgba(128,128,128,0.18);
    }}
    .dlg-stat:first-child {{ padding-left: 0; }}
    .dlg-stat:last-child {{ border-right: none; }}
    .dlg-stat-val {{
        font-size: 1.05rem;
        font-weight: 700;
        color: {text0};
        line-height: 1.2;
    }}
    .dlg-stat-lbl {{
        font-size: 0.72rem;
        color: {text2};
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}

    /* ── Section label ── */
    .dlg-section-label {{
        font-size: 0.70rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: {text2};
        margin: 14px 0 5px;
    }}

    /* ── Provider card ── */
    .dlg-prov-card {{
        padding: 8px 12px;
        border-radius: 8px;
        background: {prov_card_bg};
        border-left: 3px solid #888;
        margin: 5px 0;
        font-size: 0.82rem;
    }}
    .dlg-prov-card.ok {{ border-left-color: #3ecf8e; }}
    .dlg-prov-card.err {{ border-left-color: #e05555; }}
    .dlg-prov-name {{ font-weight: 600; color: {text0}; }}
    .dlg-prov-meta {{ color: {text2}; margin-top: 2px; font-size: 0.78rem; }}

    /* ── Tighten spacing inside modal ── */
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) .stMarkdown p {{ margin: 0; }}
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) .stNumberInput {{ margin-bottom: 4px; }}
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) .stSelectbox  {{ margin-bottom: 4px; }}
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) .stTextInput  {{ margin-bottom: 4px; }}
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) hr {{ margin: 10px 0 !important; }}

    /* ── File uploader in dialog: compact style ── */
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) [data-testid="stFileUploader"] > label,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) [data-testid="stFileUploader"] > section > label {{
        display: none !important;
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
    }}
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) [data-testid="stFileUploader"] > section,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) [data-testid="stFileUploader"] > div {{
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
    }}
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) [data-testid="stFileUploader"] button,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) [data-testid="stFileUploader"] button[data-testid="stBaseButton-secondary"],
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) [data-testid="stFileUploader"] button[class*="st-emotion-cache"] {{
        background: {accent} !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 6px 16px !important;
        font-weight: 500 !important;
    }}
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) [data-testid="stFileUploader"] button:hover,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) [data-testid="stFileUploader"] button[data-testid="stBaseButton-secondary"]:hover,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) [data-testid="stFileUploader"] button[class*="st-emotion-cache"]:hover {{
        opacity: 0.85 !important;
    }}
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) [data-testid="stFileUploader"] small,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) [data-testid="stFileUploader"] span,
    :is(div[data-testid="stDialog"], div[data-testid="stModal"]) [data-testid="stFileUploader"] div[class*="st-emotion-cache"] {{
        color: {text2} !important;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def _section(text: str) -> None:
    """Render a muted uppercase section label."""
    st.markdown(f'<p class="dlg-section-label">{text}</p>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Document Settings
# ---------------------------------------------------------------------------
def render_document_settings_in_dialog() -> None:
    """Renders the document folder, indexing, and uploads management inside the settings dialog."""
    _inject_css()

    # Check if API is configured
    api_persistence = st.session_state.api_persistence
    if api_persistence and not api_persistence.is_configured():
        warning_text_color = "#d4900a" if not st.session_state.is_dark else "#ffb800"
        st.markdown(f"""
        <div style="padding:10px 14px;background:rgba(255,184,0,0.08);border:1px solid rgba(255,184,0,0.28);
             border-radius:8px;margin-bottom:10px">
            <span style="color:{warning_text_color};font-weight:600;font-size:0.84rem">⚠️ API Not Configured</span>
            <p style="color:var(--text1);margin:4px 0 0;font-size:0.81rem">
                Please configure your API settings in <strong>API &amp; Model Settings</strong> before managing documents.
            </p>
        </div>
        """, unsafe_allow_html=True)
        return

    # Check if embedding model is set
    if not st.session_state.settings.get("embedding_model"):
        warning_text_color = "#d4900a" if not st.session_state.is_dark else "#ffb800"
        st.markdown(f"""
        <div style="padding:10px 14px;background:rgba(255,184,0,0.08);border:1px solid rgba(255,184,0,0.28);
             border-radius:8px;margin-bottom:10px">
            <span style="color:{warning_text_color};font-weight:600;font-size:0.84rem">⚠️ Embedding Model Not Set</span>
            <p style="color:var(--text1);margin:4px 0 0;font-size:0.81rem">
                Please set an embedding model in <strong>API &amp; Model Settings → Embeddings</strong>.
            </p>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── System Status (slim inline row) ───────────────────────────────────
    if st.session_state.initialized:
        doc_manager = st.session_state.doc_manager
        if doc_manager:
            status = doc_manager.get_status()
            llm_val = "Ready" if st.session_state.llm else "—"
            folder_val = "Set" if status["selected_folder"] else "—"
            st.markdown(f"""
            <div class="dlg-status-row">
                <div class="dlg-stat">
                    <span class="dlg-stat-val">{status["document_count"]}</span>
                    <span class="dlg-stat-lbl">Documents</span>
                </div>
                <div class="dlg-stat">
                    <span class="dlg-stat-val">{status["vector_count"]}</span>
                    <span class="dlg-stat-lbl">Vectors</span>
                </div>
                <div class="dlg-stat">
                    <span class="dlg-stat-val">{llm_val}</span>
                    <span class="dlg-stat-lbl">LLM</span>
                </div>
                <div class="dlg-stat">
                    <span class="dlg-stat-val">{folder_val}</span>
                    <span class="dlg-stat-lbl">Folder</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.divider()

    # ── Folder paths ───────────────────────────────────────────────────────
    _section("Folder Paths")
    col1, col2 = st.columns([5, 1])
    with col1:
        new_folder_path = st.text_input(
            "Folder Path",
            placeholder="C:/Users/Documents/PDFs",
            key="dlg_folder_input",
            label_visibility="collapsed",
        )
    with col2:
        if st.button("Add", key="dlg_add_folder_path_btn", use_container_width=True):
            if new_folder_path and os.path.isdir(new_folder_path):
                try:
                    if st.session_state.doc_manager is None:
                        doc_manager = DocumentManager(
                            index_path=DOC_INDEX_PATH,
                            vector_dir=VECTOR_DIR,
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

    # ── Folder list & actions ──────────────────────────────────────────────
    if st.session_state.doc_manager:
        status = st.session_state.doc_manager.get_status()
        folders = status.get("selected_folders", [])
        indexed_docs = status.get("documents", [])

        sync_disabled = bool(not folders or (st.session_state.get("sync_task") is not None and st.session_state.sync_task.is_running))
        reindex_disabled = bool(not folders or (st.session_state.get("reindex_task") is not None and st.session_state.reindex_task.is_running))

        col_a, col_b, col_c, _sp = st.columns([1, 1, 1, 3])
        with col_a:
            if st.button("↺ Sync", key="dlg_sync_folder", disabled=sync_disabled, use_container_width=True):
                task = BackgroundTask(target=st.session_state.doc_manager.sync)
                st.session_state.sync_task = task
                task.start()
                st.toast("🔄 Sync started in background!", icon="⚡")
                st.rerun()
        with col_b:
            if st.button("↺ Re-index", key="dlg_reindex_all", disabled=reindex_disabled, use_container_width=True):
                task = BackgroundTask(target=st.session_state.doc_manager.index_all, kwargs={"force_reindex": True})
                st.session_state.reindex_task = task
                task.start()
                st.toast("🔄 Re-indexing started in background!", icon="⚡")
                st.rerun()
        with col_c:
            if st.button("Clear Index", key="dlg_clear_index", use_container_width=True):
                st.session_state.doc_manager.vector_store.clear()
                st.session_state.doc_manager.documents = {}
                st.session_state.doc_manager._save_index()
                st.success("Index cleared")
                st.rerun()

        # Background Task Status
        sync_task = st.session_state.sync_task
        if sync_task:
            if sync_task.is_running:
                st.info("🔄 Synchronizing folders in the background...")
                st.button("🔄 Check Sync Status", key="dlg_chk_sync_btn")
            elif sync_task.is_done:
                if sync_task.error:
                    st.error(f"❌ Synchronization failed: {sync_task.error}")
                else:
                    res = sync_task.result
                    if isinstance(res, dict):
                        msg = f"✅ Indexed {res.get('indexed', 0)} chunks from {res.get('files', 0)} files"
                        failed = res.get("failed_files", [])
                        if failed:
                            st.warning(
                                f"⚠️ {len(failed)} file(s) failed to index.\n"
                                + "\n".join(f"  - {f.split('/')[-1]}" for f in failed[:5])
                                + ("\n  ..." if len(failed) > 5 else "")
                                + "\n\nTry Re-index after fixing the issue."
                            )
                        else:
                            st.success(msg)
                    else:
                        st.success("✅ Synchronization complete!")
                st.session_state.sync_task = None
                st.button("Dismiss", key="dlg_dismiss_sync_btn")

        reindex_task = st.session_state.reindex_task
        if reindex_task:
            if reindex_task.is_running:
                st.info("🔄 Re-indexing files in the background...")
                st.button("🔄 Check Re-index Status", key="dlg_chk_reindex_btn")
            elif reindex_task.is_done:
                if reindex_task.error:
                    st.error(f"❌ Re-indexing failed: {reindex_task.error}")
                else:
                    res = reindex_task.result
                    if isinstance(res, dict):
                        failed = res.get("failed_files", [])
                        total = res.get("total_files", 0)
                        indexed = res.get("total_indexed", 0)
                        if failed:
                            st.warning(
                                f"⚠️ Indexed {indexed} chunks from {total} files; "
                                f"{len(failed)} file(s) failed.\n"
                                + "\n".join(f"  - {f.split('/')[-1]}" for f in failed[:5])
                                + ("\n  ..." if len(failed) > 5 else "")
                            )
                        else:
                            st.success(f"✅ Re-indexing complete! {indexed} chunks from {total} files.")
                    else:
                        st.success("✅ Re-indexing complete!")
                st.session_state.reindex_task = None
                st.button("Dismiss", key="dlg_dismiss_reindex_btn")

        # Folder list
        if folders:
            _section("Indexed Folders")
            for f_path in folders:
                folder_docs = [d for d in indexed_docs if d["file"].startswith(f_path) and d["status"] == "indexed"]
                col_exp, col_del = st.columns([5, 1])
                with col_exp:
                    with st.expander(f"📁 {f_path} ({len(folder_docs)} files)", expanded=False):
                        if folder_docs:
                            for doc in folder_docs:
                                filename = os.path.basename(doc["file"])
                                st.markdown(f"""
                                <div style="display:flex;justify-content:space-between;padding:3px 0;
                                     font-size:0.82rem;border-bottom:1px solid rgba(128,128,128,0.10)">
                                    <span style="color:var(--text0)">{filename}</span>
                                    <span style="color:var(--text2)">{doc['chunks']} chunks</span>
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.caption("No files indexed in this folder yet.")
                with col_del:
                    if st.button("Remove", key=f"dlg_del_folder_{hash(f_path)}", use_container_width=True):
                        try:
                            st.session_state.doc_manager.remove_folder(f_path)
                            st.success(f"Removed: {f_path}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

            other_docs = [d for d in indexed_docs if d["status"] == "indexed" and not any(d["file"].startswith(fp) for fp in folders)]
            if other_docs:
                with st.expander(f"📤 Uploaded Files ({len(other_docs)} files)", expanded=False):
                    for doc in other_docs:
                        filename = os.path.basename(doc["file"])
                        st.markdown(f"""
                        <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:0.82rem">
                            <span style="color:var(--text0)">{filename}</span>
                            <span style="color:var(--text2)">{doc['chunks']} chunks (uploaded)</span>
                        </div>
                        """, unsafe_allow_html=True)

    # ── PDF Upload ─────────────────────────────────────────────────────────
    _section("Upload PDF")
    uploaded_file = st.file_uploader(
        "Drop PDF here",
        type=["pdf"],
        key="dlg_pdf_uploader",
        label_visibility="collapsed",
    )
    if uploaded_file:
        upload_dir = UPLOADS_DIR
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        if st.button("Index File", key="dlg_index_upload"):
            with st.spinner("Indexing..."):
                count = st.session_state.doc_manager.handle_upload(str(file_path))
                st.success(f"Indexed {count} chunks from {uploaded_file.name}")
                st.rerun()


# ---------------------------------------------------------------------------
# API Settings
# ---------------------------------------------------------------------------
def render_api_settings_in_dialog() -> None:
    """Renders the API and system settings tab pages."""
    _inject_css()

    api_persistence = st.session_state.api_persistence
    settings = st.session_state.settings

    if not api_persistence:
        st.error("API Persistence system is not initialized.")
        return

    providers = api_persistence.get_providers()
    default_provider, default_model = api_persistence.get_default()

    tab_chat, tab_embed, tab_rerank, tab_providers = st.tabs([
        "💬 Chat Models (对话模型)",
        "🔤 Embeddings (向量模型)",
        "🔍 Reranking (重排模型)",
        "🛠️ API Providers (服务商管理)"
    ])

    # ── Chat Models ────────────────────────────────────────────────────────
    with tab_chat:
        if providers:
            chat_prov_options = list(providers.keys())
            try:
                chat_prov_idx = chat_prov_options.index(default_provider)
            except ValueError:
                chat_prov_idx = 0

            selected_chat_prov = st.selectbox(
                "Chat Provider (对话服务商)",
                options=chat_prov_options,
                index=chat_prov_idx,
                key="settings_chat_prov"
            )

            chat_models = providers.get(selected_chat_prov, {}).get("models", [])
            if chat_models:
                try:
                    chat_model_idx = chat_models.index(default_model)
                except ValueError:
                    chat_model_idx = 0
                selected_chat_model = st.selectbox(
                    "Chat Model (对话模型)",
                    options=chat_models,
                    index=chat_model_idx,
                    key="settings_chat_model"
                )
            else:
                st.warning("Selected provider has no models configured. Go to Service Providers tab to add models.")
                selected_chat_model = st.text_input("Enter Model Name manually", value=default_model, key="settings_chat_model_manual")

            if st.button("Save", key="save_chat_settings_btn"):
                try:
                    api_persistence.update_provider(selected_chat_prov, selected_chat_model)
                    st.session_state.needs_reinit = True
                    st.success(f"✅ Chat settings saved: {selected_chat_prov} — {selected_chat_model}")
                except Exception as e:
                    st.error(f"❌ Failed to save chat settings: {e}")
        else:
            st.info("No API providers configured yet. Please add a provider in the 'API Providers' tab.")

    # ── Embeddings ─────────────────────────────────────────────────────────
    with tab_embed:
        emb_provider = settings.get("embedding_provider", "")
        emb_model = settings.get("embedding_model", "")
        chunk_size = settings.get("chunk_size", 800)
        chunk_overlap = settings.get("chunk_overlap", 100)

        if providers:
            embed_prov_options = list(providers.keys())
            try:
                embed_prov_idx = embed_prov_options.index(emb_provider)
            except ValueError:
                embed_prov_idx = 0

            selected_emb_prov = st.selectbox(
                "Embedding Provider (向量服务商)",
                options=embed_prov_options,
                index=embed_prov_idx,
                key="settings_emb_prov"
            )
            emb_models = providers.get(selected_emb_prov, {}).get("models", [])
            if emb_models:
                try:
                    emb_model_idx = emb_models.index(emb_model)
                except ValueError:
                    emb_model_idx = 0
                selected_emb_model = st.selectbox(
                    "Embedding Model (向量模型)",
                    options=emb_models,
                    index=emb_model_idx,
                    key="settings_emb_model"
                )
            else:
                selected_emb_model = st.text_input("Embedding Model Name", value=emb_model, key="settings_emb_model_manual")
        else:
            selected_emb_prov = st.text_input("Embedding Provider Name", value=emb_provider, key="settings_emb_prov_manual")
            selected_emb_model = st.text_input("Embedding Model Name", value=emb_model, key="settings_emb_model_manual_no_prov")

        _section("Chunker")
        col_cs, col_co = st.columns(2)
        with col_cs:
            new_chunk_size = st.number_input("Chunk Size (分片大小)", min_value=50, value=chunk_size, step=50)
        with col_co:
            new_chunk_overlap = st.number_input("Chunk Overlap (分片重叠)", min_value=0, value=chunk_overlap, step=10)

        if selected_emb_model != emb_model:
            st.warning("⚠️ Changing the embedding model requires clearing the index and re-syncing documents!")

        if st.button("Save", key="save_emb_settings_btn"):
            try:
                settings["embedding_provider"] = selected_emb_prov
                settings["embedding_model"] = selected_emb_model
                settings["chunk_size"] = new_chunk_size
                settings["chunk_overlap"] = new_chunk_overlap
                write_json(SETTINGS_PATH, settings)
                st.session_state.needs_reinit = True
                st.success("✅ Embedding settings saved successfully!")
            except Exception as e:
                st.error(f"❌ Failed to save embedding settings: {e}")

    # ── Reranking ──────────────────────────────────────────────────────────
    with tab_rerank:
        rerank_enabled = settings.get("rerank_enabled", False)
        rerank_model = settings.get("rerank_model", "")
        rerank_top_k = settings.get("rerank_top_k", 10)
        top_k = settings.get("top_k", 5)

        col_tog, col_k = st.columns(2)
        with col_tog:
            new_rerank_enabled = st.toggle("Enable Reranking (启用重排)", value=rerank_enabled, key="settings_rerank_enabled")
        with col_k:
            new_top_k = st.slider("Base Top-K (基础检索数)", 1, 30, top_k, 1)

        selected_rerank_prov = ""
        selected_rerank_model = ""
        new_rerank_top_k = rerank_top_k

        if new_rerank_enabled:
            if providers:
                current_rerank_prov = ""
                for name, pconf in providers.items():
                    if rerank_model in pconf.get("models", []):
                        current_rerank_prov = name
                        break

                rerank_prov_options = list(providers.keys())
                try:
                    rerank_prov_idx = rerank_prov_options.index(current_rerank_prov)
                except ValueError:
                    rerank_prov_idx = 0

                selected_rerank_prov = st.selectbox(
                    "Reranker Provider (重排服务商)",
                    options=rerank_prov_options,
                    index=rerank_prov_idx,
                    key="settings_rerank_prov"
                )
                rerank_models = providers.get(selected_rerank_prov, {}).get("models", [])
                if rerank_models:
                    try:
                        rerank_model_idx = rerank_models.index(rerank_model)
                    except ValueError:
                        rerank_model_idx = 0
                    selected_rerank_model = st.selectbox(
                        "Reranker Model (重排模型)",
                        options=rerank_models,
                        index=rerank_model_idx,
                        key="settings_rerank_model"
                    )
                else:
                    selected_rerank_model = st.text_input("Reranker Model Name", value=rerank_model, key="settings_rerank_model_manual")
            else:
                selected_rerank_model = st.text_input("Reranker Model Name", value=rerank_model, key="settings_rerank_model_manual_no_prov")

            new_rerank_top_k = st.slider("Rerank Top-K (重排后保留数)", 1, 30, rerank_top_k, 1)

        if st.button("Save", key="save_rerank_settings_btn"):
            try:
                settings["rerank_enabled"] = new_rerank_enabled
                if new_rerank_enabled:
                    settings["rerank_model"] = selected_rerank_model
                    settings["rerank_top_k"] = new_rerank_top_k
                settings["top_k"] = new_top_k
                write_json(SETTINGS_PATH, settings)
                st.session_state.needs_reinit = True
                st.success("✅ Reranker settings saved successfully!")
            except Exception as e:
                st.error(f"❌ Failed to save reranker settings: {e}")

    # ── API Providers ──────────────────────────────────────────────────────
    with tab_providers:
        prov_mode = st.segmented_control(
            "Action (操作)",
            options=["Add New Provider", "Edit / Remove Provider"],
            default="Add New Provider",
            label_visibility="collapsed"
        )

        st.divider()

        if prov_mode == "Add New Provider":
            _section("New Provider")
            new_prov_name = st.text_input("Provider Name (服务商名称)", placeholder="e.g. deepseek-v4")
            new_prov_base_url = st.text_input("Base URL (接口地址)", placeholder="https://api.deepseek.com/v1")
            new_prov_key = st.text_input("API Key (密匙)", type="password", placeholder="sk-...")
            new_prov_models_text = st.text_area("Models (每行一个)", placeholder="deepseek-chat\ndeepseek-coder", height=72)

            if st.button("Add Provider", key="add_prov_btn"):
                if not new_prov_name:
                    st.error("❌ Provider Name is required.")
                elif not new_prov_base_url:
                    st.error("❌ Base URL is required.")
                else:
                    try:
                        models_list = [m.strip() for m in new_prov_models_text.split("\n") if m.strip()]
                        api_persistence.add_provider(
                            name=new_prov_name,
                            base_url=new_prov_base_url,
                            api_key=new_prov_key,
                            models=models_list,
                            description=""
                        )
                        st.session_state.needs_reinit = True
                        st.success(f"✅ Provider '{new_prov_name}' added successfully!")
                    except Exception as e:
                        st.error(f"❌ Failed to add provider: {e}")
        else:
            if providers:
                selected_edit_prov = st.selectbox("Select Provider", options=list(providers.keys()))
                edit_conf = providers[selected_edit_prov]
                edit_base_url = st.text_input("Base URL", value=edit_conf.get("base_url", ""))
                edit_key = st.text_input("API Key", value=edit_conf.get("api_key", ""), type="password")
                edit_models_text = st.text_area("Models (每行一个)", value="\n".join(edit_conf.get("models", [])), height=72)

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Save Changes", key="save_edit_prov_btn", use_container_width=True):
                        try:
                            models_list = [m.strip() for m in edit_models_text.split("\n") if m.strip()]
                            api_persistence.update_provider_config(
                                provider=selected_edit_prov,
                                api_key=edit_key,
                                base_url=edit_base_url,
                                models=models_list
                            )
                            st.session_state.needs_reinit = True
                            st.success(f"✅ Changes to {selected_edit_prov} saved!")
                        except Exception as e:
                            st.error(f"❌ Failed to save: {e}")
                with col2:
                    if st.button("Delete Provider", key="delete_prov_btn", use_container_width=True):
                        try:
                            api_persistence.remove_provider(selected_edit_prov)
                            st.session_state.needs_reinit = True
                            st.success(f"Provider '{selected_edit_prov}' removed.")
                        except Exception as e:
                            st.error(f"❌ Failed: {e}")
            else:
                st.info("No providers configured to edit.")

        # Provider status list
        _section("Configured Providers")
        updated_providers = api_persistence.get_providers()
        validation = api_persistence.validate()

        if updated_providers:
            for name, pconf in updated_providers.items():
                is_valid = validation.get(name, False)
                models_str = ", ".join(pconf.get("models", []))
                status_color = "#3ecf8e" if is_valid else "#e05555"
                status_text = "Active" if is_valid else "Key Missing"
                card_cls = "ok" if is_valid else "err"
                st.markdown(f"""
                <div class="dlg-prov-card {card_cls}">
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <span class="dlg-prov-name">{'🟢' if is_valid else '🔴'} {name}</span>
                        <span style="font-size:0.76rem;font-weight:600;color:{status_color}">{status_text}</span>
                    </div>
                    <div class="dlg-prov-meta"><code style="font-size:0.74rem">{pconf.get('base_url','')}</code></div>
                    <div class="dlg-prov-meta">Models: <code style="font-size:0.74rem">{models_str}</code></div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No providers configured yet.")


# ---------------------------------------------------------------------------
# Dialog entry point
# ---------------------------------------------------------------------------
@st.dialog("⚙️ Settings (系统设置)", width="large")
def settings_dialog() -> None:
    """Unified floating settings dialog using tabs — no st.rerun() needed inside dialog."""
    tab_docs, tab_api = st.tabs(["📁 Document Settings", "🔑 API & Model Settings"])

    with tab_docs:
        st.markdown("<h3 style='margin-top: 0; color: var(--text0);'>📁 Document Settings</h3>", unsafe_allow_html=True)
        st.markdown("<hr class='minimal-divider' style='margin: 12px 0;'>", unsafe_allow_html=True)
        render_document_settings_in_dialog()

    with tab_api:
        st.markdown("<h3 style='margin-top: 0; color: var(--text0);'>🔑 API & Model Settings</h3>", unsafe_allow_html=True)
        st.markdown("<hr class='minimal-divider' style='margin: 12px 0;'>", unsafe_allow_html=True)
        render_api_settings_in_dialog()
