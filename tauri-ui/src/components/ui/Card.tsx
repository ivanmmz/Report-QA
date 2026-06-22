import { HTMLAttributes, forwardRef } from "react";
import { clsx } from "clsx";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "accent";
  hover?: boolean;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant = "default", hover = true, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={clsx(
          "rounded-xl transition-all-normal",
          {
            "bg-[var(--card-bg)] border border-[var(--border)] p-4":
              variant === "default",
            "bg-[var(--accent-bg)] border border-[rgba(0,120,212,0.2)] p-4":
              variant === "accent",
            "hover:bg-[var(--card-hover)] hover:border-[var(--border-hover)]":
              hover && variant === "default",
          },
          className
        )}
        {...props}
      >
        {children}
      </div>
    );
  }
);

Card.displayName = "Card";
