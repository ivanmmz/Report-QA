import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Chart from "chart.js/auto";
import { useAppStore } from "../../stores/appStore";
import { Button } from "../ui/Button";
import { Download, FileText, Eye, Edit, ChevronLeft, ChevronRight } from "lucide-react";
import { message } from "@tauri-apps/plugin-dialog";
import { writeTextFile } from "@tauri-apps/plugin-fs";
import { downloadDir, join } from "@tauri-apps/api/path";


// Interactive chart rendering component
function InteractiveChart({ configStr }: { configStr: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<any>(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    try {
      // Use new Function to safely evaluate relaxed JSON/JS (supports trailing commas, single quotes, comments)
      const config = new Function(`return ${configStr}`)();
      if (chartRef.current) {
        chartRef.current.destroy();
      }
      chartRef.current = new Chart(canvasRef.current, config);
    } catch (e) {
      console.error("Failed to render interactive chart:", e);
    }
    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
      }
    };
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
    // Strip wrapping <pre> block around InteractiveChart to avoid double backgrounds
    if (
      children &&
      children.props &&
      children.props.className === "language-chart-config"
    ) {
      return <>{children}</>;
    }
    return <pre {...rest}>{children}</pre>;
  },
  code(props: any) {
    const { children, className, node, ...rest } = props;
    // Support hyphens inside language names (e.g. chart-config)
    const match = /language-([\w-]+)/.exec(className || "");
    const language = match ? match[1] : "";
    if (language === "chart-config") {
      return <InteractiveChart configStr={String(children).trim()} />;
    }
    return (
      <code className={className} {...rest}>
        {children}
      </code>
    );
  }
};

