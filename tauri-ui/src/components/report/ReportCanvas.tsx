import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAppStore } from "../../stores/appStore";
import { Button } from "../ui/Button";
import { Download, FileText, Eye, Edit } from "lucide-react";

export default function ReportCanvas() {
  const { activeReportTitle, activeReportContent, setActiveReportContent } = useAppStore();
  const [viewMode, setViewMode] = useState<"edit" | "preview">("preview");

  const download = (content: string, ext: string, type: string) => {
    const blob = new Blob([content], { type });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${activeReportTitle.replace(/[^a-z0-9]/gi, "_")}.${ext}`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="glass-card relative">
      <div className="floating-bar">
        <button className="dl-btn" onClick={() => download(activeReportContent, "md", "text/markdown")}>
          <FileText className="w-3.5 h-3.5" />MD
        </button>
        <button className="dl-btn" onClick={() => download(`<!DOCTYPE html><html><head><meta charset="UTF-8"><title>${activeReportTitle}</title><script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script></head><body style="font-family:sans-serif;background:#0f1117;color:#e4e6eb;padding:20px 40px"><div id="root"></div><script>document.getElementById("root").innerHTML=new DOMParser().parseFromString(\`${activeReportContent.replace(/`/g, "\\`")}\`,"text/markdown").body.textContent</script></body></html>`, "html", "text/html")}>
          <Download className="w-3.5 h-3.5" />HTML
        </button>
      </div>

      <div className="flex gap-2 mb-4">
        <Button variant={viewMode === "edit" ? "primary" : "ghost"} size="sm" onClick={() => setViewMode("edit")}>
          <Edit className="w-4 h-4 mr-2" />Edit
        </Button>
        <Button variant={viewMode === "preview" ? "primary" : "ghost"} size="sm" onClick={() => setViewMode("preview")}>
          <Eye className="w-4 h-4 mr-2" />Preview
        </Button>
      </div>

      {viewMode === "edit" ? (
        <textarea
          value={activeReportContent}
          onChange={(e) => setActiveReportContent(e.target.value)}
          className="w-full min-h-[500px] bg-[var(--input-bg)] border border-[var(--border)] rounded-lg p-4 text-[var(--text0)] font-mono text-sm resize-y focus:border-[rgba(0,188,242,0.5)] focus:outline-none"
          placeholder="Write your report in Markdown..."
        />
      ) : (
        <div className="min-h-[500px] text-[var(--text0)] leading-relaxed">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{activeReportContent}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}
