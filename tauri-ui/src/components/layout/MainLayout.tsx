import { useState, useEffect, useRef } from "react";
import CopilotSidebar from "./CopilotSidebar";
import TopControls from "./TopControls";
import ReportCanvas from "../report/ReportCanvas";
import SettingsDialog from "../settings/SettingsDialog";

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
        className="flex-1 overflow-y-auto"
        style={{ paddingRight: `${sidebarWidth}px` }}
      >
        <div className="p-6">
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
    <div className="mt-8">
      <h3 className="text-heading-3 text-[var(--text0)] mb-4">
        Saved Reports Library
      </h3>
      <p className="text-[var(--text1)]">No saved reports yet.</p>
    </div>
  );
}