export default function ReportCanvas() {
  const { activeReportTitle, activeReportContent, setActiveReportContent } = useAppStore();
  const [viewMode, setViewMode] = useState<"edit" | "preview">("preview");

  // Canvas History Stack (Undo/Redo) for Copilot modifications and user typing
  const [history, setHistory] = useState<string[]>([]);
  const [currentIndex, setCurrentIndex] = useState<number>(-1);
  const isNavigatingRef = useRef(false);
  const lastPushedContentRef = useRef("");

  // Initialize history on mount / content load
  useEffect(() => {
    if (history.length === 0 && activeReportContent) {
      setHistory([activeReportContent]);
      setCurrentIndex(0);
      lastPushedContentRef.current = activeReportContent;
    }
  }, [activeReportContent]);

  // Handle history updates with a debounce to group rapid typing keystrokes
  useEffect(() => {
    if (history.length === 0) return;

    if (isNavigatingRef.current) {
      isNavigatingRef.current = false;
      lastPushedContentRef.current = activeReportContent;
      return;
    }

    if (activeReportContent === lastPushedContentRef.current) {
      return;
    }

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

  // Keyboard shortcuts (Ctrl+Z / Ctrl+Y)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && !e.shiftKey) {
        if (e.key.toLowerCase() === "z") {
          e.preventDefault();
          handleUndo();
        } else if (e.key.toLowerCase() === "y") {
          e.preventDefault();
          handleRedo();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentIndex, history]);

  const download = async (content: string, ext: string, type: string) => {
    try {
      // Resolve the user's downloads directory dynamically (works on all computers)
      const dir = await downloadDir();
      const safeTitle = activeReportTitle.replace(/[/\\?%*:|"<>]/g, "_") || "Untitled_Report";
      const filePath = await join(dir, `${safeTitle}.${ext}`);
      
      await writeTextFile(filePath, content);
      await message(`Saved to Downloads:\n${safeTitle}.${ext}`, { title: "Export Success", kind: "info" });
    } catch (err) {
      console.warn("Tauri native save failed, falling back to browser download:", err);
      // Fallback for browser-based debugging or environments without Tauri APIs
      const blob = new Blob([content], { type });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${activeReportTitle.replace(/[^a-z0-9]/gi, "_")}.${ext}`;
      a.click();
      URL.revokeObjectURL(a.href);
    }
  };

  const handleDownloadHtml = () => {
    // Generate standalone HTML that compiles Markdown and renders interactive Chart.js charts
    const htmlTemplate = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>${activeReportTitle}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
    body {
      background-color: #0f1117;
      color: #e4e6eb;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    .markdown-content table {
      width: 100%;
      border-collapse: collapse;
      margin: 16px 0;
      font-size: 0.92rem;
      border: 1px solid rgba(255, 255, 255, 0.08);
    }
    .markdown-content th {
      background: rgba(255, 255, 255, 0.03);
      font-weight: 600;
      text-align: left;
      padding: 8px 12px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      color: #e4e6eb;
    }
    .markdown-content td {
      padding: 8px 12px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      color: rgba(255, 255, 255, 0.7);
    }
    .markdown-content tr:nth-child(even) {
      background: rgba(255, 255, 255, 0.01);
    }
    .markdown-content h1 {
      font-size: 1.8em;
      font-weight: 700;
      margin: 28px 0 16px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      padding-bottom: 8px;
    }
    .markdown-content h2 {
      font-size: 1.4em;
      font-weight: 600;
      margin: 22px 0 12px;
    }
    .markdown-content p {
      margin: 12px 0;
      line-height: 1.6;
    }
    .markdown-content ul {
      list-style-type: disc;
      padding-left: 24px;
      margin: 12px 0;
    }
  </style>
</head>
<body class="max-w-4xl mx-auto px-6 py-12">
  <div id="content" class="markdown-content"></div>
  <script>
    // Escape backslashes, backticks and dollar signs for safe rendering inside template literal
    const markdownText = \`${activeReportContent.replace(/\\/g, "\\\\").replace(/`/g, "\\`").replace(/\$/g, "\\$")}\`;
    
    const renderer = new marked.Renderer();
    renderer.code = function(code, infostring, escaped) {
      let codeText = typeof code === 'object' ? code.text : code;
      let lang = typeof code === 'object' ? code.lang : infostring;
      
      if (lang === 'chart-config') {
        return \`<div class="chart-container my-8 bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.08)] rounded-xl p-4 max-w-2xl mx-auto" data-config="\${encodeURIComponent(codeText.trim())}">
          <canvas class="w-full"></canvas>
        </div>\`;
      }
      return \`<pre><code class="language-\${lang}">\${codeText}</code></pre>\`;
    };
    
    marked.use({ renderer });
    document.getElementById("content").innerHTML = marked.parse(markdownText);
    
    // Render all charts in the document after markdown has been parsed and inserted
    document.querySelectorAll('.chart-container').forEach(container => {
      const canvas = container.querySelector('canvas');
      const configStr = decodeURIComponent(container.getAttribute('data-config'));
      try {
        const config = new Function("return " + configStr)();
        new Chart(canvas, config);
      } catch (e) {
        console.error("Failed to render chart:", e);
      }
    });
  </script>
</body>
</html>`;

    download(htmlTemplate, "html", "text/html");
  };

  return (
    <>
      {/* Floating Canvas Toolbar - Fixed top-left to align with top-right controls */}
      <div className="fixed top-4 left-6 z-[9990] flex items-center gap-2 bg-[var(--bg1)] border border-[var(--border)] rounded-lg p-1.5 shadow-lg backdrop-blur-md">
        <div className="flex gap-1 pr-2 border-r border-[var(--border)]">
          <Button
            variant={viewMode === "edit" ? "primary" : "ghost"}
            size="sm"
            onClick={() => setViewMode("edit")}
          >
            <Edit className="w-4 h-4 mr-1.5" />Edit
          </Button>
          <Button
            variant={viewMode === "preview" ? "primary" : "ghost"}
            size="sm"
            onClick={() => setViewMode("preview")}
          >
            <Eye className="w-4 h-4 mr-1.5" />Preview
          </Button>
        </div>

        {/* Undo / Redo History Navigation */}
        <div className="flex gap-1 pr-2 border-r border-[var(--border)]">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleUndo}
            disabled={currentIndex <= 0}
            title="撤销 (Ctrl+Z)"
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRedo}
            disabled={currentIndex >= history.length - 1}
            title="重做 (Ctrl+Y)"
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>

        <div className="flex gap-1 pl-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => download(activeReportContent, "md", "text/markdown")}
          >
            <FileText className="w-4 h-4 mr-1.5" />MD
          </Button>
          <Button variant="ghost" size="sm" onClick={handleDownloadHtml}>
            <Download className="w-4 h-4 mr-1.5" />HTML
          </Button>
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
