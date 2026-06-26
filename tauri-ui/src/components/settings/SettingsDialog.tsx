import { useState, useEffect } from "react";
import { useAppStore, type Provider, type RAGConfig } from "../../stores/appStore";
import { Dialog } from "../ui/Dialog";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Tabs, TabPanel } from "../ui/Tabs";
import {
  FolderOpen, Upload, RefreshCw, Trash2, Plus, Check, Cpu,
  ChevronDown, ChevronRight, FileText, Settings, ExternalLink,
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
          { id: "others", label: "Others", icon: <Settings className="w-4 h-4" /> },
        ]}
      >
        <TabPanel tabId="documents" activeTab={activeTab}><DocumentSettings /></TabPanel>
        <TabPanel tabId="api" activeTab={activeTab}><APISettings /></TabPanel>
        <TabPanel tabId="others" activeTab={activeTab}><OtherSettings /></TabPanel>
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
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);

  // Persist folders on change
  useEffect(() => {
    localStorage.setItem("document_folders", JSON.stringify(folders));
  }, [folders]);

  const handleAddFolder = () => {
    if (folderPath && !folders.some((f: any) => f.path === folderPath)) {
      setFolders([...folders, { path: folderPath, expanded: false, files: [] }]);
      setFolderPath("");
    }
  };

  const toggleFolder = (path: string) => {
    setFolders(folders.map((f: any) => (f.path === path ? { ...f, expanded: !f.expanded } : f)));
  };

  const handleRemoveFolder = (path: string) => {
    setFolders(folders.filter((f: any) => f.path !== path));
  };

  const handleReindex = async (folderPath: string) => {
    setIsSyncing(true);
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const pdfFiles: { name: string; chunks: number; status: string }[] =
        await invoke("scan_pdf_files", { path: folderPath });

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
        `Re-indexed ${pdfFiles.length} file(s) from ${folderPath || "all folders"}`
      );
    } catch (err) {
      setSyncResult(`Failed to scan folder: ${err}`);
    } finally {
      setIsSyncing(false);
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
                    <Button variant="ghost" size="sm" onClick={() => handleReindex(folder.path)} disabled={isSyncing} title="Re-index this folder">
                      <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? "animate-spin" : ""}`} />
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
                          <div key={i} className="flex items-center justify-between px-3 py-1.5 bg-[var(--bg1)] hover:bg-[var(--bg2)]">
                            <div className="flex items-center gap-2 text-sm text-[var(--text1)]">
                              <FileText className="w-3.5 h-3.5" />
                              <span className="truncate">{file.name}</span>
                            </div>
                            <span className="text-xs text-[var(--text2)] font-mono">{file.chunks} chunks</span>
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
        <Button variant="primary" size="sm" onClick={() => handleReindex("")} disabled={isSyncing || folders.length === 0}>
          <RefreshCw className={`w-4 h-4 mr-1 ${isSyncing ? "animate-spin" : ""}`} />
          {isSyncing ? "Syncing..." : "Sync All"}
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

  const handleSaveProvider = () => {
    if (formData.name && formData.baseUrl) {
      addProvider({ name: formData.name, baseUrl: formData.baseUrl, apiKey: formData.apiKey, models: formData.models.split("\n").filter(Boolean), isValid: true });
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
        description: "",
      };
    });
    // Also save RAG config alongside providers
    config._rag_config = ragConfig;
    const json = JSON.stringify(config, null, 2);

    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("save_api_keys", { config_json: json });
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

      {/* ── New Provider ── */}
      <div className="border border-[var(--border)] rounded-xl p-4">
        <h4 className="section-label">New Provider</h4>
        <div className="space-y-3 mt-3">
          <Input label="Provider Name" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} placeholder="e.g. deepseek-v4" />
          <Input label="Base URL" value={formData.baseUrl} onChange={(e) => setFormData({ ...formData, baseUrl: e.target.value })} placeholder="https://api.deepseek.com/v1" />
          <Input label="API Key" type="password" value={formData.apiKey} onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })} placeholder="sk-..." />
          <div className="w-full">
            <label className="block text-sm font-medium text-[var(--text1)] mb-1">Models (one per line)</label>
            <textarea value={formData.models} onChange={(e) => setFormData({ ...formData, models: e.target.value })} rows={3} className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-sm text-[var(--text0)] resize-y placeholder:text-[var(--text2)] focus:border-[rgba(0,188,242,0.5)] focus:outline-none" placeholder={"deepseek-chat\ndeepseek-coder"} />
          </div>
          <Button variant="primary" size="sm" onClick={handleSaveProvider} disabled={!formData.name || !formData.baseUrl}><Plus className="w-4 h-4 mr-1" />Add Provider</Button>
        </div>
      </div>

      {/* ── Configured Providers ── */}
      <div>
        <h4 className="section-label">Configured Providers</h4>
        <div className="space-y-2 mt-2">
          {providers.length > 0 ? providers.map((p) => (
            <div key={p.name} className={`provider-card ${p.isValid ? "ok" : "err"}`}>
              <div className="flex items-center justify-between">
                <span className="font-semibold text-[var(--text0)]">{p.isValid ? "\u{1F7E2}" : "\u{1F534}"} {p.name}</span>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-semibold ${p.isValid ? "text-[#3ecf8e]" : "text-[#e05555]"}`}>{p.isValid ? "Active" : "Key Missing"}</span>
                  <button onClick={() => removeProvider(p.name)} className="text-[#e05555] hover:text-[#ff7070]">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
              <div className="text-xs text-[var(--text2)] mt-1 font-mono">{p.baseUrl}</div>
              <div className="text-xs text-[var(--text2)] mt-1">Models: <span className="font-mono">{p.models.join(", ")}</span></div>
            </div>
          )) : <p className="text-sm text-[var(--text2)]">No providers configured yet.</p>}
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

function OtherSettings() {
  const { chatHistoryPath, setChatHistoryPath } = useAppStore();
  const [pathInput, setPathInput] = useState(chatHistoryPath);
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

  // Update input field when store changes
  useEffect(() => {
    setPathInput(chatHistoryPath);
  }, [chatHistoryPath]);

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
      const selected = await open({
        directory: true,
        multiple: false,
        defaultPath: chatHistoryPath || undefined
      });
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

  return (
    <div className="space-y-6 py-2">
      <div className="border border-[var(--border)] rounded-xl p-4 space-y-4">
        <h4 className="section-label text-xs">Chat History Storage</h4>
        <div className="space-y-3">
          <p className="text-xs text-[var(--text2)] leading-relaxed">
            Configure the physical save path for your permanent Copilot chat history. The history is saved in a <code className="bg-[var(--bg2)] px-1 py-0.5 rounded">chat_sessions.json</code> file.
          </p>
          
          <div className="flex gap-2">
            <Input
              value={pathInput}
              onChange={(e) => setPathInput(e.target.value)}
              placeholder="C:\path\to\save\folder"
              className="flex-1 font-mono text-xs"
            />
            <Button variant="ghost" size="sm" onClick={handleBrowseFolder} className="h-[38px] px-3 shrink-0">
              Browse...
            </Button>
            <Button variant="primary" size="sm" onClick={handleSavePath} className="h-[38px] px-4 shrink-0">
              Save
            </Button>
          </div>
          
          {saveResult && (
            <div className="text-xs text-[#00cc6a] font-semibold">{saveResult}</div>
          )}
          
          <p className="text-[11px] text-[var(--text2)]">
            Default: <span className="font-mono bg-[var(--bg2)] px-1 py-0.5 rounded">{defaultConfigPath}</span>
          </p>
        </div>
      </div>
    </div>
  );
}
