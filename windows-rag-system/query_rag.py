import sys
from pathlib import Path
import json

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from core.embedder import APIEmbedder
from vectorstore.faiss_store import FAISSStore
from core.retriever import DocumentRetriever
from core.reranker import Reranker
from core.rag_pipeline import RAGPipeline
from llm.gateway import LLMGateway
from llm import edit_plan as ep
from utils.file_io import read_json
from utils.logger import setup_logger

logger = setup_logger("query_rag")

def read_attachment_content(file_path):
    path = Path(file_path.strip())
    if not path.exists():
        return f"[Attachment Error: File {path.name} not found]"
    
    ext = path.suffix.lower()
    
    # 1. Text files
    if ext in [".txt", ".md", ".json", ".csv", ".xml", ".html", ".css", ".js", ".py", ".ts", ".tsx"]:
        for encoding in ["utf-8", "gbk", "utf-16", "latin1"]:
            try:
                with open(path, "r", encoding=encoding) as f:
                    content = f.read()
                return f"\n--- Start of Attachment: {path.name} ---\n{content}\n--- End of Attachment: {path.name} ---\n"
            except Exception:
                continue
        return f"[Attachment Error: Could not read text content of {path.name}]"
        
    # 2. Excel spreadsheets
    elif ext in [".xlsx", ".xls"]:
        try:
            import pandas as pd
            df = pd.read_excel(path)
            return f"\n--- Start of Attachment Excel: {path.name} ---\n{df.to_string(index=False)}\n--- End of Attachment Excel: {path.name} ---\n"
        except Exception as e:
            return f"[Attachment Excel: {path.name} (Pandas parse failed: {e})]"
            
    # 3. Word files
    elif ext in [".docx"]:
        try:
            import docx
            doc = docx.Document(path)
            fullText = [para.text for para in doc.paragraphs]
            return f"\n--- Start of Attachment Word: {path.name} ---\n" + "\n".join(fullText) + f"\n--- End of Attachment Word: {path.name} ---\n"
        except Exception as e:
            return f"[Attachment Word: {path.name} (docx parse failed: {e})]"
            
    # 4. PDF files
    elif ext in [".pdf"]:
        try:
            import pypdf
            reader = pypdf.PdfReader(path)
            text = ""
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
            return f"\n--- Start of Attachment PDF: {path.name} ---\n{text}\n--- End of Attachment PDF: {path.name} ---\n"
        except Exception:
            try:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    text = "\n".join([page.extract_text() or "" for page in pdf.pages])
                return f"\n--- Start of Attachment PDF: {path.name} ---\n{text}\n--- End of Attachment PDF: {path.name} ---\n"
            except Exception as e:
                return f"[Attachment PDF: {path.name} (PDF parse failed: {e})]"
                
    # 5. Image placeholder
    elif ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
        return f"[Attachment Image: {path.name} (Image analysis context placeholder)]"
        
    return f"[Attachment Binary File: {path.name} ({ext.upper()} format)]"


def split_into_sections(document):
    """Split a Markdown document into top-level sections by ## headers.

    Returns a list of (header, body) tuples where body includes the header line.
    Content before the first ## (e.g. the # title) is treated as section -1 (preamble).
    """
    lines = document.split("\n")
    sections = []
    current_header = None
    current_lines = []
    for line in lines:
        if line.startswith("## "):
            if current_header is not None or current_lines:
                sections.append((current_header, "\n".join(current_lines)))
            current_header = line
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_header, "\n".join(current_lines)))
    return sections

