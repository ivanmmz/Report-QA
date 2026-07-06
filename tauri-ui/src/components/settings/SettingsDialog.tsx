import { useState, useEffect } from "react";
import { useAppStore, type Provider, type RAGConfig } from "../../stores/appStore";
import { Dialog } from "../ui/Dialog";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Tabs, TabPanel } from "../ui/Tabs";
import {
  FolderOpen, Upload, RefreshCw, Trash2, Plus, Check, Cpu,
  ChevronDown, ChevronRight, FileText, Settings, ExternalLink, Info,
  Download, Archive, Puzzle, Edit3, ToggleLeft, ToggleRight,
} from "lucide-react";

export default function SettingsDialog() {
  const { showSettings, setShowSettings } = useAppStore();
  const [activeTab, setActiveTab] = useState("documents");

  return (
    <Dialog open={showSettings} onClose={() => setShowSettings(false)} title="Settings" className="max-w-4xl">
      <Tabs
        onChange={setActiveTab}
        tabs={[
          { id: "documents", label: "Documents", icon: <FolderOpen className="w-4 h-4" /> },
          { id: "api", label: "API & Models", icon: <Cpu className="w-4 h-4" /> },
          { id: "plugins", label: "Plugins", icon: <Puzzle className="w-4 h-4" /> },
          { id: "others", label: "Others", icon: <Settings className="w-4 h-4" /> },
          { id: "about", label: "About", icon: <Info className="w-4 h-4" /> },
        ]}
      >
        <TabPanel tabId="documents" activeTab={activeTab}><DocumentSettings /></TabPanel>
        <TabPanel tabId="api" activeTab={activeTab}><APISettings /></TabPanel>
        <TabPanel tabId="plugins" activeTab={activeTab}><PluginSettings /></TabPanel>
        <TabPanel tabId="others" activeTab={activeTab}><OtherSettings /></TabPanel>
        <TabPanel tabId="about" activeTab={activeTab}><AboutSettings /></TabPanel>
      </Tabs>
    </Dialog>
  );
}

/* ─── Documents Tab ─── */

