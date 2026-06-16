"""End-to-end smoke test for Windows Local RAG System."""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.embedder import APIEmbedder
from vectorstore.faiss_store import FAISSStore
from core.retriever import DocumentRetriever
from core.rag_pipeline import RAGPipeline
from core.document_manager import DocumentManager
from llm.gateway import LLMGateway


def test_full_pipeline():
    """Run a full indexing + retrieval pipeline test."""
    # Use configured embedding provider from local config
    import json
    config_path = project_root / "config" / "api_keys.local.json"
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    embed_provider_name = "讯飞"
    pconf = config["providers"].get(embed_provider_name, {})
    embed_model = pconf.get("models", ["Qwen3-Embedding-8B"])[0]
    base_url = pconf.get("base_url", "")
    api_key = pconf.get("api_key", "")

    print(f"Loading embedder: {embed_model} via {embed_provider_name}...")
    embedder = APIEmbedder(
        model_name=embed_model,
        base_url=base_url,
        api_key=api_key,
    )
    print(f"  dimension={embedder.dimension}")

    store = FAISSStore(
        dimension=embedder.dimension,
        index_path="data/test/faiss.index",
        metadata_path="data/test/metadata.pkl",
    )
    store.clear()

    # Clean previous test state so we actually re-index
    for p in [Path("data/test/doc_index.json"), Path("data/test/faiss.index"), Path("data/test/metadata.pkl")]:
        if p.exists():
            p.unlink()

    gateway = LLMGateway()

    doc_manager = DocumentManager(
        index_path="data/test/doc_index.json",
        vector_dir="data/test",
        settings={"chunk_size": 500, "chunk_overlap": 50},
    )
    doc_manager.initialize_stores(embedder, store)

    report_folder = Path("C:/Users/Ivan/Desktop/Report QA/1. Report")
    doc_manager.set_folder(str(report_folder))
    result = doc_manager.sync()
    print(f"Sync result: {result}")

    retriever = DocumentRetriever(vector_store=store, embedder=embedder, top_k=3)
    pipeline = RAGPipeline(retriever=retriever, llm_gateway=gateway)

    answer = pipeline.answer("What is the water usage?")
    print("Answer:", answer.answer[:200] if answer.answer else "No answer")
    print("Sources:", len(answer.sources))
    for s in answer.sources:
        print(f"  - {s['source']} score={s['score']:.4f}")

    print("\nEnd-to-end test PASSED")


if __name__ == "__main__":
    test_full_pipeline()
