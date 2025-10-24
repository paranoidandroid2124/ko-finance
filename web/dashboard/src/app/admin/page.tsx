"use client";

import { useState } from "react";
import { AdminShell } from "@/components/layout/AdminShell";

type Section = {
  id: string;
  title: string;
  description: string;
  bullets: string[];
  actionLabel: string;
};

type QuickAction = {
  id: string;
  label: string;
  description: string;
};

const CONFIG_SECTIONS: Section[] = [
  {
    id: "llm",
    title: "LLM & Prompts",
    description: "Manage base prompts, model routing, and runtime parameters used by chat and RAG flows.",
    bullets: ["System instructions", "LiteLLM profiles", "Fallback / retry policy"],
    actionLabel: "Open prompt controls"
  },
  {
    id: "guardrails",
    title: "Guardrail Policies",
    description: "Tune the intent filter thresholds, blocklists, and user-facing guardrail copy.",
    bullets: ["Intent filter rules", "Semi-pass messaging", "Forbidden keywords"],
    actionLabel: "Review guardrails"
  },
  {
    id: "rag",
    title: "RAG Context",
    description: "Select data sources and similarity cutoffs that power retrieval augmented responses.",
    bullets: ["Context sources", "Default filters", "Similarity threshold"],
    actionLabel: "Configure RAG context"
  },
  {
    id: "ui",
    title: "UI & UX Settings",
    description: "Control dashboard defaults, labeling, and informational banners presented to operators.",
    bullets: ["Default date ranges", "Highlight palette", "Admin notices"],
    actionLabel: "Adjust interface"
  }
];

const OPERATIONS_SECTIONS: Section[] = [
  {
    id: "news-pipeline",
    title: "News & Sector Pipeline",
    description: "Enable feeds, assign sector mappings, and tune aggregation thresholds.",
    bullets: ["RSS sources", "Sector keywords", "Sentiment thresholds"],
    actionLabel: "Edit pipeline config"
  },
  {
    id: "schedules",
    title: "Schedules & Tasks",
    description: "Inspect Celery beat cadence, trigger jobs on demand, and view run history.",
    bullets: ["Job intervals", "Manual triggers", "Recent logs"],
    actionLabel: "Manage schedules"
  },
  {
    id: "operations",
    title: "Operations & Access",
    description: "Rotate API keys, toggle observability sinks, and manage test or maintenance modes.",
    bullets: ["API keys", "Langfuse toggle", "Test mode"],
    actionLabel: "Review operations"
  },
  {
    id: "alerts",
    title: "Notification Channels",
    description: "Maintain Telegram, email, and webhook endpoints for automated alerts.",
    bullets: ["Channel settings", "Message templates", "Escalation rules"],
    actionLabel: "Update channels"
  }
];

const QUICK_ACTIONS: QuickAction[] = [
  {
    id: "seed-news",
    label: "Seed news feeds",
    description: "Queue the `m2.seed_news_feeds` task to fetch the latest RSS content."
  },
  {
    id: "aggregate-sentiment",
    label: "Run sentiment aggregation",
    description: "Trigger `m2.aggregate_news` and sector aggregation warm-ups."
  },
  {
    id: "rebuild-rag",
    label: "Refresh RAG index",
    description: "Launch the vector service backfill to sync filings and documents."
  }
];

function SectionCard({ section, onSelect, isActive }: { section: Section; onSelect: (id: string) => void; isActive: boolean }) {
  const { id, title, description, bullets, actionLabel } = section;
  const borderClass = isActive
    ? "border-primary shadow-lg shadow-primary/10 dark:border-primary.dark"
    : "border-border-light dark:border-border-dark";

  return (
    <article
      className={`flex h-full flex-col rounded-xl border bg-background-cardLight p-6 shadow-card transition-colors dark:bg-background-cardDark ${borderClass}`}
    >
      <header>
        <h3 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">{title}</h3>
        <p className="mt-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">{description}</p>
      </header>
      <ul className="mt-4 space-y-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
        {bullets.map((item) => (
          <li key={`${id}-${item}`}>- {item}</li>
        ))}
      </ul>
      <button
        type="button"
        onClick={() => onSelect(id)}
        className="mt-auto inline-flex items-center justify-center rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-primaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-primaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
      >
        {actionLabel}
      </button>
    </article>
  );
}

function QuickActionCard({ action }: { action: QuickAction }) {
  return (
    <div className="flex items-start justify-between rounded-xl border border-border-light bg-background-cardLight p-5 text-sm transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <div>
        <h4 className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{action.label}</h4>
        <p className="mt-1 text-text-secondaryLight dark:text-text-secondaryDark">{action.description}</p>
      </div>
      <button
        type="button"
        disabled
        className="inline-flex cursor-not-allowed items-center rounded-md bg-border-light px-3 py-1 text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:bg-border-dark dark:text-text-secondaryDark"
      >
        coming soon
      </button>
    </div>
  );
}

export default function AdminPage() {
  const [activeSection, setActiveSection] = useState<string | null>(null);

  return (
    <AdminShell
      title="Administration"
      description="Manage runtime configuration, pipelines, and operational controls for the K-Finance Copilot."
    >
      <div className="rounded-xl border border-dashed border-border-light bg-background-cardLight p-6 text-sm text-text-secondaryLight dark:border-border-dark dark:bg-background-cardDark dark:text-text-secondaryDark">
        <p>
          Configure production-ready controls for prompts, guardrails, pipelines, and operational toggles from a single
          surface. Start by selecting a section below; detail panels will open in this workspace.
        </p>
        <p className="mt-2">
          Active section: <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{activeSection ?? "none"}</span>
        </p>
      </div>

      <section className="space-y-4">
        <header>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
            Configuration Domains
          </h2>
        </header>
        <div className="grid gap-4 md:grid-cols-2">
          {CONFIG_SECTIONS.map((section) => (
            <SectionCard key={section.id} section={section} onSelect={setActiveSection} isActive={activeSection === section.id} />
          ))}
        </div>
      </section>

      <section className="space-y-4">
        <header>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
            Pipeline & Operations
          </h2>
        </header>
        <div className="grid gap-4 md:grid-cols-2">
          {OPERATIONS_SECTIONS.map((section) => (
            <SectionCard key={section.id} section={section} onSelect={setActiveSection} isActive={activeSection === section.id} />
          ))}
        </div>
      </section>

      <section className="space-y-4">
        <header>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
            Quick Actions
          </h2>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            These shortcuts will dispatch Celery tasks or API calls once available. They are disabled until the backend endpoints land.
          </p>
        </header>
        <div className="space-y-3">
          {QUICK_ACTIONS.map((action) => (
            <QuickActionCard key={action.id} action={action} />
          ))}
        </div>
      </section>
    </AdminShell>
  );
}