function DocumentSettings() {
  const [folderPath, setFolderPath] = useState("");
  const [folders, setFolders] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("document_folders") || "[]");
      return saved.map((f: any) => ({ ...f, expanded: false }));
    } catch {
      return [];
    }
  });
  const [syncingFolder, setSyncingFolder] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<string | null>(null);

  // Persist folders on change
  useEffect(() => {
    localStorage.setItem("document_folders", JSON.stringify(folders));
  }, [folders]);

  const handleAddFolder = () => {
    if (folderPath && !folders.some((f: any) => f.path === folderPath)) {
      const newPath = folderPath;
      setFolders([...folders, { path: newPath, expanded: false, files: [] }]);
      setFolderPath("");
      handleReindex(newPath);
    }
  };

  const toggleFolder = (path: string) => {
    setFolders(folders.map((f: any) => (f.path === path ? { ...f, expanded: !f.expanded } : f)));
  };

  const handleRemoveFolder = (path: string) => {
    setFolders(folders.filter((f: any) => f.path !== path));
  };

  const handleReindex = async (folderPath: string) => {
    setSyncingFolder(folderPath);
    try {
      const { invoke } = await import("@tauri-apps/api/core");

      if (folderPath === "") {
        let totalFilesScanned = 0;
        for (const folder of folders) {
          try {
            setSyncingFolder(folder.path);
            const pdfFiles: { name: string; chunks: number; status: string }[] =
              await invoke("scan_pdf_files", { path: folder.path });

            const hasPluginRequired = pdfFiles.some(f => f.status === "plugin_required");
            if (hasPluginRequired) {
              const confirmDownload = window.confirm(
                `文件夹 ${folder.path} 包含 Word/Excel 文档，系统需要下载解析插件以获取最佳效果，是否立即下载？`
              );
              if (confirmDownload) {
                setSyncResult("Downloading parsing plugin (~15MB)...");
                await invoke("download_officecli");
                setSyncResult("Plugin installed! Re-scanning...");
                const rescannedFiles: { name: string; chunks: number; status: string }[] =
                  await invoke("scan_pdf_files", { path: folder.path });
                pdfFiles.splice(0, pdfFiles.length, ...rescannedFiles);
              }
            }

            setFolders((prev: any[]) =>
              prev.map((f: any) => {
                if (f.path !== folder.path) return f;
                const files: FolderFileInfo[] = pdfFiles.map((entry) => ({
                  name: entry.name,
                  chunks: entry.chunks,
                  status: entry.status,
                }));
                return { ...f, expanded: true, files };
              })
            );
            totalFilesScanned += pdfFiles.length;
          } catch (folderErr) {
            console.error(`Failed to scan folder ${folder.path}:`, folderErr);
          }
        }
        setSyncResult(`Re-indexed all folders (total ${totalFilesScanned} files)`);
        return;
      }

      const pdfFiles: { name: string; chunks: number; status: string }[] =
        await invoke("scan_pdf_files", { path: folderPath });

      // Detect if officecli is missing when user has word/excel files
      const hasPluginRequired = pdfFiles.some(f => f.status === "plugin_required");
      if (hasPluginRequired) {
        const confirmDownload = window.confirm(
          "您上传了 Word/Excel 文档，系统需要下载一个约 15MB 的解析插件以获取最佳排版效果，是否立即下载启用？"
        );
        if (confirmDownload) {
          setSyncResult("Downloading parsing plugin (~15MB)...");
          try {
            await invoke("download_officecli");
            setSyncResult("Plugin installed! Re-scanning documents...");
            setTimeout(() => handleReindex(folderPath), 1000);
            return;
          } catch (dlErr) {
            setSyncResult(`Failed to download plugin: ${dlErr}`);
            setTimeout(() => setSyncResult(null), 5000);
          }
        }
      }

      setFolders((prev: any[]) =>
        prev.map((f: any) => {
          if (folderPath && f.path !== folderPath) return f;
          const files: FolderFileInfo[] = pdfFiles.map((entry) => ({
            name: entry.name,
            chunks: entry.chunks,
            status: entry.status,
          }));
          return { ...f, expanded: true, files };
        })
      );
      setSyncResult(
        `Re-indexed ${pdfFiles.length} file(s) from ${folderPath}`
      );
    } catch (err) {
      setSyncResult(`Failed to scan folder: ${err}`);
    } finally {
      setSyncingFolder(null);
      setTimeout(() => setSyncResult(null), 3000);
    }
  };

  const handleOpenInExplorer = async (folderPath: string) => {
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("open_in_explorer", { path: folderPath });
    } catch (err) {
      console.error("Failed to open explorer:", err);
    }
  };

  const totalFiles = folders.reduce((sum: number, f: any) => sum + f.files.length, 0);
  const totalChunks = folders.reduce((sum: number, f: any) => sum + f.files.reduce((s: number, fi: any) => s + fi.chunks, 0), 0);

  return (
    <div className="space-y-6">
      {/* Add folder */}
      <div>
        <h4 className="section-label">Folder Paths</h4>
        <div className="flex gap-2 mt-2">
          <Input value={folderPath} onChange={(e) => setFolderPath(e.target.value)} placeholder="C:/Users/Documents/PDFs" className="flex-1" />
          <Button variant="primary" size="sm" onClick={handleAddFolder}><Plus className="w-4 h-4 mr-1" />Add</Button>
        </div>
      </div>

      {/* Indexed folders list */}
      {folders.length > 0 && (
        <div>
          <h4 className="section-label">Indexed Folders ({folders.length})</h4>
          <div className="space-y-2 mt-2">
            {folders.map((folder: any) => (
              <div key={folder.path} className="border border-[var(--border)] rounded-lg overflow-hidden">
                {/* Folder header row */}
                <div className="flex items-center justify-between p-3 bg-[var(--bg2)]">
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <button onClick={() => toggleFolder(folder.path)} className="flex-shrink-0">
                      {folder.expanded ? (
                        <ChevronDown className="w-4 h-4 text-[var(--text1)]" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-[var(--text1)]" />
                      )}
                    </button>
                    <FolderOpen className="w-4 h-4 text-[var(--accent)] flex-shrink-0" />
                    <span className="text-sm text-[var(--text0)] truncate" title={folder.path}>{folder.path}</span>
                    <span className="text-xs text-[var(--text2)] flex-shrink-0">
                      {folder.files.length > 0 ? `${folder.files.length} files · ${folder.files.reduce((s: number, fi: any) => s + fi.chunks, 0)} chunks` : "Not indexed yet"}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0 ml-2">
                    <Button variant="ghost" size="sm" onClick={() => handleOpenInExplorer(folder.path)} title="Open folder in Explorer">
                      <ExternalLink className="w-3.5 h-3.5" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => handleReindex(folder.path)} disabled={syncingFolder !== null} title="Re-index this folder">
                      <RefreshCw className={`w-3.5 h-3.5 ${syncingFolder === folder.path ? "animate-spin" : ""}`} />
                      <span className="ml-1 text-xs">Re-index</span>
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => handleRemoveFolder(folder.path)} title="Remove folder">
                      <Trash2 className="w-3.5 h-3.5 text-[#e05555]" />
                    </Button>
                  </div>
                </div>

                {/* Expandable file list */}
                {folder.expanded && (
                  <div className="border-t border-[var(--border)]">
                    {folder.files.length > 0 ? (
                      <div className="max-h-60 overflow-y-auto">
                        {folder.files.map((file: any, i: number) => (
                          <div key={i} className="flex items-center justify-between px-3 py-1.5 bg-[var(--bg1)] hover:bg-[var(--bg2)] border-b border-[rgba(255,255,255,0.02)]">
                            <div className="flex items-center gap-2 text-sm text-[var(--text1)] min-w-0">
                              <FileText className="w-3.5 h-3.5 shrink-0" />
                              <span className="truncate">{file.name}</span>
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                              <span className="text-xs text-[var(--text2)] font-mono">{file.chunks} chunks</span>
                              {file.status === "plugin_required" && (
                                <span className="text-[10px] bg-[rgba(224,85,85,0.15)] text-[#e05555] px-1.5 py-0.5 rounded border border-[rgba(224,85,85,0.3)]">
                                  Plugin Missing
                                </span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="px-3 py-3 text-xs text-[var(--text2)]">No files indexed yet. Click Re-index to scan.</div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Global sync */}
      <div className="flex gap-2">
        <Button variant="primary" size="sm" onClick={() => handleReindex("")} disabled={syncingFolder !== null || folders.length === 0}>
          <RefreshCw className={`w-4 h-4 mr-1 ${syncingFolder !== null ? "animate-spin" : ""}`} />
          {syncingFolder !== null ? "Syncing..." : "Sync All"}
        </Button>
      </div>

      {syncResult && (
        <div className="flex items-center gap-2 p-3 bg-[rgba(0,204,106,0.1)] border border-[rgba(0,204,106,0.3)] rounded-lg">
          <Check className="w-4 h-4 text-[#00cc6a]" />
          <span className="text-sm text-[#00cc6a]">{syncResult}</span>
        </div>
      )}

      {/* Upload PDF */}
      <div>
        <h4 className="section-label">Upload PDF</h4>
        <div className="file-uploader relative mt-2">
          <Upload className="w-8 h-8 mx-auto mb-2 text-[var(--text2)]" />
          <p className="text-sm text-[var(--text1)]">Drag &amp; drop a PDF file here, or click to select</p>
          <input type="file" accept=".pdf" className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" />
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        <div className="stat-card"><div className="stat-value">{folders.length}</div><div className="stat-label">Folders</div></div>
        <div className="stat-card"><div className="stat-value">{totalFiles}</div><div className="stat-label">Documents</div></div>
        <div className="stat-card"><div className="stat-value">{totalChunks}</div><div className="stat-label">Vectors</div></div>
        <div className="stat-card"><div className="stat-value">Ready</div><div className="stat-label">LLM</div></div>
      </div>
    </div>
  );
}

interface FolderFileInfo {
  name: string;
  chunks: number;
  status: string;
}

/* ─── API & Models Tab ─── */

function APISettings() {
  const { providers, addProvider, removeProvider, setProviders, ragConfig, setRAGConfig } = useAppStore();
  const [formData, setFormData] = useState({ name: "", baseUrl: "", apiKey: "", models: "" });
  const [editingName, setEditingName] = useState<string | null>(null);
  const [saveResult, setSaveResult] = useState<string | null>(null);
  const [defaultConfigPath, setDefaultConfigPath] = useState("Loading...");

  useEffect(() => {
    const fetchPath = async () => {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        const path: string = await invoke("get_default_config_dir");
        setDefaultConfigPath(path);
      } catch {
        setDefaultConfigPath("windows-rag-system/config");
      }
    };
    fetchPath();
  }, []);

  // Embedding & Ranking settings — synced with store
  const [embeddingProvider, setEmbeddingProvider] = useState(ragConfig.embedding_provider);
  const [embeddingModel, setEmbeddingModel] = useState(ragConfig.embedding_model);
  const [rerankEnabled, setRerankEnabled] = useState(ragConfig.rerank_enabled);
  const [rerankModel, setRerankModel] = useState(ragConfig.rerank_model);
  const [chunkSize, setChunkSize] = useState(ragConfig.chunk_size);
  const [chunkOverlap, setChunkOverlap] = useState(ragConfig.chunk_overlap);
  const [topK, setTopK] = useState(ragConfig.top_k);
  const [rerankTopK, setRerankTopK] = useState(ragConfig.rerank_top_k);
  const [defaultThinkingIntensity, setDefaultThinkingIntensity] = useState<"Low" | "Medium" | "High">(ragConfig.default_thinking_intensity || "Medium");

  const handleStartEdit = (p: any) => {
    setEditingName(p.name);
    setFormData({
      name: p.name,
      baseUrl: p.baseUrl,
      apiKey: p.apiKey,
      models: p.models.join("\n")
    });
  };

  const handleCancelEdit = () => {
    setEditingName(null);
    setFormData({ name: "", baseUrl: "", apiKey: "", models: "" });
  };

  const toggleProviderEnabled = (name: string) => {
    const next = providers.map(p =>
      p.name === name ? { ...p, enabled: p.enabled === false ? true : false } : p
    );
    setProviders(next);
    setTimeout(() => {
      handleExportToBackend();
    }, 100);
  };

  const handleSaveProvider = () => {
    if (formData.name && formData.baseUrl) {
      const existing = providers.find(p => p.name === formData.name);
      const isCurrentlyEnabled = existing ? (existing.enabled !== false) : true;
      
      const newProvider = {
        name: formData.name.trim(),
        baseUrl: formData.baseUrl.trim(),
        apiKey: formData.apiKey.trim(),
        models: formData.models.split("\n").map(m => m.trim()).filter(Boolean),
        isValid: true,
        enabled: isCurrentlyEnabled
      };

      if (editingName) {
        // Edit mode
        if (formData.name !== editingName && providers.some(p => p.name === formData.name)) {
          alert("Provider Name already exists!");
          return;
        }
        const next = providers.map(p => p.name === editingName ? newProvider : p);
        setProviders(next);
        setEditingName(null);
      } else {
        // Create mode
        if (providers.some(p => p.name === formData.name)) {
          alert("Provider Name already exists!");
          return;
        }
        addProvider(newProvider);
      }
      
      setFormData({ name: "", baseUrl: "", apiKey: "", models: "" });
      
      // Auto-sync to backend
      setTimeout(() => {
        handleExportToBackend();
      }, 100);
    }
  };

  const handleExportToBackend = async () => {
    // ponytail: write providers + RAG config to api_keys.local.json for Python backend
    const providers = useAppStore.getState().providers;
    const ragConfig = useAppStore.getState().ragConfig;
    const config: any = {
      providers: {},
      default_provider: ragConfig.embedding_provider,
      default_model: ragConfig.embedding_model,
    };
    providers.forEach((p) => {
      config.providers[p.name] = {
        base_url: p.baseUrl,
        api_key: p.apiKey,
        models: p.models,
        enabled: p.enabled !== false,
        description: "",
      };
    });
    // Also save RAG config alongside providers
    config._rag_config = ragConfig;
    const json = JSON.stringify(config, null, 2);

    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("save_api_keys", { configJson: json });
      setSaveResult("Successfully saved configuration to RAG backend!");
      setTimeout(() => setSaveResult(null), 3000);
    } catch (err) {
      console.error("Failed to save config directly to RAG backend:", err);
      setSaveResult(`Failed to save to backend: ${err}`);
      setTimeout(() => setSaveResult(null), 5000);
    }
  };

  const handleImportFromBackend = () => {
    // open file picker to load api_keys.local.json or settings.json
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json";
    input.onchange = (e: any) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const config = JSON.parse(reader.result as string);

          // ── Determine file format ──
          // Format A: api_keys.local.json  (has "providers" key)
          // Format B: settings.json        (has "embedding_provider" key, flat structure)
          const hasProviders = !!config.providers && typeof config.providers === "object";
          const isSettingsJson = "embedding_provider" in config;

          if (hasProviders) {
            // Format A: api_keys.local.json — extract provider list
            const imported: Provider[] = Object.entries(config.providers).map(([name, p]: [string, any]) => ({
              name,
              baseUrl: p.base_url || p.baseUrl || "",
              apiKey: p.api_key || "",
              models: p.models || [],
              isValid: !!p.api_key && p.api_key !== "dummy",
              enabled: p.enabled !== false,
            }));
            // Replace all providers (clear + re-populate)
            setProviders(imported);

             // Restore RAG config if embedded
            if (config._rag_config) {
              setRAGConfig(config._rag_config);
              // Sync local state
              setEmbeddingProvider(config._rag_config.embedding_provider);
              setEmbeddingModel(config._rag_config.embedding_model);
              setRerankEnabled(config._rag_config.rerank_enabled);
              setRerankModel(config._rag_config.rerank_model);
              setDefaultThinkingIntensity(config._rag_config.default_thinking_intensity || "Medium");
            }

          } else if (isSettingsJson) {
            // Format B: settings.json — update RAG settings only
            const rag: RAGConfig = {
              embedding_provider: config.embedding_provider || ragConfig.embedding_provider,
              embedding_model: config.embedding_model || ragConfig.embedding_model,
              rerank_enabled: config.rerank_enabled !== undefined ? config.rerank_enabled : ragConfig.rerank_enabled,
              rerank_model: config.rerank_model || ragConfig.rerank_model,
              chunk_size: config.chunk_size ?? ragConfig.chunk_size,
              chunk_overlap: config.chunk_overlap ?? ragConfig.chunk_overlap,
              top_k: config.top_k ?? ragConfig.top_k,
              rerank_top_k: config.rerank_top_k ?? ragConfig.rerank_top_k,
              default_thinking_intensity: config.default_thinking_intensity || ragConfig.default_thinking_intensity || "Medium",
            };
            setRAGConfig(rag);
            // Sync local state
            setEmbeddingProvider(rag.embedding_provider);
            setEmbeddingModel(rag.embedding_model);
            setRerankEnabled(rag.rerank_enabled);
            setRerankModel(rag.rerank_model);
            setChunkSize(rag.chunk_size);
            setChunkOverlap(rag.chunk_overlap);
            setTopK(rag.top_k);
            setRerankTopK(rag.rerank_top_k);
            setDefaultThinkingIntensity(rag.default_thinking_intensity || "Medium");
          } else {
            alert("Unrecognized config format. Expected api_keys.local.json or settings.json");
          }
        } catch (err) {
          alert("Failed to parse config file: " + err);
        }
      };
      reader.readAsText(file);
    };
    input.click();
  };

  const handleSaveRagSettings = () => {
    const config: RAGConfig = {
      embedding_provider: embeddingProvider,
      embedding_model: embeddingModel,
      rerank_enabled: rerankEnabled,
      rerank_model: rerankModel,
      chunk_size: chunkSize,
      chunk_overlap: chunkOverlap,
      top_k: topK,
      rerank_top_k: rerankTopK,
      default_thinking_intensity: defaultThinkingIntensity,
    };
    setRAGConfig(config);
    
    // Auto-sync to backend
    setTimeout(() => {
      handleExportToBackend();
    }, 100);
  };

  // Sync local state when store changes
  useEffect(() => {
    setEmbeddingProvider(ragConfig.embedding_provider);
    setEmbeddingModel(ragConfig.embedding_model);
    setRerankEnabled(ragConfig.rerank_enabled);
    setRerankModel(ragConfig.rerank_model);
    setChunkSize(ragConfig.chunk_size);
    setChunkOverlap(ragConfig.chunk_overlap);
    setTopK(ragConfig.top_k);
    setRerankTopK(ragConfig.rerank_top_k);
    setDefaultThinkingIntensity(ragConfig.default_thinking_intensity || "Medium");
  }, [ragConfig]);

  return (
    <div className="space-y-6">
      {/* ── Embedding & Ranking (RAG) ── */}
      <div className="border border-[var(--border)] rounded-xl p-4">
        <h4 className="section-label flex items-center gap-2"><Settings className="w-4 h-4" /> Embedding &amp; Ranking (RAG)</h4>
        <div className="grid grid-cols-2 gap-4 mt-3">
          <div>
            <label className="block text-sm font-medium text-[var(--text1)] mb-1">Embedding Provider</label>
            <select
              value={embeddingProvider}
              onChange={(e) => setEmbeddingProvider(e.target.value)}
              className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-sm text-[var(--text0)] focus:border-[rgba(0,188,242,0.5)] focus:outline-none"
              style={{ colorScheme: "dark" }}
            >
              <option value="Nv" className="bg-[var(--bg1)] text-[var(--text0)]">Nvidia</option>
              <option value="qwen" className="bg-[var(--bg1)] text-[var(--text0)]">Qwen</option>
              <option value="魔力" className="bg-[var(--bg1)] text-[var(--text0)]">Gitee (魔力)</option>
              <option value="LMstudio" className="bg-[var(--bg1)] text-[var(--text0)]">LM Studio</option>
              <option value="deepseek-v4" className="bg-[var(--bg1)] text-[var(--text0)]">DeepSeek</option>
              <option value="Opencode go" className="bg-[var(--bg1)] text-[var(--text0)]">Opencode</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--text1)] mb-1">Embedding Model</label>
            <input
              value={embeddingModel}
              onChange={(e) => setEmbeddingModel(e.target.value)}
              placeholder="e.g. nvidia/nv-embed-v1"
              className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-sm text-[var(--text0)] placeholder:text-[var(--text2)] focus:border-[rgba(0,188,242,0.5)] focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--text1)] mb-1">Rerank Enabled</label>
            <select
              value={rerankEnabled ? "true" : "false"}
              onChange={(e) => setRerankEnabled(e.target.value === "true")}
              className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-sm text-[var(--text0)] focus:border-[rgba(0,188,242,0.5)] focus:outline-none"
              style={{ colorScheme: "dark" }}
            >
              <option value="true" className="bg-[var(--bg1)] text-[var(--text0)]">Yes</option>
              <option value="false" className="bg-[var(--bg1)] text-[var(--text0)]">No</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--text1)] mb-1">Rerank Model</label>
            <input
              value={rerankModel}
              onChange={(e) => setRerankModel(e.target.value)}
              placeholder="e.g. nv-rerank-qa-mistral-4b"
              className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-sm text-[var(--text0)] placeholder:text-[var(--text2)] focus:border-[rgba(0,188,242,0.5)] focus:outline-none"
            />
          </div>

          {/* ── Chunk & Retrieval Settings ── */}
          <div>
            <label className="block text-sm font-medium text-[var(--text1)] mb-1">Chunk Size (index)</label>
            <input
              type="number"
              min={128}
              max={16384}
              step={128}
              value={chunkSize}
              onChange={(e) => setChunkSize(Number(e.target.value))}
              placeholder="4096"
              className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-sm text-[var(--text0)] placeholder:text-[var(--text2)] focus:border-[rgba(0,188,242,0.5)] focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--text1)] mb-1">Chunk Overlap</label>
            <input
              type="number"
              min={0}
              max={4096}
              step={50}
              value={chunkOverlap}
              onChange={(e) => setChunkOverlap(Number(e.target.value))}
              placeholder="500"
              className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-sm text-[var(--text0)] placeholder:text-[var(--text2)] focus:border-[rgba(0,188,242,0.5)] focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--text1)] mb-1">Top K (base rank)</label>
            <input
              type="number"
              min={1}
              max={100}
              step={1}
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              placeholder="25"
              className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-sm text-[var(--text0)] placeholder:text-[var(--text2)] focus:border-[rgba(0,188,242,0.5)] focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--text1)] mb-1">Rerank Top K (top rank)</label>
            <input
              type="number"
              min={1}
              max={50}
              step={1}
              value={rerankTopK}
              onChange={(e) => setRerankTopK(Number(e.target.value))}
              placeholder="10"
              className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-sm text-[var(--text0)] placeholder:text-[var(--text2)] focus:border-[rgba(0,188,242,0.5)] focus:outline-none"
            />
          </div>
        </div>
        <div className="mt-3">
          <Button variant="primary" size="sm" onClick={handleSaveRagSettings}>Save RAG Settings</Button>
        </div>
      </div>

      {/* ── New / Edit Provider ── */}
      <div className="border border-[var(--border)] rounded-xl p-4">
        <h4 className="section-label">{editingName ? `Edit Provider (${editingName})` : "New Provider"}</h4>
        <div className="space-y-3 mt-3">
          <Input label="Provider Name" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} placeholder="e.g. deepseek-v4" />
          <Input label="Base URL" value={formData.baseUrl} onChange={(e) => setFormData({ ...formData, baseUrl: e.target.value })} placeholder="https://api.deepseek.com/v1" />
          <Input label="API Key" type="password" value={formData.apiKey} onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })} placeholder="sk-..." />
          <div className="w-full">
            <label className="block text-sm font-medium text-[var(--text1)] mb-1">Models (one per line)</label>
            <textarea value={formData.models} onChange={(e) => setFormData({ ...formData, models: e.target.value })} rows={3} className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-sm text-[var(--text0)] resize-y placeholder:text-[var(--text2)] focus:border-[rgba(0,188,242,0.5)] focus:outline-none" placeholder={"deepseek-chat\ndeepseek-coder"} />
          </div>
          <div className="flex gap-2">
            <Button variant="primary" size="sm" onClick={handleSaveProvider} disabled={!formData.name || !formData.baseUrl}>
              {editingName ? "Save Changes" : "Add Provider"}
            </Button>
            {editingName && (
              <Button variant="ghost" size="sm" onClick={handleCancelEdit}>Cancel</Button>
            )}
          </div>
        </div>
      </div>

      {/* ── Configured Providers ── */}
      <div>
        <h4 className="section-label">Configured Providers</h4>
        <div className="space-y-2 mt-2">
          {providers.length > 0 ? providers.map((p) => {
            const isEnabled = p.enabled !== false;
            return (
              <div key={p.name} className={`provider-card ${p.isValid ? "ok" : "err"} ${!isEnabled ? "opacity-50" : ""}`}>
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-[var(--text0)]">
                    {p.isValid && isEnabled ? "\u{1F7E2}" : "\u{1F534}"} {p.name} {!isEnabled && <span className="text-xs text-[var(--text2)] italic">(Disabled)</span>}
                  </span>
                  <div className="flex items-center gap-3">
                    <select
                      value={p.thinking_intensity || "Medium"}
                      onChange={(e) => {
                        const updated = providers.map(prov => 
                          prov.name === p.name ? { ...prov, thinking_intensity: e.target.value as any } : prov
                        );
                        setProviders(updated);
                        setTimeout(handleExportToBackend, 100);
                      }}
                      className="bg-[var(--input-bg)] border border-[var(--border)] rounded px-2 py-0.5 text-[11px] text-[var(--text0)] focus:outline-none"
                      style={{ colorScheme: "dark" }}
                      title="Default Thinking Intensity for this API"
                    >
                      <option value="Low" className="bg-[var(--bg1)]">Low</option>
                      <option value="Medium" className="bg-[var(--bg1)]">Medium</option>
                      <option value="High" className="bg-[var(--bg1)]">High</option>
                    </select>

                    <button
                      onClick={() => toggleProviderEnabled(p.name)}
                      className="text-[var(--text1)] hover:text-white flex items-center"
                      title={isEnabled ? "Disable this provider" : "Enable this provider"}
                    >
                      {isEnabled ? (
                        <ToggleRight className="w-5.5 h-5.5 text-[var(--accent)]" />
                      ) : (
                        <ToggleLeft className="w-5.5 h-5.5 text-[var(--text2)]" />
                      )}
                    </button>
                    
                    <button
                      onClick={() => handleStartEdit(p)}
                      className="text-[var(--text2)] hover:text-[var(--accent)]"
                      title="Edit this provider"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                    </button>

                    <button
                      onClick={() => removeProvider(p.name)}
                      className="text-[#e05555] hover:text-[#ff7070]"
                      title="Remove this provider"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
                <div className="text-xs text-[var(--text2)] mt-1 font-mono">{p.baseUrl}</div>
                <div className="text-xs text-[var(--text2)] mt-1">Models: <span className="font-mono">{p.models.join(", ")}</span></div>
              </div>
            );
          }) : <p className="text-sm text-[var(--text2)]">No providers configured yet.</p>}
        </div>
      </div>

      {/* ── API Key Storage Path ── */}
      <div className="border border-[var(--border)] rounded-xl p-4">
        <h4 className="section-label text-xs">API Key Storage</h4>
        <div className="text-xs text-[var(--text2)] mt-2 space-y-2">
          <p>Keys are persisted in browser localStorage. Sync with the Python backend:</p>
          <div className="flex gap-2 flex-wrap">
            <Button variant="ghost" size="sm" onClick={handleExportToBackend}>
              <Upload className="w-3.5 h-3.5 mr-1" />
              Export to Backend
            </Button>
            <Button variant="ghost" size="sm" onClick={handleImportFromBackend}>
              <FolderOpen className="w-3.5 h-3.5 mr-1" />
              Import from Backend
            </Button>
          </div>
          {saveResult && (
            <div className="text-xs text-[#00cc6a] mt-1 font-semibold">{saveResult}</div>
          )}
          <p>Backend config path:</p>
          <code className="block p-2 bg-[var(--bg2)] rounded border border-[var(--border)] break-all text-[var(--text1)]">
            {defaultConfigPath}\api_keys.local.json
          </code>
          <p>You can also set a custom path via environment variable: <code className="bg-[var(--bg2)] px-1 rounded">RAG_API_KEYS_PATH</code></p>
        </div>
      </div>
    </div>
  );
}

