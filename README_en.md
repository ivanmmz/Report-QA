[简体中文](README.md) | [English](README_en.md)

---

# 🧠 Windows Local Intelligent Document RAG System & Report Canvas

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tauri](https://img.shields.io/badge/Tauri-2.x-orange.svg)](https://tauri.app/)
[![FAISS](https://img.shields.io/badge/FAISS-1.8.0+-green.svg)](https://github.com/facebookresearch/faiss)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A deploy-free, high-fidelity table reconstruction, and two-stage vector retrieval (RAG) report generation system designed specifically for Windows users. Combining a dual-column Markdown Canvas editor with an Edge-Copilot style sidebar AI Assistant, the system enables secure local text and table extraction, semantic search, and dynamic Chart.js chart visualization.

---

## 📸 Interface Preview

Here is the core dual-column layout of the system in action (Left: Report Canvas preview; Right: AI Copilot assistant and document citations):

![RAG System Screenshot](assets/screenshot.png)

---

## ✨ Core Features

- **📁 Document Import & Monitor**: Supports incremental automatic folder scanning and manual PDF uploads. Detects files, hashes content for modification checks, and updates index slices.
- **📊 Smart Table Reconstruction**: Addresses the text alignment errors typical of PDF parsers by combining PyMuPDF's table extraction engine with custom row assembly heuristics. Keeps tables intact and associated with column header categories.
- **🔤 Embedding Dimension Auto-Detection**: Supports any OpenAI-compatible API embedding provider. The system sends a dummy request on initialization to probe and detect the output vector dimension, removing the need to configure FAISS dimensions manually.
- **🔍 Two-Stage Retrieval (Retrieve & Rerank)**:
  - **Stage 1 (Retrieval)**: Fast similarity search using FAISS Inner Product (equivalent to cosine similarity on normalized vectors).
  - **Stage 2 (Reranking)**: Optional LLM-based Reranker that scores chunk relevance from 1-10 to refine context quality, filtering out noise and irrelevant segments.
- **💬 Citation & Strict Anti-Hallucination**: Answers include inline reference tags with cosine similarity scores. The AI Copilot is strictly instructed to say "information not found" rather than inventing statistics when data is absent in the retrieved context.
- **🎨 Fluent Design Theme Overlay**: Native custom CSS styling implementing light/dark modes with glassmorphism card and floating overlays.
- **🚀 Interactive Dual-Column Canvas Panel**:
  - The left area is the writing board, featuring **Edit** (Markdown code area) and **Preview** (Fluent-styled HTML layout) tabs.
  - Recognizes ` ```chart ` code blocks with valid JSON formatting to automatically render line, bar, doughnut, and other interactive graphs using Chart.js.
  - Supports exporting reports directly as `.md` or standalone `.html` files containing embedded visualization scripts for offline presentations.
  - Click **"Apply to Canvas"** on Copilot answers to merge AI revisions directly into your active draft.

---

## 🚀 Quick Start

### Prerequisites
- Operating System: Windows 10 or Windows 11
- Python Version: `3.11` or higher
- Network: Internet access required for initial dependency installation and LLM/Embedding API queries.

### Run the Launcher
1. **Clone/Download** the repository to your local drive.
2. **Double-click** `windows-rag-system/run.cmd` to start the backend.
   - The launcher will verify Python installation.
   - Automatically initialize a local Python virtual environment (`venv`).
   - Pip install packages listed in `requirements.txt` and prepare required subdirectories under `data/`.
3. **Launch the Tauri frontend** from the `tauri-ui/` directory for the desktop application experience.
4. **Access the application** through the Tauri desktop window.

---

## ⚙️ Full Usage Guide

### Step 1: Configure APIs and Models
1. Click **⚙️ Settings (系统设置)** at the top right of the main header.
2. Under the **🔑 API & Model Settings** tab, go to **🛠️ API Providers**.
3. Add your LLM and Embedding API gateway settings (DeepSeek, OpenAI, local server, etc.), configure the `Base URL` and `API Key`, and insert the available model list.
4. Go back to the **💬 Chat Models** or **🔤 Embeddings** tabs to select default models. Set your preferred chunk settings (recommended `chunk_size`: 800) and click **Save**.

> [!TIP]
> Your keys and credentials are saved locally in `config/api_keys.local.json` and are ignored by git to keep your data secure.

### Step 2: Index Local Documents
1. In the **⚙️ Settings** modal, go to **📁 Document Settings**.
2. Enter the absolute path of your target document folder in the `Folder Path` input field (e.g., `C:/Users/Ivan/Desktop/Report QA1/1. Report`).
3. Click **Add**.
4. Click **↺ Sync** or **Re-index** to start the background thread indexing your files.
5. Once completed, a status toast will display the number of indexed files and vector chunks.

### Step 3: Write Reports and Chat with Copilot
1. **Left Canvas Area**:
   - Manage documents with **Save/Load** buttons or write content in the text editor.
   - Switch to **Preview** to read the formatted report and interact with rendering charts.
2. **Right Copilot Sidebar**:
   - Enter your prompt in the chat input (e.g., "Analyze the chiller COP trend from last Q4 and output a line chart").
   - Copilot retrieves text passages and answers with source references.
   - If the answer includes an updated report section, it will be placed in a `markdown-canvas` container. Hover and click **"Apply to Canvas"** to override or insert the draft directly.
3. **Exporting Documents**:
   - Click the floating `MD` or `HTML` buttons in the preview tab to save your document locally.

---

## 📁 Directory Layout

```
Report QA/
├── tauri-ui/                   # Tauri frontend (TypeScript + Tailwind CSS)
│   ├── src/                    # Frontend source code
│   ├── src-tauri/              # Tauri Rust backend
│   ├── index.html              # Entry HTML
│   ├── package.json            # Node.js dependencies
│   └── vite.config.ts          # Vite build configuration
└── windows-rag-system/         # Python backend core
    ├── run.cmd                 # Windows one-click batch launcher
    ├── requirements.txt        # Third-party package declarations
    ├── config/
    │   ├── settings.json       # Search and chunk configurations
    │   └── api_keys.json       # API preset structures
    ├── core/
    │   ├── api_persistence.py  # Local API key CRUD handler
    │   ├── pdf_loader.py       # PyMuPDF text & table extraction logic
    │   ├── chunker.py          # Chunker preserving table boundaries
    │   ├── embedder.py         # API embedding wrapper & dimension probe
    │   ├── retriever.py        # Dual FAISS search coordinator
    │   ├── reranker.py         # LLM-based reranking scoring mechanism
    │   ├── rag_pipeline.py     # Orchestrates Retrieve & Generation
    │   ├── data_extractor.py   # Regex metric & date extraction
    │   └── report_generator.py # RAG-based report generation orchestrator
    └── utils/
        ├── paths.py            # Absolute directory constant resolver
        ├── file_io.py          # Atomic file writers with retry locks
        ├── logger.py           # System log recorder
        └── background_task.py  # Daemon thread wrapper for background tasks
```

---

## 🔧 FAQ & Troubleshooting

#### 1. Why does Document Sync or Re-indexing fail?
- Ensure the API configuration of your active Embedding provider shows as **🟢 Active** in settings. If you changed the embedding model, clear previous indexes by clicking **Clear Index** first, then re-trigger **Re-index**.

#### 2. Copilot answers with "API Not Configured"
- Make sure default providers are configured under Settings, the credentials have been saved successfully, and the endpoint is accessible.

#### 3. Chart displays "Chart render error"
- Ensure the JSON content in the ` ```chart ` block is valid. Key and string values must use **double quotes** (`"`), and there must be no trailing commas.
- Example structure: `{ "type": "bar", "title": "Energy", "labels": ["Jan", "Feb"], "datasets": [{"label": "Usage", "data": [12, 19]}] }`

---

## 🛡️ Privacy & Security

- **Local Storage**: All indexed text metadata, FAISS indexes, uploads, and report draft revisions are **saved locally on your machine**.
- **API Requests**: Text snippets (Context) are sent to the external provider endpoints via encrypted HTTPS channels only during LLM generation and embedding calculations.
- **Local Mode**: Supports mock responses when using local endpoints without external credentials.

---

## 📝 License

This project is open-source under the **MIT License**. Feel free to modify and adapt it for commercial or personal use.
