# 🧠 Windows 本地 RAG 系统项目重建蓝图与工程规划 (Project Reconstruction Blueprint)

本文件是 **Windows Local RAG System (Windows 本地 RAG 系统)** 的完整技术蓝图。该系统专门用于对包含复杂表格与非结构化文本的 PDF 报告进行智能提取、分析、向量检索（RAG）、报告辅助编写以及 AI Copilot 侧边栏对话。

本文件旨在提供极致详细的规划、系统架构、数据库/配置规范、核心业务逻辑流和各模块代码蓝图，以便在未来可基于此文档百分之百重新构建该软件。

---

## 目录
1. [系统总体概述与技术栈](#1-系统总体概述与技术栈)
2. [项目目录树结构](#2-项目目录树结构)
3. [依赖环境与启动器说明](#3-依赖环境与启动器说明)
4. [系统配置规范 (Configuration Specifications)](#4-系统配置规范-configuration-specifications)
5. [核心业务模块架构与代码蓝图](#5-核心业务模块架构与代码蓝图)
   - [5.1 路径管理模块 (`utils/paths.py`)](#51-路径管理模块-utilspathspy)
   - [5.2 文件 IO 工具与原子写入 (`utils/file_io.py`)](#52-文件-io-工具与原子写入-utilsfile_iopy)
   - [5.3 线程级后台任务管理器 (`utils/background_task.py`)](#53-线程级后台任务管理器-utilsbackground_taskpy)
   - [5.4 PDF 提取与智能表格重建 (`core/pdf_loader.py`)](#54-pdf-提取与智能表格重建-corepdf_loaderpy)
   - [5.5 边界保持文本切片器 (`core/chunker.py`)](#55-边界保持文本切片器-corechunkerpy)
   - [5.6 向量维度探测与鲁棒嵌入 (`core/embedder.py`)](#56-向量维度探测与鲁棒嵌入-coreembedderpy)
   - [5.7 基础向量检索器 (`core/retriever.py` 与 `vectorstore/faiss_store.py`)](#57-基础向量检索器-coreretrieverpy-与-vectorstorefaiss_storepy)
   - [5.8 LLM 驱动的重排器 (`core/reranker.py`)](#58-llm-驱动的重排器-corererankerpy)
   - [5.9 多提供商大模型网关 (`llm/gateway.py`)](#59-多提供商大模型网关-llmgatewaypy)
   - [5.10 结构化数据提取与时间过滤器 (`core/data_extractor.py` & `core/report_generator.py`)](#510-结构化数据提取与时间过滤器-coredata_extractorpy--corereport_generatorpy)
6. [Streamlit 界面主题与 Fluent Design 渲染](#6-streamlit-界面主题与-fluent-design-渲染)
7. [UI 交互与控制面板设计蓝图](#7-ui-交互与控制面板设计蓝图)
   - [7.1 浮动设置对话框 UI (`ui/api_settings.py`)](#71-浮动设置对话框-ui-uiapi_settingspy)
   - [7.2 报告画板与 AI 侧边栏 UI (`ui/report_generator.py`)](#72-报告画板与-ai-侧边栏-ui-uireport_generatorpy)
8. [系统重建运行指南](#8-系统重建运行指南)

---

## 1. 系统总体概述与技术栈

本系统的定位是 **单机免部署、对 Windows 用户极其友好的本地知识库报告生成与辅助编写工具**。

### 核心功能
1. **多目录监控与文档索引**：支持选择多个 PDF 文件夹进行后台增量同步，支持单个 PDF 上传。
2. **智能表格结构保持**：突破传统 PDF 提取的“分行错乱”问题，利用 PyMuPDF 内置表格解析引擎和上下文启发式算法重构表格数据。
3. **鲁棒的向量模型适配**：支持火山引擎、讯飞星火、DeepSeek、OpenAI、Nvidia 等各类兼容 OpenAI 规范的 API 嵌入服务。系统支持“一呼探测维度”，自动匹配 FAISS 的 Index 维度。
4. **两阶段检索 (Retrieve & Rerank)**：第一阶段基于 FAISS 进行内积最大化相似检索；第二阶段调用 LLM 重排器进行精细化相关性评分排序，过滤低噪切片。
5. **Edge Copilot 风格画板**：左侧为 Markdown 实时编辑、渲染、保存画板（Canvas），支持下载为 MD/HTML（集成 Chart.js 可视化图表）；右侧为 Copilot 对话，支持一键将 AI 建议应用到 Canvas，或让 AI 直接更新 Canvas。

### 核心技术栈
- **UI 框架**：Streamlit >= 1.40.0 (利用 Dialogs, Columns, Segmented Control 实现多栏布局)
- **文档解析**：PyMuPDF (fitz) >= 1.24.0 (支持页面布局块分析与表格对象提取)
- **向量数据库**：FAISS-CPU >= 1.8.0 (轻量、无服务的内积检索模式 `IndexFlatIP`)
- **HTTP 客户端**：Httpx >= 0.27.0 (异步/同步请求大模型接口，具有重试机制)
- **大语言模型协议**：OpenAI Python SDK >= 1.30.0 (支持 OpenAI 兼容格式网关)

---

## 2. 项目目录树结构

重建该应用时，必须严格遵守以下目录及命名规范：

```
windows-rag-system/
├── app.py                    # Streamlit 应用主入口
├── requirements.txt          # 项目依赖包声明
├── run.cmd                   # 双击一键启动脚本
├── README.md                 # 说明文档
├── config/
│   ├── settings.json         # 核心系统设置 (分片、检索阈值、向量模型等)
│   ├── api_keys.json         # API 提供商模板配置
│   └── api_keys.local.json   # 用户配置的本地 API 密钥存储（运行时动态生成，不应提交 git）
├── data/
│   ├── documents/            # 默认扫描的源 PDF 文件夹（用户将 PDF 放入此目录）
│   ├── uploads/              # UI 手动上传的 PDF 文件存储目录
│   ├── reports/              # 用户保存的 Canvas 报告（JSON 格式）
│   ├── copilot_history/      # AI 聊天会话历史（JSON 格式）
│   ├── vectors/
│   │   ├── faiss.index       # FAISS 序列化向量索引文件
│   │   └── metadata.pkl      # 序列化的分片元数据映射 (Pickle 格式)
│   └── metadata/
│       └── doc_index.json    # 文件扫描状态注册表 (哈希值、状态、分片数)
├── core/
│   ├── __init__.py
│   ├── api_persistence.py    # API 密钥与服务商信息持久化读写
│   ├── pdf_loader.py         # PDF 文字与表格混合提取引擎
│   ├── chunker.py            # 分片大小控制与表格边界保持切片器
│   ├── embedder.py           # API 向量嵌入与维度自探测
│   ├── retriever.py          # 召回阶段逻辑
│   ├── reranker.py           # 精排重定位打分器
│   ├── rag_pipeline.py       # RAG 执行流编排
│   ├── data_extractor.py     # 正则结合上下文的指标与日期提取器
│   └── report_generator.py   # 自定义报告生成与 Markdown 切块解析
├── ui/
│   ├── __init__.py
│   ├── theme.py              # 流畅设计 CSS 注入和深浅色模式适配
│   ├── api_settings.py       # 统一设置面板 UI (包含文档管理与 API 配置)
│   └── report_generator.py   # 画板与 Copilot 双栏核心 UI 控制
└── utils/
    ├── __init__.py
    ├── paths.py              # 绝对路径配置中心
    ├── file_io.py            # 鲁棒性读写与原子化文件替换
    ├── logger.py             # 标准日志记录器
    └── background_task.py    # 流式后台工作线程封装
```

---

## 3. 依赖环境与启动器说明

### requirements.txt 配置文件
```text
streamlit>=1.40.0
pymupdf>=1.24.0
faiss-cpu>=1.8.0
numpy>=1.26.0
pandas>=2.0.0
python-dotenv>=1.0.0
openai>=1.30.0
packaging
```

### run.cmd 脚本
为应对用户移动文件夹导致的绝对路径失效，`run.cmd` 必须使用本地 Python `python -m streamlit run app.py` 方式拉起应用，不能直接使用 `streamlit.exe`。
```cmd
@echo off
cd /d "%~dp0"
chcp 65001 >nul
cls
title Windows RAG System

echo ============================================
echo    Windows Local RAG System Launcher
echo ============================================

if not exist "app.py" (
    echo [ERROR] app.py not found. Run this from the project root.
    pause
    exit /b 1
)

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed. Please install Python 3.11+
    pause
    exit /b 1
)

if not exist "venv\Scripts\activate.bat" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate

echo [INFO] Resolving Python dependencies...
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    python -m pip install -r requirements.txt
)

:: Create local database directory layout
if not exist "data\documents" mkdir "data\documents"
if not exist "data\uploads" mkdir "data\uploads"
if not exist "data\vectors" mkdir "data\vectors"
if not exist "data\metadata" mkdir "data\metadata"

echo Starting Streamlit App on http://localhost:8501...
python -m streamlit run app.py
deactivate
```

---

## 4. 系统配置规范 (Configuration Specifications)

### `config/settings.json` (核心设置)
```json
{
  "chunk_size": 4096,
  "chunk_overlap": 500,
  "top_k": 25,
  "embedding_provider": "nvidia",
  "embedding_model": "nvidia/nv-embed-v1",
  "rerank_enabled": true,
  "rerank_model": "nv-rerank-qa-mistral-4b:1",
  "rerank_top_k": 10,
  "vector_store": "faiss",
  "ui_theme": "fluent_dark",
  "sidebar_width": 320,
  "max_upload_size_mb": 100,
  "supported_extensions": [".pdf"],
  "auto_index": true,
  "watch_interval_seconds": 30
}
```

### `config/api_keys.json` (初始密钥模板)
```json
{
  "providers": {},
  "default_provider": "",
  "default_model": ""
}
```

### `config/api_keys.local.json` (已配服务商样例)
```json
{
  "providers": {
    "deepseek-v4": {
      "base_url": "https://api.deepseek.com/v1",
      "models": ["deepseek-chat", "deepseek-coder"],
      "api_key": "sk-your-deepseek-key",
      "description": "DeepSeek API Presets"
    },
    "local-server": {
      "base_url": "http://localhost:8000/v1",
      "models": ["local-model"],
      "api_key": "not-needed",
      "description": "Local mock server"
    }
  },
  "default_provider": "deepseek-v4",
  "default_model": "deepseek-chat"
}
```

---

## 5. 核心业务模块架构与代码蓝图

### 5.1 路径管理模块 (`utils/paths.py`)
确保应用被移动至系统任何位置时，绝对路径仍能自动重定位。
```python
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

CONFIG_DIR: Path = PROJECT_ROOT / "config"
DATA_DIR: Path = PROJECT_ROOT / "data"

VECTOR_DIR: Path = DATA_DIR / "vectors"
METADATA_DIR: Path = DATA_DIR / "metadata"
UPLOADS_DIR: Path = DATA_DIR / "uploads"
REPORTS_DIR: Path = DATA_DIR / "reports"
DOCUMENTS_DIR: Path = DATA_DIR / "documents"

SETTINGS_PATH: Path = CONFIG_DIR / "settings.json"
API_KEYS_LOCAL_PATH: Path = CONFIG_DIR / "api_keys.local.json"
API_KEYS_PATH: Path = CONFIG_DIR / "api_keys.json"

DOC_INDEX_PATH: Path = METADATA_DIR / "doc_index.json"
FAISS_INDEX_PATH: Path = VECTOR_DIR / "faiss.index"
FAISS_METADATA_PATH: Path = VECTOR_DIR / "metadata.pkl"
```

### 5.2 文件 IO 工具与原子写入 (`utils/file_io.py`)
防止在写入元数据索引或配置文件时，系统崩溃或断电造成文件损毁。这里采用 **写入临时文件 + Windows 锁定轮询重试替换** 策略。
```python
import json
import os
import time
import tempfile
import hashlib
from pathlib import Path
from typing import Any

def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

def read_json(path: str | Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def write_json(path: str | Path, data: dict[str, Any], indent: int = 2) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    
    # 写入同一文件夹下的隐秘临时文件中，防跨分区移动失败
    fd, tmp_path = tempfile.mkstemp(
        dir=str(p.parent),
        prefix="." + p.name + ".",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
        
        # 轮询替换，应对 Windows 杀毒软件或 IDE 锁死文件
        for attempt in range(5):
            try:
                os.replace(tmp_path, str(p))
                break
            except PermissionError:
                if attempt < 4:
                    time.sleep(0.05 * (2 ** attempt))
                    continue
                raise
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

def file_hash(path: str | Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
```

### 5.3 线程级后台任务管理器 (`utils/background_task.py`)
用于 Streamlit 执行长时间的同步文件夹与重置索引动作，保证前端 UI 在扫描与切片过程中绝不假死。
```python
import threading
from typing import Callable, Any, Tuple, Dict, Optional

class BackgroundTask:
    def __init__(self, target: Callable, args: Tuple = (), kwargs: Optional[Dict[str, Any]] = None):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        self.thread: Optional[threading.Thread] = None
        self.result: Any = None
        self.error: Optional[Exception] = None
        self.is_running: bool = False
        self.is_done: bool = False

    def start(self) -> None:
        self.is_running = True
        self.is_done = False
        self.result = None
        self.error = None
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()

    def _run(self) -> None:
        try:
            self.result = self.target(*self.args, **self.kwargs)
        except Exception as e:
            self.error = e
        finally:
            self.is_running = False
            self.is_done = True
```

### 5.4 PDF 提取与智能表格重建 (`core/pdf_loader.py`)
这是整个系统的灵魂功能之一。它不仅提取 PDF 的常规段落文本，还会主动检测 PDF 原生的表格对象，将其重新组装为列键值对应的特殊符号行，保证 LLM 能够在上下文中读懂行列属性。
```python
import fitz  # PyMuPDF
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class PDFDocument:
    source: str
    text: str
    pages: int
    metadata: dict

def _reconstruct_tables(text: str) -> str:
    """启发式：将 PDF 中解析出因间距导致多行错开的单元格重构成 ' | ' 分割的行"""
    lines = text.split('\n')
    if not lines:
        return text

    result_lines = []
    buffer = []
    buffer_len = 0

    def flush_buffer():
        if not buffer:
            return
        result_lines.append(' | '.join(buffer))
        buffer.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_buffer()
            result_lines.append('')
            buffer_len = 0
            continue
        if len(stripped) > 60:  # 长段落通常非表格
            flush_buffer()
            result_lines.append(stripped)
            buffer_len = 0
            continue
        if buffer and buffer_len + len(stripped) > 120:
            flush_buffer()
        buffer.append(stripped)
        buffer_len += len(stripped)

    flush_buffer()
    return '\n'.join(result_lines)

def _format_table_rows(rows: List[List[str]]) -> str:
    """把 PyMuPDF 表格转换为带 COLUMNS 前缀的自描述格式，避免位置错乱"""
    if not rows or len(rows) <= 1:
        return ""
    header = rows[0]
    col_labels = [str(cell).strip() if cell else f"COL_{i}" for i, cell in enumerate(header)]
    
    data_lines = []
    for row in rows[1:]:
        cells = [str(cell).strip() if cell else "" for cell in row]
        if any(cells):
            labeled = [f"{col_labels[i]}: {cell}" for i, cell in enumerate(cells) if cell]
            data_lines.append(" | ".join(labeled))

    if not data_lines:
        return ""
    return "COLUMNS: " + " | ".join(col_labels) + "\n---\n" + "\n".join(data_lines)

def load_pdf(path: str | Path) -> PDFDocument:
    path = Path(path)
    doc = fitz.open(str(path))
    text_parts = []
    table_parts = []

    for page in doc:
        # 优先使用 fitz 结构化表格组件
        try:
            tab = page.find_tables()
            if tab and hasattr(tab, 'tables'):
                for t in tab.tables:
                    fmt = _format_table_rows(t.extract())
                    if fmt:
                        table_parts.append(fmt)
        except Exception:
            pass
        
        # 获取段落文本，经过启发式排版复原器
        txt = page.get_text()
        if txt and txt.strip():
            text_parts.append(_reconstruct_tables(txt))

    full_parts = []
    if table_parts:
        full_parts.append("=== TABLE DATA ===")
        full_parts.extend(table_parts)
        full_parts.append("=== DOCUMENT TEXT ===")
    full_parts.extend(text_parts)
    full_text = "\n\n".join(full_parts)

    # 兜底抓取
    if len(full_text.strip()) < 100:
        for page in doc:
            blocks = page.get_text("blocks")
            if blocks:
                full_text += "\n\n" + "\n".join([b[4].strip() for b in blocks if len(b) > 4 and b[4].strip()])

    metadata = {
        "title": doc.metadata.get("title", "") or path.stem,
        "author": doc.metadata.get("author", ""),
        "page_count": len(doc),
        "source": str(path),
    }
    doc.close()
    return PDFDocument(str(path), full_text, len(doc), metadata)
```

### 5.5 边界保持文本切片器 (`core/chunker.py`)
在切分长文档时，避免将表格区域的内容斩断到不同的切片里。
```python
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List

MIN_MEANINGFUL_CHUNK_LEN = 50

@dataclass
class TextChunk:
    content: str
    source: str
    page: int
    chunk_index: int
    total_chunks: int

class TextChunker:
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _split_text(self, text: str) -> List[str]:
        # 检测表格起始和截止的范围索引，跳过针对这部分的细碎切分
        regions = self._detect_table_regions(text)
        if regions:
            raw = self._split_with_tables(text, regions)
        else:
            raw = self._split_paragraphs(text)
            
        # 移除空值或无意义的指示分界线
        return [
            c for c in raw 
            if len(c.strip()) >= MIN_MEANINGFUL_CHUNK_LEN
            and not re.match(r'^===\s*[^=]+\s*===$', c.strip())
        ]

    def _detect_table_regions(self, text: str) -> List[tuple[int, int]]:
        regions = []
        lines = text.split('\n')
        in_table = False
        start_offset = -1
        
        for i, line in enumerate(lines):
            if '=== TABLE DATA ===' in line:
                in_table = True
                start_offset = self._line_to_offset(text, lines, i)
                continue
            if in_table and line.startswith('=== '):
                end_offset = self._line_to_offset(text, lines, i)
                regions.append((start_offset, end_offset))
                in_table = False
                start_offset = -1
        if in_table and start_offset >= 0:
            regions.append((start_offset, len(text)))
        return regions

    def _line_to_offset(self, text: str, lines: List[str], line_idx: int) -> int:
        return min(sum(len(lines[j]) + 1 for j in range(line_idx)), len(text))

    def _split_with_tables(self, text: str, regions: List[tuple[int, int]]) -> List[str]:
        chunks = []
        last_end = 0
        for start, end in sorted(regions):
            if start > last_end:
                chunks.extend(self._split_paragraphs(text[last_end:start]))
            chunks.append(text[start:end].strip()) # 表格一调整体保留
            last_end = end
        if last_end < len(text):
            chunks.extend(self._split_paragraphs(text[last_end:]))
        return chunks

    def _split_paragraphs(self, text: str) -> List[str]:
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        chunks = []
        current = ""
        for p in paragraphs:
            if len(current) + len(p) + 2 <= self.chunk_size:
                current += ("\n\n" + p if current else p)
            else:
                if current: chunks.append(current)
                current = p
        if current: chunks.append(current)
        
        # 若仍有超大段，按照标点分句
        final_chunks = []
        for c in chunks:
            if len(c) > self.chunk_size * 1.5:
                sents = re.split(r'(?<=[.!?。！？])\s+', c)
                tmp = ""
                for s in sents:
                    if len(tmp) + len(s) + 1 <= self.chunk_size:
                        tmp += (" " + s if tmp else s)
                    else:
                        if tmp: final_chunks.append(tmp)
                        tmp = s
                if tmp: final_chunks.append(tmp)
            else:
                final_chunks.append(c)
        return final_chunks

    def chunk_document(self, text: str, source: str, page: int = 1) -> List[TextChunk]:
        filename = Path(source).stem
        # 兼容性归一化：将诸如 Sept/ 归一化为 Sep/ 以便后期做时序正则和检索匹对
        text = re.sub(r'\bSept/', 'Sep/', text)
        text = f"[File: {filename}] {text}"
        
        raw = self._split_text(text)
        chunks = []
        for i, block in enumerate(raw):
            if i > 0 and self.chunk_overlap > 0:
                prev = raw[i - 1]
                overlap = prev[-self.chunk_overlap:]
                block = overlap + "\n" + block
            chunks.append(TextChunk(block, source, page, i, len(raw)))
        return chunks
```

### 5.6 向量维度探测与鲁棒嵌入 (`core/embedder.py`)
当用户变更第三方 Embedding 模型时，系统不能假设向量维度固定为 1536 或 1024。在此处通过向 API 发送一个 `"hello"` 探测词，获取实际返回的 Vector 大小，用来无缝更新本地的 FAISS 属性。
```python
import httpx
import numpy as np
from typing import List, Dict

class APIEmbedder:
    def __init__(self, model_name: str, base_url: str, api_key: str):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._actual_dimension = None

    def detect_dimension(self, probe_text: str = "hello") -> int:
        try:
            embs = self._embed_api([probe_text])
            self._actual_dimension = embs.shape[1]
            return self._actual_dimension
        except Exception:
            # 兜底降级默认 1024
            return 1024

    def embed(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self._actual_dimension or 1024))
        return self._embed_api(texts)

    def embed_query(self, query: str) -> np.ndarray:
        return self.embed([query])[0]

    def _get_endpoint_urls(self) -> List[str]:
        # 针对有些用户把 base_url 写成 http://...v1，有些写成 http://...v1/embeddings 的鲁棒适应
        url = self.base_url
        if url.endswith("/embeddings"):
            return [url, url.replace("/v2/", "/v1/")]
        return [f"{url}/embeddings"]

    def _embed_api(self, texts: List[str]) -> np.ndarray:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        endpoints = self._get_endpoint_urls()
        last_err = None
        
        for endpoint in endpoints:
            try:
                payload = {
                    "model": self.model_name,
                    "input": texts if len(texts) > 1 else texts[0]
                }
                with httpx.Client(timeout=60.0) as client:
                    resp = client.post(endpoint, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                
                # 多种返回协议解析支持
                raw_vectors = self._parse_response(data)
                return np.array(raw_vectors, dtype=np.float32)
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError(f"Embedding API request failed: {last_err}")

    def _parse_response(self, data: dict) -> List[List[float]]:
        # OpenAI标准格式
        if "data" in data and isinstance(data["data"], list):
            items = data["data"]
            if items and "embedding" in items[0]:
                return [item["embedding"] for item in items]
            return items
        # 其他一些国产API专有格式
        if "embeddings" in data:
            return data["embeddings"]
        if isinstance(data, list):
            return data
        raise ValueError("Invalid format returned by embedding API.")
```

### 5.7 基础向量检索器 (`core/retriever.py` 与 `vectorstore/faiss_store.py`)
检索逻辑分为 FAISS 的添加/存储，以及 Retriever 对 FAISS 的快速查询封装。

#### `vectorstore/faiss_store.py`
```python
import faiss
import pickle
import numpy as np
from pathlib import Path
from typing import List, Dict, Any

class FAISSStore:
    def __init__(self, dimension: int, index_path: Path, metadata_path: Path):
        self.dimension = dimension
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.metadata: List[Dict[str, Any]] = []
        self.id_map: Dict[int, str] = {}
        self._index = None
        self._next_id = 0

    @property
    def index(self) -> faiss.Index:
        if self._index is None:
            if self.index_path and self.index_path.exists():
                self._index = faiss.read_index(str(self.index_path))
                self._next_id = self._index.ntotal
            else:
                # 内积匹配（Inner Product），对于预先归一化的嵌入向量等价于余弦相似度
                self._index = faiss.IndexFlatIP(self.dimension)
        return self._index

    def add(self, embeddings: np.ndarray, chunks: List[Dict[str, Any]]) -> None:
        if len(embeddings) == 0:
            return
        # 归一化保障内积为标准余弦值
        faiss.normalize_L2(embeddings)
        self.index.add(embeddings.astype(np.float32))
        for chunk in chunks:
            self.id_map[self._next_id] = chunk.get("id", f"chunk_{self._next_id}")
            self.metadata.append(chunk)
            self._next_id += 1

    def search(self, query_emb: np.ndarray, k: int = 5, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        if self.index.ntotal == 0:
            return []
        
        query_emb = np.array(query_emb).astype(np.float32).reshape(1, -1)
        faiss.normalize_L2(query_emb)
        scores, indices = self.index.search(query_emb, min(k, self.index.ntotal))
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            meta = self.metadata[idx]
            if filters and not all(meta.get(key) == val for key, val in filters.items()):
                continue
            results.append({
                "content": meta.get("content", ""),
                "source": meta.get("source", ""),
                "score": float(score),
                "metadata": meta,
            })
        return results

    def save(self) -> None:
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_path, "wb") as f:
            pickle.dump({
                "metadata": self.metadata,
                "id_map": self.id_map,
                "next_id": self._next_id
            }, f)
        faiss.write_index(self.index, str(self.index_path))

    def load(self) -> bool:
        if self.index_path.exists() and self.metadata_path.exists():
            self._index = faiss.read_index(str(self.index_path))
            with open(self.metadata_path, "rb") as f:
                data = pickle.load(f)
            self.metadata = data["metadata"]
            self.id_map = data["id_map"]
            self._next_id = data["next_id"]
            return True
        return False

    def clear(self) -> None:
        self._index = faiss.IndexFlatIP(self.dimension)
        self.metadata = []
        self.id_map = {}
        self._next_id = 0
```

#### `core/retriever.py`
```python
from typing import List, Dict, Any

class DocumentRetriever:
    def __init__(self, vector_store, embedder, top_k: int = 5, reranker = None):
        self.vector_store = vector_store
        self.embedder = embedder
        self.top_k = top_k
        self.reranker = reranker

    def retrieve(self, query: str, filters: Dict[str, Any] = None, top_k: int = None, rerank: bool = None) -> List[Dict[str, Any]]:
        k = top_k or self.top_k
        search_k = k
        
        # 启用重排时，先从向量中扩大 3 倍检索作为池子
        do_rerank = (rerank is True) or (rerank is None and self.reranker is not None)
        if do_rerank:
            search_k = k * 3

        query_emb = self.embedder.embed_query(query)
        results = self.vector_store.search(query_emb, k=search_k, filters=filters)
        
        if do_rerank and self.reranker:
            results = self.reranker.rerank(query, results, top_k=k)
        return results[:k]
```

### 5.8 LLM 驱动的重排器 (`core/reranker.py`)
在 RAG 系统中，单纯靠 Embedding 向量检索容易被干扰项误导。本系统通过专有接口向指定的重排模型（Reranker）发送召回的多个切片，要求模型从相关性维度进行打分排序并截断。
```python
import json
import re
from openai import OpenAI
from typing import List, Dict, Any

class Reranker:
    def __init__(self, model: str, base_url: str, api_key: str):
        self.model = model
        self.client = OpenAI(base_url=base_url, api_key=api_key or "dummy")

    def rerank(self, query: str, results: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        if not results or len(results) <= top_k:
            return results[:top_k]

        try:
            docs_text = "\n\n".join(
                f"[{i+1}] {r.get('content', '')[:500]}"
                for i, r in enumerate(results)
            )
            system_prompt = """You are a relevance scoring assistant. Rate each document's relevance to the query on a scale of 1-10.
Respond ONLY with a JSON array in this exact format:
[{"id": 1, "score": 8}, {"id": 2, "score": 3}, ...]"""
            
            user_prompt = f"Query: {query}\n\nDocuments:\n{docs_text}\n\nScore each document."
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            raw_text = response.choices[0].message.content or ""
            scores = self._parse_scores(raw_text, len(results))
            
            for i, score in enumerate(scores):
                results[i]["rerank_score"] = score
                
            results.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
            return results[:top_k]
        except Exception:
            return results[:top_k]

    def _parse_scores(self, text: str, num_docs: int) -> List[float]:
        try:
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                scores = [0.0] * num_docs
                for item in data:
                    idx = item.get("id", 0) - 1
                    if 0 <= idx < num_docs:
                        scores[idx] = float(item.get("score", 0))
                return scores
        except Exception:
            pass
        return [5.0] * num_docs
```

### 5.9 多提供商大模型网关 (`llm/gateway.py`)
网关负责对接各种大语言模型，并负责流式 (`stream_chat`) 与非流式 (`chat`) 的输出管理。
```python
from openai import OpenAI
from typing import Generator, Dict, Any

class LLMGateway:
    def __init__(self, config_path, fallback_path):
        self.config = self._load_config(config_path, fallback_path)
        self.provider = self.config.get("default_provider", "")
        self.model = self.config.get("default_model", "")
        self.client = None
        self._init_client()

    def _load_config(self, primary, fallback) -> Dict[str, Any]:
        # 详见 persistence 读取逻辑，合并环境变量
        from utils.file_io import read_json
        import os
        config = read_json(primary) or read_json(fallback)
        for provider_name in config.get("providers", {}):
            env_key = os.getenv(f"{provider_name.upper().replace('-', '_')}_API_KEY")
            if env_key:
                config["providers"][provider_name]["api_key"] = env_key
        return config

    def _init_client(self):
        if not self.provider or not self.model: return
        pconf = self.config.get("providers", {}).get(self.provider, {})
        base_url = pconf.get("base_url", "")
        api_key = pconf.get("api_key", "")
        
        # 兼容性微调：针对没有写 /v1 的非云端国内提供商
        if base_url and not base_url.endswith("/v1") and not base_url.endswith("/v1/"):
            if "googleapis.com" not in base_url and "anthropic.com" not in base_url:
                base_url = base_url.rstrip("/") + "/v1"
                
        self.client = OpenAI(base_url=base_url, api_key=api_key or "dummy")

    def chat(self, query: str, context: str, system_prompt: str = None) -> str:
        if not self.client:
            return "API not configured."
        sys_p = system_prompt or "Answer based ONLY on the provided context."
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": sys_p},
                    {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
                ],
                temperature=0.3
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            return f"Error: {e}"

    def stream_chat(self, query: str, context: str, system_prompt: str = None) -> Generator[str, None, None]:
        if not self.client:
            yield "API not configured."
            return
        sys_p = system_prompt or "Answer based ONLY on the provided context."
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": sys_p},
                    {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
                ],
                temperature=0.3,
                stream=True
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            yield f"Error: {e}"
```

### 5.10 结构化数据提取与时间过滤器 (`core/data_extractor.py` & `core/report_generator.py`)
在生成最终报告前，`ReportGenerator` 可以利用正则从匹配片段中提取关键数据点（如性能效率指标、COP值、日期时间等）。
```python
# core/data_extractor.py
import re
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class ExtractedDataPoint:
    type: str  # 'date', 'number', 'metric'
    value: str
    context: str
    source: str
    page: int
    confidence: float = 1.0

class DataExtractor:
    DATE_PATTERNS = [
        r'\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b',
        r'\b(Q[1-4])\s+(\d{4})\b',
        r'\b(20\d{2})\b'
    ]
    METRIC_KEYWORDS = ["COP", "能效", "电耗", "能耗", "efficiency", "savings"]

    def extract_from_chunks(self, chunks: List[Dict[str, Any]]) -> List[ExtractedDataPoint]:
        results = []
        for chunk in chunks:
            content = chunk.get("content", "")
            source = chunk.get("source", "")
            page = chunk.get("page", 1)
            
            # 正则匹配日期
            for pattern in self.DATE_PATTERNS:
                for match in re.finditer(pattern, content):
                    results.append(ExtractedDataPoint(
                        type="date", value=match.group(0),
                        context=content[max(0, match.start()-30):min(len(content), match.end()+30)].strip(),
                        source=source, page=page, confidence=0.9
                    ))
            
            # 指标检索
            for kw in self.METRIC_KEYWORDS:
                pattern = rf'\b{kw}\b[^.\n]{{0,30}}?(\d+(?:\.\d+)?%?)'
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    results.append(ExtractedDataPoint(
                        type="metric", value=match.group(0),
                        context=content[max(0, match.start()-30):min(len(content), match.end()+30)].strip(),
                        source=source, page=page, confidence=0.95
                    ))
        return results
```

---

## 6. Streamlit 界面主题与 Fluent Design 渲染

本系统采用了极具微软 Fluent Design (流畅设计) 风格的现代玻璃质感（Glassmorphism）CSS 覆盖注入方案，适配 Streamlit 的深浅色转换。

以下为 UI 渲染所用的定制 CSS 主干逻辑（位于 `ui/theme.py`）：
- **深浅色自适应变量**：`--bg0`, `--bg1`, `--accent`, `--border` 等。
- **元素覆盖**：隐藏 Streamlit 默认的 Header 和侧边栏多余的折叠按键。
- **对话框和弹出层特殊适配**：Streamlit 的 `st.dialog` 和 `st.popover` 的底色覆盖。
- **Canvas 卡片视觉效果**：提供三维卡片阴影 `.card` 和高光阴影 `.accent-card`。
- **Markdown 画板与表格渲染规范**：包裹 `.table-wrap` 的响应式表格布局。

---

## 7. UI 交互与控制面板设计蓝图

### 7.1 浮动设置对话框 UI (`ui/api_settings.py`)
在主页右上角或侧边顶部提供入口，弹出一个统一管理的 `large` 对话框，由两个主 Tab 组成：
- **📁 Document Settings (文档管理)**：
  - 显示当前文档总量、已导入向量数、服务就绪指示灯。
  - 通过单行输入框 + 异步校验，提供多个监控文件夹的管理（添加、清除、彻底重建）。
  - 内嵌基于 `st.file_uploader` 的单个 PDF 实时导入及切片逻辑。
  - 显示后台 `BackgroundTask` 执行的进度百分比和 toast 提示。
- **🔑 API & Model Settings (模型设置)**：
  - **Chat Models Tab**：配置当前使用的 LLM 服务商（如 DeepSeek）以及具体对话模型。
  - **Embeddings Tab**：指定向量服务商、模型名称、以及 Chunker 的 `chunk_size` 和 `chunk_overlap` 两个重要数值。
  - **Reranking Tab**：开启/关闭 Reranker 功能，配置重排模型与基础检索池大小。
  - **API Providers Tab**：增删改第三方兼容 API 的 Base URL，支持展示各渠道的活跃指示灯。

### 7.2 报告画板与 AI 侧边栏 UI (`ui/report_generator.py`)
整个软件的操作界面，布局比例为 `[7, 5]` 两栏：
- **左侧画板 (Canvas Area - 70% 宽度)**：
  - 顶部显示当前报告的标题输入框及状态。
  - 提供 Edit (Markdown 文本框编辑区) 和 Preview (HTML/CSS 高保真样式展示区) 双 Tab 交互。
  - HTML 展示区集成 Chart.js 库，识别 Markdown 里的 ` ```chart ` 段落并动态渲染图表。
  - 提供保存、载入、重命名及删除历史报告的功能。
- **右侧 AI 助手栏 (Copilot Assistant - 30% 宽度)**：
  - 聊天记录历史：支持气泡式流式加载，自动显示回答的文档引用置信度和引用文件。
  - 提供快捷指令卡片（“总结报告”、“寻找瓶颈”等）。
  - 大模型回答的系统 Prompt 拥有特殊约束：如要求模型生成带有修改指令的 ````markdown-canvas ` 标签，此时前端会自动呈现 **“应用修改到 Canvas”** 悬浮悬挂按键，用户一键即可覆盖更新左侧画板。
  - 大模型遵守 **严格防幻觉规范**，若 Context 无相关数据，直白说出“未找到事实依据”。

---

## 8. System Reconstruction Run Guide (项目重启步骤)

如果您拿到此文件夹，并想重建并立即运行系统：

1. **核对物理结构**：
   将全部代码文件放入指定目录，核对 `utils/paths.py` 的解析级别是否正常。
2. **启动虚拟环境**：
   在根目录下打开终端，双击或运行 `run.cmd`。
3. **初始化设置**：
   - 在弹出的 Streamlit 网页右上角中打开 **⚙️ Settings**。
   - 切换到 **🔑 API & Model Settings** -> **Service Providers**，添加您的 LLM & Embedding 服务端密钥（或写入 `api_keys.local.json`）。
   - 在 **🔤 Embeddings** 标签页中选定嵌入模型并保存，触发第一次探测探测。
4. **导入文档**：
   - 切换到 **📁 Document Settings**，在 `Folder Path` 输入框中填入 PDF 存放目录（如本工程自带的 `C:/Users/Ivan/Desktop/Report QA1/1. Report`）。
   - 点击 **↺ Sync** 或是 **Re-index**，系统启动后台线程开始并行抽取与 FAISS 构筑。
5. **开启分析对话**：
   - 导入完成后，在 Canvas 中创建一个新报告。
   - 在右侧输入提问，例如：“请分析 2025 年 9 月到 12 月制冷机组的系统效率变化趋势，并用柱状图显示。”
   - 点击生成的建议直接应用在左侧画板，通过 MD/HTML 按钮自由输出成果！

---
**蓝图编写时间：2026年6月**
**系统设计宗旨：本地轻量化，界面极客美观，处理数据真实防幻觉。**
