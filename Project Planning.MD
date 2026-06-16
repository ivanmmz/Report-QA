# 🧠 Windows Local RAG System (bge-m3 + FAISS + Streamlit)
# ENHANCED IMPLEMENTATION PLAN (v2 - Production MVP)

==================================================
🎯 CORE OBJECTIVE
==================================================

Build a Windows-native AI Document Intelligence System that supports:

1. PDF upload OR folder selection
2. Persistent document knowledge base (auto-reload on restart)
3. Local embedding using bge-m3
4. FAISS vector search
5. LLM-powered Q&A with citations
6. AI-assisted report improvement chat interface
7. Windows Fluent Design-like UI in Streamlit
8. CMD-based one-click startup

==================================================
📁 FINAL PROJECT STRUCTURE (UPDATED)
==================================================

windows-rag-system/

│
├── app.py                          # Streamlit entry
├── run.cmd                         # ⭐ Windows one-click launcher
├── requirements.txt
├── README.md
│
├── config/
│   ├── settings.json              # system config (chunk, top_k, ui)
│   ├── api_keys.json              # model routing (NO hardcoding)
│   ├── api_keys.local.json        # ⭐ persistent encrypted-safe local copy (optional)
│
├── data/
│   ├── documents/                 # ⭐ user-selected folder sync target
│   ├── uploads/
│   ├── vectors/
│   ├── metadata/
│   │   ├── doc_index.json         # persistent document registry
│   │   ├── api_cache.json         # ⭐ stores API config backup
│
├── core/
│   ├── document_manager.py        # folder selection + sync engine
│   ├── pdf_loader.py
│   ├── chunker.py
│   ├── embedder.py
│   ├── retriever.py
│   ├── rag_pipeline.py
│   ├── api_persistence.py         # ⭐ NEW: API persistence handler
│
├── vectorstore/
│   ├── faiss_store.py
│
├── llm/
│   ├── gateway.py
│   ├── prompts.py
│
├── ui/
│   ├── chat_ui.py                 # chat assistant panel
│   ├── report_chat.py             # ⭐ AI report improvement chat
│   ├── theme.py                   # Fluent UI styling tokens
│
├── utils/
│   ├── file_io.py
│   ├── logger.py

==================================================
🧠 NEW FEATURE 1 — FOLDER SELECTION SYSTEM
==================================================

FILE: core/document_manager.py

FEATURES:

✔ User selects folder via Streamlit UI:
   st.text_input() OR st.folder_picker (simulated)

✔ Watch selected folder:

selected_path = user_defined_path

✔ System behavior:
- scan folder on startup
- detect new PDFs
- auto index missing docs

✔ Persistent mapping:

doc_index.json:

{
  "selected_folder": "D:/AI_Docs/",
  "files": [
    {
      "file": "hvac.pdf",
      "hash": "...",
      "status": "indexed"
    }
  ]
}

✔ Must support:
- folder change
- re-sync button
- incremental indexing

==================================================
🔐 NEW FEATURE 2 — API PERSISTENCE (NO LOSS AFTER RESTART)
==================================================

FILE: core/api_persistence.py

PROBLEM:
- Streamlit restart loses runtime state

SOLUTION:
- persist API config locally

✔ STORAGE PRIORITY:

1. config/api_keys.local.json (persistent)
2. config/api_keys.json (default template)
3. .env (fallback)

✔ FUNCTIONS:

save_api_config()
load_api_config()
update_api_key(provider, key)
validate_keys()

✔ Streamlit behavior:

- user edits API keys in UI
- saved immediately to local JSON
- auto loaded on startup

==================================================
🖥️ NEW FEATURE 3 — WINDOWS FLUENT DESIGN UI (STREAMLIT)
==================================================

IMPORTANT:
Streamlit does NOT support native Fluent UI,
so we simulate Fluent Design via:

FILE: ui/theme.py

✔ DESIGN RULES:

- soft blur panels (CSS cards)
- rounded corners (12–16px)
- subtle shadows
- gradient accents (blue / cyan)
- sidebar navigation like Windows Settings
- card-based layout

✔ CSS INJECTION:

st.markdown("""
<style>
    .stApp {
        background-color: #0f1117;
        color: white;
    }

    .card {
        background: rgba(255,255,255,0.05);
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0px 4px 20px rgba(0,0,0,0.3);
    }
</style>
""", unsafe_allow_html=True)

✔ UI STYLE TARGET:
- Windows 11 Settings-like layout
- Fluent spacing system
- soft glassmorphism

==================================================
🖥️ NEW FEATURE 4 — CMD LAUNCHER (ONE CLICK START)
==================================================

FILE: run.cmd

@echo off
echo Starting Windows RAG System...
cd /d %~dp0
call venv\Scripts\activate
streamlit run app.py
pause

✔ Optional improvements:
- auto pip install check
- auto env check

==================================================
🤖 NEW FEATURE 5 — AI REPORT CHAT ASSISTANT
==================================================

FILE: ui/report_chat.py

FEATURE:

User can:
👉 talk to AI to improve report output

EXAMPLE:

User:
"Make the COP analysis more technical"

AI:
- updates chart description
- refines KPI explanation
- suggests new metric

✔ INPUT:
- current report context
- generated charts
- dataset metadata

✔ OUTPUT:

{
  "improved_insights": "...",
  "suggested_metrics": [],
  "chart_changes": []
}

✔ USE CASE:
- report refinement loop
- iterative analytics improvement

==================================================
🧠 SYSTEM FLOW (UPDATED)
==================================================

Startup:

CMD → run.cmd
        ↓
Load Streamlit App
        ↓
Load API config (persistent)
        ↓
Load selected folder (doc_index.json)
        ↓
Load FAISS index
        ↓
Ready

User Flow:

1. Select Folder OR Upload PDF
2. Auto indexing
3. Ask questions (RAG chat)
4. View citations
5. Open "Report Chat"
   → AI improves report iteratively

==================================================
📦 CORE ARCHITECTURE (UNCHANGED BUT ENHANCED)
==================================================

PDF / Folder
   ↓
Document Manager
   ↓
Chunker
   ↓
bge-m3 embedding
   ↓
FAISS index
   ↓
Retriever
   ↓
LLM Gateway
   ↓
RAG Answer + Report + Chat system

==================================================
🧾 REQUIREMENTS UPDATE

streamlit
pymupdf
faiss-cpu
sentence-transformers
numpy
pandas
python-dotenv
openai

==================================================
🚀 SUCCESS CRITERIA (UPDATED)

System is successful if:

✔ User selects folder OR uploads PDF
✔ System remembers folder after restart
✔ API keys persist after restart
✔ User can chat with documents
✔ AI can improve report interactively
✔ UI feels like Windows Fluent-style app
✔ System starts via CMD script
✔ Fully local Windows execution

==================================================
🚫 STRICT CONSTRAINTS

DO NOT:
- use external desktop frameworks (Electron, PyQT)
- require LM Studio
- use database server
- break Streamlit single-app design

DO:
- keep everything local file-based
- persist state via JSON
- ensure restart recovery
- keep modular architecture

==================================================
🔥 FUTURE EXTENSIONS

- multi-folder knowledge system
- enterprise document workspace
- Excel + PDF unified RAG
- chiller plant industrial analytics AI
- AI report editor agent
- vector + keyword hybrid search (grep + RAG)

==================================================
END OF ENHANCED IMPLEMENTATION PLAN
==================================================