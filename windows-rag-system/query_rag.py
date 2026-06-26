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

def query_rag(query_text):
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
    
    # Initialize components
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
        
    gateway = LLMGateway()
    
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
        answer = pipeline.answer(query_text)
        
        # Structure results
        output = {
            "answer": answer.answer,
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
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No query provided."}))
        sys.exit(1)
    query_text = sys.argv[1]
    query_rag(query_text)
