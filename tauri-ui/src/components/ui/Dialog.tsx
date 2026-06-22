import { ReactNode, useEffect, useRef } from "react";
import { clsx } from "clsx";
import { X } from "lucide-react";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  title?: string;
  className?: string;
}

export function Dialog({ open, onClose, children, title, className }: DialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (open) {
      dialog.showModal();
    } else {
      dialog.close();
    }
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      className={clsx(
        "backdrop:bg-[var(--dialog-overlay)] bg-transparent border-none p-0",
        "rounded-xl overflow-hidden",
        className
      )}
    >
      <div className="bg-[var(--bg1)] text-[var(--text0)] border border-[var(--border)] rounded-xl shadow-glass-lg min-w-[400px] max-w-[90vw] max-h-[90vh] overflow-hidden">
        {/* Header */}
        {title && (
          <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border)]">
            <h2 className="text-heading-2">{title}</h2>
            <button
              onClick={onClose}
              className="p-1 rounded-lg hover:bg-[var(--bg2)] transition-all-fast"
            >
              <X className="w-5 h-5 text-[var(--text1)]" />
            </button>
          </div>
        )}

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-120px)]">
          {children}
        </div>
      </div>
    </dialog>
  );
}
