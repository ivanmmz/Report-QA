# 🧠 Windows Local RAG System

A Windows-native AI Document Intelligence System built with Tauri, FAISS, and bge-m3 embeddings.

## ✨ Features

- **📁 PDF & Folder Upload** — Select entire folders or upload individual PDFs
- **💾 Persistent Knowledge Base** — Auto-reload documents and vectors on restart
- **🔤 Local Embeddings** — Uses BAAI/bge-m3 for high-quality local embeddings
- **🔍 FAISS Vector Search** — Fast similarity search with metadata filtering
- **💬 LLM Q&A with Citations** — Chat with your documents, see source references
- **🤖 AI Report Assistant** — Get AI suggestions to improve your reports
- **🎨 Windows Fluent Design** — Modern glassmorphism UI in Tauri desktop app
- **⚡ One-Click Startup** — Launch with `run.cmd`

## 🚀 Quick Start

### Prerequisites

- Windows 10/11
- Python 3.11 or higher
- At least 4GB RAM (8GB recommended for embedding model)

### Installation

1. **Clone or extract** the project to a folder (e.g., `C:\RAG-System`)

2. **Run the launcher:**
   ```cmd
   run.cmd
   ```

   The script will:
   - Check Python installation
   - Create a virtual environment
   - Install dependencies
   - Start the backend server

3. **Launch the Tauri frontend** from the `tauri-ui/` directory

### Manual Setup

If you prefer manual setup:

```cmd
# Create virtual environment
python -m venv venv

# Activate
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run backend server
python -m uvicorn main:app
```

Then launch the Tauri frontend from the `tauri-ui/` directory.

## 📖 Usage

### 1. Configure API Keys

Go to **⚙️ Settings** in the sidebar:
- Select your LLM provider (OpenAI, Azure, Local)
- Enter your API key
- Select a model
- Click **Save API Key**

Keys are stored securely in `config/api_keys.local.json` and persist across restarts.

### 2. Add Documents

Go to **📄 Documents**:

**Option A: Folder Selection**
- Enter a folder path containing PDFs
- Click **Set Folder**
- Click **Sync Folder** to auto-index all PDFs

**Option B: Upload**
- Use the file uploader to select a PDF
- Click **Index Uploaded File**

### 3. Chat with Documents

Go to **💬 Chat**:
- Ask questions about your documents
- View inline citations with source references
- See confidence scores for each source

### 4. Improve Reports

Go to **📊 Report Assistant**:
- Paste your current report content
- Ask for improvements (e.g., "Make the analysis more technical")
- Get structured suggestions with metrics and chart ideas

## 📁 Project Structure

```
windows-rag-system/
├── run.cmd                   # One-click Windows launcher
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── config/
│   ├── settings.json         # App settings
│   ├── api_keys.json         # Default API config template
│   └── api_keys.local.json   # Your persistent API keys
├── data/
│   ├── documents/            # Synced folder target
│   ├── uploads/              # Uploaded files
│   ├── vectors/              # FAISS index & metadata
│   └── metadata/
│       └── doc_index.json    # Document registry
├── core/
│   ├── document_manager.py   # Folder sync & indexing
│   ├── pdf_loader.py         # PDF text extraction
│   ├── chunker.py            # Text chunking
│   ├── embedder.py           # bge-m3 embeddings
│   ├── retriever.py          # Vector search
│   ├── rag_pipeline.py       # RAG orchestration
│   └── api_persistence.py    # API key persistence
├── vectorstore/
│   └── faiss_store.py        # FAISS vector store
├── llm/
│   ├── gateway.py            # LLM provider gateway
│   └── prompts.py            # Prompt templates
└── utils/
    ├── file_io.py            # File utilities
    └── logger.py             # Logging setup
```

## ⚙️ Configuration

### Settings (`config/settings.json`)

```json
{
  "chunk_size": 800,
  "chunk_overlap": 100,
  "top_k": 5,
  "embedding_model": "BAAI/bge-m3",
  "auto_index": true,
  "watch_interval_seconds": 30
}
```

### API Keys (`config/api_keys.local.json`)

Created automatically when you save keys in the UI. Never commit this file.

## 🔧 Troubleshooting

### Model Download Slow

The first run will download the bge-m3 model (~2.5GB). This is normal. Subsequent runs use the cached model.

### Out of Memory

- Reduce `chunk_size` in settings
- Close other applications
- Use `faiss-cpu` instead of `faiss-gpu` (already configured)

### API Key Not Persisting

Ensure `config/api_keys.local.json` is writable. The app saves keys automatically when you click **Save API Key**.

### No Documents Found

- Check that your folder path is correct
- Ensure PDFs have `.pdf` extension
- Click **Sync Folder** to force a rescan

## 🛡️ Security

- API keys are stored locally in `config/api_keys.local.json`
- No data is sent to external servers except LLM API calls
- All embeddings are generated locally
- FAISS index stays on your machine

## 📝 License

MIT License — Free for personal and commercial use.

## 🔥 Future Roadmap

- [ ] Multi-folder knowledge system
- [ ] Excel + PDF unified RAG
- [ ] Hybrid search (vector + keyword)
- [ ] Document comparison mode
- [ ] Export chat history
- [ ] Batch document upload

---

Built with ❤️ for Windows users who want local AI document intelligence.
