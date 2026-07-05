import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "Cascadia Code", "Fira Code", "Consolas", "monospace"],
      },
      spacing: {
        xs: "4px", sm: "8px", md: "12px", lg: "16px", xl: "24px", "2xl": "32px",
        sidebar: "380px", "control-offset": "400px",
      },
      boxShadow: {
        glass: "0 8px 32px rgba(0, 0, 0, 0.12)",
        "glass-lg": "0 8px 32px rgba(0, 0, 0, 0.25)",
        button: "0 4px 12px rgba(0, 120, 212, 0.3)",
      },
      animation: { "fade-in": "fadeIn 0.2s ease-out" },
      keyframes: { fadeIn: { "0%": { opacity: "0" }, "100%": { opacity: "1" } } },
    },
  },
  plugins: [],
} satisfies Config;
