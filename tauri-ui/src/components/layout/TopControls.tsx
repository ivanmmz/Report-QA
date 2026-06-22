import { useAppStore } from "../../stores/appStore";
import { Button } from "../ui/Button";
import { Settings, Sun, Moon, FileText } from "lucide-react";

interface TopControlsProps {
  isDark: boolean;
  toggleTheme: () => void;
}

export default function TopControls({ isDark, toggleTheme }: TopControlsProps) {
  const { setShowSettings } = useAppStore();

  return (
    <div className="fixed top-4 right-[400px] z-[9995] flex items-center gap-2">
      {/* Report Generator */}
      <Button variant="icon" size="sm" title="Report Generator">
        <FileText className="w-4 h-4" />
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
