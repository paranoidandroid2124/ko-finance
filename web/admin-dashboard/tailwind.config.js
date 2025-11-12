const plugin = require("tailwindcss/plugin");

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx}",
    "./src/components/**/*.{js,ts,jsx,tsx}",
    "./src/lib/**/*.{js,ts,jsx,tsx}",
    "../dashboard/src/**/*.{js,ts,jsx,tsx}"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Pretendard", "Inter", "system-ui", "sans-serif"],
        mono: ["Roboto Mono", "ui-monospace", "SFMono-Regular", "monospace"]
      },
      colors: {
        background: {
          light: "#F5F7FB",
          dark: "#0D1423",
          cardLight: "#FFFFFF",
          cardDark: "#171F2F"
        },
        text: {
          primaryLight: "#111827",
          secondaryLight: "#4B5563",
          primaryDark: "#F9FAFB",
          secondaryDark: "#9CA3AF"
        },
        border: {
          light: "#E5E7EB",
          dark: "#1F2937"
        },
        primary: {
          DEFAULT: "#4B6CFB",
          dark: "#5C7CFF",
          hover: "#3755E8"
        },
        accent: {
          positive: "#2AC5A8",
          negative: "#F45B69",
          warning: "#F2B636"
        }
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
      },
      animation: {
        "motion-shimmer": "motion-shimmer var(--motion-medium-duration) var(--motion-medium-ease) infinite",
        "lock-shake": "motion-lock-shake var(--motion-tactile-duration) var(--motion-tactile-ease)"
      },
      boxShadow: {
        card: "0 10px 30px rgba(17, 24, 39, 0.08)"
      }
    }
  },
  plugins: [
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
