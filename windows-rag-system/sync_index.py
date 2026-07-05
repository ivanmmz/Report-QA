import sys
from pathlib import Path
import json

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from core.document_manager import DocumentManager
from core.embedder import APIEmbedder
from vectorstore.faiss_store import FAISSStore
from utils.file_io import read_json

def run_sync(folder_path=None):
    # Load settings
    settings = read_json(project_root / "config" / "settings.json")
    
    # Load API keys — try local file first, fall back to main config
    api_config = read_json(project_root / "config" / "api_keys.local.json")
    if not api_config:
        api_config = read_json(project_root / "config" / "api_keys.json")
    if not api_config or not api_config.get("providers"):
        print("WARNING: API keys not configured. Files will be tracked but not embedded.")
        print("Please export api_keys.local.json from UI or configure providers in settings.")
        # Still proceed — doc_manager can track files without embedding
        
    # Resolve embedding provider and model
    provider_name = settings.get("embedding_provider")
    if not provider_name:
        provider_name = api_config.get("default_provider")
    if not provider_name:
        providers = api_config.get("providers", {})
        if providers:
            provider_name = list(providers.keys())[0]
            
    pconf = api_config.get("providers", {}).get(provider_name, {}) if provider_name else {}
    # Determine embedding model from settings or provider
    embed_model = settings.get("embedding_model")
    if not embed_model:
        models = pconf.get("models", [])
        embed_model = models[0] if models else ""
        
    base_url = pconf.get("base_url", "")
    api_key = pconf.get("api_key", "")
    
    # Initialize doc_manager first — it always works
    doc_manager = DocumentManager(
        index_path=str(project_root / "data" / "metadata" / "doc_index.json"),
        vector_dir=str(project_root / "data" / "vectors"),
        settings=settings,
    )
    
    if folder_path:
        print(f"Setting folder path: {folder_path}")
        doc_manager.set_folder(folder_path)
    
    # Only initialize embedder + vector store if we have valid API config
    if provider_name and base_url and api_key:
        print(f"Initializing embedder {embed_model} via {provider_name}...")
        try:
            embedder = APIEmbedder(
                model_name=embed_model,
                base_url=base_url,
                api_key=api_key,
            )
            
            store = FAISSStore(
                dimension=embedder.dimension,
                index_path=str(project_root / "data" / "vectors" / "faiss.index"),
                metadata_path=str(project_root / "data" / "vectors" / "metadata.pkl"),
            )
            store.load()
            
            doc_manager.initialize_stores(embedder, store)
        except Exception as e:
            print(f"WARNING: Failed to initialize embedder: {e}")
            print("Files will be tracked but not embedded.")
    else:
        print("WARNING: No valid API provider configured. Files will be tracked but not embedded.")
    
    print("Running sync...")
    result = doc_manager.sync(folder_path)
    print(f"Sync result: {result}")

if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else None
    if folder == "":
        folder = None
    run_sync(folder)
