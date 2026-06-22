import { ButtonHTMLAttributes, forwardRef } from "react";
import { clsx } from "clsx";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost" | "danger" | "icon";
  size?: "sm" | "md" | "lg";
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={clsx(
          "inline-flex items-center justify-center font-medium transition-all-fast",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          {
            // Variants
            "bg-[var(--accent)] text-white hover:bg-[#005a9e] hover:-translate-y-0.5 hover:shadow-button active:translate-y-0":
              variant === "primary",
            "bg-transparent border border-[rgba(128,128,128,0.3)] text-[var(--text0)] hover:bg-[var(--accent-hover)] hover:border-[rgba(128,128,128,0.5)]":
              variant === "ghost",
            "bg-transparent border border-[rgba(224,85,85,0.35)] text-[#e05555] hover:bg-[rgba(224,85,85,0.08)]":
              variant === "danger",
            "bg-[var(--bg2)] border border-[var(--border)] text-[var(--text0)] hover:bg-[var(--accent-hover)] hover:border-[#0078d4] hover:text-[#0078d4] hover:scale-105":
              variant === "icon",
            // Sizes
            "h-8 px-3 text-xs rounded-lg": size === "sm",
            "h-10 px-6 text-sm rounded-lg": size === "md",
            "h-12 px-8 text-base rounded-xl": size === "lg",
          },
          className
        )}
        {...props}
      >
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
