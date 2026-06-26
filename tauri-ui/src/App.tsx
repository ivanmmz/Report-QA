import { useEffect } from "react";
import MainLayout from "./components/layout/MainLayout";
import { useAppStore } from "./stores/appStore";

function App() {
  const { isDark, toggleTheme, providers, ragConfig, chatSessions, chatHistoryPath, setChatSessions, setChatHistoryPath } = useAppStore();

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
    document.documentElement.classList.toggle("light", !isDark);
  }, [isDark]);

  // Dynamically initialize chatHistoryPath on startup if it is not configured
  useEffect(() => {
    const initPath = async () => {
      if (!chatHistoryPath) {
        try {
          const { invoke } = await import("@tauri-apps/api/core");
          const defaultPath: string = await invoke("get_default_config_dir");
          setChatHistoryPath(defaultPath);
          console.log("Dynamically initialized default chat history path:", defaultPath);
        } catch (err) {
          console.error("Failed to get default config directory from Rust:", err);
        }
      }
    };
    initPath();
  }, [chatHistoryPath, setChatHistoryPath]);

  // Auto-sync configuration to Python backend on startup / store changes
  useEffect(() => {
    const syncConfig = async () => {
      const config: any = {
        providers: {},
        default_provider: ragConfig.embedding_provider,
        default_model: ragConfig.embedding_model,
      };
      providers.forEach((p) => {
        config.providers[p.name] = {
          base_url: p.baseUrl,
          api_key: p.apiKey,
          models: p.models,
          description: "",
        };
      });
      config._rag_config = ragConfig;
      const json = JSON.stringify(config, null, 2);

      try {
        const { invoke } = await import("@tauri-apps/api/core");
        await invoke("save_api_keys", { config_json: json });
        console.log("Auto-synced API keys and settings to Python backend.");
      } catch (err) {
        console.error("Failed to auto-sync config to Python backend:", err);
      }
    };

    syncConfig();
  }, [providers, ragConfig]);

  // Load chat history from custom file on startup / path changes
  useEffect(() => {
    const loadHistory = async () => {
      if (!chatHistoryPath) return;
      try {
        const { exists, readTextFile, mkdir } = await import("@tauri-apps/plugin-fs");
        
        // Ensure directory exists
        const dirExists = await exists(chatHistoryPath);
        if (!dirExists) {
          await mkdir(chatHistoryPath, { recursive: true });
        }
        
        const filePath = `${chatHistoryPath}/chat_sessions.json`.replace(/\\/g, "/");
        const fileExists = await exists(filePath);
        
        if (fileExists) {
          const content = await readTextFile(filePath);
          if (content.trim()) {
            const sessions = JSON.parse(content);
            if (Array.isArray(sessions) && sessions.length > 0) {
              setChatSessions(sessions);
              console.log("Loaded chat sessions from custom path:", filePath);
              return;
            }
          }
        }
        
        // If file doesn't exist or is empty, write the current store sessions to create it
        const { writeTextFile } = await import("@tauri-apps/plugin-fs");
        await writeTextFile(filePath, JSON.stringify(chatSessions, null, 2));
      } catch (err) {
        console.error("Failed to load chat history from file:", err);
      }
    };
    
    setTimeout(loadHistory, 100);
  }, [chatHistoryPath]);

  // Save chat history to custom file whenever sessions change
  useEffect(() => {
    const saveHistory = async () => {
      if (!chatHistoryPath) return;
      try {
        const { exists, mkdir, writeTextFile } = await import("@tauri-apps/plugin-fs");
        
        const dirExists = await exists(chatHistoryPath);
        if (!dirExists) {
          await mkdir(chatHistoryPath, { recursive: true });
        }
        
        const filePath = `${chatHistoryPath}/chat_sessions.json`.replace(/\\/g, "/");
        await writeTextFile(filePath, JSON.stringify(chatSessions, null, 2));
        console.log("Saved chat sessions to custom path:", filePath);
      } catch (err) {
        console.error("Failed to save chat history to file:", err);
      }
    };

    saveHistory();
  }, [chatSessions, chatHistoryPath]);

  return (
    <div className={isDark ? "dark" : "light"}>
      <MainLayout isDark={isDark} toggleTheme={toggleTheme} />
    </div>
  );
}

export default App;
