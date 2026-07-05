import { useState, useEffect, useRef } from "react";
import CopilotSidebar from "./CopilotSidebar";
import TopControls from "./TopControls";
import ReportCanvas from "../report/ReportCanvas";
import SettingsDialog from "../settings/SettingsDialog";
import { useAppStore } from "../../stores/appStore";
import { Button } from "../ui/Button";

interface MainLayoutProps {
  isDark: boolean;
  toggleTheme: () => void;
}

export default function MainLayout({ isDark, toggleTheme }: MainLayoutProps) {
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem("sidebar_width");
    return saved ? Number(saved) : 400;
  });
  const isDraggingRef = useRef(false);

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    isDraggingRef.current = true;
    document.body.style.cursor = "ew-resize";
    document.body.style.userSelect = "none";
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDraggingRef.current) return;
      const newWidth = window.innerWidth - e.clientX;
      const minWidth = 250;
      const maxWidth = Math.min(800, window.innerWidth * 0.6);
      if (newWidth >= minWidth && newWidth <= maxWidth) {
        setSidebarWidth(newWidth);
        localStorage.setItem("sidebar_width", String(newWidth));
      }
    };

    const handleMouseUp = () => {
      if (isDraggingRef.current) {
        isDraggingRef.current = false;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      }
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  return (
    <div className="h-screen w-screen overflow-hidden flex relative">
      {/* Settings Dialog - Global overlay */}
      <SettingsDialog />

      {/* Main Content Area */}
      <main
        className="flex-1 flex flex-col h-screen overflow-hidden"
        style={{ paddingRight: `${sidebarWidth}px` }}
      >
        {/* Scrollable Upper Area */}
        <div className="flex-1 overflow-y-auto p-6 relative">
          {/* Top Controls - Fixed Position */}
          <TopControls
            isDark={isDark}
            toggleTheme={toggleTheme}
            sidebarWidth={sidebarWidth}
          />

          {/* Report Canvas */}
          <div className="mt-16">
            <ReportCanvas />
          </div>

          {/* Report History */}
          <ReportHistory />
        </div>

        {/* Debug Console Panel - Bottom Drawer */}
        <DebugConsolePanel />
      </main>

      {/* Drag Handle (Resizer) */}
      <div
        className="fixed top-0 bottom-0 w-3 cursor-ew-resize hover:bg-[rgba(0,188,242,0.04)] active:bg-[rgba(0,188,242,0.08)] transition-all duration-150 z-[9999] flex items-center justify-center group"
        style={{ right: `${sidebarWidth - 6}px` }}
        onMouseDown={handleMouseDown}
      >
        <div className="w-[1px] h-full bg-[var(--border)] group-hover:bg-[var(--accent)] group-active:bg-[var(--accent)] group-hover:w-[2px] transition-all duration-150" />
      </div>

      {/* Copilot Sidebar - Fixed Right */}
      <CopilotSidebar width={sidebarWidth} />
    </div>
  );
}

function ReportHistory() {
  return (
    <div className="mt-8 no-print">
      <h3 className="text-heading-3 text-[var(--text0)] mb-4">
        Saved Reports Library
      </h3>
      <p className="text-[var(--text1)]">No saved reports yet.</p>
    </div>
  );
}

function DebugConsolePanel() {
  const { showDebugPanel, setShowDebugPanel, debugLogs, clearDebugLogs } = useAppStore();
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (showDebugPanel && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [debugLogs, showDebugPanel]);

  if (!showDebugPanel) return null;

  return (
    <div className="border-t border-[var(--border)] bg-[var(--bg1)] backdrop-blur-md overflow-hidden flex flex-col h-64 shrink-0 no-print animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--border)] bg-[var(--bg2)] shrink-0 select-none">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#00ff00] animate-pulse" />
          <span className="text-xs font-semibold text-[var(--text0)] uppercase tracking-wider font-mono">Debug Console Logs</span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={clearDebugLogs}
            className="h-7 px-2.5 text-xs text-[var(--text1)] hover:text-[#e05555] hover:bg-[rgba(224,85,85,0.08)]"
          >
            Clear Logs
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowDebugPanel(false)}
            className="h-7 px-2.5 text-xs text-[var(--text1)] hover:text-[var(--text0)] hover:bg-[var(--bg2)]"
          >
            Collapse ▾
          </Button>
        </div>
      </div>

      {/* Logs scrollbox */}
      <div className="p-4 flex-1 overflow-y-auto font-mono text-xs text-[#1b815a] dark:text-[#00ff00] space-y-1 select-text bg-[var(--bg0)]/40 dark:bg-black/40">
        {debugLogs.length > 0 ? (
          debugLogs.map((log, index) => (
            <div key={index} className="leading-relaxed hover:bg-[rgba(0,255,0,0.02)] dark:hover:bg-[rgba(0,255,0,0.03)] px-1 rounded whitespace-pre-wrap">
              {log}
            </div>
          ))
        ) : (
          <div className="text-[var(--text2)] italic text-center py-8">
            Console is empty. Perform an action to view logs.
          </div>
        )}
        <div ref={logEndRef} />
      </div>
    </div>
  );
}
