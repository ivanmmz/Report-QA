import { useState, useEffect } from "react";
import { check } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";
import { Download, X, RefreshCw } from "lucide-react";

type State =
  | { phase: "idle" }
  | { phase: "available"; version: string; body: string }
  | { phase: "downloading"; pct: number }
  | { phase: "ready" }
  | { phase: "error"; msg: string };

export default function UpdateBanner() {
  const [state, setState] = useState<State>({ phase: "idle" });
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!(window as any).__TAURI_INTERNALS__) return;
    (async () => {
      try {
        const update = await check();
        if (update?.available) {
          setState({ phase: "available", version: update.version, body: update.body ?? "" });
        }
      } catch { /* silently ignore */ }
    })();
  }, []);

  const handleUpdate = async () => {
    if (state.phase !== "available") return;
    try {
      const update = await check();
      if (!update?.available) return;
      setState({ phase: "downloading", pct: 0 });
      let downloaded = 0;
      let total = 0;
      await update.downloadAndInstall((event) => {
        switch (event.event) {
          case "Started":
            total = event.data.contentLength ?? 0;
            break;
          case "Progress":
            downloaded += event.data.chunkLength;
            setState({ phase: "downloading", pct: total > 0 ? Math.round((downloaded / total) * 100) : 50 });
            break;
          case "Finished":
            setState({ phase: "ready" });
            break;
        }
      });
    } catch (err) {
      setState({ phase: "error", msg: String(err) });
    }
  };

  if (dismissed || state.phase === "idle") return null;

  const base: React.CSSProperties = {
    position: "fixed", top: 0, left: 0, right: 0, zIndex: 99999,
    background: "linear-gradient(90deg,#0d7cf2 0%,#7c3aed 100%)",
    color: "#fff", fontSize: 13, display: "flex", alignItems: "center",
    gap: 12, padding: "6px 16px", boxShadow: "0 2px 12px rgba(0,0,0,.4)",
  };
  const btn: React.CSSProperties = {
    background: "rgba(255,255,255,.2)", border: "1px solid rgba(255,255,255,.4)",
    color: "#fff", borderRadius: 6, padding: "3px 12px",
    cursor: "pointer", fontWeight: 600, fontSize: 12, whiteSpace: "nowrap",
  };
  const ghost: React.CSSProperties = { background: "none", border: "none", color: "rgba(255,255,255,.7)", cursor: "pointer", padding: 2 };

  return (
    <div id="update-banner" style={base}>
      {state.phase === "available" && (<>
        <Download style={{ width: 15, height: 15, flexShrink: 0 }} />
        <span style={{ flex: 1 }}>Update <strong>v{state.version}</strong> available{state.body ? ` — ${state.body.slice(0, 80)}` : ""}</span>
        <button id="update-and-restart-btn" style={btn} onClick={handleUpdate}>Update and restart</button>
        <button style={ghost} onClick={() => setDismissed(true)} title="Dismiss"><X style={{ width: 14, height: 14 }} /></button>
      </>)}

      {state.phase === "downloading" && (<>
        <RefreshCw style={{ width: 15, height: 15, flexShrink: 0 }} />
        <span style={{ flex: 1 }}>Downloading… {state.pct}%</span>
        <div style={{ width: 120, height: 6, background: "rgba(255,255,255,.3)", borderRadius: 3, overflow: "hidden" }}>
          <div style={{ width: `${state.pct}%`, height: "100%", background: "#fff", borderRadius: 3, transition: "width .2s" }} />
        </div>
      </>)}

      {state.phase === "ready" && (<>
        <span style={{ flex: 1 }}>✅ Update downloaded!</span>
        <button id="restart-now-btn" style={{ ...btn, fontWeight: 700 }} onClick={() => relaunch()}>Restart Now</button>
      </>)}

      {state.phase === "error" && (<>
        <span style={{ flex: 1 }}>⚠️ Update failed: {state.msg}</span>
        <button style={ghost} onClick={() => setState({ phase: "idle" })}><X style={{ width: 14, height: 14 }} /></button>
      </>)}
    </div>
  );
}
