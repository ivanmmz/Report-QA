import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Key, Copy, Check, ShieldAlert, Cpu, Sparkles, RefreshCw, Github, Mail, Clock } from "lucide-react";

interface ActivationPageProps {
  onActivated: () => void;
  trialExpired?: boolean;
}

export default function ActivationPage({ onActivated, trialExpired = false }: ActivationPageProps) {
  const [machineCode, setMachineCode] = useState<string>("Loading...");
  const [regCode, setRegCode] = useState<string>("");
  const [isCopied, setIsCopied] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    invoke<string>("get_machine_code")
      .then(setMachineCode)
      .catch((err) => setMachineCode("Error fetching machine code: " + err));
  }, []);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(machineCode);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy text: ", err);
    }
  };

  const handleActivate = async () => {
    if (!regCode.trim()) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      await invoke("activate_license", { code: regCode.trim() });
      onActivated();
    } catch (err) {
      setErrorMsg(String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleDevAutoActivate = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const devCode = await invoke<string>("generate_test_license_code");
      setRegCode(devCode);
      await invoke("activate_license", { code: devCode });
      setTimeout(() => {
        onActivated();
      }, 1000);
    } catch (err) {
      setErrorMsg("Dev activation failed: " + err);
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[99999] flex items-center justify-center bg-[#090b0f] text-[#e4e6eb] font-sans"
      style={{
        backgroundImage: "radial-gradient(circle at 50% 50%, #1e1b4b 0%, #090b0f 100%)",
      }}
    >
      {/* Sleek card container */}
      <div
        className="w-full max-w-md p-8 rounded-2xl border border-[rgba(255,255,255,0.08)] shadow-2xl relative overflow-hidden"
        style={{
          background: "rgba(13, 17, 23, 0.7)",
          backdropFilter: "blur(20px)",
          boxShadow: "0 8px 32px 0 rgba(0, 0, 0, 0.37)",
        }}
      >
        {/* Glow decoration */}
        <div className="absolute -top-24 -left-24 w-48 h-48 rounded-full bg-[var(--accent)] opacity-20 blur-3xl" />
        <div className="absolute -bottom-24 -right-24 w-48 h-48 rounded-full bg-[#7c3aed] opacity-20 blur-3xl" />

        {/* Header */}
        <div className="flex flex-col items-center text-center mb-8 relative">
          <div
            className="w-14 h-14 rounded-xl flex items-center justify-center mb-4"
            style={{
              background: trialExpired
                ? "linear-gradient(135deg, #e05555 0%, #b91c1c 100%)"
                : "linear-gradient(135deg, var(--accent) 0%, #7c3aed 100%)",
              boxShadow: trialExpired
                ? "0 0 20px rgba(224,85,85,0.3)"
                : "0 0 20px rgba(0, 188, 242, 0.3)",
            }}
          >
            {trialExpired ? (
              <Clock className="w-6 h-6 text-white" />
            ) : (
              <Key className="w-6 h-6 text-white" />
            )}
          </div>
          {trialExpired ? (
            <>
              <h2 className="text-xl font-bold tracking-tight text-white">Trial Period Ended</h2>
              <p className="text-xs text-[var(--text2)] mt-1">
                Your 90-day free trial has expired. Enter a license key below or contact us to continue.
              </p>
            </>
          ) : (
            <>
              <h2 className="text-xl font-bold tracking-tight text-white">Software Activation</h2>
              <p className="text-xs text-[var(--text2)] mt-1">Please enter your registration code to activate Report QA</p>
            </>
          )}
        </div>

        {/* Contact info — only shown when trial has expired */}
        {trialExpired && (
          <div className="mb-6 p-4 rounded-xl border border-[rgba(224,85,85,0.25)] bg-[rgba(224,85,85,0.06)] space-y-3">
            <p className="text-xs text-[var(--text2)] leading-relaxed">
              To extend your trial or purchase a license, reach out via:
            </p>
            <div className="flex flex-col gap-2">
              <a
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  window.open("https://github.com/ivanmmz/Report-QA", "_blank");
                }}
                className="flex items-center gap-2 text-xs text-[var(--accent)] hover:underline"
              >
                <Github className="w-3.5 h-3.5" />
                github.com/ivanmmz/Report-QA
              </a>
              <a
                href="mailto:imamingze@gmail.com"
                className="flex items-center gap-2 text-xs text-[var(--accent)] hover:underline"
              >
                <Mail className="w-3.5 h-3.5" />
                imamingze@gmail.com
              </a>
            </div>
          </div>
        )}

        {/* Content body */}
        <div className="space-y-6 relative">
          {/* Machine code segment */}
          <div>
            <label className="block text-xs font-semibold text-[var(--text2)] uppercase tracking-wider mb-2">
              Your Hardware Challenge Code
            </label>
            <div className="flex items-center gap-2 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-xl px-4 py-3">
              <span className="font-mono text-sm tracking-wide text-white select-all truncate flex-1">
                {machineCode}
              </span>
              <button
                onClick={handleCopy}
                className="text-[var(--text2)] hover:text-white p-1 rounded-lg transition-colors hover:bg-[rgba(255,255,255,0.05)]"
                title="Copy machine code"
              >
                {isCopied ? <Check className="w-4 h-4 text-[#00cc6a]" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-[10px] text-[var(--text2)] mt-1.5">
              Send this challenge code to Ivan to request a permanent offline registration code.
            </p>
          </div>

          {/* Registration Code Input */}
          <div>
            <label className="block text-xs font-semibold text-[var(--text2)] uppercase tracking-wider mb-2">
              Registration Code
            </label>
            <textarea
              value={regCode}
              onChange={(e) => setRegCode(e.target.value)}
              placeholder="EXD-A82D-9C21-FA87..."
              rows={3}
              className="w-full bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.08)] rounded-xl px-4 py-3 text-sm font-mono text-white placeholder:text-[var(--text2)] focus:border-[rgba(0,188,242,0.4)] focus:outline-none resize-none transition-colors"
            />
          </div>

          {/* Error Message */}
          {errorMsg && (
            <div className="flex gap-2.5 p-3.5 bg-[rgba(224,85,85,0.1)] border border-[rgba(224,85,85,0.25)] rounded-xl text-xs text-[#ff6b6b]">
              <ShieldAlert className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Action button */}
          <div className="space-y-3 pt-2">
            <button
              onClick={handleActivate}
              disabled={loading || !regCode.trim()}
              className="w-full py-3 px-4 rounded-xl font-semibold text-sm text-white flex items-center justify-center gap-2 transition-all"
              style={{
                background: "linear-gradient(135deg, var(--accent) 0%, #7c3aed 100%)",
                opacity: (loading || !regCode.trim()) ? 0.6 : 1,
                cursor: (loading || !regCode.trim()) ? "not-allowed" : "pointer",
                boxShadow: "0 4px 15px rgba(0, 188, 242, 0.2)",
              }}
            >
              {loading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4" />
              )}
              {loading ? "Activating..." : "Activate Now"}
            </button>

            {/* Developer Test Bypass */}
            <div className="border-t border-[rgba(255,255,255,0.06)] pt-4 mt-2">
              <div className="text-[11px] text-[var(--text2)] text-center mb-2">
                🔒 Developer Mode Detected
              </div>
              <button
                onClick={handleDevAutoActivate}
                disabled={loading}
                className="w-full py-2.5 px-4 rounded-xl border border-dashed border-[rgba(0,188,242,0.3)] bg-[rgba(0,188,242,0.03)] hover:bg-[rgba(0,188,242,0.08)] text-[var(--accent)] font-semibold text-xs transition-colors flex items-center justify-center gap-1.5"
              >
                <Cpu className="w-3.5 h-3.5" /> One-click Developer Activation
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