def query_rag(query_text, history=None, override_provider=None, override_model=None, thinking_intensity=None, attachments=None, canvas_content=None, stream=False):
    # Process attachments if present
    attachment_context = ""
    if attachments:
        file_paths = attachments.split(",")
        for fp in file_paths:
            if fp.strip():
                attachment_context += read_attachment_content(fp)
                
    if attachment_context:
        query_text = attachment_context + "\n" + (query_text or "Please analyze the attached files.")

    # Load settings
    settings = read_json(project_root / "config" / "settings.json")
    
    # Load API keys
    api_config = read_json(project_root / "config" / "api_keys.local.json")
    if not api_config:
        api_config = read_json(project_root / "config" / "api_keys.json")
        
    # Resolve embedding provider and model
    embed_provider_name = settings.get("embedding_provider")
    if not embed_provider_name:
        embed_provider_name = api_config.get("default_provider")
    if not embed_provider_name:
        providers = api_config.get("providers", {})
        if providers:
            embed_provider_name = list(providers.keys())[0]
            
    pconf_embed = api_config.get("providers", {}).get(embed_provider_name, {}) if embed_provider_name else {}
    embed_model = settings.get("embedding_model")
    if not embed_model:
        models = pconf_embed.get("models", [])
        embed_model = models[0] if models else ""
        
    embed_base_url = pconf_embed.get("base_url", "")
    embed_api_key = pconf_embed.get("api_key", "")
    
    # Initialize LLM gateway
    gateway = LLMGateway()
    if override_provider:
        gateway.provider = override_provider
    if override_model:
        gateway.model = override_model
    if override_provider or override_model:
        gateway._init_client()
        
    if thinking_intensity:
        ti = thinking_intensity.lower()
        if ti == "low":
            gateway.temperature = 0.1
            gateway.max_tokens = 4096
        elif ti == "high":
            gateway.temperature = 0.2
            gateway.max_tokens = 16384
        else: # medium
            gateway.temperature = 0.15
            gateway.max_tokens = 8192

    # Initialize embedder and vector store for RAG search
    embedder = None
    store = None
    if embed_provider_name and embed_base_url and embed_api_key:
        try:
            embedder = APIEmbedder(
                model_name=embed_model,
                base_url=embed_base_url,
                api_key=embed_api_key,
            )
            
            store = FAISSStore(
                dimension=embedder.dimension,
                index_path=str(project_root / "data" / "vectors" / "faiss.index"),
                metadata_path=str(project_root / "data" / "vectors" / "metadata.pkl"),
            )
            store.load()
        except Exception as e:
            print(json.dumps({"error": f"Failed to initialize embedder: {e}"}))
            sys.exit(1)
            
    # Initialize Reranker if enabled
    reranker = None
    rerank_model = settings.get("rerank_model")
    if settings.get("rerank_enabled") and rerank_model:
        # Find which provider supports the rerank model
        rerank_provider = None
        for name, p in api_config.get("providers", {}).items():
            if rerank_model in p.get("models", []):
                rerank_provider = p
                break
        
        # Fallback to default provider if not found in list
        fallback_prov = api_config.get("default_provider")
        if not rerank_provider and fallback_prov:
            rerank_provider = api_config.get("providers", {}).get(fallback_prov, {})
            
        if rerank_provider:
            try:
                reranker = Reranker(
                    model=rerank_model,
                    base_url=rerank_provider.get("base_url", ""),
                    api_key=rerank_provider.get("api_key", ""),
                )
            except Exception as e:
                print(json.dumps({"error": f"Failed to initialize reranker: {e}"}))
                sys.exit(1)
        else:
            print(json.dumps({"error": f"No provider configured for rerank model: {rerank_model}"}))
            sys.exit(1)
            
    retriever = None
    if store and embedder:
        retriever = DocumentRetriever(
            vector_store=store,
            embedder=embedder,
            top_k=settings.get("top_k", 5),
            reranker=reranker,
        )

    # Classify intent (always, even if canvas is empty/None)
    classified_intent = gateway.classify_intent(query_text, canvas_content)

    # Post-classification override: if the LLM said search_kb but the user's message
    # explicitly asks to write/display/put content into the canvas, force modify_canvas.
    # This handles queries like "write a report and display it in the canvas".
    if classified_intent == "search_kb":
        _qt = query_text.lower()
        _CANVAS_WRITE_PHRASES = (
            "canvas", "put it in", "write it", "display it", "show it",
            "place it", "写入", "放入", "显示在", "写到", "放到", "生成报告",
            "generate a report", "create a report", "write a report",
            "organize.*report", "compile.*report",
        )
        if any(p in _qt for p in _CANVAS_WRITE_PHRASES):
            classified_intent = "modify_canvas"
            logger.info("Intent upgraded to modify_canvas (canvas write keyword detected in search_kb query)")

    # Retrieve RAG context if retriever is available
    retrieved_context = ""
    sources = []
    if retriever:
        try:
            results = retriever.retrieve(query_text, top_k=settings.get("top_k", 5))
            if results:
                context_parts = []
                for i, r in enumerate(results):
                    content = r.get("content", "")
                    source = f"[{i+1}] {r.get('source', 'Unknown')}"
                    context_parts.append(f"{source}\n{content}")
                    sources.append(r)
                retrieved_context = "\n\n---\n\n".join(context_parts)
        except Exception as e:
            logger.warning(f"Retrieval failed (embedding issue?): {e}")

    # Build context for LLM based on intent
    if classified_intent in ("modify_canvas", "read_canvas"):
        canvas_str = canvas_content if canvas_content else ""
        context = (
            "--- CURRENT CANVAS CONTENT (The document the user is currently viewing/editing) ---\n"
            f"{canvas_str}\n"
            "--- END OF CURRENT CANVAS CONTENT ---\n\n"
        )
        if retrieved_context:
            context += (
                "--- RETRIEVED BACKGROUND DOCUMENTS (Use this to help edit/answer/write the report) ---\n"
                f"{retrieved_context}\n"
                "--- END OF RETRIEVED BACKGROUND DOCUMENTS ---\n\n"
            )
        try:
            if stream:
                # --- Route canvas-rewrite by document size ---
                WHOLE_TRANSFORM_THRESHOLD = 12000  # chars; ~3-4k output tokens, fits 8k budget
                use_whole = len(canvas_str) < WHOLE_TRANSFORM_THRESHOLD

                full_text = ""
                full_thinking = ""
                in_thinking = False

                if use_whole:
                    sub_intent = gateway.sub_classify_modify_intent(query_text, canvas_str)
                    _surgical_done = False
                    logger.info(f"modify_canvas: size={len(canvas_str)} sub_intent={sub_intent}")

                    # ── surgical_edit: Plan/Exec with SEARCH/REPLACE ─────────
                    if sub_intent == "surgical_edit":
                        _plan_sys = (
                            "You are a surgical document editor. Generate a SEARCH/REPLACE "
                            "plan that applies the user's requested change.\n\n"
                            "Output one or more blocks in this EXACT format:\n"
                            "<<<< SEARCH\n<exact text from the document>\n"
                            "==== REPLACE\n<replacement text>\n>>>> REPLACE\n\n"
                            "Also supported: INSERT_BEFORE and INSERT_AFTER "
                            "(same format but ==== INSERT_BEFORE / >>>> INSERT_BEFORE).\n\n"
                            "Rules:\n"
                            "- SEARCH text must EXACTLY match the document (case-sensitive).\n"
                            "- Only change what the user asked for — keep everything else intact.\n"
                            "- For large sections, include enough SEARCH context to uniquely identify the location.\n"
                            "- Use multiple blocks if needed; they are applied in order.\n"
                            "- If the change is a full rewrite, output a single REPLACE block with the entire new content."
                        )
                        try:
                            plan_text, _ = gateway.chat(
                                f"CURRENT CANVAS CONTENT:\n{canvas_str}\n\nUser request: {query_text}",
                                "",
                                history=history,
                                system_prompt=_plan_sys,
                                thinking_intensity=thinking_intensity,
                                intent="modify_canvas",
                            )
                            er = ep.execute_plan(canvas_str, plan_text, sub_intent="surgical_edit")
                            if er.ok:
                                full_text = "```markdown-canvas\n" + er.document + "\n```"
                                print(json.dumps({"type": "token", "content": "```markdown-canvas\n"}), flush=True)
                                print(json.dumps({"type": "token", "content": er.document}), flush=True)
                                print(json.dumps({"type": "token", "content": "\n```"}), flush=True)
                                print(json.dumps({
                                    "type": "done",
                                    "answer": full_text,
                                    "thinking": None,
                                    "sources": [],
                                    "context_length": len(canvas_str),
                                    "intent": classified_intent,
                                    "sub_path": f"surgical_edit:{er.applied}_ops",
                                }), flush=True)
                                _surgical_done = True
                            else:
                                logger.warning(f"surgical_edit failed ({er.fallback_reason}), falling back to whole_transform")
                        except Exception as se_err:
                            logger.error(f"surgical_edit exception: {se_err}, falling back")

                    # ── whole_transform: single-pass stream rewrite ─────────
                    if not _surgical_done:
                        _NL = chr(10)
                        _THINK_OPEN = chr(60) + "think" + chr(62) + _NL
                        _THINK_CLOSE = _NL + chr(60) + "/think" + chr(62) + _NL
                        for chunk in gateway.stream_chat(
                            query_text, context,
                            history=history,
                            thinking_intensity=thinking_intensity,
                            intent=classified_intent,
                        ):
                            if chunk == _THINK_OPEN:
                                in_thinking = True
                                continue
                            if chunk == _THINK_CLOSE:
                                in_thinking = False
                                continue
                            if in_thinking:
                                full_thinking += chunk
                            else:
                                full_text += chunk
                                print(json.dumps({"type": "token", "content": chunk}), flush=True)

                        print(json.dumps({
                            "type": "done",
                            "answer": full_text,
                            "thinking": full_thinking or None,
                            "sources": [],
                            "context_length": len(canvas_str),
                            "intent": classified_intent,
                            "sub_path": sub_intent,
                        }), flush=True)
                else:
                    # Large document: segmented rewrite
                    logger.info(f"modify_canvas: segmented rewrite (canvas len {len(canvas_str)} >= {WHOLE_TRANSFORM_THRESHOLD})")
                    sections = split_into_sections(canvas_str)
                    total = len(sections)

                    fence_open = "```markdown-canvas\n"
                    full_text += fence_open
                    print(json.dumps({"type": "token", "content": fence_open}), flush=True)

                    for i, (header, body) in enumerate(sections):
                        for chunk in gateway.stream_section(
                            canvas_str, i, total, header, body,
                            query_text, thinking_intensity=thinking_intensity,
                        ):
                            if chunk == "[THINK]":
                                in_thinking = True
                                continue
                            if chunk == "[/THINK]":
                                in_thinking = False
                                continue
                            if in_thinking:
                                full_thinking += chunk
                            else:
                                full_text += chunk
                                print(json.dumps({"type": "token", "content": chunk}), flush=True)

                        if i < total - 1:
                            sep = "\n\n"
                            full_text += sep
                            print(json.dumps({"type": "token", "content": sep}), flush=True)

                    fence_close = "\n```"
                    full_text += fence_close
                    print(json.dumps({"type": "token", "content": fence_close}), flush=True)

                    print(json.dumps({
                        "type": "done",
                        "answer": full_text,
                        "thinking": full_thinking or None,
                        "sources": [],
                        "context_length": len(canvas_str),
                        "intent": classified_intent,
                        "sub_path": "segmented_rewrite",
                    }), flush=True)
            else:
                answer_text, thinking = gateway.chat(
                    query_text, context,
                    history=history,
                    thinking_intensity=thinking_intensity,
                    intent=classified_intent,
                )
                output = {
                    "answer": answer_text,
                    "thinking": thinking,
                    "sources": [],
                    "context_length": len(context),
                    "intent": classified_intent,
                }
                print(json.dumps(output, ensure_ascii=False))
        except Exception as e:
            if stream:
                print(json.dumps({"type": "error", "error": f"Canvas edit error: {e}"}), flush=True)
            else:
                print(json.dumps({"error": f"Canvas edit error: {e}"}))
            sys.exit(1)
        return

    # search_kb path: use RAG pipeline if retriever is available, otherwise fall back to LLM-only
    if not retriever:
        logger.warning("Retriever not initialized, falling back to LLM-only answer.")
        try:
            kb_context = (
                "--- CURRENT CANVAS CONTENT ---\n" + (canvas_content or "") + "\n--- END ---\n\n"
            ) if canvas_content else ""
            if stream:
                full_text = ""
                full_thinking = ""
                in_thinking_fb = False
                _NL = chr(10)
                _TO = chr(60) + "think" + chr(62) + _NL
                _TC = _NL + chr(60) + "/think" + chr(62) + _NL
                for chunk in gateway.stream_chat(query_text, kb_context, history=history, thinking_intensity=thinking_intensity, intent="search_kb"):
                    if chunk == _TO: in_thinking_fb = True; continue
                    if chunk == _TC: in_thinking_fb = False; continue
                    if in_thinking_fb: full_thinking += chunk
                    else:
                        full_text += chunk
                        print(json.dumps({"type": "token", "content": chunk}), flush=True)
                print(json.dumps({"type": "done", "answer": full_text, "thinking": full_thinking or None, "sources": [], "context_length": 0, "intent": "search_kb"}), flush=True)
            else:
                answer_text, thinking = gateway.chat(query_text, kb_context, history=history, thinking_intensity=thinking_intensity, intent="search_kb")
                print(json.dumps({"answer": answer_text, "thinking": thinking, "sources": [], "context_length": 0}, ensure_ascii=False))
        except Exception as e:
            if stream:
                print(json.dumps({"type": "error", "error": f"LLM error: {e}"}), flush=True)
            else:
                print(json.dumps({"error": f"LLM error: {e}"}))
            sys.exit(1)
        return
        
    pipeline = RAGPipeline(retriever=retriever, llm_gateway=gateway)
    
    # Run query
    try:
        answer = pipeline.answer(query_text, history=history, canvas_content=canvas_content, thinking_intensity=thinking_intensity, intent=classified_intent)
        
        # Structure results
        output = {
            "answer": answer.answer,
            "thinking": answer.thinking,
            "sources": [
                {
                    "source": str(Path(s.get("source", "")).name),
                    "page": s.get("page", 1),
                    "score": float(s.get("score", 0.0)),
                    "snippet": s.get("content", ""),
                }
                for s in answer.sources
            ],
            "context_length": len(answer.context),
        }
        if stream:
            print(json.dumps({"type": "done", **output}), flush=True)
        else:
            print(json.dumps(output, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": f"RAG pipeline error: {e}"}))
        sys.exit(1)
if __name__ == "__main__":
    import argparse
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--thinking", default=None)
    parser.add_argument("--attachments", default=None)
    parser.add_argument("--canvas-content", default=None)
    parser.add_argument("--stdin", action="store_true", help="Read payload from STDIN as JSON")
    parser.add_argument("--stream", action="store_true", help="Stream tokens back as NDJSON")
    args = parser.parse_args()
    
    if args.stdin:
        # Read from raw buffer and decode as utf-8 to avoid Windows default encoding issues
        raw_data = sys.stdin.buffer.read()
        payload = json.loads(raw_data.decode("utf-8", errors="replace"))
        query = payload.get("query", "")
        provider = payload.get("provider")
        model = payload.get("model")
        thinking = payload.get("thinking")
        attachments = payload.get("attachments")
        canvas_content = payload.get("canvas_content")
        stream = payload.get("stream", False)
        history = payload.get("history")
    else:
        query = args.query
        provider = args.provider
        model = args.model
        thinking = args.thinking
        attachments = args.attachments
        canvas_content = args.canvas_content
        stream = args.stream
        history = None
    
    if not query and not attachments:
        print(json.dumps({"error": "No query or attachments provided."}))
        sys.exit(1)
        
    query_rag(
        query,
        history=history,
        override_provider=provider,
        override_model=model,
        thinking_intensity=thinking,
        attachments=attachments,
        canvas_content=canvas_content,
        stream=stream
    )
