import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Stage
        ink: {
          950: "#0A0B0D",
          900: "#0E0F12",
          850: "#131417",
          800: "#181A1E",
          750: "#1A1B1F",
          700: "#1E2025",
          600: "#23252B",
          500: "#2E3038",
          400: "#3A3D46",
          300: "#5A5D65",
          200: "#8B8E96",
          100: "#B8BBC2",
          50: "#EDEEF0",
        },
        // Sodium amber — the signature accent
        sodium: {
          50: "#FEF7E6",
          100: "#FDEEC2",
          200: "#FCE08C",
          300: "#F9CE5F",
          400: "#F7C24D",
          500: "#F5B947",
          600: "#D9A234",
          700: "#A87D27",
          800: "#78591B",
          900: "#3F2F0E",
        },
        // Steel blue — data accent
        steel: {
          400: "#94AEFF",
          500: "#6B8AFF",
          600: "#4F6FE6",
          700: "#3D55B3",
        },
        // Status
        live: {
          ok: "#4ADE80",
          pending: "#FBBF24",
          reject: "#F87171",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        display: ["var(--font-inter-tight)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "ui-monospace", "monospace"],
        serif: ["var(--font-instrument)", "Georgia", "serif"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.04em" }],
      },
      letterSpacing: {
        tightest: "-0.04em",
      },
      borderRadius: {
        DEFAULT: "6px",
        lg: "10px",
        xl: "14px",
      },
      keyframes: {
        "pulse-live": {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.45", transform: "scale(1.35)" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.7)", opacity: "0.7" },
          "100%": { transform: "scale(2.4)", opacity: "0" },
        },
        "shimmer": {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "typewriter": {
          "0%": { width: "0" },
          "100%": { width: "100%" },
        },
      },
      animation: {
        "pulse-live": "pulse-live 1.6s ease-in-out infinite",
        "pulse-ring": "pulse-ring 1.6s ease-out infinite",
        "shimmer": "shimmer 2.4s linear infinite",
        "fade-in": "fade-in 0.5s ease-out forwards",
        "slide-up": "slide-up 0.45s cubic-bezier(0.16, 1, 0.3, 1) forwards",
      },
    },
  },
  plugins: [],
};

export default config;
