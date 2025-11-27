const plugin = require("tailwindcss/plugin");
const typography = require("@tailwindcss/typography");

const withOpacityValue = (variable, fallbackOpacity = 1) => ({ opacityValue }) => {
  const opacity = opacityValue ?? fallbackOpacity;
  return `rgb(var(${variable}) / ${opacity})`;
};

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
          DEFAULT: withOpacityValue("--color-bg-canvas"),
          alt: withOpacityValue("--color-bg-alt")
        },
        surface: {
          1: withOpacityValue("--color-surface-1"),
          2: withOpacityValue("--color-surface-2"),
          3: withOpacityValue("--color-surface-3"),
          glass: withOpacityValue("--color-surface-glass", 0.9),
          // Legacy aliases
          primary: withOpacityValue("--color-surface-1"),
          secondary: withOpacityValue("--color-surface-2"),
          tertiary: withOpacityValue("--color-surface-3"),
          highlight: withOpacityValue("--color-accent-glow", 0.12),
          muted: withOpacityValue("--color-surface-2")
        },
        text: {
          primary: withOpacityValue("--color-text-primary"),
          secondary: withOpacityValue("--color-text-secondary"),
          tertiary: withOpacityValue("--color-text-tertiary"),
          muted: withOpacityValue("--color-text-muted"),
          primaryLight: withOpacityValue("--color-text-primary"),
          secondaryLight: withOpacityValue("--color-text-secondary"),
          tertiaryLight: withOpacityValue("--color-text-tertiary"),
          primaryDark: withOpacityValue("--color-text-primary"),
          secondaryDark: withOpacityValue("--color-text-secondary"),
          tertiaryDark: withOpacityValue("--color-text-tertiary")
        },
        border: {
          DEFAULT: withOpacityValue("--color-border-hair", 0.12),
          hair: withOpacityValue("--color-border-hair", 0.12),
          subtle: withOpacityValue("--color-border-hair", 0.08),
          light: withOpacityValue("--color-border-hair", 0.12),
          strong: withOpacityValue("--color-border-strong", 0.28),
          dark: withOpacityValue("--color-border-strong", 0.32),
          glow: withOpacityValue("--color-border-glow", 0.4)
        },
        primary: {
          DEFAULT: withOpacityValue("--color-accent-brand"),
          hover: withOpacityValue("--color-accent-brand-strong"),
          glow: withOpacityValue("--color-accent-glow"),
          dark: withOpacityValue("--color-accent-brand")
        },
        accent: {
          primary: withOpacityValue("--color-accent-brand"),
          brand: withOpacityValue("--color-accent-brand"),
          glow: withOpacityValue("--color-accent-glow"),
          emerald: withOpacityValue("--color-accent-emerald"),
          amber: withOpacityValue("--color-accent-amber"),
          rose: withOpacityValue("--color-accent-rose"),
          positive: withOpacityValue("--color-status-success"),
          warning: withOpacityValue("--color-status-warning"),
          negative: withOpacityValue("--color-status-error")
        },
        status: {
          success: withOpacityValue("--color-status-success"),
          error: withOpacityValue("--color-status-error"),
          warning: withOpacityValue("--color-status-warning"),
          info: withOpacityValue("--color-status-info")
        },
        background: {
          light: withOpacityValue("--color-bg-alt"),
          dark: withOpacityValue("--color-bg-canvas"),
          card: withOpacityValue("--color-surface-1"),
          cardLight: withOpacityValue("--color-surface-1"),
          cardDark: withOpacityValue("--color-surface-2")
        }
      },
      borderRadius: {
        xs: "var(--radius-xs)",
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
        "2xl": "calc(var(--radius-xl) + 4px)",
        "3xl": "calc(var(--radius-xl) + 8px)"
      },
      backgroundImage: {
        "aurora-gradient":
          "radial-gradient(circle at 50% 0%, rgba(59,130,246,0.15), transparent 50%), radial-gradient(circle at 100% 0%, rgba(139,92,246,0.1), transparent 50%)",
        "noise-pattern": "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='0.4'/%3E%3C/svg%3E\")",
      },
      animation: {
        "aurora-flow": "aurora-flow 20s linear infinite",
      },
      keyframes: {
        "aurora-flow": {
          "0%": { backgroundPosition: "50% 50%, 50% 50%" },
          "100%": { backgroundPosition: "350% 50%, 350% 50%" },
        },
      },
      backdropBlur: {
        soft: "var(--blur-soft)",
        glass: "var(--blur-glass)",
        heavy: "var(--blur-heavy)"
      },
      boxShadow: {
        subtle: "var(--shadow-1)",
        card: "var(--shadow-2)",
        "elevation-1": "var(--shadow-1)",
        "elevation-2": "var(--shadow-2)",
        "elevation-3": "var(--shadow-3)",
        "glow-brand": "var(--shadow-glow-brand)"
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
