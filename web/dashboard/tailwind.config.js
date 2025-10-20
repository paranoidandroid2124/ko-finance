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
      boxShadow: {
        card: "0 10px 30px rgba(17, 24, 39, 0.08)"
      }
    }
  },
  plugins: []
};

