import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const MOTION_TOKENS = [
  { name: "motion-fast", description: "140ms ease-out (buttons, chips)" },
  { name: "motion-medium", description: "220ms ease (cards, tabs)" },
  { name: "motion-slow", description: "360ms ease-in-out (dialogs, overlays)" },
  { name: "motion-tactile", description: "90ms linear tactile feedback" }
];

const COLOR_GROUPS = [
  {
    title: "Surfaces",
    description: "Depth stack for cards, panels, overlays.",
    items: [
      { token: "bg-surface-1", label: "Surface 1" },
      { token: "bg-surface-2", label: "Surface 2" },
      { token: "bg-surface-3", label: "Surface 3" },
      { token: "bg-surface-glass", label: "Surface Glass" }
    ]
  },
  {
    title: "Brand & Accent",
    description: "Primary cyan + orchid glow and utility accents.",
    items: [
      { token: "bg-accent-brand", label: "Accent Brand", inverted: true },
      { token: "bg-accent-glow", label: "Accent Glow", inverted: true },
      { token: "bg-accent-emerald", label: "Accent Emerald", inverted: true },
      { token: "bg-accent-amber", label: "Accent Amber", inverted: true },
      { token: "bg-accent-rose", label: "Accent Rose", inverted: true }
    ]
  },
  {
    title: "Status",
    description: "Feedback states for system UI.",
    items: [
      { token: "bg-status-success", label: "Success", inverted: true },
      { token: "bg-status-warning", label: "Warning", inverted: true },
      { token: "bg-status-error", label: "Error", inverted: true },
      { token: "bg-status-info", label: "Info", inverted: true }
    ]
  }
];

const TYPOGRAPHY = [
  { token: "text-text-primary", label: "Text / Primary" },
  { token: "text-text-secondary", label: "Text / Secondary" },
  { token: "text-text-tertiary", label: "Text / Tertiary" },
  { token: "text-text-muted", label: "Text / Muted" }
];

const SHADOWS = [
  { className: "shadow-elevation-1", label: "Shadow 1 (Cards)" },
  { className: "shadow-elevation-2", label: "Shadow 2 (Overlays)" },
  { className: "shadow-elevation-3", label: "Shadow 3 (Dialogs)" },
  { className: "shadow-glow-brand", label: "Brand Glow" }
];

const RADII = [
  { className: "rounded-md", label: "Radius md (16px)" },
  { className: "rounded-lg", label: "Radius lg (20px)" },
  { className: "rounded-xl", label: "Radius xl (24px)" },
  { className: "rounded-3xl", label: "Radius 3xl (xl + 8px)" }
];

const meta: Meta = {
  title: "Design Tokens/Motion & Theme Preview",
  parameters: {
    layout: "fullscreen"
  }
};

export default meta;

type Story = StoryObj;

const PreviewCard = ({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) => (
  <section className="space-y-3 rounded-2xl border border-border-hair bg-surface-1/95 p-6 shadow-card backdrop-blur-glass">
    <header>
      <h3 className="text-base font-semibold text-text-primary">{title}</h3>
      {description ? <p className="text-sm text-text-secondary">{description}</p> : null}
    </header>
    <div className="grid gap-3">{children}</div>
  </section>
);

const Swatch = ({ token, label, inverted }: { token: string; label: string; inverted?: boolean }) => (
  <div className={`flex h-24 flex-col justify-between rounded-xl border border-border-hair/70 p-3 text-sm shadow-subtle ${token}`}>
    <span className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${inverted ? "text-white/80" : "text-text-secondary"}`}>{token}</span>
    <span className={`font-semibold ${inverted ? "text-white" : "text-text-primary"}`}>{label}</span>
  </div>
);

export const Overview: Story = {
  render: () => (
    <div className="space-y-6 bg-canvas p-6 text-text-primary">
      <PreviewCard title="Motion Tokens" description="Utility classes mapped to motion variables.">
        {MOTION_TOKENS.map((token) => (
          <div key={token.name} className="flex items-center justify-between gap-4 rounded-xl border border-dashed border-border-hair p-4">
            <div>
              <p className="font-semibold">{token.name}</p>
              <p className="text-sm text-text-secondary">{token.description}</p>
            </div>
            <div className={`h-10 w-10 rounded-full bg-accent-brand/80 ${token.name === "motion-tactile" ? "animate-lock-shake" : `transition-${token.name}`} `} />
          </div>
        ))}
      </PreviewCard>

      {COLOR_GROUPS.map((group) => (
        <PreviewCard key={group.title} title={group.title} description={group.description}>
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
            {group.items.map((item) => (
              <Swatch key={item.token} token={item.token} label={item.label} inverted={item.inverted} />
            ))}
          </div>
        </PreviewCard>
      ))}

      <PreviewCard title="Typography" description="Text tokens across semantic tiers.">
        {TYPOGRAPHY.map((item) => (
          <p key={item.token} className={`rounded-lg border border-border-hair bg-surface-2/70 p-3 text-base ${item.token}`}>
            {item.label} — token `{item.token}`
          </p>
        ))}
      </PreviewCard>

      <PreviewCard title="Shadows & Radius" description="Depth + curvature primitives used by cards, panels, and pills.">
        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-3 rounded-2xl border border-border-hair/80 bg-surface-2/80 p-4 shadow-elevation-1">
            <p className="text-sm font-semibold text-text-primary">Shadows</p>
            <div className="grid gap-3 sm:grid-cols-2">
              {SHADOWS.map((item) => (
                <div key={item.className} className={`flex h-20 flex-col justify-between rounded-xl border border-border-hair/60 bg-surface-1/90 p-3 ${item.className}`}>
                  <span className="text-[11px] uppercase tracking-[0.2em] text-text-secondary">{item.className}</span>
                  <span className="text-sm font-semibold text-text-primary">{item.label}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="space-y-3 rounded-2xl border border-border-hair/80 bg-surface-2/80 p-4 shadow-elevation-1">
            <p className="text-sm font-semibold text-text-primary">Radius</p>
            <div className="grid grid-cols-2 gap-3">
              {RADII.map((item) => (
                <div key={item.className} className={`flex h-20 items-center justify-center border border-border-hair/60 bg-surface-1/90 text-sm font-semibold text-text-primary ${item.className}`}>
                  {item.label}
                </div>
              ))}
            </div>
          </div>
        </div>
      </PreviewCard>
    </div>
  )
};
