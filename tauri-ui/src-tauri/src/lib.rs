use std::path::Path;
use std::collections::HashMap;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .invoke_handler(tauri::generate_handler![open_in_explorer, scan_pdf_files, query_rag, save_api_keys, get_default_config_dir])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

/// Opens a folder in Windows File Explorer.
#[tauri::command]
fn open_in_explorer(path: String) -> Result<(), String> {
    std::process::Command::new("explorer")
        .arg(&path)
        .spawn()
        .map_err(|e| format!("Failed to open explorer: {}", e))?;
    Ok(())
}

#[derive(serde::Serialize)]
struct PdfFileEntry {
    name: String,
    chunks: u32,
    status: String,
}

fn normalize_path_str(p: &str) -> String {
    p.to_lowercase().replace("/", "\\")
}

fn find_project_root() -> Option<std::path::PathBuf> {
    let mut dir = std::env::current_dir().ok()?;
    loop {
        if dir.join("windows-rag-system").is_dir() && dir.join("tauri-ui").is_dir() {
            return Some(dir);
        }
        if !dir.pop() {
            break;
        }
    }
    None
}

/// Scans a directory for PDF files and returns a list of file entries.
#[tauri::command]
async fn scan_pdf_files(path: String) -> Result<Vec<PdfFileEntry>, String> {
    let dir = Path::new(&path);
    if !dir.is_dir() {
        return Err(format!("Path is not a directory: {}", path));
    }

    let root = find_project_root().unwrap_or_else(|| std::path::PathBuf::from("."));
    let python_path = root.join("windows-rag-system/venv/Scripts/python.exe");
    let script_path = root.join("windows-rag-system/sync_index.py");
    let index_path = root.join("windows-rag-system/data/metadata/doc_index.json");

    // 1. Try to run the Python sync script to update the index
    if python_path.exists() && script_path.exists() {
        let mut cmd = std::process::Command::new(&python_path);
        cmd.arg(&script_path);
        if !path.is_empty() {
            cmd.arg(&path);
        }
        // Capture both stdout and stderr for debugging
        cmd.stdout(std::process::Stdio::piped());
        cmd.stderr(std::process::Stdio::piped());
        match cmd.output() {
            Ok(output) => {
                let stdout = String::from_utf8_lossy(&output.stdout);
                let stderr = String::from_utf8_lossy(&output.stderr);
                if !output.status.success() {
                    eprintln!("[sync_index] FAILED (exit {}):\nstdout: {}\nstderr: {}",
                        output.status.code().unwrap_or(-1), stdout, stderr);
                } else {
                    println!("[sync_index] OK:\n{}", stdout);
                }
            }
            Err(e) => {
                eprintln!("[sync_index] Failed to spawn Python: {}", e);
            }
        }
    } else {
        eprintln!("[sync_index] Python or script not found at project root {:?}: python={} script={}",
            root, python_path.exists(), script_path.exists());
    }

    // 2. Load the updated doc_index.json
    let mut chunks_map = HashMap::new();
    if index_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&index_path) {
            if let Ok(index) = serde_json::from_str::<serde_json::Value>(&content) {
                if let Some(files) = index.get("files").and_then(|f| f.as_object()) {
                    for (file_key, val) in files {
                        let normalized_key = normalize_path_str(file_key);
                        if let Some(chunks) = val.get("chunks").and_then(|c| c.as_u64()) {
                            let status = val.get("status")
                                .and_then(|s| s.as_str())
                                .unwrap_or("indexed")
                                .to_string();
                            chunks_map.insert(normalized_key, (chunks as u32, status));
                        }
                    }
                }
            }
        }
    } else {
        eprintln!("[scan_pdf_files] doc_index.json not found at {:?}", index_path);
    }

    // 3. Scan the directory and populate entries with actual chunk counts and status
    let mut results = Vec::new();
    let entries = std::fs::read_dir(dir)
        .map_err(|e| format!("Failed to read directory: {}", e))?;

    for entry in entries {
        let entry = entry.map_err(|e| format!("Failed to read entry: {}", e))?;
        let name = entry.file_name().to_string_lossy().to_string();
        if name.to_lowercase().ends_with(".pdf") {
            let file_path = dir.join(&name);
            let normalized_file_path = normalize_path_str(&file_path.to_string_lossy());
            
            let (chunks, status) = match chunks_map.get(&normalized_file_path) {
                Some((c, s)) => (*c, s.clone()),
                None => (0, "not_indexed".to_string()),
            };

            results.push(PdfFileEntry {
                name,
                chunks,
                status,
            });
        }
    }

    Ok(results)
}

