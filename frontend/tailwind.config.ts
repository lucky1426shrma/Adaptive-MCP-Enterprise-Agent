import type { Config } from "tailwindcss";

// Design tokens for the investigation console. Palette is deliberately
// NOT the generic warm-cream/terracotta AI-chat default — this is a
// telemetry/trace-toned console (the system it's a UI for is literally
// OpenTelemetry-traced end to end), and the three "server" colors below
// are semantic: they're the same hue used to badge RAG/DB/GitHub calls
// throughout the tool timeline, so a person can visually group a trace
// by source at a glance without reading every label.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0B0E11",
        surface: "#12161C",
        "surface-raised": "#171C24",
        border: "#232933",
        "border-subtle": "#1A1F27",
        "text-primary": "#E7EAEE",
        "text-secondary": "#8B93A1",
        "text-tertiary": "#5B6472",
        accent: "#2DD4BF",
        "accent-dim": "#123B37",
        success: "#34D399",
        "success-dim": "#0F2E24",
        warning: "#FBBF24",
        "warning-dim": "#332A0D",
        danger: "#F87171",
        "danger-dim": "#331616",
        "server-rag": "#2DD4BF",
        "server-db": "#A78BFA",
        "server-github": "#94A3B8",
      },
      fontFamily: {
        sans: ["var(--font-plex-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-plex-mono)", "ui-monospace", "monospace"],
      },
      animation: {
        "fade-in": "fade-in 320ms ease-out both",
        "pulse-dot": "pulse-dot 1.4s ease-in-out infinite",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "0.35" },
          "50%": { opacity: "1" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
