import { ReactNode, useState } from "react";
import { clsx } from "clsx";

interface Tab {
  id: string;
  label: string;
  icon?: ReactNode;
}

interface TabsProps {
  tabs: Tab[];
  onChange?: (tabId: string) => void;
  children: ReactNode;
}

export function Tabs({ tabs, onChange, children }: TabsProps) {
  const [activeTab, setActiveTab] = useState(tabs[0]?.id || "");

  const handleChange = (tabId: string) => {
    setActiveTab(tabId);
    onChange?.(tabId);
  };

  return (
    <div className="w-full">
      <div className="flex gap-1 p-1 bg-[var(--bg2)] rounded-xl mb-4">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleChange(tab.id)}
            className={clsx(
              "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all-fast flex-1 justify-center",
              activeTab === tab.id
                ? "bg-[rgba(0,120,212,0.15)] text-[var(--accent)]"
                : "text-[var(--text1)] hover:bg-[var(--bg2)]"
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>
      <div className="animate-fade-in">{children}</div>
    </div>
  );
}

interface TabPanelProps {
  tabId: string;
  activeTab: string;
  children: ReactNode;
}

export function TabPanel({ tabId, activeTab, children }: TabPanelProps) {
  if (tabId !== activeTab) return null;
  return <div>{children}</div>;
}
