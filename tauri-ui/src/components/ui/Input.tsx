import { InputHTMLAttributes, forwardRef } from "react";
import { clsx } from "clsx";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, ...props }, ref) => (
    <div className="w-full">
      {label && <label className="block text-sm font-medium text-[var(--text1)] mb-1">{label}</label>}
      <input
        ref={ref}
        className={clsx(
          "w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg",
          "text-[var(--text0)] px-3 py-2.5 text-sm placeholder:text-[var(--text2)]",
          "focus:border-[rgba(0,188,242,0.5)] focus:outline-none transition-all-fast",
          error && "border-[#e05555]",
          className
        )}
        {...props}
      />
      {error && <p className="mt-1 text-xs text-[#e05555]">{error}</p>}
    </div>
  )
);

Input.displayName = "Input";
