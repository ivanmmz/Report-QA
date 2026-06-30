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
from utils.file_io import read_json

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

def query_rag(query_text, override_provider=None, override_model=None, thinking_intensity=None, attachments=None, canvas_content=None):
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
            gateway.max_tokens = 2048
        elif ti == "high":
            gateway.temperature = 0.2
            gateway.max_tokens = 8192
        else: # medium
            gateway.temperature = 0.15
            gateway.max_tokens = 4096

    # Early canvas-only path: when the user has content in the canvas, classify
    # their intent first. If they want to modify or read the canvas, we can
    # skip the entire RAG retrieval pipeline (KB search is irrelevant).
    classified_intent = "search_kb"
    if canvas_content:
        classified_intent = gateway.classify_intent(query_text, canvas_content)
        if classified_intent in ("modify_canvas", "read_canvas"):
            context = (
                "--- CURRENT CANVAS CONTENT (The document the user is currently viewing/editing) ---\n"
                f"{canvas_content}\n"
                "--- END OF CURRENT CANVAS CONTENT ---\n\n"
            )
            try:
                answer_text, thinking = gateway.chat(
                    query_text, context,
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
                print(json.dumps({"error": f"Canvas edit error: {e}"}))
                sys.exit(1)
            return

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
            
    if not embedder or not store:
        print(json.dumps({"error": "Embedder or vector store not initialized. Make sure API keys are configured."}))
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
            
    retriever = DocumentRetriever(
        vector_store=store,
        embedder=embedder,
        top_k=settings.get("top_k", 5),
        reranker=reranker,
    )
    
    pipeline = RAGPipeline(retriever=retriever, llm_gateway=gateway)
    
    # Run query
    try:
        answer = pipeline.answer(query_text, canvas_content=canvas_content, thinking_intensity=thinking_intensity, intent=classified_intent)
        
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
    else:
        query = args.query
        provider = args.provider
        model = args.model
        thinking = args.thinking
        attachments = args.attachments
        canvas_content = args.canvas_content
    
    if not query and not attachments:
        print(json.dumps({"error": "No query or attachments provided."}))
        sys.exit(1)
        
    query_rag(
        query,
        override_provider=provider,
        override_model=model,
        thinking_intensity=thinking,
        attachments=attachments,
        canvas_content=canvas_content
    )
