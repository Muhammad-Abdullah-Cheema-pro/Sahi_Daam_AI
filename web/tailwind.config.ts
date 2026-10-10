import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./hooks/**/*.{ts,tsx}",
    "./context/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        emerald: {
          950: "#022C22",
          900: "#064E3B",
          800: "#065F46",
          700: "#047857",
          600: "#059669",
          100: "#D1FAE5",
          50: "#ECFDF5",
        },
        clay: {
          700: "#9A3412",
          500: "#C2410C",
          300: "#FDBA74",
          100: "#FFEDD5",
          50: "#FFF7ED",
        },
        sand: {
          100: "#F5F0E6",
          50: "#FAF7F2",
        },
      },
      fontFamily: {
        naskh: ["var(--font-naskh)", "serif"],
        nastaliq: ["var(--font-nastaliq)", "serif"],
        inter: ["var(--font-inter)", "sans-serif"],
      },
      fontSize: {
        base: ["1.125rem", { lineHeight: "1.7" }],
      },
      minHeight: {
        tap: "48px",
      },
      minWidth: {
        tap: "48px",
      },
      transitionProperty: {
        lang: "opacity, transform, color, background-color",
      },
    },
  },
  plugins: [],
};

export default config;
