import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";

import { GlobalSearchBar } from "../src/components/search/GlobalSearchBar";
import { SearchResults, type SearchResult } from "../src/components/search/SearchResults";

const mockResults: SearchResult[] = [
  {
    id: "filing-1",
    type: "filing",
    title: "삼성전자 정기공시 (사업보고서)",
    category: "정기보고",
    filedAt: "2025-10-20",
    latestIngestedAt: "5분 전",
    sourceReliability: 0.96,
    evidenceCounts: {
      filings: 5,
      news: 3,
      charts: 2
    },
    actions: {
      compareLocked: false,
      alertLocked: true,
      exportLocked: true
    }
  },
  {
    id: "filing-2",
    type: "filing",
    title: "LG에너지솔루션 투자설명서",
    category: "증자",
    filedAt: "2025-10-19",
    latestIngestedAt: "1시간 전",
    sourceReliability: 0.88,
    evidenceCounts: {
      filings: 2,
      news: 6
    },
    actions: {
      compareLocked: true,
      alertLocked: true,
      exportLocked: true
    }
  },
  {
    id: "news-1",
    type: "news",
    title: "한국 조선업 수주 확대, 조선주 급등",
    category: "섹터 뉴스",
    filedAt: "2025-10-21",
    latestIngestedAt: "10분 전",
    sourceReliability: 0.74,
    evidenceCounts: {
      news: 12,
      charts: 1
    },
    actions: {
      compareLocked: true,
      alertLocked: false,
      exportLocked: true
    }
  },
  {
    id: "news-2",
    type: "news",
    title: "반도체 업황 하락 전망",
    category: "애널리스트 리포트",
    filedAt: "2025-10-18",
    latestIngestedAt: "4시간 전",
    sourceReliability: 0.81,
    evidenceCounts: {
      news: 8
    },
    actions: {
      compareLocked: true,
      alertLocked: true,
      exportLocked: true
    }
  },
  {
    id: "table-1",
    type: "table",
    title: "KOSPI 섹터별 감성 & 수익률 비교",
    category: "데이터 테이블",
    filedAt: "2025-10-20",
    latestIngestedAt: "30분 전",
    actions: {
      compareLocked: true,
      alertLocked: true,
      exportLocked: false
    },
    evidenceCounts: {
      charts: 1,
      tables: 1
    }
  }
];

const meta: Meta = {
  title: "Dashboard/SearchHub",
  parameters: {
    layout: "fullscreen"
  }
};

export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: function Render() {
    const [query, setQuery] = useState("");

    return (
      <div className="space-y-8 bg-background-light p-10 text-text-primaryLight dark:bg-background-dark">
        <GlobalSearchBar value={query} onChange={setQuery} onSubmit={() => undefined} onOpenCommand={() => undefined} />
        <SearchResults results={mockResults} />
      </div>
    );
  }
};
