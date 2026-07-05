import sys
from pathlib import Path
import json
import httpx
import time

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.pdf_loader import load_pdf
from core.chunker import TextChunker

def test_nvidia_all():
    # Load API keys
    api_config = {}
    for p in [project_root / "config" / "api_keys.local.json", project_root / "config" / "api_keys.json"]:
        if p.exists():
            with open(p, encoding="utf-8") as f:
                api_config = json.load(f)
            break
            
    pconf = api_config.get("providers", {}).get("Nv", {})
    api_key = pconf.get("api_key", "")
    base_url = pconf.get("base_url", "")
    
    if not api_key or not base_url:
        print("API key or base URL not found")
        return
        
    pdf_path = r"D:\Repository\Report QA\2. SG GreenMark requirement\green_mark_nrb_2015_criteria_r3.pdf"
    print("Loading PDF...")
    doc = load_pdf(pdf_path)
    
    chunker = TextChunker(chunk_size=4096, chunk_overlap=500)
    chunks = chunker.chunk_document(doc.text, source=pdf_path)
    print(f"Generated {len(chunks)} chunks.")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    
    for idx, chunk in enumerate(chunks):
        chunk_text = chunk.content
        payload = {
            "model": "nvidia/nv-embed-v1",
            "input": [chunk_text]
        }
        try:
            r = httpx.post(f"{base_url.rstrip('/')}/embeddings", headers=headers, json=payload, timeout=30.0)
            if r.status_code != 200:
                print(f"Chunk {idx} (len {len(chunk_text)}) failed: HTTP {r.status_code} - {r.text[:300]}")
                break
            else:
                if idx % 10 == 0:
                    print(f"Processed {idx}/{len(chunks)} chunks successfully...")
            # Add a tiny sleep to avoid spamming the API
            time.sleep(0.1)
        except Exception as e:
            print(f"Chunk {idx} request failed: {e}")
            break
            
    print("Completed test.")

if __name__ == "__main__":
    test_nvidia_all()
