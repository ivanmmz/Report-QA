import { useState } from "react";
import { AlertTriangle, X, Github } from "lucide-react";

interface TrialBannerProps {
  daysLeft: number;
}

export default function TrialBanner({ daysLeft }: TrialBannerProps) {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;

  const urgency = daysLeft <= 14;

  return (
    <div
      style={{
        background: urgency
          ? "linear-gradient(90deg, rgba(224,85,85,0.12) 0%, rgba(180,30,30,0.08) 100%)"
          : "linear-gradient(90deg, rgba(251,191,36,0.10) 0%, rgba(245,158,11,0.06) 100%)",
        borderBottom: urgency
          ? "1px solid rgba(224,85,85,0.25)"
          : "1px solid rgba(251,191,36,0.22)",
      }}
      className="relative flex items-center justify-between gap-3 px-4 py-2 text-xs z-50"
    >
      {/* Left: icon + message */}
      <div className="flex items-center gap-2 min-w-0">
        <AlertTriangle
          className="w-3.5 h-3.5 shrink-0"
          style={{ color: urgency ? "#e05555" : "#f59e0b" }}
        />
        <span
          className="truncate"
          style={{ color: urgency ? "#f87171" : "#fcd34d" }}
        >
          <span className="font-semibold">
            Trial — {daysLeft} day{daysLeft !== 1 ? "s" : ""} remaining.&nbsp;
          </span>
          This software is under active development; features may be incomplete
          or change without notice.
        </span>
      </div>

      {/* Right: GitHub link + dismiss */}
      <div className="flex items-center gap-3 shrink-0">
        <button
          onClick={() => window.open("https://github.com/ivanmmz/Report-QA/issues", "_blank")}
          className="flex items-center gap-1 font-medium hover:underline transition-opacity hover:opacity-80"
          style={{ color: urgency ? "#f87171" : "#fcd34d" }}
        >
          <Github className="w-3 h-3" />
          Report on GitHub
        </button>
        <button
          onClick={() => setDismissed(true)}
          className="opacity-50 hover:opacity-100 transition-opacity"
          style={{ color: urgency ? "#f87171" : "#fcd34d" }}
          title="Dismiss"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