/* ─── Others Tab ─── */

// All localStorage keys that are included in settings backup
const BACKUP_KEYS = [
  { key: "document_folders",  label: "Document Folders",      group: "folders" },
  { key: "providers",         label: "API Providers & Keys",   group: "api" },
  { key: "rag_config",        label: "RAG Configuration",       group: "api" },
  { key: "prompt_tools",      label: "Prompt Tools",            group: "others" },
  { key: "chat_history_path", label: "Chat History Save Path",  group: "others" },
  { key: "theme",             label: "Theme (Dark/Light)",      group: "others" },
] as const;

type BackupKey = typeof BACKUP_KEYS[number]["key"];

function OtherSettings() {
  const { chatHistoryPath, setChatHistoryPath, setProviders, setRAGConfig } = useAppStore();
  const [pathInput, setPathInput] = useState(chatHistoryPath);
  const [saveResult, setSaveResult] = useState<string | null>(null);
  const [defaultConfigPath, setDefaultConfigPath] = useState("Loading...");

  // Partial import modal state
  const [importPayload, setImportPayload] = useState<Record<string, any> | null>(null);
  const [selected, setSelected] = useState<Set<BackupKey>>(new Set());

  useEffect(() => {
    const fetchPath = async () => {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        const path: string = await invoke("get_default_config_dir");
        setDefaultConfigPath(path);
      } catch {
        setDefaultConfigPath("windows-rag-system/config");
      }
    };
    fetchPath();
  }, []);

  useEffect(() => { setPathInput(chatHistoryPath); }, [chatHistoryPath]);

  const handleSavePath = () => {
    if (pathInput.trim()) {
      setChatHistoryPath(pathInput.trim());
      setSaveResult("Save path updated successfully");
      setTimeout(() => setSaveResult(null), 3000);
    }
  };

  const handleBrowseFolder = async () => {
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({ directory: true, multiple: false, defaultPath: chatHistoryPath || undefined });
      if (typeof selected === "string") {
        setPathInput(selected);
        setChatHistoryPath(selected);
        setSaveResult("Save path updated successfully");
        setTimeout(() => setSaveResult(null), 3000);
      }
    } catch (err) {
      console.error("Failed to select folder:", err);
    }
  };

  /* ─── Backup (导出) ─── */
  const handleExportSettings = async () => {
    const snapshot: Record<string, any> = {
      _version: 1,
      _exportedAt: new Date().toISOString(),
    };
    BACKUP_KEYS.forEach(({ key }) => {
      try {
        const raw = localStorage.getItem(key);
        snapshot[key] = raw ? JSON.parse(raw) : null;
      } catch {
        snapshot[key] = null;
      }
    });

    try {
      const { save } = await import("@tauri-apps/plugin-dialog");
      const { writeTextFile } = await import("@tauri-apps/plugin-fs");
      const dest = await save({
        defaultPath: `report-qa-settings-${new Date().toISOString().slice(0,10)}.json`,
        filters: [{ name: "JSON", extensions: ["json"] }],
      });
      if (dest) {
        await writeTextFile(dest, JSON.stringify(snapshot, null, 2));
        setSaveResult("✅ Settings exported successfully");
        setTimeout(() => setSaveResult(null), 3000);
      }
    } catch (err) {
      setSaveResult(`❌ Export failed: ${err}`);
      setTimeout(() => setSaveResult(null), 5000);
    }
  };

  /* ─── Import (导入) ─── */
  const handleImportSettings = async () => {
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const { readTextFile } = await import("@tauri-apps/plugin-fs");
      const src = await open({
        filters: [{ name: "JSON", extensions: ["json"] }],
        multiple: false,
      });
      if (typeof src !== "string") return;

      const raw = await readTextFile(src);
      const data = JSON.parse(raw);
      // Pre-select all keys that exist in the backup file
      const available = new Set(
        BACKUP_KEYS.filter(({ key }) => key in data).map(({ key }) => key)
      ) as Set<BackupKey>;
      setImportPayload(data);
      setSelected(available);
    } catch (err) {
      setSaveResult(`❌ Import failed: ${err}`);
      setTimeout(() => setSaveResult(null), 5000);
    }
  };

  const handleApplyImport = () => {
    if (!importPayload) return;
    selected.forEach((key) => {
      const val = importPayload[key];
      if (val !== null && val !== undefined) {
        localStorage.setItem(key, JSON.stringify(val));
      }
    });
    // Sync Zustand store for live fields
    if (selected.has("providers") && importPayload.providers) setProviders(importPayload.providers);
    if (selected.has("rag_config") && importPayload.rag_config) setRAGConfig(importPayload.rag_config);
    if (selected.has("chat_history_path") && importPayload.chat_history_path)
      setChatHistoryPath(importPayload.chat_history_path);
    setImportPayload(null);
    setSaveResult("✅ Settings imported — restart may be required for some changes");
    setTimeout(() => setSaveResult(null), 4000);
  };

  const toggleKey = (key: BackupKey) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  return (
    <div className="space-y-6 py-2">
      {/* Chat History Storage */}
      <div className="border border-[var(--border)] rounded-xl p-4 space-y-4">
        <h4 className="section-label text-xs">Chat History Storage</h4>
        <div className="space-y-3">
          <p className="text-xs text-[var(--text2)] leading-relaxed">
            Configure the physical save path for your permanent Copilot chat history.
          </p>
          <div className="flex gap-2">
            <Input value={pathInput} onChange={(e) => setPathInput(e.target.value)} placeholder="C:\path\to\save\folder" className="flex-1 font-mono text-xs" />
            <Button variant="ghost" size="sm" onClick={handleBrowseFolder} className="h-[38px] px-3 shrink-0">Browse...</Button>
            <Button variant="primary" size="sm" onClick={handleSavePath} className="h-[38px] px-4 shrink-0">Save</Button>
          </div>
          {saveResult && <div className="text-xs text-[#00cc6a] font-semibold">{saveResult}</div>}
          <p className="text-[11px] text-[var(--text2)]">
            Default: <span className="font-mono bg-[var(--bg2)] px-1 py-0.5 rounded">{defaultConfigPath}</span>
          </p>
        </div>
      </div>

      {/* Settings Backup & Restore */}
      <div className="border border-[var(--border)] rounded-xl p-4 space-y-3">
        <h4 className="section-label text-xs flex items-center gap-2">
          <Archive className="w-3.5 h-3.5" /> Settings Backup &amp; Restore
        </h4>
        <p className="text-xs text-[var(--text2)] leading-relaxed">
          Export all settings (folders, API keys, RAG config, prompt tools) to a single JSON file.
          Import back on a new machine with selective restore.
        </p>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={handleExportSettings} id="backup-export-btn">
            <Download className="w-3.5 h-3.5 mr-1.5" /> Export Settings
          </Button>
          <Button variant="ghost" size="sm" onClick={handleImportSettings} id="backup-import-btn">
            <Upload className="w-3.5 h-3.5 mr-1.5" /> Import Settings
          </Button>
        </div>
        {saveResult && <div className="text-xs text-[#00cc6a] font-semibold">{saveResult}</div>}
      </div>

      {/* Partial Import Modal */}
      {importPayload && (
        <Dialog open title="Import Settings" onClose={() => setImportPayload(null)} className="max-w-sm">
          <div className="space-y-4">
            <p className="text-sm text-[var(--text1)]">
              Select which settings to restore:
            </p>
            <div className="space-y-2">
              {BACKUP_KEYS.filter(({ key }) => key in importPayload).map(({ key, label }) => (
                <label key={key} className="flex items-center gap-3 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={selected.has(key as BackupKey)}
                    onChange={() => toggleKey(key as BackupKey)}
                    className="w-4 h-4 rounded accent-[var(--accent)]"
                  />
                  <span className="text-sm text-[var(--text0)] group-hover:text-[var(--accent)]">{label}</span>
                </label>
              ))}
            </div>
            <div className="flex gap-2 pt-2">
              <Button variant="primary" size="sm" onClick={handleApplyImport} disabled={selected.size === 0}>
                <Check className="w-3.5 h-3.5 mr-1.5" /> Apply ({selected.size})
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setImportPayload(null)}>Cancel</Button>
            </div>
          </div>
        </Dialog>
      )}
    </div>
  );
}

