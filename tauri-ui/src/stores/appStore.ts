import { create } from "zustand";

export interface Message {
  role: "user" | "assistant";
  content: string;
  thinking?: string;
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
  enabled?: boolean;
  thinking_intensity?: "Low" | "Medium" | "High";
}

export interface RAGConfig {
  embedding_provider: string;
  embedding_model: string;
  rerank_enabled: boolean;
  rerank_model: string;
  chunk_size: number;
  chunk_overlap: number;
  top_k: number;
  rerank_top_k: number;
  default_thinking_intensity?: "Low" | "Medium" | "High";
}

export interface LicenseInfo {
  is_activated: boolean;
  is_expired: boolean;
  license_id: string;
  edition: string;
  expire_date: string;
  permanent: boolean;
  features: string[];
  is_trial: boolean;
  trial_days_left: number;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string;
}

export interface PromptTool {
  id: string;
  name: string;
  prompt: string;
}

export interface AppState {
  isDark: boolean;
  toggleTheme: () => void;
  setProviders: (providers: Provider[]) => void;
  initialized: boolean;
  setInitialized: (value: boolean) => void;
  activeReportTitle: string;
  activeReportContent: string;
  setActiveReportTitle: (title: string) => void;
  setActiveReportContent: (content: string) => void;
  copilotMessages: Message[];
  addCopilotMessage: (message: Message) => void;
  clearCopilotMessages: () => void;
  
  // Chat History
  chatSessions: ChatSession[];
  activeSessionId: string | null;
  setActiveSessionId: (id: string | null) => void;
  deleteChatSession: (id: string) => void;
  setChatSessions: (sessions: ChatSession[]) => void;
  
  // Custom Storage Path
  chatHistoryPath: string;
  setChatHistoryPath: (path: string) => void;
  
  // Prompt Tools
  promptTools: PromptTool[];
  addPromptTool: (tool: PromptTool) => void;
  updatePromptTool: (id: string, updated: Partial<PromptTool>) => void;
  deletePromptTool: (id: string) => void;
  savedReports: Report[];
  addSavedReport: (report: Report) => void;
  removeSavedReport: (index: number) => void;
  providers: Provider[];
  addProvider: (provider: Provider) => void;
  removeProvider: (name: string) => void;
  showSettings: boolean;
  setShowSettings: (value: boolean) => void;
  ragConfig: RAGConfig;
  setRAGConfig: (config: RAGConfig) => void;
  licenseInfo: LicenseInfo | null;
  setLicenseInfo: (info: LicenseInfo | null) => void;
  debugLogs: string[];
  addDebugLog: (log: string) => void;
  clearDebugLogs: () => void;
  showDebugPanel: boolean;
  setShowDebugPanel: (value: boolean) => void;
}

// Load persisted state from localStorage
function loadState<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

const defaultTools: PromptTool[] = [
  {
    id: "tool-1",
    name: "能效数据月报",
    prompt: "找出过去12个月的eff数据，放进表格，并生成合适的图表"
  },
  {
    id: "tool-2",
    name: "系统负载分析",
    prompt: "分析系统运行负载情况，找出最高功率并生成负荷趋势图表"
  },
  {
    id: "tool-3",
    name: "系统运行水耗分析",
    prompt: "分析系统月度水耗数据，生成水耗趋势图表并提供能效优化建议"
  }
];

const initialSessions = loadState<ChatSession[]>("chat_sessions", []);
const initialActiveId = loadState<string | null>("active_session_id", null);

