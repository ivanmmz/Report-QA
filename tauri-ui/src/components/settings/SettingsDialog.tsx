import { useState } from "react";
import { useAppStore } from "../../stores/appStore";
import { Dialog } from "../ui/Dialog";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Tabs, TabPanel } from "../ui/Tabs";
import { FolderOpen, Upload, RefreshCw, Trash2, Plus, Check, Cpu } from "lucide-react";

export default function SettingsDialog() {
  const { showSettings, setShowSettings } = useAppStore();

  return (
    <Dialog open={showSettings} onClose={() => setShowSettings(false)} title="Settings" className="max-w-3xl">
      <Tabs
        onChange={() => {}}
        tabs={[
          { id: "documents", label: "Documents", icon: <FolderOpen className="w-4 h-4" /> },
          { id: "api", label: "API & Models", icon: <Cpu className="w-4 h-4" /> },
        ]}
      >
        <TabPanel tabId="documents" activeTab="documents"><DocumentSettings /></TabPanel>
        <TabPanel tabId="api" activeTab="api"><APISettings /></TabPanel>
      </Tabs>
    </Dialog>
  );
}

function DocumentSettings() {
  const [folderPath, setFolderPath] = useState("");
  const [folders, setFolders] = useState<string[]>([]);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);

  const handleAddFolder = () => {
    if (folderPath && !folders.includes(folderPath)) {
      setFolders([...folders, folderPath]);
      setFolderPath("");
    }
  };

  const handleSync = () => {
    setIsSyncing(true);
    setTimeout(() => {
      setIsSyncing(false);
      setSyncResult("Synced 150 chunks from 12 files");
      setTimeout(() => setSyncResult(null), 3000);
    }, 2000);
  };

  return (
    <div className="space-y-6">
      <div>
        <h4 className="section-label">Folder Paths</h4>
        <div className="flex gap-2 mt-2">
          <Input value={folderPath} onChange={(e) => setFolderPath(e.target.value)} placeholder="C:/Users/Documents/PDFs" className="flex-1" />
          <Button variant="primary" size="sm" onClick={handleAddFolder}><Plus className="w-4 h-4 mr-1" />Add</Button>
        </div>
      </div>

      {folders.length > 0 && (
        <div>
          <h4 className="section-label">Indexed Folders</h4>
          <div className="space-y-2 mt-2">
            {folders.map((folder) => (
              <div key={folder} className="flex items-center justify-between p-3 bg-[var(--bg2)] border border-[var(--border)] rounded-lg">
                <div className="flex items-center gap-2">
                  <FolderOpen className="w-4 h-4 text-[var(--accent)]" />
                  <span className="text-sm text-[var(--text0)]">{folder}</span>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setFolders(folders.filter((f) => f !== folder))}>
                  <Trash2 className="w-4 h-4 text-[#e05555]" />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-2">
        <Button variant="primary" size="sm" onClick={handleSync} disabled={isSyncing || folders.length === 0}>
          <RefreshCw className={`w-4 h-4 mr-1 ${isSyncing ? "animate-spin" : ""}`} />
          {isSyncing ? "Syncing..." : "Sync"}
        </Button>
      </div>

      {syncResult && (
        <div className="flex items-center gap-2 p-3 bg-[rgba(0,204,106,0.1)] border border-[rgba(0,204,106,0.3)] rounded-lg">
          <Check className="w-4 h-4 text-[#00cc6a]" />
          <span className="text-sm text-[#00cc6a]">{syncResult}</span>
        </div>
      )}

      <div>
        <h4 className="section-label">Upload PDF</h4>
        <div className="file-uploader relative mt-2">
          <Upload className="w-8 h-8 mx-auto mb-2 text-[var(--text2)]" />
          <p className="text-sm text-[var(--text1)]">Drag & drop a PDF file here, or click to select</p>
          <input type="file" accept=".pdf" className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" />
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <div className="stat-card"><div className="stat-value">12</div><div className="stat-label">Documents</div></div>
        <div className="stat-card"><div className="stat-value">1.2k</div><div className="stat-label">Vectors</div></div>
        <div className="stat-card"><div className="stat-value">Ready</div><div className="stat-label">LLM</div></div>
        <div className="stat-card"><div className="stat-value">Set</div><div className="stat-label">Folder</div></div>
      </div>
    </div>
  );
}

function APISettings() {
  const { providers, addProvider, removeProvider } = useAppStore();
  const [formData, setFormData] = useState({ name: "", baseUrl: "", apiKey: "", models: "" });

  const handleSave = () => {
    if (formData.name && formData.baseUrl) {
      addProvider({ name: formData.name, baseUrl: formData.baseUrl, apiKey: formData.apiKey, models: formData.models.split("\n").filter(Boolean), isValid: true });
      setFormData({ name: "", baseUrl: "", apiKey: "", models: "" });
    }
  };

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <h4 className="section-label">New Provider</h4>
        <Input label="Provider Name" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} placeholder="e.g. deepseek-v4" />
        <Input label="Base URL" value={formData.baseUrl} onChange={(e) => setFormData({ ...formData, baseUrl: e.target.value })} placeholder="https://api.deepseek.com/v1" />
        <Input label="API Key" type="password" value={formData.apiKey} onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })} placeholder="sk-..." />
        <div className="w-full">
          <label className="block text-sm font-medium text-[var(--text1)] mb-1">Models (one per line)</label>
          <textarea value={formData.models} onChange={(e) => setFormData({ ...formData, models: e.target.value })} rows={3} className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-sm text-[var(--text0)] resize-y placeholder:text-[var(--text2)] focus:border-[rgba(0,188,242,0.5)] focus:outline-none" placeholder={"deepseek-chat\ndeepseek-coder"} />
        </div>
        <Button variant="primary" size="sm" onClick={handleSave} disabled={!formData.name || !formData.baseUrl}><Plus className="w-4 h-4 mr-1" />Add Provider</Button>
      </div>

      <div>
        <h4 className="section-label">Configured Providers</h4>
        <div className="space-y-2 mt-2">
          {providers.length > 0 ? providers.map((p) => (
            <div key={p.name} className={`provider-card ${p.isValid ? "ok" : "err"}`}>
              <div className="flex items-center justify-between">
                <span className="font-semibold text-[var(--text0)]">{p.isValid ? "🟢" : "🔴"} {p.name}</span>
                <span className={`text-xs font-semibold ${p.isValid ? "text-[#3ecf8e]" : "text-[#e05555]"}`}>{p.isValid ? "Active" : "Key Missing"}</span>
              </div>
              <div className="text-xs text-[var(--text2)] mt-1 font-mono">{p.baseUrl}</div>
              <div className="text-xs text-[var(--text2)] mt-1">Models: <span className="font-mono">{p.models.join(", ")}</span></div>
            </div>
          )) : <p className="text-sm text-[var(--text2)]">No providers configured yet.</p>}
        </div>
      </div>
    </div>
  );
}