/* ─── About Tab ─── */

function AboutSettings() {
  const [version, setVersion] = useState<string>("...");
  const { licenseInfo, setLicenseInfo, setShowSettings } = useAppStore();
  const [deactivating, setDeactivating] = useState(false);

  useEffect(() => {
    import("@tauri-apps/api/app")
      .then(({ getVersion }) => getVersion())
      .then(setVersion)
      .catch(() => setVersion("N/A"));
  }, []);

  const handleDeactivate = async () => {
    if (!confirm("Are you sure you want to deactivate and remove license information from this device?")) {
      return;
    }
    setDeactivating(true);
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("deactivate_license");
      setLicenseInfo(null);
      setShowSettings(false);
      // Let App.tsx refresh status which redirects to ActivationPage
      window.location.reload();
    } catch (err) {
      alert("Failed to deactivate: " + err);
    } finally {
      setDeactivating(false);
    }
  };

  const rows: { label: string; value: React.ReactNode }[] = [
    { label: "Version", value: <span className="font-mono text-[var(--accent)]">v{version}</span> },
    { label: "Product", value: "Report QA" },
    { label: "Platform", value: "Windows (Tauri v2)" },
    {
      label: "Source",
      value: (
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            window.open("https://github.com/ivanmmz/Report-QA", "_blank");
          }}
          className="text-[var(--accent)] hover:underline flex items-center gap-1"
        >
          GitHub <ExternalLink className="w-3 h-3" />
        </a>
      ),
    },
    {
      label: "Contact",
      value: (
        <a
          href="mailto:imamingze@gmail.com"
          className="text-[var(--accent)] hover:underline"
        >
          imamingze@gmail.com
        </a>
      ),
    },
  ];

  const hasLicense = licenseInfo?.is_activated && !licenseInfo?.is_expired;

  return (
    <div className="space-y-6 py-2">
      {/* Logo / title block */}
      <div className="flex flex-col items-center gap-3 py-4">
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: 14,
            background: "linear-gradient(135deg, var(--accent) 0%, #7c3aed 100%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <FileText className="w-7 h-7 text-white" />
        </div>
        <div className="text-center">
          <h3 className="text-lg font-semibold text-[var(--text0)]">Report QA</h3>
          <p className="text-xs text-[var(--text2)] mt-0.5">RAG-powered document question answering</p>
        </div>
      </div>

      {/* Info table */}
      <div className="border border-[var(--border)] rounded-xl overflow-hidden">
        {rows.map((row, i) => (
          <div
            key={row.label}
            className={`flex items-center justify-between px-4 py-3 text-sm ${
              i < rows.length - 1 ? "border-b border-[var(--border)]" : ""
            }`}
          >
            <span className="text-[var(--text2)]">{row.label}</span>
            <span className="text-[var(--text0)]">{row.value}</span>
          </div>
        ))}
      </div>

      {/* License status */}
      <div className="border border-[var(--border)] rounded-xl p-4">
        <h4 className="section-label">License</h4>
        {hasLicense ? (
          <div className="mt-3 space-y-4">
            <div className="grid grid-cols-2 gap-y-2 text-sm text-[var(--text1)] bg-[rgba(255,255,255,0.02)] p-3 rounded-lg border border-[var(--border)]">
              <div>License ID:</div>
              <div className="font-mono text-white text-right">{licenseInfo.license_id}</div>
              <div>Edition:</div>
              <div className="font-semibold text-[var(--accent)] text-right">{licenseInfo.edition}</div>
              <div>Expiry Date:</div>
              <div className="text-white text-right">
                {licenseInfo.permanent ? "Lifetime / Permanent" : licenseInfo.expire_date}
              </div>
            </div>

            <div className="flex justify-between items-center pt-2">
              <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-[rgba(0,204,106,0.15)] text-[#00cc6a] border border-[rgba(0,204,106,0.3)]">
                <span className="w-1.5 h-1.5 rounded-full bg-[#00cc6a] inline-block animate-pulse" />
                Activated &amp; Genuine
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleDeactivate}
                disabled={deactivating}
                className="text-[#e05555] hover:bg-[rgba(224,85,85,0.08)]"
              >
                Deactivate Device
              </Button>
            </div>
          </div>
        ) : (
          <div className="mt-3">
            <p className="text-xs text-[var(--text2)] leading-relaxed">
              This software is unlicensed or the license key has expired.
            </p>
            <div className="mt-3">
              <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-[rgba(224,85,85,0.15)] text-[#e05555] border border-[rgba(224,85,85,0.3)]">
                <span className="w-1.5 h-1.5 rounded-full bg-[#e05555] inline-block" />
                Unlicensed
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Plugins Tab ─── */

function PluginSettings() {
  const [installed, setInstalled] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const checkStatus = async () => {
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const isInstalled: boolean = await invoke("check_officecli_installed");
      setInstalled(isInstalled);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    checkStatus();
  }, []);

  const handleInstall = async () => {
    setLoading(true);
    setMsg("Downloading OfficeCLI converter plugin (~15MB)...");
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("download_officecli");
      setInstalled(true);
      setMsg("✅ Plugin installed and activated successfully!");
      setTimeout(() => setMsg(null), 4000);
    } catch (err) {
      setMsg(`❌ Installation failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 py-2">
      <div className="border border-[var(--border)] rounded-xl p-4 space-y-4">
        <h4 className="section-label text-xs flex items-center gap-2">
          <Puzzle className="w-3.5 h-3.5" /> OfficeCLI Plugin
        </h4>
        <p className="text-xs text-[var(--text2)] leading-relaxed">
          The OfficeCLI plugin converts Word (.docx), Excel (.xlsx), and PowerPoint (.pptx) documents into structured text for high-fidelity RAG ingestion and supports exporting canvas content back into Office files.
        </p>
        
        <div className="flex items-center justify-between bg-[rgba(255,255,255,0.02)] p-3 rounded-lg border border-[var(--border)]">
          <div className="space-y-1">
            <div className="text-sm font-medium text-[var(--text0)]">Plugin Status</div>
            <div className="text-xs text-[var(--text2)]">
              {installed === null ? "Checking..." : installed ? "Fully active and deployed in app private directory" : "Not installed"}
            </div>
          </div>
          <div>
            {installed === null ? (
              <span className="text-xs text-[var(--text2)]">Checking...</span>
            ) : installed ? (
              <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-[rgba(0,204,106,0.15)] text-[#00cc6a] border border-[rgba(0,204,106,0.3)]">
                Active
              </span>
            ) : (
              <Button variant="primary" size="sm" onClick={handleInstall} disabled={loading}>
                {loading ? "Downloading..." : "Download & Enable"}
              </Button>
            )}
          </div>
        </div>

        {msg && <div className="text-xs font-semibold text-[var(--accent)]">{msg}</div>}
      </div>
    </div>
  );
}