const finalSessions = initialSessions.length > 0 ? initialSessions : [
  {
    id: "default",
    title: "New Chat",
    messages: [],
    createdAt: new Date().toISOString(),
  }
];
const finalActiveId = initialActiveId || finalSessions[0].id;
const activeSession = finalSessions.find((s) => s.id === finalActiveId) || finalSessions[0];
const initialMessages = activeSession ? activeSession.messages : [];

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
  activeReportTitle: localStorage.getItem("active_report_title") || "Untitled Report",
  activeReportContent: localStorage.getItem("active_report_content") || "Start typing or ask Copilot to generate report sections.",
  setActiveReportTitle: (title) => {
    localStorage.setItem("active_report_title", title);
    set({ activeReportTitle: title });
  },
  setActiveReportContent: (content) => {
    localStorage.setItem("active_report_content", content);
    set({ activeReportContent: content });
  },
  
  // Chat History State
  chatSessions: finalSessions,
  activeSessionId: finalActiveId,
  copilotMessages: initialMessages,
  
  setActiveSessionId: (id) =>
    set((state) => {
      const session = state.chatSessions.find((s) => s.id === id) || state.chatSessions[0];
      localStorage.setItem("active_session_id", JSON.stringify(id));
      return {
        activeSessionId: id,
        copilotMessages: session ? session.messages : [],
      };
    }),
    
  addCopilotMessage: (message) =>
    set((state) => {
      let sessions = [...state.chatSessions];
      let activeId = state.activeSessionId;
      
      if (!activeId) {
        activeId = Date.now().toString();
        sessions.push({
          id: activeId,
          title: message.content.substring(0, 30) || "New Chat",
          messages: [],
          createdAt: new Date().toISOString(),
        });
        localStorage.setItem("active_session_id", JSON.stringify(activeId));
      }
      
      sessions = sessions.map((s) => {
        if (s.id === activeId) {
          const title = s.title === "New Chat" && message.role === "user"
            ? (message.content.substring(0, 30) || "New Chat")
            : s.title;
          return {
            ...s,
            title,
            messages: [...s.messages, message],
          };
        }
        return s;
      });
      
      localStorage.setItem("chat_sessions", JSON.stringify(sessions));
      const currentActiveSession = sessions.find((s) => s.id === activeId);
      return {
        chatSessions: sessions,
        activeSessionId: activeId,
        copilotMessages: currentActiveSession ? currentActiveSession.messages : [],
      };
    }),
    
  clearCopilotMessages: () =>
    set((state) => {
      const newId = Date.now().toString();
      const newSession: ChatSession = {
        id: newId,
        title: "New Chat",
        messages: [],
        createdAt: new Date().toISOString(),
      };
      const sessions = [...state.chatSessions, newSession];
      localStorage.setItem("chat_sessions", JSON.stringify(sessions));
      localStorage.setItem("active_session_id", JSON.stringify(newId));
      return {
        chatSessions: sessions,
        activeSessionId: newId,
        copilotMessages: [],
      };
    }),
    
  deleteChatSession: (id) =>
    set((state) => {
      let sessions = state.chatSessions.filter((s) => s.id !== id);
      if (sessions.length === 0) {
        sessions = [
          {
            id: "default",
            title: "New Chat",
            messages: [],
            createdAt: new Date().toISOString(),
          }
        ];
      }
      let activeId = state.activeSessionId;
      if (activeId === id) {
        activeId = sessions[sessions.length - 1].id;
      }
      localStorage.setItem("chat_sessions", JSON.stringify(sessions));
      localStorage.setItem("active_session_id", JSON.stringify(activeId));
      const activeSession = sessions.find((s) => s.id === activeId) || sessions[0];
      return {
        chatSessions: sessions,
        activeSessionId: activeId,
        copilotMessages: activeSession ? activeSession.messages : [],
      };
    }),
    
  setChatSessions: (sessions) =>
    set((state) => {
      const activeSession = sessions.find((s) => s.id === state.activeSessionId) || sessions[0];
      localStorage.setItem("chat_sessions", JSON.stringify(sessions));
      return {
        chatSessions: sessions,
        copilotMessages: activeSession ? activeSession.messages : [],
      };
    }),
    
  chatHistoryPath: loadState<string>("chat_history_path", ""),
  setChatHistoryPath: (path) => {
    localStorage.setItem("chat_history_path", JSON.stringify(path));
    set({ chatHistoryPath: path });
  },
    
  // Prompt Tools State
  promptTools: loadState<PromptTool[]>("prompt_tools", defaultTools),
  
  addPromptTool: (tool) =>
    set((state) => {
      const next = [...state.promptTools, tool];
      localStorage.setItem("prompt_tools", JSON.stringify(next));
      return { promptTools: next };
    }),
    
  updatePromptTool: (id, updated) =>
    set((state) => {
      const next = state.promptTools.map((t) => (t.id === id ? { ...t, ...updated } : t));
      localStorage.setItem("prompt_tools", JSON.stringify(next));
      return { promptTools: next };
    }),
    
  deletePromptTool: (id) =>
    set((state) => {
      const next = state.promptTools.filter((t) => t.id !== id);
      localStorage.setItem("prompt_tools", JSON.stringify(next));
      return { promptTools: next };
    }),
  savedReports: [],
  addSavedReport: (report) =>
    set((state) => ({ savedReports: [report, ...state.savedReports] })),
  removeSavedReport: (index) =>
    set((state) => ({ savedReports: state.savedReports.filter((_, i) => i !== index) })),

  // Persist providers to localStorage
  providers: loadState<Provider[]>("providers", []),
  setProviders: (providers) => {
    localStorage.setItem("providers", JSON.stringify(providers));
    set({ providers });
  },
  addProvider: (provider) =>
    set((state) => {
      const next = [...state.providers, provider];
      localStorage.setItem("providers", JSON.stringify(next));
      return { providers: next };
    }),
  removeProvider: (name) =>
    set((state) => {
      const next = state.providers.filter((p) => p.name !== name);
      localStorage.setItem("providers", JSON.stringify(next));
      return { providers: next };
    }),

  showSettings: false,
  setShowSettings: (value) => set({ showSettings: value }),

  // Persist RAG config
  ragConfig: loadState<RAGConfig>("rag_config", {
    embedding_provider: "Nv",
    embedding_model: "nvidia/nv-embed-v1",
    rerank_enabled: true,
    rerank_model: "nv-rerank-qa-mistral-4b:1",
    chunk_size: 4096,
    chunk_overlap: 500,
    top_k: 25,
    rerank_top_k: 10,
    default_thinking_intensity: "Medium",
  }),
  setRAGConfig: (config) => {
    localStorage.setItem("rag_config", JSON.stringify(config));
    set({ ragConfig: config });
  },
  licenseInfo: null,
  setLicenseInfo: (info) => set({ licenseInfo: info }),
  debugLogs: [],
  addDebugLog: (log) =>
    set((state) => {
      const timestamp = new Date().toLocaleTimeString();
      const newLog = `[${timestamp}] ${log}`;
      return { debugLogs: [...state.debugLogs.slice(-299), newLog] };
    }),
  clearDebugLogs: () => set({ debugLogs: [] }),
  showDebugPanel: false,
  setShowDebugPanel: (value) => set({ showDebugPanel: value }),
}));
