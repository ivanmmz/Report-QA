import CopilotSidebar from "./CopilotSidebar";
import TopControls from "./TopControls";
import ReportCanvas from "../report/ReportCanvas";
import SettingsDialog from "../settings/SettingsDialog";

interface MainLayoutProps {
  isDark: boolean;
  toggleTheme: () => void;
}

export default function MainLayout({ isDark, toggleTheme }: MainLayoutProps) {
  return (
    <div className="h-screen w-screen overflow-hidden flex">
      {/* Settings Dialog - Global overlay */}
      <SettingsDialog />

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto pr-[400px]">
        <div className="p-6">
          {/* Top Controls - Fixed Position */}
          <TopControls isDark={isDark} toggleTheme={toggleTheme} />

          {/* Report Canvas */}
          <div className="mt-16">
            <ReportCanvas />
          </div>

          {/* Report History */}
          <ReportHistory />
        </div>
      </main>

      {/* Copilot Sidebar - Fixed Right */}
      <CopilotSidebar />
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
