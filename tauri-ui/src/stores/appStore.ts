import { create } from "zustand";

export interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  timestamp: Date;
}

export interface Citation {
  source: string;
  score: number;
  snippet: string;
}

export interface Report {
  title: string;
  content: string;
  savedAt: Date;
}

export interface Provider {
  name: string;
  baseUrl: string;
  apiKey: string;
  models: string[];
  isValid: boolean;
}

export interface AppState {
  isDark: boolean;
  toggleTheme: () => void;
  initialized: boolean;
  setInitialized: (value: boolean) => void;
  activeReportTitle: string;
  activeReportContent: string;
  setActiveReportTitle: (title: string) => void;
  setActiveReportContent: (content: string) => void;
  copilotMessages: Message[];
  addCopilotMessage: (message: Message) => void;
  clearCopilotMessages: () => void;
  savedReports: Report[];
  addSavedReport: (report: Report) => void;
  removeSavedReport: (index: number) => void;
  providers: Provider[];
  addProvider: (provider: Provider) => void;
  removeProvider: (name: string) => void;
  showSettings: boolean;
  setShowSettings: (value: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  isDark: localStorage.getItem("theme") !== "light",
  toggleTheme: () =>
    set((state) => {
      const next = !state.isDark;
      localStorage.setItem("theme", next ? "dark" : "light");
      document.documentElement.classList.toggle("dark", next);
      document.documentElement.classList.toggle("light", !next);
      return { isDark: next };
    }),
  initialized: false,
  setInitialized: (value) => set({ initialized: value }),
  activeReportTitle: "Untitled Report",
  activeReportContent: "# Active Report\n\nStart typing or ask Copilot to generate report sections.",
  setActiveReportTitle: (title) => set({ activeReportTitle: title }),
  setActiveReportContent: (content) => set({ activeReportContent: content }),
  copilotMessages: [],
  addCopilotMessage: (message) =>
    set((state) => ({ copilotMessages: [...state.copilotMessages, message] })),
  clearCopilotMessages: () => set({ copilotMessages: [] }),
  savedReports: [],
  addSavedReport: (report) =>
    set((state) => ({ savedReports: [report, ...state.savedReports] })),
  removeSavedReport: (index) =>
    set((state) => ({ savedReports: state.savedReports.filter((_, i) => i !== index) })),
  providers: [],
  addProvider: (provider) =>
    set((state) => ({ providers: [...state.providers, provider] })),
  removeProvider: (name) =>
    set((state) => ({ providers: state.providers.filter((p) => p.name !== name) })),
  showSettings: false,
  setShowSettings: (value) => set({ showSettings: value }),
}));
