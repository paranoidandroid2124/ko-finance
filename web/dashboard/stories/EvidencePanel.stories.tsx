import type { Meta, StoryObj } from "@storybook/react";
import { EvidencePanel, type EvidencePanelItem } from "@/components/evidence";

const SAMPLE_ITEMS: EvidencePanelItem[] = [
  {
    urnId: "urn:chunk:fin-1",
    section: "재무 하이라이트",
    pageNumber: 12,
    quote:
      "3분기 영업이익은 전년 대비 28% 증가했으며, 해외 매출 비중이 55%로 확대되었습니다.",
    anchor: { similarity: 0.84 },
    selfCheck: { verdict: "pass", score: 0.82 },
    sourceReliability: "high",
    chunkId: "chunk-401",
  },
  {
    urnId: "urn:chunk:fin-2",
    section: "리스크 요인",
    pageNumber: 17,
    quote:
      "원자재 가격 상승에 따라 4분기 마진은 1.4%p 하락이 예상되며, 환율 변동성이 확대되었습니다.",
    anchor: { similarity: 0.73 },
    selfCheck: { verdict: "warn", score: 0.58, explanation: "환율 영향 수치가 미확인" },
    sourceReliability: "medium",
    chunkId: "chunk-429",
  },
  {
    urnId: "urn:chunk:locked",
    section: "PDF 주석",
    pageNumber: 22,
    quote: "Pro 이상 플랜에서만 하이라이트를 확인할 수 있는 문단입니다.",
    anchor: null,
    selfCheck: null,
    sourceReliability: "high",
    chunkId: "chunk-477",
    locked: true,
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
  },
};

export default meta;

type Story = StoryObj<typeof EvidencePanel>;

export const Ready: Story = {};

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