#[derive(serde::Serialize, serde::Deserialize)]
struct CitationEntry {
    source: String,
    score: f64,
    page: u32,
    #[serde(rename = "snippet")]
    content: String,
}

#[derive(serde::Serialize, serde::Deserialize)]
struct QueryResponse {
    answer: String,
    sources: Vec<CitationEntry>,
}

/// Invokes the Python RAG pipeline to query context-based answers.
#[tauri::command]
async fn query_rag(query: String) -> Result<QueryResponse, String> {
    let root = find_project_root().unwrap_or_else(|| std::path::PathBuf::from("."));
    let python_path = root.join("windows-rag-system/venv/Scripts/python.exe");
    let script_path = root.join("windows-rag-system/query_rag.py");

    if !python_path.exists() || !script_path.exists() {
        return Err("Python executable or query_rag.py script not found.".to_string());
    }

    let mut cmd = std::process::Command::new(&python_path);
    cmd.arg(&script_path);
    cmd.arg(&query);

    cmd.stdout(std::process::Stdio::piped());
    cmd.stderr(std::process::Stdio::piped());

    match cmd.output() {
        Ok(output) => {
            let stdout = String::from_utf8_lossy(&output.stdout);
            let stderr = String::from_utf8_lossy(&output.stderr);
            if !output.status.success() {
                return Err(format!("Python RAG execution failed (exit {}):\nstdout: {}\nstderr: {}",
                    output.status.code().unwrap_or(-1), stdout, stderr));
            }
            match serde_json::from_str::<QueryResponse>(&stdout) {
                Ok(resp) => Ok(resp),
                Err(e) => Err(format!("Failed to parse Python RAG output: {}\nRaw output: {}", e, stdout)),
            }
        }
        Err(e) => Err(format!("Failed to run Python RAG process: {}", e)),
    }
}

/// Saves the API provider configuration JSON directly to the Python backend.
#[tauri::command]
fn save_api_keys(config_json: String) -> Result<(), String> {
    let root = find_project_root().unwrap_or_else(|| std::path::PathBuf::from("."));
    let config_dir = root.join("windows-rag-system/config");
    if !config_dir.exists() {
        std::fs::create_dir_all(&config_dir)
            .map_err(|e| format!("Failed to create config directory: {}", e))?;
    }
    let local_keys_path = config_dir.join("api_keys.local.json");
    std::fs::write(&local_keys_path, &config_json)
        .map_err(|e| format!("Failed to write api_keys.local.json: {}", e))?;
        
    // Also parse it to extract the RAG config and save it to settings.json!
    if let Ok(value) = serde_json::from_str::<serde_json::Value>(&config_json) {
        if let Some(rag_val) = value.get("_rag_config") {
            let settings_path = config_dir.join("settings.json");
            // Load existing settings if they exist to preserve other settings
            let mut settings_map = if settings_path.exists() {
                let content = std::fs::read_to_string(&settings_path).unwrap_or_default();
                serde_json::from_str::<serde_json::Value>(&content).unwrap_or_else(|_| serde_json::json!({}))
            } else {
                serde_json::json!({})
            };
            
            // Update settings_map from _rag_config
            if let Some(rag_obj) = rag_val.as_object() {
                if let Some(obj) = settings_map.as_object_mut() {
                    for (k, v) in rag_obj {
                        obj.insert(k.clone(), v.clone());
                    }
                }
            }
            
            let settings_json = serde_json::to_string_pretty(&settings_map).unwrap_or_default();
            let _ = std::fs::write(&settings_path, settings_json);
        }
    }
    
    Ok(())
}

/// Dynamically resolves the default configuration directory path based on the project root.
#[tauri::command]
fn get_default_config_dir() -> Result<String, String> {
    let root = find_project_root().unwrap_or_else(|| std::path::PathBuf::from("."));
    let config_dir = root.join("windows-rag-system/config");
    Ok(config_dir.to_string_lossy().to_string())
}
