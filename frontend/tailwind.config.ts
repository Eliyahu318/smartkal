import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Heebo Variable",
          "-apple-system",
          "BlinkMacSystemFont",
          "SF Pro Text",
          "Segoe UI",
          "system-ui",
          "sans-serif",
        ],
      },
      colors: {
        // Backgrounds
        app: "rgb(var(--bg-app) / <alpha-value>)",
        grouped: "rgb(var(--bg-grouped) / <alpha-value>)",
        "grouped-secondary": "rgb(var(--bg-grouped-secondary) / <alpha-value>)",
        "grouped-tertiary": "rgb(var(--bg-grouped-tertiary) / <alpha-value>)",

        // Surfaces
        surface: "rgb(var(--surface) / <alpha-value>)",
        "surface-elevated": "rgb(var(--surface-elevated) / <alpha-value>)",
        "surface-overlay": "rgb(var(--surface-overlay) / <alpha-value>)",

        // Labels (Apple text hierarchy)
        label: "rgb(var(--label) / <alpha-value>)",
        "label-secondary": "rgb(var(--label-secondary) / <alpha-value>)",
        "label-tertiary": "rgb(var(--label-tertiary) / <alpha-value>)",
        "label-quaternary": "rgb(var(--label-quaternary) / <alpha-value>)",

        // Separators
        separator: "rgb(var(--separator) / <alpha-value>)",
        "separator-opaque": "rgb(var(--separator-opaque) / <alpha-value>)",

        // Fills
        fill: "rgb(var(--fill) / <alpha-value>)",
        "fill-secondary": "rgb(var(--fill-secondary) / <alpha-value>)",
        "fill-tertiary": "rgb(var(--fill-tertiary) / <alpha-value>)",

        // Brand & status
        brand: "rgb(var(--brand) / <alpha-value>)",
        "brand-hover": "rgb(var(--brand-hover) / <alpha-value>)",
        "brand-pressed": "rgb(var(--brand-pressed) / <alpha-value>)",
        "on-brand": "rgb(var(--on-brand) / <alpha-value>)",

        success: "rgb(var(--success) / <alpha-value>)",
        warning: "rgb(var(--warning) / <alpha-value>)",
        danger: "rgb(var(--danger) / <alpha-value>)",
        info: "rgb(var(--info) / <alpha-value>)",
        link: "rgb(var(--link) / <alpha-value>)",

        // Categorical accents (system colors used for per-section identity)
        "accent-purple": "rgb(var(--accent-purple) / <alpha-value>)",
        "accent-blue": "rgb(var(--accent-blue) / <alpha-value>)",
      },
      borderRadius: {
        "ios-sm": "10px",
        ios: "14px",
        "ios-lg": "20px",
        "ios-sheet": "28px",
      },
      boxShadow: {
        "ios-sm": "0 1px 2px 0 rgb(0 0 0 / 0.04), 0 1px 1px 0 rgb(0 0 0 / 0.03)",
        "ios-md":
          "0 4px 12px -2px rgb(0 0 0 / 0.06), 0 2px 4px -1px rgb(0 0 0 / 0.04)",
        "ios-lg":
          "0 12px 24px -6px rgb(0 0 0 / 0.10), 0 4px 8px -2px rgb(0 0 0 / 0.06)",
        "ios-sheet":
          "0 24px 48px -12px rgb(0 0 0 / 0.18), 0 8px 16px -4px rgb(0 0 0 / 0.08)",
      },
      transitionTimingFunction: {
        ios: "cubic-bezier(0.32, 0.72, 0, 1)",
      },
      maxWidth: {
        phone: "430px",
      },
      fontSize: {
        // iOS HIG type scale
        largeTitle: ["34px", { lineHeight: "41px", fontWeight: "700" }],
        title1: ["28px", { lineHeight: "34px", fontWeight: "700" }],
        title2: ["22px", { lineHeight: "28px", fontWeight: "700" }],
        title3: ["20px", { lineHeight: "25px", fontWeight: "600" }],
        headline: ["17px", { lineHeight: "22px", fontWeight: "600" }],
        body: ["17px", { lineHeight: "22px", fontWeight: "400" }],
        callout: ["16px", { lineHeight: "21px", fontWeight: "400" }],
        subhead: ["15px", { lineHeight: "20px", fontWeight: "400" }],
        footnote: ["13px", { lineHeight: "18px", fontWeight: "400" }],
        caption1: ["12px", { lineHeight: "16px", fontWeight: "400" }],
        caption2: ["11px", { lineHeight: "13px", fontWeight: "400" }],
      },
      keyframes: {
        "slide-up": {
          "0%": { transform: "translateY(100%)" },
          "100%": { transform: "translateY(0)" },
        },
      },
      animation: {
        "slide-up": "slide-up 250ms cubic-bezier(0.32, 0.72, 0, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
