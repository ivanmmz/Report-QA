use std::path::Path;
use std::collections::HashMap;
use tauri::Manager;

mod license;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .invoke_handler(tauri::generate_handler![
            open_in_explorer, scan_pdf_files, query_rag, save_api_keys, get_default_config_dir,
            check_officecli_installed, download_officecli, export_via_officecli,
            get_machine_code, activate_license, check_license, deactivate_license,
            generate_test_license_code,
        ])
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
async fn scan_pdf_files(app_handle: tauri::AppHandle, path: String) -> Result<Vec<PdfFileEntry>, String> {
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

    // Check if officecli is installed locally (免 Admin APP Data)
    let officecli_exists = officecli_path(&app_handle).exists();

    // 3. Scan the directory and populate entries
    let mut results = Vec::new();
    let entries = std::fs::read_dir(dir)
        .map_err(|e| format!("Failed to read directory: {}", e))?;

    for entry in entries {
        let entry = entry.map_err(|e| format!("Failed to read entry: {}", e))?;
        let name = entry.file_name().to_string_lossy().to_string();
        let ext = Path::new(&name).extension().and_then(|e| e.to_str()).unwrap_or("").to_lowercase();
        
        if ["pdf", "docx", "xlsx", "pptx", "txt", "md"].contains(&ext.as_str()) {
            let file_path = dir.join(&name);
            let normalized_file_path = normalize_path_str(&file_path.to_string_lossy());
            
            let (chunks, mut status) = match chunks_map.get(&normalized_file_path) {
                Some((c, s)) => (*c, s.clone()),
                None => (0, "not_indexed".to_string()),
            };

            // If it is docx/xlsx/pptx but officecli.exe is missing, tag as plugin_required
            if ["docx", "xlsx", "pptx"].contains(&ext.as_str()) && !officecli_exists {
                status = "plugin_required".to_string();
            }

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
    #[serde(default)]
    thinking: Option<String>,
    sources: Vec<CitationEntry>,
}

/// Invokes the Python RAG pipeline to query context-based answers.
#[tauri::command]
async fn query_rag(
    query: String,
    provider: Option<String>,
    model: Option<String>,
    thinking_intensity: Option<String>,
    attachments: Option<Vec<String>>,
    canvas_content: Option<String>,
) -> Result<QueryResponse, String> {
    let root = find_project_root().unwrap_or_else(|| std::path::PathBuf::from("."));
    let python_path = root.join("windows-rag-system/venv/Scripts/python.exe");
    let script_path = root.join("windows-rag-system/query_rag.py");

    if !python_path.exists() || !script_path.exists() {
        return Err("Python executable or query_rag.py script not found.".to_string());
    }

    let mut cmd = std::process::Command::new(&python_path);
    cmd.arg(&script_path);
    cmd.arg("--stdin");

    cmd.stdin(std::process::Stdio::piped());
    cmd.stdout(std::process::Stdio::piped());
    cmd.stderr(std::process::Stdio::piped());

    let payload = serde_json::json!({
        "query": query,
        "provider": provider,
        "model": model,
        "thinking": thinking_intensity,
        "attachments": attachments,
        "canvas_content": canvas_content
    });

    let mut child = match cmd.spawn() {
        Ok(c) => c,
        Err(e) => return Err(format!("Failed to spawn Python process: {}", e)),
    };

    if let Some(mut stdin) = child.stdin.take() {
        use std::io::Write;
        if let Err(e) = stdin.write_all(payload.to_string().as_bytes()) {
            return Err(format!("Failed to write payload to Python stdin: {}", e));
        }
    }

    match child.wait_with_output() {
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

// ─── OfficeCLI Plugin Commands ───

/// Returns the path where officecli.exe should live (in app-local data, no admin required).
fn officecli_path(app_handle: &tauri::AppHandle) -> std::path::PathBuf {
    let base = app_handle
        .path()
        .app_local_data_dir()
        .unwrap_or_else(|_| std::path::PathBuf::from("."));
    base.join("bin").join("officecli.exe")
}

/// Checks whether officecli.exe is present in the app-local data directory.
#[tauri::command]
fn check_officecli_installed(app_handle: tauri::AppHandle) -> bool {
    officecli_path(&app_handle).exists()
}

/// Downloads the latest officecli.exe binary from the official GitHub release
/// into the app-local data directory (%LOCALAPPDATA%\report-qa\bin\).
/// No administrator permissions are required.
#[tauri::command]
async fn download_officecli(app_handle: tauri::AppHandle) -> Result<(), String> {
    let dest = officecli_path(&app_handle);

    // Ensure the bin directory exists
    if let Some(parent) = dest.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("Failed to create bin directory: {}", e))?;
    }

    // Download the pre-built Windows binary from GitHub Releases
    let url = "https://github.com/iOfficeAI/OfficeCLI/releases/latest/download/officecli-windows-x64.exe";
    let response = reqwest::get(url)
        .await
        .map_err(|e| format!("Download failed: {}", e))?;

    if !response.status().is_success() {
        return Err(format!("Download returned HTTP {}", response.status()));
    }

    let bytes = response.bytes()
        .await
        .map_err(|e| format!("Failed to read download body: {}", e))?;

    std::fs::write(&dest, &bytes)
        .map_err(|e| format!("Failed to write officecli.exe: {}", e))?;

    Ok(())
}

/// Exports Canvas Markdown content to DOCX / XLSX / PPTX via the OfficeCLI binary.
/// Falls back to a descriptive error if the plugin is not installed.
#[tauri::command]
async fn export_via_officecli(
    app_handle: tauri::AppHandle,
    content: String,
    format: String,
    output_path: String,
) -> Result<(), String> {
    let cli = officecli_path(&app_handle);
    if !cli.exists() {
        return Err("OfficeCLI plugin is not installed. Please install it from Settings → Plugins.".to_string());
    }

    // Write the markdown to a temp file so officecli can read it
    let tmp = std::env::temp_dir().join("reportqa_export_input.md");
    std::fs::write(&tmp, &content)
        .map_err(|e| format!("Failed to write temp file: {}", e))?;

    let out = std::process::Command::new(&cli)
        .args(&[
            "convert",
            tmp.to_str().unwrap_or(""),
            "--format", &format,
            "--output", &output_path,
        ])
        .output()
        .map_err(|e| format!("Failed to run officecli: {}", e))?;

    if !out.status.success() {
        let stderr = String::from_utf8_lossy(&out.stderr);
        return Err(format!("officecli export failed: {}", stderr));
    }

    Ok(())
}

// ─── Offline Licensing Commands ───

#[tauri::command]
fn get_machine_code() -> Result<String, String> {
    Ok(license::get_local_machine_code())
}

#[tauri::command]
fn activate_license(app_handle: tauri::AppHandle, code: String) -> Result<(), String> {
    let _payload = license::verify_registration_code(&code)
        .map_err(|e| format!("Verification failed: {}", e))?;
    
    // Save to the 3 registry/file systems
    license::save_registration_code(&app_handle, &code);
    Ok(())
}

#[tauri::command]
fn check_license(app_handle: tauri::AppHandle) -> Result<license::LicenseInfo, String> {
    Ok(license::check_license_status(&app_handle))
}

#[tauri::command]
fn deactivate_license(app_handle: tauri::AppHandle) -> Result<(), String> {
    license::delete_registration_code(&app_handle);
    Ok(())
}

#[tauri::command]
fn generate_test_license_code() -> Result<String, String> {
    license::generate_developer_code()
}


