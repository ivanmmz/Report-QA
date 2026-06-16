"""Floating API settings dialog UI for Windows RAG System."""
import streamlit as st
from utils.file_io import write_json


@st.dialog("⚙️ API & System Settings", width="large")
def api_settings_dialog() -> None:
    """Renders the floating API and system settings modal dialog."""
    api_persistence = st.session_state.api_persistence
    settings = st.session_state.settings

    if not api_persistence:
        st.error("API Persistence system is not initialized.")
        return

    # Load configurations
    providers = api_persistence.get_providers()
    default_provider, default_model = api_persistence.get_default()

    # Redesigned Layout using Tabs
    tab_chat, tab_embed, tab_rerank, tab_providers = st.tabs([
        "💬 Chat Models (对话模型)",
        "🔤 Embeddings (向量模型)",
        "🔍 Reranking (重排模型)",
        "🛠️ API Providers (服务商管理)"
    ])

    with tab_chat:
        st.markdown("### 💬 Chat Model Configuration")
        if providers:
            # Dropdown for chat provider
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

            # Dropdown for chat model
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

            st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)
            if st.button("Save Chat Settings", key="save_chat_settings_btn", use_container_width=True):
                try:
                    api_persistence.update_provider(selected_chat_prov, selected_chat_model)
                    st.session_state.needs_reinit = True
                    st.success(f"✅ Chat settings saved: {selected_chat_prov} - {selected_chat_model}")
                except Exception as e:
                    st.error(f"❌ Failed to save chat settings: {e}")
        else:
            st.info("No API providers configured yet. Please add a provider in the 'API Providers' tab.")

    with tab_embed:
        st.markdown("### 🔤 Embedding Configuration")
        # Separate embedding settings!
        emb_provider = settings.get("embedding_provider", "")
        emb_model = settings.get("embedding_model", "")
        chunk_size = settings.get("chunk_size", 800)
        chunk_overlap = settings.get("chunk_overlap", 100)

        # Provider and Model input/selection
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

        st.markdown("<hr class='minimal-divider'>", unsafe_allow_html=True)
        st.markdown("#### Document Chunker Settings")
        new_chunk_size = st.slider("Chunk Size (分片大小)", 100, 2000, chunk_size, 50)
        new_chunk_overlap = st.slider("Chunk Overlap (分片重叠)", 0, 500, chunk_overlap, 10)

        if selected_emb_model != emb_model:
            st.warning("⚠️ Changing the embedding model requires clearing the index and re-syncing documents!")

        st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)
        if st.button("Save Embedding Settings", key="save_emb_settings_btn", use_container_width=True):
            try:
                settings["embedding_provider"] = selected_emb_prov
                settings["embedding_model"] = selected_emb_model
                settings["chunk_size"] = new_chunk_size
                settings["chunk_overlap"] = new_chunk_overlap

                write_json("config/settings.json", settings)
                st.session_state.needs_reinit = True
                st.success("✅ Embedding settings saved successfully!")
            except Exception as e:
                st.error(f"❌ Failed to save embedding settings: {e}")

    with tab_rerank:
        st.markdown("### 🔍 Reranker Configuration")
        rerank_enabled = settings.get("rerank_enabled", False)
        rerank_model = settings.get("rerank_model", "")
        rerank_top_k = settings.get("rerank_top_k", 10)
        top_k = settings.get("top_k", 5)

        new_rerank_enabled = st.toggle("Enable Reranking (启用重排)", value=rerank_enabled, key="settings_rerank_enabled")
        new_top_k = st.slider("Base Top-K (基础检索数)", 1, 30, top_k, 1)

        selected_rerank_prov = ""
        selected_rerank_model = ""
        new_rerank_top_k = rerank_top_k

        if new_rerank_enabled:
            if providers:
                # Find provider of current rerank model
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

        st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)
        if st.button("Save Reranker Settings", key="save_rerank_settings_btn", use_container_width=True):
            try:
                settings["rerank_enabled"] = new_rerank_enabled
                if new_rerank_enabled:
                    settings["rerank_model"] = selected_rerank_model
                    settings["rerank_top_k"] = new_rerank_top_k
                settings["top_k"] = new_top_k

                write_json("config/settings.json", settings)
                st.session_state.needs_reinit = True
                st.success("✅ Reranker settings saved successfully!")
            except Exception as e:
                st.error(f"❌ Failed to save reranker settings: {e}")

    with tab_providers:
        st.markdown("### 🛠️ API Provider Manager")

        # Option to Add or Edit
        prov_mode = st.radio("Action (操作)", ["Add New Provider", "Edit/Remove Existing Provider"], horizontal=True, label_visibility="collapsed")

        st.markdown("<hr class='minimal-divider'>", unsafe_allow_html=True)

        if prov_mode == "Add New Provider":
            st.markdown("#### Add New Provider Presets")
            new_prov_name = st.text_input("Provider Name (服务商名称)", placeholder="e.g. deepseek-v4, custom-embeddings")
            new_prov_base_url = st.text_input("Base URL (接口地址)", placeholder="https://api.deepseek.com/v1")
            new_prov_key = st.text_input("API Key (密匙)", type="password", placeholder="sk-...")
            new_prov_models_text = st.text_area("Models (模型列表, 每行一个)", placeholder="deepseek-chat\ndeepseek-coder")

            st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)
            if st.button("➕ Add Provider", use_container_width=True):
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
                selected_edit_prov = st.selectbox("Select Provider to Edit/Remove", options=list(providers.keys()))
                edit_conf = providers[selected_edit_prov]

                edit_base_url = st.text_input("Base URL", value=edit_conf.get("base_url", ""))
                edit_key = st.text_input("API Key", value=edit_conf.get("api_key", ""), type="password")
                edit_models_text = st.text_area("Models (每行一个)", value="\n".join(edit_conf.get("models", [])))

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Save Changes", use_container_width=True, key="save_edit_prov_btn"):
                        try:
                            models_list = [m.strip() for m in edit_models_text.split("\n") if m.strip()]
                            api_persistence.update_provider_config(
                                provider=selected_edit_prov,
                                api_key=edit_key,
                                base_url=edit_base_url,
                                models=models_list
                            )
                            st.session_state.needs_reinit = True
                            st.success(f"✅ Changes to {selected_edit_prov} saved successfully!")
                        except Exception as e:
                            st.error(f"❌ Failed to save changes: {e}")
                with col2:
                    if st.button("🗑️ Delete Provider", use_container_width=True, key="delete_prov_btn"):
                        try:
                            api_persistence.remove_provider(selected_edit_prov)
                            st.session_state.needs_reinit = True
                            st.success(f"🗑️ Provider '{selected_edit_prov}' removed successfully!")
                        except Exception as e:
                            st.error(f"❌ Failed to delete provider: {e}")
            else:
                st.info("No providers configured to edit.")

        # Real-time listing of configured providers inside the tab
        st.markdown("<hr class='minimal-divider'>", unsafe_allow_html=True)
        st.markdown("#### Configured Providers (已配置的服务商列表)")
        
        # Re-fetch configurations to display the newest data instantly in this run
        updated_providers = api_persistence.get_providers()
        validation = api_persistence.validate()

        if updated_providers:
            for name, pconf in updated_providers.items():
                is_valid = validation.get(name, False)
                status_icon = "🟢" if is_valid else "🔴"
                models_str = ", ".join(pconf.get("models", []))
                st.markdown(f"""
                <div style="padding: 10px 14px; background: rgba(255,255,255,0.02); border-left: 3px solid {'#00cc6a' if is_valid else '#ff4343'}; border-radius: 4px; margin: 6px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong>{status_icon} {name}</strong>
                        <span style="font-size: 0.85em; font-weight: bold; color: {'#00cc6a' if is_valid else '#ff4343'};">
                            {'Active' if is_valid else 'Key Missing'}
                        </span>
                    </div>
                    <div style="font-size: 0.85em; color: rgba(255,255,255,0.5); margin-top: 4px;">
                        Base URL: <code>{pconf.get('base_url', '')}</code>
                    </div>
                    <div style="font-size: 0.85em; color: rgba(255,255,255,0.5); margin-top: 2px;">
                        Models: <code>{models_str}</code>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No providers configured yet.")
