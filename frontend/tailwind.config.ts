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
        // Stage (Colder Slate/Zinc for industrial feel)
        ink: {
          950: "#09090b",
          900: "#18181b",
          850: "#222225",
          800: "#27272a",
          750: "#323235",
          700: "#3f3f46",
          600: "#52525b",
          500: "#71717a",
          400: "#a1a1aa",
          300: "#d4d4d8",
          200: "#e4e4e7",
          100: "#f4f4f5",
          50: "#fafafa",
        },
        // Sodium amber — industrial tech accent
        sodium: {
          50: "#fff8ed",
          100: "#ffefd3",
          200: "#ffdfa6",
          300: "#ffc96a",
          400: "#ffad2b",
          500: "#ff9100", // pure safety orange/amber
          600: "#ea7500",
          700: "#c25802",
          800: "#9a430a",
          900: "#7c380b",
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
        "fade-in": "fade-in 0.3s ease-out forwards",
        "slide-up": "slide-up 0.45s cubic-bezier(0.16, 1, 0.3, 1) forwards",
      },
    },
  },
  plugins: [],
};

export default config;
