# Report QA (Windows Local Intelligent Document RAG System & Report Canvas)

**English** | [简体中文](README.zh.md)

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Tauri](https://img.shields.io/badge/Tauri-2.x-orange.svg)](https://tauri.app/)
[![FAISS](https://img.shields.io/badge/FAISS-1.8.0+-green.svg)](https://github.com/facebookresearch/faiss)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A deploy-free, high-fidelity table reconstruction, and two-stage vector retrieval (RAG) report generation system designed specifically for Windows users. Combining a dual-column Markdown Canvas editor with an Edge-Copilot style sidebar AI Assistant, the system enables secure local text and table extraction, semantic search, and dynamic Chart.js chart visualization.

This application features a Microsoft Fluent Design dark theme with native-like mica translucency, dynamic data previewing, and a real-time system log panel to monitor the pipeline's progress.

---

## 🎬 Demo Video

[Watch Demo on YouTube](https://youtu.be/VLMLq1FwVYc?si=4o5Lie32L2jJpf1C)

---

## 📸 Interface Preview

### 1. Initial Dashboard
A clean, modern Fluent Design interface. The left panel serves as the writing Canvas area, and the right panel hosts the Copilot AI assistant sidebar. The sidebar boundary is fully draggable to easily customize panel widths:
![Initial Dashboard](./docs/images/initial_dashboard.png)

### 2. AI Copilot Chat & Canvas Auto-Reconstruction
When a query is entered (e.g., "Find the EFF data for the past 12 months"), the system executes RAG retrieval with precise source citations. If the assistant's answer includes document modifications, the Canvas dynamically renders the **12-month chiller efficiency table** and an interactive **Chart.js bar chart**:
![Processed Preview and Success](./docs/images/processed_data.png)

### 3. Markdown Editor & Dual-Column Sync
Click **Edit** in the floating toolbar at the top-left of the Canvas to switch the editor to Markdown source mode. It supports raw Markdown text editing and custom `~~~chart-config` blocks for chart configurations:
![Markdown Editor](./docs/images/edit_mode.png)

### 4. Centered Settings Panel & API Configuration
Click the **Gear (Settings)** icon in the top-right corner to open the centered settings dialog. Easily add target document folders under the `Documents` tab, and dynamically configure providers and API keys under the `API & Models` tab (all sensitive data is saved locally):
![Settings Dialog](./docs/images/settings_dialog.png)

---

## 🚀 Key Features

Report QA runs a sequential RAG retrieval and document compilation pipeline:

1. **📁 Smart Document Import & Monitor**
   - Supports incremental multi-folder background scanning and manual PDF uploads.
   - Automatically extracts text, performs MD5 hash checks, and constructs vector chunks.

2. **📊 High-Fidelity Table Reconstruction**
   - Resolves text alignment errors typical of PDF parsers by combining PyMuPDF's table extraction engine with custom row boundary restoration heuristics.
   - Ensures tabular data aligns perfectly with columns and header categories.

3. **🔤 Embedding Dimension Auto-Detection**
   - Supports any OpenAI-compatible API embedding provider.
   - Automatically probes the model with a dummy request to detect vector dimensions, removing the need to configure FAISS dimensions manually.

4. **🔍 Two-Stage Retrieval (Retrieve & Rerank)**
   - **Stage 1 (Retrieval)**: High-speed cosine similarity search using FAISS Inner Product to fetch relevant text and table chunks.
   - **Stage 2 (Reranking)**: Optional LLM-based Reranker that scores chunk relevance from 1-10 to refine context quality, filtering out irrelevant noise.

5. **💬 Citations & Strict Anti-Hallucination**
   - Answers include clickable inline reference tags with similarity confidence scores.
   - Strictly instructed to say "information not found" rather than inventing statistics when data is absent in the retrieved context.

6. **🚀 Dynamic Writing Canvas Panel**
   - Features **Edit** (Markdown code) and **Preview** (Fluent-styled HTML layout) tabs.
   - Recognizes custom chart configurations to automatically render interactive bar and line graphs using Chart.js.
   - Supports exporting reports directly as `.md` or standalone `.html` files containing embedded visualization scripts for offline presentations.

---

## 🛠️ Step-by-Step Walkthrough with Chiller Efficiency Report

To perform a test run with a folder containing monthly PDF load profiles:

1. **Import and Index Files**:
   - Open **⚙️ Settings** -> **📁 Document Settings**.
   - Enter the absolute path of the target folder containing monthly PDFs, click **Add**, and click **Re-index** to start background multi-threaded indexing.
2. **Query the Copilot**:
   - Once indexing is complete, enter the prompt: "找出过去12个月的eff数据，并生成合适的图表" (Find the EFF data for the past 12 months and generate a suitable chart) in the Copilot sidebar.
   - Copilot retrieves text passages and answers with source references.
3. **One-Click Apply to Canvas**:
   - Click **Apply to Canvas** at the top of the Copilot's answer. The left Canvas will instantly render the structured data table and trend chart.
4. **Edit and Preview**:
   - Click **Edit** to tweak the report text, or modify the colors, ranges, or titles in the `~~~chart-config` block.
   - Switch back to **Preview** to see the high-fidelity rendered layout.
5. **Export Offline Report**:
   - Click the floating **HTML** button. The system will compile the document and save a single, standalone HTML file to your downloads folder.
   - The exported file is completely offline-capable, keeping all styling and interactive Chart.js scripts intact.

---

## 🖥️ Running Locally

### Prerequisites
* **Node.js** v18+ (LTS recommended)
* **Python** 3.11+
* **Rust** (for Tauri desktop compilation)

### Install Dependencies

#### 1. Backend Python Dependencies
Navigate to the `windows-rag-system` directory and run `run.cmd` to automatically initialize the virtual environment and install dependencies:
```cmd
cd windows-rag-system
./run.cmd
```
Or manually install using pip:
```bash
pip install -r requirements.txt
```

#### 2. Frontend Node.js Dependencies
Navigate to the `tauri-ui` directory and install:
```bash
cd tauri-ui
npm install
```

### Start Development Server

#### 1. Start Python Backend
Run the backend query script in the `windows-rag-system` directory:
```bash
python query_rag.py "test query"
```

#### 2. Start Frontend & Tauri Client
In the `tauri-ui` directory, start the hot-reloaded Tauri application shell:
```bash
npm run tauri dev
```
To run the project in a local web browser environment instead:
```bash
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

### Build Standalone App
To build the production installer:
```bash
npm run tauri build
```
The standalone installer will be outputted under `src-tauri/target/release/bundle/nsis/`.

---

## 📁 Project Structure

```
Report QA/
├── tauri-ui/                   # Tauri frontend application (React + TS + Vite)
│   ├── src/                    # Frontend React source code
│   │   ├── components/         # Canvas, Sidebar, and Settings components
│   │   ├── stores/             # Zustand global store
│   │   ├── styles/             # Fluent UI themes and Mica effects
│   │   └── main.tsx            # App entry point (with browser mock bridge)
│   ├── src-tauri/              # Tauri Rust backend
│   │   ├── src/lib.rs          # Core system commands (scans, syncs, key storage)
│   │   └── tauri.conf.json     # Tauri app configurations
│   └── package.json            # npm scripts & dependencies
└── windows-rag-system/         # Python RAG core service
    ├── config/                 # Configurations (settings.json, api_keys.json)
    ├── core/                   # RAG retriever, chunker, and reranker cores
    ├── llm/                    # Multi-provider gateway
    ├── utils/                  # Path, File IO, and Logger modules
    ├── query_rag.py            # CLI query entry point
    ├── sync_index.py           # Directory scanning and indexing sync script
    └── requirements.txt        # Python dependency declarations
```

---

## 🔧 FAQ & Troubleshooting

#### 1. Why does Document Sync or Re-indexing fail?
- Ensure the API configuration of your active Embedding provider shows as **🟢 Active** in settings.
- If you changed the embedding model, clear previous indexes by clicking **Clear Index** first, then re-trigger **Re-index**.

#### 2. Copilot answers with "API Not Configured"
- Make sure default providers are configured under Settings, the credentials have been saved successfully, and the endpoint is accessible.

#### 3. Chart displays "Chart render error"
- Ensure the JSON content in the ` ```chart ` or `~~~chart-config` block is valid. Key and string values must use **double quotes** (`"`), and there must be no trailing commas.

---

## 🛡️ Privacy & Security

- **Local Storage**: All indexed text metadata, FAISS indexes, uploads, and report draft revisions are **saved locally on your machine**.
- **API Requests**: Text snippets (Context) are sent to the external provider endpoints via encrypted HTTPS channels only during LLM generation and embedding calculations.
- **Local Mode**: Supports mock responses when using local endpoints without external credentials.

---

## License
This project is open-source under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.
By submitting a PR, you agree to license your contributions under the same [MIT License](LICENSE).

---

## Buy Me a Coffee / Support

If Report QA helped you save time and solve document search or report layout challenges, feel free to support the developer! ☕

<img src="./docs/images/%E4%B8%80%E6%9D%AF%E5%92%96%E5%95%A1.JPG" width="280" alt="Buy Me a Coffee" />
