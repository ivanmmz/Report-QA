import { useEffect } from "react";
import MainLayout from "./components/layout/MainLayout";
import UpdateBanner from "./components/layout/UpdateBanner";
import ActivationPage from "./components/layout/ActivationPage";
import TrialBanner from "./components/layout/TrialBanner";
import { useAppStore } from "./stores/appStore";

function App() {
  const {
    isDark, toggleTheme, providers, ragConfig, chatSessions,
    chatHistoryPath, setChatSessions, setChatHistoryPath,
    licenseInfo, setLicenseInfo
  } = useAppStore();

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
    document.documentElement.classList.toggle("light", !isDark);
  }, [isDark]);

  // Dynamically initialize chatHistoryPath on startup if it is not configured
  useEffect(() => {
    const initPath = async () => {
      if (!chatHistoryPath) {
        if (!(window as any).__TAURI_INTERNALS__) {
          setChatHistoryPath("dev-browser-config");
          return;
        }
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
      if (!(window as any).__TAURI_INTERNALS__) return;
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
          enabled: p.enabled !== false,
          description: "",
        };
      });
      config._rag_config = ragConfig;
      const json = JSON.stringify(config, null, 2);

      try {
        const { invoke } = await import("@tauri-apps/api/core");
        await invoke("save_api_keys", { configJson: json });
        console.log("Auto-synced API keys and settings to Python backend.");
      } catch (err) {
        console.error("Failed to auto-sync config to Python backend:", err);
      }
    };

    syncConfig();
  }, [providers, ragConfig]);

  // Listen to background Python logs and add them to debug console
  useEffect(() => {
    let unlisten: (() => void) | null = null;
    const setupListener = async () => {
      if (!(window as any).__TAURI_INTERNALS__) return;
      try {
        const { listen } = await import("@tauri-apps/api/event");
        const { addDebugLog } = useAppStore.getState();
        const sub = await listen<string>("python-log", (event) => {
          addDebugLog(event.payload);
        });
        unlisten = sub;
      } catch (err) {
        console.error("Failed to setup python-log event listener:", err);
      }
    };
    setupListener();
    return () => {
      if (unlisten) {
        unlisten();
      }
    };
  }, []);

  // Load chat history from custom file on startup / path changes
  useEffect(() => {
    const loadHistory = async () => {
      if (!(window as any).__TAURI_INTERNALS__) return;
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
      if (!(window as any).__TAURI_INTERNALS__) return;
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

  const checkLicenseStatus = async () => {
    if (!(window as any).__TAURI_INTERNALS__) {
      console.log("Running in browser dev mode, bypassing offline activation intercept.");
      setLicenseInfo({
        is_activated: true,
        is_expired: false,
        license_id: "DEV-BROWSER-MODE",
        edition: "Enterprise",
        expire_date: "2099-12-31",
        permanent: true,
        features: ["PDF_EXPORT", "WORD_EXPORT", "AI", "PLUGIN"],
        is_trial: false,
        trial_days_left: 0,
      });
      return;
    }

    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const info = await invoke<any>("check_license");
      setLicenseInfo(info);
    } catch (err) {
      console.error("License check failed:", err);
      setLicenseInfo({
        is_activated: false,
        is_expired: false,
        license_id: "",
        edition: "Trial",
        expire_date: "",
        permanent: false,
        features: [],
        is_trial: true,
        trial_days_left: 90,
      });
    }
  };

  useEffect(() => {
    checkLicenseStatus();
  }, []);

  if (!licenseInfo) {
    return (
      <div className="fixed inset-0 bg-[#090b0f] flex items-center justify-center text-[var(--text1)] text-sm font-medium">
        Verifying software integrity...
      </div>
    );
  }

  // Trial expired or explicitly not activated with no remaining trial days → activation gate
  const trialExpired = licenseInfo.is_trial && licenseInfo.trial_days_left <= 0;
  if ((!licenseInfo.is_activated || licenseInfo.is_expired) && (!licenseInfo.is_trial || trialExpired)) {
    return <ActivationPage onActivated={checkLicenseStatus} trialExpired={trialExpired} />;
  }

  return (
    <div className={isDark ? "dark" : "light"}>
      <UpdateBanner />
      {licenseInfo.is_trial && licenseInfo.trial_days_left > 0 && (
        <TrialBanner daysLeft={licenseInfo.trial_days_left} />
      )}
      <MainLayout isDark={isDark} toggleTheme={toggleTheme} />
    </div>
  );
}

export default App;
