import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Chart from "chart.js/auto";
import { useAppStore } from "../../stores/appStore";
import { Button } from "../ui/Button";
import {
  Download, FileText, Eye, Edit, ChevronLeft, ChevronRight,
  ChevronDown, FileCode, Presentation, Table2, Printer, Upload,
} from "lucide-react";
import { message } from "@tauri-apps/plugin-dialog";
import { writeTextFile } from "@tauri-apps/plugin-fs";
import { downloadDir, join } from "@tauri-apps/api/path";
import { invoke } from "@tauri-apps/api/core";


// Interactive chart rendering component
function InteractiveChart({ configStr }: { configStr: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<any>(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    try {
      const config = new Function(`return ${configStr}`)();
      if (chartRef.current) chartRef.current.destroy();
      chartRef.current = new Chart(canvasRef.current, config);
    } catch (e) {
      console.error("Failed to render interactive chart:", e);
    }
    return () => { if (chartRef.current) chartRef.current.destroy(); };
  }, [configStr]);

  return (
    <div className="my-6 bg-[rgba(255,255,255,0.02)] border border-[var(--border)] rounded-xl p-4 max-w-xl mx-auto">
      <canvas ref={canvasRef} />
    </div>
  );
}

// ReactMarkdown components override
const markdownComponents = {
  pre(props: any) {
    const { children, ...rest } = props;
    if (children?.props?.className === "language-chart-config") return <>{children}</>;
    return <pre {...rest}>{children}</pre>;
  },
  code(props: any) {
    const { children, className, node, ...rest } = props;
    const match = /language-([\w-]+)/.exec(className || "");
    const language = match ? match[1] : "";
    if (language === "chart-config") return <InteractiveChart configStr={String(children).trim()} />;
    return <code className={className} {...rest}>{children}</code>;
  },
};

/* ─── Export dropdown items ─── */
type ExportFormat = { id: string; label: string; ext: string; icon: React.ReactNode; description: string };

const EXPORT_FORMATS: ExportFormat[] = [
  { id: "md",   label: "Markdown",    ext: "md",   icon: <FileText className="w-4 h-4" />,     description: ".md — Plain text" },
  { id: "html", label: "HTML",        ext: "html", icon: <FileCode className="w-4 h-4" />,      description: ".html — Standalone page" },
  { id: "docx", label: "Word",        ext: "docx", icon: <FileText className="w-4 h-4" />,     description: ".docx — Requires plugin" },
  { id: "xlsx", label: "Excel",       ext: "xlsx", icon: <Table2 className="w-4 h-4" />,        description: ".xlsx — Requires plugin" },
  { id: "pptx", label: "PowerPoint",  ext: "pptx", icon: <Presentation className="w-4 h-4" />, description: ".pptx — Requires plugin" },
  { id: "pdf",  label: "PDF (Print)", ext: "pdf",  icon: <Printer className="w-4 h-4" />,       description: "System print dialog" },
];

