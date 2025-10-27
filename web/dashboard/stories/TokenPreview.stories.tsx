import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const MOTION_TOKENS = [
  { name: "motion-fast", description: "120ms ease-out (button hover, locks)" },
  { name: "motion-medium", description: "220ms ease-in-out (card hover, tab transitions)" },
  { name: "motion-slow", description: "320ms ease-in-out (modal, panel)" },
  { name: "motion-tactile", description: "keyframe lock shake, reduced motion aware" },
];

const COLOR_SWATCHES = [
  { token: "bg-primary", label: "Primary / Brand" },
  { token: "bg-success", label: "Success State" },
  { token: "bg-warning", label: "Warning State" },
  { token: "bg-error", label: "Error State" },
];

const TYPOGRAPHY = [
  { token: "text-text-primaryLight", label: "Primary Light" },
  { token: "text-text-secondaryLight", label: "Secondary Light" },
  { token: "dark:text-text-primaryDark", label: "Primary Dark" },
  { token: "dark:text-text-secondaryDark", label: "Secondary Dark" },
];

const meta: Meta = {
  title: "Design Tokens/Motion & Theme Preview",
  parameters: {
    layout: "fullscreen",
  },
};

export default meta;

type Story = StoryObj;

const PreviewCard = ({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) => (
  <section className="space-y-3 rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
    <header>
      <h3 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">{title}</h3>
      {description ? (
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">{description}</p>
      ) : null}
    </header>
    <div className="grid gap-3">{children}</div>
  </section>
);

export const Overview: Story = {
  render: () => (
    <div className="space-y-6 bg-background-light p-6 text-text-primaryLight dark:bg-background-dark dark:text-text-primaryDark">
      <PreviewCard title="Motion Tokens" description="Utility classes used throughout Phase 1 interactions.">
        {MOTION_TOKENS.map((token) => (
          <div key={token.name} className="flex items-center justify-between gap-4 rounded-xl border border-dashed border-border-light p-4 dark:border-border-dark">
            <div>
              <p className="font-semibold">{token.name}</p>
              <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">{token.description}</p>
            </div>
            <div className={`h-10 w-10 rounded-full bg-primary/80 ${token.name === "motion-tactile" ? "animate-lock-shake" : `transition-${token.name}`} `} />
          </div>
        ))}
      </PreviewCard>

      <PreviewCard title="Color Theme" description="Brand and feedback palette pairings.">
        <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
          {COLOR_SWATCHES.map((item) => (
            <div
              key={item.token}
              className={`flex h-24 flex-col justify-between rounded-xl border border-border-light p-3 text-sm text-white shadow-card dark:border-border-dark ${item.token}`}
            >
              <span className="font-semibold">{item.token}</span>
              <span>{item.label}</span>
            </div>
          ))}
        </div>
      </PreviewCard>

      <PreviewCard title="Typography" description="Primary text tokens in light/dark modes.">
        {TYPOGRAPHY.map((item) => (
          <p key={item.token} className={`rounded-lg border border-border-light bg-background-light p-3 text-base dark:border-border-dark dark:bg-background-dark ${item.token}`}>
            {item.label} — token `{item.token}`
          </p>
        ))}
      </PreviewCard>
    </div>
  ),
};
