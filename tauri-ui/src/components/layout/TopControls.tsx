import { useAppStore } from "../../stores/appStore";
import { Button } from "../ui/Button";
import { Settings, Sun, Moon, Trash2 } from "lucide-react";
import { ask } from "@tauri-apps/plugin-dialog";

interface TopControlsProps {
  isDark: boolean;
  toggleTheme: () => void;
  sidebarWidth?: number;
}

export default function TopControls({ isDark, toggleTheme, sidebarWidth = 400 }: TopControlsProps) {
  const { setShowSettings, setActiveReportContent } = useAppStore();

  return (
    <div
      className="fixed top-4 z-[9995] flex items-center gap-2"
      style={{ right: `${sidebarWidth + 24}px` }}
    >
      {/* Clear Canvas Content */}
      <Button
        variant="icon"
        size="sm"
        title="Clear Canvas Content"
        onClick={async () => {
          try {
            const confirmed = await ask("Are you sure you want to clear the canvas? This action cannot be undone.", {
              title: "Clear Canvas",
              kind: "warning",
              okLabel: "Clear",
              cancelLabel: "Cancel",
            });
            if (confirmed) {
              setActiveReportContent("");
            }
          } catch (err) {
            console.error("Failed to show native dialog:", err);
            // Fallback for standard browser testing environments
            if (window.confirm("Are you sure you want to clear the canvas? This action cannot be undone.")) {
              setActiveReportContent("");
            }
          }
        }}
      >
        <Trash2 className="w-4 h-4" />
      </Button>

      {/* Settings */}
      <Button
        variant="icon"
        size="sm"
        title="Settings"
        onClick={() => setShowSettings(true)}
      >
        <Settings className="w-4 h-4" />
      </Button>

      {/* Theme Toggle */}
      <Button variant="icon" size="sm" title="Toggle Theme" onClick={toggleTheme}>
        {isDark ? (
          <Sun className="w-4 h-4" />
        ) : (
          <Moon className="w-4 h-4" />
        )}
      </Button>
    </div>
  );
}