/* ─── Main component ─── */
export default function ReportCanvas() {
  const {
    activeReportTitle, activeReportContent, setActiveReportContent, isDark,
  } = useAppStore();
  const [viewMode, setViewMode] = useState<"edit" | "preview">("preview");
  const [exportOpen, setExportOpen] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const exportRef = useRef<HTMLDivElement>(null);

  const handleImport = async () => {
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const { readTextFile } = await import("@tauri-apps/plugin-fs");
      
      const file = await open({
        filters: [{ name: "Markdown / Text", extensions: ["md", "txt"] }],
        multiple: false,
      });
      
      if (typeof file === "string") {
        const text = await readTextFile(file);
        setActiveReportContent(text);
        useAppStore.getState().addDebugLog(`[UI_SYNC] Imported file successfully: ${file}`);
        await message(`Imported successfully:\n${file.split(/[/\\]/).pop()}`, { title: "Success", kind: "info" });
      }
    } catch (err) {
      await message(`Import failed: ${err}`, { title: "Error", kind: "error" });
    }
  };



  // Canvas History Stack (Undo/Redo)
  const [history, setHistory] = useState<string[]>([]);
  const [currentIndex, setCurrentIndex] = useState<number>(-1);
  const isNavigatingRef = useRef(false);
  const lastPushedContentRef = useRef("");

  useEffect(() => {
    if (history.length === 0 && activeReportContent) {
      setHistory([activeReportContent]);
      setCurrentIndex(0);
      lastPushedContentRef.current = activeReportContent;
    }
  }, [activeReportContent]);

  useEffect(() => {
    if (history.length === 0) return;
    if (isNavigatingRef.current) {
      isNavigatingRef.current = false;
      lastPushedContentRef.current = activeReportContent;
      return;
    }
    if (activeReportContent === lastPushedContentRef.current) return;
    const timer = setTimeout(() => {
      const newHistory = history.slice(0, currentIndex + 1);
      newHistory.push(activeReportContent);
      setHistory(newHistory);
      setCurrentIndex(newHistory.length - 1);
      lastPushedContentRef.current = activeReportContent;
    }, 800);
    return () => clearTimeout(timer);
  }, [activeReportContent, currentIndex, history]);

  const handleUndo = () => {
    if (currentIndex > 0) {
      const newIndex = currentIndex - 1;
      isNavigatingRef.current = true;
      setCurrentIndex(newIndex);
      setActiveReportContent(history[newIndex]);
    }
  };

  const handleRedo = () => {
    if (currentIndex < history.length - 1) {
      const newIndex = currentIndex + 1;
      isNavigatingRef.current = true;
      setCurrentIndex(newIndex);
      setActiveReportContent(history[newIndex]);
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && !e.shiftKey) {
        if (e.key.toLowerCase() === "z") { e.preventDefault(); handleUndo(); }
        else if (e.key.toLowerCase() === "y") { e.preventDefault(); handleRedo(); }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentIndex, history]);

  // Close dropdown when clicking outside
  useEffect(() => {
    if (!exportOpen) return;
    const handler = (e: MouseEvent) => {
      if (exportRef.current && !exportRef.current.contains(e.target as Node)) {
        setExportOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [exportOpen]);

  /* ─── Save helper (Tauri FS with browser fallback) ─── */
  const saveFile = async (content: string, ext: string, mimeType: string) => {
    try {
      const dir = await downloadDir();
      const safeTitle = activeReportTitle.replace(/[/\\?%*:|"<>]/g, "_") || "Untitled_Report";
      const filePath = await join(dir, `${safeTitle}.${ext}`);
      await writeTextFile(filePath, content);
      await message(`Saved to Downloads:\n${safeTitle}.${ext}`, { title: "Export Success", kind: "info" });
    } catch {
      const blob = new Blob([content], { type: mimeType });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${activeReportTitle.replace(/[^a-z0-9]/gi, "_")}.${ext}`;
      a.click();
      URL.revokeObjectURL(a.href);
    }
  };

  /* ─── HTML template generator ─── */
  const buildHtml = () => {
    const rgbaPrefix = isDark ? "255, 255, 255" : "0, 0, 0";
    const bodyBg = isDark ? "#0f1117" : "#ffffff";
    const bodyColor = isDark ? "#e4e6eb" : "#1a1a2e";
    const accentColor = isDark ? "rgba(0, 188, 242, 0.5)" : "rgba(0, 102, 204, 0.5)";

    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>${activeReportTitle}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
    body {
      background-color: ${bodyBg};
      color: ${bodyColor};
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      max-width: 56rem;
      margin: 0 auto;
      padding: 3rem 1.5rem;
      word-wrap: break-word;
      overflow-wrap: break-word;
    }
    .markdown-content table {
      width: 100%;
      border-collapse: collapse;
      margin: 20px 0;
      font-size: 0.92rem;
      border: 1px solid rgba(${rgbaPrefix}, 0.08);
      display: block;
      overflow-x: auto;
    }
    .markdown-content th {
      background: rgba(${rgbaPrefix}, 0.03);
      font-weight: 600;
      text-align: left;
      padding: 10px 14px;
      border: 1px solid rgba(${rgbaPrefix}, 0.08);
      color: ${bodyColor};
    }
    .markdown-content td {
      padding: 10px 14px;
      border: 1px solid rgba(${rgbaPrefix}, 0.08);
      color: rgba(${rgbaPrefix}, 0.7);
    }
    .markdown-content tr:nth-child(even) {
      background: rgba(${rgbaPrefix}, 0.01);
    }
    .markdown-content h1 {
      font-size: 2em;
      font-weight: 700;
      margin: 32px 0 16px;
      border-bottom: 1px solid rgba(${rgbaPrefix}, 0.08);
      padding-bottom: 8px;
    }
    .markdown-content h2 {
      font-size: 1.5em;
      font-weight: 600;
      margin: 24px 0 12px;
      border-bottom: 1px solid rgba(${rgbaPrefix}, 0.04);
      padding-bottom: 6px;
    }
    .markdown-content h3 {
      font-size: 1.25em;
      font-weight: 600;
      margin: 20px 0 8px;
    }
    .markdown-content p {
      margin: 14px 0;
      line-height: 1.625;
    }
    .markdown-content ul, .markdown-content ol {
      padding-left: 24px;
      margin: 14px 0;
    }
    .markdown-content ul {
      list-style-type: disc;
    }
    .markdown-content ol {
      list-style-type: decimal;
    }
    .markdown-content li {
      margin: 6px 0;
    }
    .markdown-content pre {
      background: rgba(${rgbaPrefix}, 0.03);
      padding: 16px;
      border-radius: 8px;
      border: 1px solid rgba(${rgbaPrefix}, 0.08);
      overflow-x: auto;
      margin: 20px 0;
    }
    .markdown-content code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      font-size: 0.875em;
      background: rgba(${rgbaPrefix}, 0.06);
      padding: 2px 6px;
      border-radius: 4px;
    }
    .markdown-content pre code {
      background: transparent;
      padding: 0;
      border-radius: 0;
    }
    .markdown-content blockquote {
      border-left: 4px solid ${accentColor};
      background: rgba(${rgbaPrefix}, 0.02);
      padding: 8px 16px;
      margin: 16px 0;
      color: rgba(${rgbaPrefix}, 0.85);
    }
    .chart-container {
      max-width: 100%;
      background: rgba(${rgbaPrefix}, 0.02);
      border: 1px solid rgba(${rgbaPrefix}, 0.08);
      border-radius: 12px;
      padding: 20px;
      margin: 24px 0;
    }
    .chart-container canvas {
      max-width: 100%;
      height: auto !important;
    }
  </style>
</head>
<body class="max-w-4xl mx-auto px-6 py-12">
  <div id="content" class="markdown-content"></div>
  <script>
    const markdownText = \`${activeReportContent.replace(/\\/g, "\\\\").replace(/`/g, "\\`").replace(/\$/g, "\\$")}\`;
    const renderer = new marked.Renderer();
    renderer.code = function(code, infostring) {
      let codeText = typeof code === 'object' ? code.text : code;
      let lang = typeof code === 'object' ? code.lang : infostring;
      if (lang === 'chart-config') {
        return \`<div class="chart-container my-8" data-config="\${encodeURIComponent(codeText.trim())}"><canvas></canvas></div>\`;
      }
      return \`<pre><code class="language-\${lang}">\${codeText}</code></pre>\`;
    };
    marked.use({ renderer });
    document.getElementById("content").innerHTML = marked.parse(markdownText);
    
    // Configure default chart options based on theme
    const isDarkTheme = ${isDark};
    if (typeof Chart !== 'undefined') {
      Chart.defaults.color = isDarkTheme ? '#e4e6eb' : '#1a1a2e';
      Chart.defaults.borderColor = isDarkTheme ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)';
    }

    document.querySelectorAll('.chart-container').forEach(c => {
      try { 
        const config = new Function("return " + decodeURIComponent(c.getAttribute('data-config')))();
        if (config.options) {
          if (isDarkTheme) {
            if (config.options.scales) {
              Object.values(config.options.scales).forEach(scale => {
                if (scale.grid) scale.grid.color = 'rgba(255, 255, 255, 0.08)';
                if (scale.ticks) scale.ticks.color = '#e4e6eb';
              });
            }
            if (config.options.plugins && config.options.plugins.legend && config.options.plugins.legend.labels) {
              config.options.plugins.legend.labels.color = '#e4e6eb';
            }
          } else {
            if (config.options.scales) {
              Object.values(config.options.scales).forEach(scale => {
                if (scale.grid) scale.grid.color = 'rgba(0, 0, 0, 0.08)';
                if (scale.ticks) scale.ticks.color = '#1a1a2e';
              });
            }
            if (config.options.plugins && config.options.plugins.legend && config.options.plugins.legend.labels) {
              config.options.plugins.legend.labels.color = '#1a1a2e';
            }
          }
        }
        new Chart(c.querySelector('canvas'), config); 
      }
      catch(e) { console.error(e); }
    });
  </script>
</body>
</html>`;
  };

  /* ─── Export dispatcher ─── */
  const handleExport = async (format: ExportFormat) => {
    setExportOpen(false);
    setExportBusy(true);
    try {
      switch (format.id) {
        case "md":
          await saveFile(activeReportContent, "md", "text/markdown");
          break;

        case "html":
          await saveFile(buildHtml(), "html", "text/html");
          break;

        case "pdf":
          // Use system print dialog — no plugin needed
          window.print();
          break;

        case "docx":
        case "xlsx":
        case "pptx": {
          // Check if OfficeCLI plugin is installed
          const isInstalled = await invoke<boolean>("check_officecli_installed");
          if (!isInstalled) {
            const confirmInstall = window.confirm(
              `检测到系统尚未安装文档转换插件（约 15MB），需要下载并启用此插件才能导出为 ${format.id.toUpperCase()} 格式。是否立即下载启用？`
            );
            if (!confirmInstall) return;
            
            // Temporary overlay message during download
            await message("正在下载文档转换插件，这可能需要数十秒，请稍候...", { title: "Downloading Plugin", kind: "info" });
            try {
              await invoke("download_officecli");
            } catch (dlErr) {
              await message(`Plugin download failed: ${dlErr}`, { title: "Error", kind: "error" });
              return;
            }
          }

          // Proceed with export
          const dir = await downloadDir();
          const safeTitle = activeReportTitle.replace(/[/\\?%*:|"<>]/g, "_") || "Untitled_Report";
          const outPath = await join(dir, `${safeTitle}.${format.ext}`);
          await invoke("export_via_officecli", {
            content: activeReportContent,
            format: format.ext,
            outputPath: outPath,
          });
          await message(`Saved to Downloads:\n${safeTitle}.${format.ext}`, { title: "Export Success", kind: "info" });
          break;
        }
      }
    } catch (err) {
      await message(`Export failed: ${err}`, { title: "Export Error", kind: "error" });
    } finally {
      setExportBusy(false);
    }
  };

  /* ─── Render ─── */
  return (
    <>
      {/* Floating Canvas Toolbar */}
      <div className="fixed top-4 left-6 z-[9990] flex items-center gap-2 bg-[var(--bg1)] border border-[var(--border)] rounded-lg p-1.5 shadow-lg backdrop-blur-md no-print">
        {/* Edit / Preview toggle */}
        <div className="flex gap-1 pr-2 border-r border-[var(--border)]">
          <Button variant={viewMode === "edit" ? "primary" : "ghost"} size="sm" onClick={() => setViewMode("edit")}>
            <Edit className="w-4 h-4 mr-1.5" />Edit
          </Button>
          <Button variant={viewMode === "preview" ? "primary" : "ghost"} size="sm" onClick={() => setViewMode("preview")}>
            <Eye className="w-4 h-4 mr-1.5" />Preview
          </Button>
        </div>

        {/* Undo / Redo */}
        <div className="flex gap-1 pr-2 border-r border-[var(--border)]">
          <Button variant="ghost" size="sm" onClick={handleUndo} disabled={currentIndex <= 0} title="撤销 (Ctrl+Z)">
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={handleRedo} disabled={currentIndex >= history.length - 1} title="重做 (Ctrl+Y)">
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>

        {/* Import file button */}
        <div className="flex gap-1 pr-2 border-r border-[var(--border)] pl-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleImport}
            title="Import Markdown/Text file"
          >
            <Upload className="w-4 h-4 mr-1.5" />
            Import
          </Button>
        </div>

        {/* Export dropdown */}
        <div ref={exportRef} className="relative pl-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExportOpen((v) => !v)}
            disabled={exportBusy}
            id="export-dropdown-trigger"
          >
            <Download className="w-4 h-4 mr-1.5" />
            {exportBusy ? "Exporting…" : "Export"}
            <ChevronDown className={`w-3.5 h-3.5 ml-1 transition-transform ${exportOpen ? "rotate-180" : ""}`} />
          </Button>

          {exportOpen && (
            <div
              className="absolute left-0 top-full mt-1.5 w-52 rounded-xl border border-[var(--border)] bg-[var(--bg1)] shadow-2xl overflow-hidden z-[9999]"
              style={{ backdropFilter: "blur(12px)" }}
            >
              {EXPORT_FORMATS.map((fmt, i) => (
                <button
                  key={fmt.id}
                  id={`export-${fmt.id}`}
                  onClick={() => handleExport(fmt)}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left text-[var(--text0)] hover:bg-[var(--bg2)] transition-colors ${
                    i < EXPORT_FORMATS.length - 1 ? "border-b border-[var(--border)]" : ""
                  }`}
                >
                  <span className="text-[var(--accent)] flex-shrink-0">{fmt.icon}</span>
                  <div>
                    <div className="font-medium">{fmt.label}</div>
                    <div className="text-[10px] text-[var(--text2)]">{fmt.description}</div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="glass-card relative p-6">
        {viewMode === "edit" ? (
          <textarea
            value={activeReportContent}
            onChange={(e) => setActiveReportContent(e.target.value)}
            className="w-full min-h-[500px] bg-[var(--input-bg)] border border-[var(--border)] rounded-lg p-4 text-[var(--text0)] font-mono text-sm resize-y focus:border-[rgba(0,188,242,0.5)] focus:outline-none"
            placeholder="Write your report in Markdown..."
          />
        ) : (
          <div className="min-h-[500px] text-[var(--text0)] leading-relaxed markdown-content animate-fade-in">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {activeReportContent}
            </ReactMarkdown>
          </div>
        )}
      </div>


    </>
  );
}
