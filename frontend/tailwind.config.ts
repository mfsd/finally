import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: "#0d1117",
          panel: "#111827",
          panel2: "#1a1a2e",
          border: "#2d3748",
          text: "#d6deeb",
          muted: "#8b949e"
        },
        ally: {
          yellow: "#ecad0a",
          blue: "#209dd7",
          purple: "#753991",
          green: "#22c55e",
          red: "#ef4444"
        }
      },
      fontFamily: {
        mono: ["var(--font-geist-mono)", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"]
      },
      boxShadow: {
        terminal: "0 0 0 1px rgba(45,55,72,.8), 0 18px 50px rgba(0,0,0,.35)"
      }
    }
  },
  plugins: []
};

export default config;
