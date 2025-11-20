const plugin = require("tailwindcss/plugin");
const typography = require("@tailwindcss/typography");

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx}",
    "./src/components/**/*.{js,ts,jsx,tsx}",
    "./src/lib/**/*.{js,ts,jsx,tsx}",
    "./stories/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Geist", "Geist Sans", "Inter", "system-ui", "sans-serif"],
        heading: ["Geist Sans", "Inter", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "SFMono-Regular", "monospace"]
      },
      letterSpacing: {
        tightest: "-0.04em",
        tighter: "-0.02em"
      },
      colors: {
        canvas: {
          light: "#F6F6F9",
          DEFAULT: "#05070F",
          dark: "#04060C"
        },
        background: {
          light: "#F6F6F9",
          dark: "#05070F",
          cardLight: "#FFFFFF",
          cardDark: "#0E1422"
        },
        surface: {
          DEFAULT: "#0E1422",
          muted: "#141B2B",
          elevated: "rgba(19, 26, 41, 0.75)"
        },
        border: {
          subtle: "rgba(255, 255, 255, 0.06)",
          DEFAULT: "rgba(255, 255, 255, 0.12)",
          strong: "#273147",
          light: "#E2E6F0",
          dark: "rgba(255, 255, 255, 0.12)"
        },
        text: {
          primaryLight: "#0B1220",
          secondaryLight: "#5B6474",
          primaryDark: "#F7F9FC",
          secondaryDark: "#B1B8C7",
          muted: "#7A849A"
        },
        primary: {
          DEFAULT: "#3B82F6",
          hover: "#2563EB",
          muted: "rgba(59, 130, 246, 0.15)",
          foreground: "#FFFFFF"
        },
        accent: {
          info: "#60A5FA",
          success: "#34D399",
          danger: "#F87171",
          warning: "#FBBF24"
        },
        finance: {
          up: "#16B27C",
          down: "#F04461",
          neutral: "#94A3B8"
        }
      },
      backdropBlur: {
        glass: "18px"
      },
      boxShadow: {
        card: "0 20px 45px rgba(5, 7, 15, 0.45)",
        subtle: "0 8px 24px rgba(3, 7, 18, 0.35)"
      },
      transitionTimingFunction: {
        "motion-fast": "var(--motion-fast-ease)",
        "motion-medium": "var(--motion-medium-ease)",
        "motion-slow": "var(--motion-slow-ease)",
        "motion-delayed": "var(--motion-delayed-ease)",
        "motion-tactile": "var(--motion-tactile-ease)"
      },
      transitionDuration: {
        "motion-fast": "var(--motion-fast-duration)",
        "motion-medium": "var(--motion-medium-duration)",
        "motion-slow": "var(--motion-slow-duration)",
        "motion-delayed": "var(--motion-delayed-duration)",
        "motion-tactile": "var(--motion-tactile-duration)"
      }
    }
  },
  plugins: [
    typography,
    plugin(({ addUtilities }) => {
      addUtilities({
        ".transition-motion-fast": {
          transitionDuration: "var(--motion-fast-duration)",
          transitionTimingFunction: "var(--motion-fast-ease)"
        },
        ".transition-motion-medium": {
          transitionDuration: "var(--motion-medium-duration)",
          transitionTimingFunction: "var(--motion-medium-ease)"
        },
        ".transition-motion-slow": {
          transitionDuration: "var(--motion-slow-duration)",
          transitionTimingFunction: "var(--motion-slow-ease)"
        },
        ".transition-motion-delayed": {
          transitionDuration: "var(--motion-delayed-duration)",
          transitionTimingFunction: "var(--motion-delayed-ease)"
        },
        ".transition-motion-tactile": {
          transitionDuration: "var(--motion-tactile-duration)",
          transitionTimingFunction: "var(--motion-tactile-ease)"
        },
        ".animate-motion-shimmer": {
          animation: "motion-shimmer var(--motion-medium-duration) var(--motion-medium-ease) infinite"
        },
        ".animate-lock-shake": {
          animation: "motion-lock-shake var(--motion-tactile-duration) var(--motion-tactile-ease)"
        }
      });
    })
  ]
};
