import type { Meta, StoryObj } from "@storybook/react";
import { EvidencePanel, type EvidencePanelItem } from "@/components/evidence";

const SAMPLE_ITEMS: EvidencePanelItem[] = [
  {
    urnId: "urn:chunk:fin-1",
    section: "Financial Highlights",
    pageNumber: 12,
    quote:
      "Q3 revenue climbed 28% year over year and export share expanded to 55%.",
    anchor: { similarity: 0.84 },
    selfCheck: { verdict: "pass", score: 0.82 },
    sourceReliability: "high",
    chunkId: "chunk-401",
    diffType: "updated",
    previousQuote: "Revenue grew 20% last quarter with exports accounting for half of sales.",
    previousSection: "Financial Highlights",
    previousPageNumber: 10,
    diffChangedFields: ["quote", "page_number"],
  },
  {
    urnId: "urn:chunk:fin-2",
    section: "Risk Factors",
    pageNumber: 17,
    quote:
      "Higher input prices are expected to compress Q4 margins by 1.4ppt while FX volatility remains elevated.",
    anchor: { similarity: 0.73 },
    selfCheck: { verdict: "warn", score: 0.58, explanation: "FX impact still pending validation" },
    sourceReliability: "medium",
    chunkId: "chunk-429",
    diffType: "created",
    diffChangedFields: ["quote", "section"],
  },
  {
    urnId: "urn:chunk:locked",
    section: "PDF Annotation",
    pageNumber: 22,
    quote: "Only Pro plans and above can open this inline highlight.",
    anchor: null,
    selfCheck: null,
    sourceReliability: "high",
    chunkId: "chunk-477",
    locked: true,
    diffType: "unchanged",
  },
];

const REMOVED_ITEMS: EvidencePanelItem[] = [
  {
    urnId: "urn:chunk:removed",
    section: "Removed reference",
    quote: "This citation existed in the previous snapshot but was removed in the latest response.",
    pageNumber: 9,
    diffType: "removed",
  },
];

const INLINE_PDF_SAMPLE =
  "data:application/pdf;base64,JVBERi0xLjMKJcTl8uXrp/Og0MTGCjEgMCBvYmoKPDwvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFI+PgplbmRvYmoKMiAwIG9iago8PC9UeXBlIC9QYWdlcyAvQ291bnQgMSAvS2lkcyBbMyAwIFJdPj4KZW5kb2JqCjMgMCBvYmoKPDwvVHlwZSAvUGFnZSAvUGFyZW50IDIgMCBSIC9NZWRpYUJveCBbMCAwIDU5NSA4NDJdIC9Db250ZW50cyA0IDAgUiAvUmVzb3VyY2VzIDw8Pj4+PgplbmRvYmoKNCAwIG9iago8PC9MZW5ndGggNTY+PgpzdHJlYW0KQlQKL0YxIDI0IFRmCjEwMCA3NjAgVGQKKChIZWxsbyBQREYpIFRqCkVUCmVuZHN0cmVhbQplbmRvYmoKeHJlZgowIDUKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDExIDAwMDAwIG4gCjAwMDAwMDAwNzMgMDAwMDAgbiAKMDAwMDAwMDE1MyAwMDAwMCBuIAowMDAwMDAwMjE3IDAwMDAwIG4gCnRyYWlsZXIKPDwvUm9vdCAxIDAgUiAvU2l6ZSA1Pj4Kc3RhcnR4cmVmCjI0MAolJUVPRgo=";

const meta: Meta<typeof EvidencePanel> = {
  title: "Evidence/EvidencePanel",
  component: EvidencePanel,
  parameters: {
    layout: "fullscreen",
    backgrounds: {
      default: "light",
    },
  },
  args: {
    planTier: "pro",
    status: "ready",
    items: SAMPLE_ITEMS,
    inlinePdfEnabled: true,
    pdfUrl: INLINE_PDF_SAMPLE,
    pdfDownloadUrl: INLINE_PDF_SAMPLE,
    diffEnabled: true,
    diffActive: false,
    removedItems: REMOVED_ITEMS,
  },
};

export default meta;

type Story = StoryObj<typeof EvidencePanel>;

export const Ready: Story = {};

export const DiffActive: Story = {
  args: {
    diffActive: true,
    removedItems: REMOVED_ITEMS,
  },
};

export const Loading: Story = {
  args: {
    status: "loading",
    items: [],
    inlinePdfEnabled: false,
    pdfUrl: null,
  },
};

export const AnchorMismatch: Story = {
  args: {
    status: "anchor-mismatch",
    inlinePdfEnabled: true,
    pdfUrl: INLINE_PDF_SAMPLE,
    pdfDownloadUrl: INLINE_PDF_SAMPLE,
    items: SAMPLE_ITEMS.map((item) => ({ ...item, anchor: null })),
  },
};

export const FreePlanLocked: Story = {
  args: {
    planTier: "free",
    items: SAMPLE_ITEMS.map((item, index) =>
      index === SAMPLE_ITEMS.length - 1 ? { ...item, locked: true } : item,
    ),
    inlinePdfEnabled: true,
    pdfUrl: INLINE_PDF_SAMPLE,
    pdfDownloadUrl: INLINE_PDF_SAMPLE,
    diffEnabled: false,
  },
};



