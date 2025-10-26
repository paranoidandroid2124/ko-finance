import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";

const transitions = [
  {
    name: "motion-fast",
    description: "Quick hover/focus transitions",
    className: "transition-motion-fast hover:-translate-y-1"
  },
  {
    name: "motion-medium",
    description: "Card entrance, skeleton shimmer",
    className: "transition-motion-medium hover:-translate-y-1.5"
  },
  {
    name: "motion-slow",
    description: "Drawer / panel slides",
    className: "transition-motion-slow hover:-translate-y-2"
  }
];

const animations = [
  {
    name: "motion-shimmer",
    description: "Skeleton loading effect",
    className: "animate-motion-shimmer"
  },
  {
    name: "lock-shake",
    description: "Locked action feedback",
    className: "animate-lock-shake"
  }
];

function TransitionSample() {
  const [active, setActive] = useState<string | null>(null);

  return (
    <div className="grid gap-4 md:grid-cols-3">
      {transitions.map((item) => (
        <button
          key={item.name}
          type="button"
          onMouseEnter={() => setActive(item.name)}
          onFocus={() => setActive(item.name)}
          onBlur={() => setActive(null)}
          onMouseLeave={() => setActive(null)}
          className={`rounded-xl border border-border-light bg-white p-4 text-left shadow-card ${
            item.className
          }`}
        >
          <p className="text-sm font-semibold text-text-primaryLight">{item.name}</p>
          <p className="mt-2 text-xs text-text-secondaryLight">{item.description}</p>
          <p className="mt-4 text-[11px] uppercase tracking-wide text-primary">
            {active === item.name ? "Active" : "Hover or focus"}
          </p>
        </button>
      ))}
    </div>
  );
}

function AnimationSample() {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="rounded-xl border border-dashed border-border-light bg-background-light/70 p-4">
        <p className="text-sm font-semibold text-text-primaryLight">Shimmer</p>
        <div className="mt-3 h-4 w-full overflow-hidden rounded">
          <div className="h-full w-1/2 rounded motion-shimmer animate-motion-shimmer bg-background-cardLight" />
        </div>
        <p className="mt-2 text-xs text-text-secondaryLight">
          Apply <code>animate-motion-shimmer</code> to skeleton blocks.
        </p>
      </div>
      <div className="rounded-xl border border-dashed border-border-light bg-background-light/70 p-4">
        <p className="text-sm font-semibold text-text-primaryLight">Lock Shake</p>
        <button
          type="button"
          className="mt-3 inline-flex items-center gap-2 rounded-lg border border-border-light px-3 py-2 text-sm font-semibold text-text-secondaryLight transition-motion-tactile hover:border-primary hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          onClick={(event) => {
            event.currentTarget.classList.remove("animate-lock-shake");
            // eslint-disable-next-line no-void
            void event.currentTarget.offsetWidth; // restart animation
            event.currentTarget.classList.add("animate-lock-shake");
          }}
        >
          Upgrade Required
        </button>
        <p className="mt-2 text-xs text-text-secondaryLight">
          Trigger <code>animate-lock-shake</code> on locked actions to emphasise gating.
        </p>
      </div>
    </div>
  );
}

const meta: Meta = {
  title: "Design/TokenPreview",
  parameters: {
    layout: "padded"
  }
};

export default meta;

type Story = StoryObj;

export const MotionTokens: Story = {
  render: () => (
    <div className="space-y-10">
      <section>
        <h2 className="text-lg font-semibold text-text-primaryLight">Transition Tokens</h2>
        <p className="mt-2 text-sm text-text-secondaryLight">
          Utility helpers that wrap duration and easing pairs defined in <code>motion.css</code>.
        </p>
        <div className="mt-6">
          <TransitionSample />
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-text-primaryLight">Animation Tokens</h2>
        <p className="mt-2 text-sm text-text-secondaryLight">
          Reusable animations for skeletons and lock interactions.
        </p>
        <div className="mt-6">
          <AnimationSample />
        </div>
      </section>
    </div>
  )
};
